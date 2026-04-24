from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
import os
from pathlib import Path
import sys
import time
from typing import Any

import httpx

from ashrise.sanitization import redact_sensitive_text
from ashrise_runtime.api_client import AshriseApiClient, AshriseApiError
from ashrise_runtime.session_store import load_json, remove_file, save_json, telegram_offset_file


class TelegramError(RuntimeError):
    pass


class TelegramBotClient:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self.token = token
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=f"https://api.telegram.org/bot{token}",
            timeout=30.0,
        )

    def close(self):
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "TelegramBotClient":
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        response = self.client.post(f"/{method}", json=payload or {})
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise TelegramError(str(data))
        return data.get("result")

    def poll_updates(self, offset: int | None = None, timeout: int = 30) -> list[dict[str, Any]]:
        payload = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload) or []

    def send_message(self, chat_id: str | int, text: str):
        return self.call("sendMessage", {"chat_id": chat_id, "text": text})


def require_telegram_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing required environment variable TELEGRAM_BOT_TOKEN")
    return token


def default_chat_id() -> str | None:
    return os.getenv("TELEGRAM_CHAT_ID")


def format_timestamp(value: str | None) -> str:
    if not value:
        return "n/a"
    return value.replace("T", " ").replace("+00:00", "Z")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_estado_message(api: AshriseApiClient, project_id: str) -> str:
    project = api.get_project(project_id)
    state = api.get_state(project_id, allow_404=True)
    if state is None:
        return f"{project['name']} ({project['id']})\nSin state cargado."

    return (
        f"{project['name']} ({project['id']})\n"
        f"status: {project.get('status')} | kind: {project.get('kind')}\n"
        f"focus: {state.get('current_focus') or '-'}\n"
        f"milestone: {state.get('current_milestone') or '-'}\n"
        f"next: {state.get('next_step') or '-'}"
    )


def build_ultimo_message(api: AshriseApiClient, project_id: str) -> str:
    runs = api.get_runs(project_id, limit=1)
    if not runs:
        return f"Sin runs para {project_id}."

    run = runs[0]
    return (
        f"Ultimo run de {project_id}\n"
        f"status: {run.get('status')}\n"
        f"started_at: {format_timestamp(run.get('started_at'))}\n"
        f"ended_at: {format_timestamp(run.get('ended_at'))}\n"
        f"summary: {run.get('summary') or '-'}"
    )


def build_candidates_message(api: AshriseApiClient, category: str | None = None) -> str:
    candidates = api.list_candidates(category=category)
    if not candidates:
        return "No hay candidatas."

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[candidate["status"]].append(candidate)

    header = "Candidatas"
    if category:
        header += f" ({category})"

    lines = [header]
    for status in sorted(groups):
        lines.append(f"{status}:")
        for candidate in groups[status]:
            lines.append(f"- {candidate['slug']} [{candidate['category']}]")

    return "\n".join(lines)


def build_candidate_message(api: AshriseApiClient, candidate_ref: str) -> str:
    candidate = api.get_candidate(candidate_ref)
    research = api.get_candidate_research(candidate_ref)

    lines = [
        f"{candidate['name']} ({candidate['slug']})",
        f"status: {candidate.get('status')} | category: {candidate.get('category')}",
        f"hypothesis: {candidate.get('hypothesis')}",
    ]

    if research:
        lines.append(
            f"latest research: {research.get('verdict')} @ {research.get('confidence')}"
        )
        lines.append(f"summary: {research.get('summary')}")
    else:
        lines.append("latest research: none")

    return "\n".join(lines)


def build_auditar_message(api: AshriseApiClient, target_ref: str) -> str:
    errors: list[str] = []

    for target_type in ("project", "candidate"):
        try:
            result = api.run_agent({"target_type": target_type, "target_id": target_ref})
        except AshriseApiError as exc:
            if exc.status_code == 404:
                errors.append(f"{target_type}: not found")
                continue
            raise

        report = result["report"]
        verdict = report.get("verdict") or "n/a"
        confidence = report.get("confidence")
        return (
            f"Auditoria corrida sobre {target_type} {target_ref}\n"
            f"run: {result['run']['id']} ({result['run']['status']})\n"
            f"report: {result['report_type']} / verdict={verdict} / confidence={confidence}\n"
            f"summary: {result['summary']}"
        )

    return f"No encontre proyecto ni candidata para '{target_ref}'."


def find_stale_projects(
    api: AshriseApiClient,
    *,
    today: date | None = None,
    days_without_audit: int = 7,
) -> list[str]:
    today = today or date.today()
    threshold = datetime.combine(today, datetime.min.time(), tzinfo=UTC) - timedelta(days=days_without_audit)
    projects = api.list_projects(status="active")
    stale: list[str] = []

    for project in projects:
        audit = api.get_audit(project["id"])
        if audit is None:
            stale.append(project["id"])
            continue

        created_at = parse_iso_datetime(audit.get("created_at"))
        if created_at is None or created_at < threshold:
            stale.append(project["id"])

    return stale


def build_daily_summary(
    api: AshriseApiClient,
    *,
    today: date | None = None,
    days_without_audit: int = 7,
) -> str:
    today = today or date.today()
    queue_items = api.get_research_queue(due="today")
    stale_projects = find_stale_projects(api, today=today, days_without_audit=days_without_audit)

    lines = [
        f"Ashrise daily reminder ({today.isoformat()})",
        f"- research_queue pending due today: {len(queue_items)}",
        f"- active projects without audit in last {days_without_audit} days: {len(stale_projects)}",
    ]

    if stale_projects:
        lines.append("Projects:")
        lines.extend(f"- {project_id}" for project_id in stale_projects)

    return "\n".join(lines)


def summarize_notification_text(text: str, max_length: int = 140) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def persist_notification_event(api: AshriseApiClient, payload: dict[str, Any]) -> None:
    try:
        api.create_notification_event(payload)
    except Exception:
        # Telegram delivery should not fail just because dashboard instrumentation could not persist.
        return


def send_message_with_notification_event(
    api: AshriseApiClient,
    telegram: TelegramBotClient,
    *,
    chat_id: str | int,
    text: str,
    message_type: str,
    payload_summary: dict[str, Any] | None = None,
    project_id: str | None = None,
    candidate_id: str | None = None,
    run_id: str | None = None,
    idea_id: str | None = None,
    task_id: str | None = None,
) -> Any:
    message = telegram.send_message(chat_id, text)
    external_ref = None
    if isinstance(message, dict) and message.get("message_id") is not None:
        external_ref = str(message["message_id"])

    persist_notification_event(
        api,
        {
            "channel": "telegram",
            "direction": "outbound",
            "project_id": project_id,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "idea_id": idea_id,
            "task_id": task_id,
            "message_type": message_type,
            "external_ref": external_ref,
            "delivery_status": "delivered",
            "summary": summarize_notification_text(text),
            "payload_summary": {
                "chat_id": str(chat_id),
                **(payload_summary or {}),
            },
            "delivered_at": datetime.now(UTC).isoformat(),
        },
    )
    return message


def _next_scheduled_date(today: date, recurrence: str | None) -> date | None:
    if recurrence == "daily":
        return today + timedelta(days=1)
    if recurrence == "weekly":
        return today + timedelta(days=7)
    if recurrence == "monthly":
        return today + timedelta(days=30)
    return None


def _candidate_queue_patch(
    queue_item: dict[str, Any],
    result: dict[str, Any],
    *,
    today: date,
    now: datetime,
) -> tuple[dict[str, Any], str]:
    verdict = result["report"].get("verdict") or "unknown"
    metadata = result["report"].get("metadata") or {}
    promotion = metadata.get("promotion_signal") or {}

    patch: dict[str, Any] = {
        "last_run_at": now.isoformat(),
        "last_report_id": result["report"]["id"],
        "notes": f"{today.isoformat()} {verdict}: {result['summary']}",
    }

    if verdict in {"kill", "park"}:
        patch["status"] = "done"
        return patch, "done"

    if verdict == "advance" and promotion.get("ready"):
        patch["status"] = "done"
        patch["notes"] += " | ready-for-promotion"
        return patch, "ready"

    patch["status"] = "pending"
    patch["scheduled_for"] = (today + timedelta(days=7)).isoformat()
    patch["recurrence"] = "weekly"
    return patch, "requeued"


def _project_queue_patch(
    queue_item: dict[str, Any],
    result: dict[str, Any],
    *,
    today: date,
    now: datetime,
) -> tuple[dict[str, Any], str]:
    patch: dict[str, Any] = {
        "last_run_at": now.isoformat(),
        "last_report_id": result["report"]["id"],
        "notes": f"{today.isoformat()} {result['report'].get('verdict')}: {result['summary']}",
    }
    next_date = _next_scheduled_date(today, queue_item.get("recurrence"))
    if next_date is None:
        patch["status"] = "done"
        return patch, "done"

    patch["status"] = "pending"
    patch["scheduled_for"] = next_date.isoformat()
    return patch, "requeued"


def run_active_daily_cycle(
    api: AshriseApiClient,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    now = datetime.now(UTC)
    queue_items = api.get_research_queue(due="today")
    verdict_counts: Counter[str] = Counter()
    results: list[dict[str, Any]] = []
    promotion_ready: list[dict[str, Any]] = []
    failures = 0

    for queue_item in queue_items:
        target_type = "project" if queue_item.get("project_id") else "candidate"
        target_id = queue_item.get("project_id") or str(queue_item.get("candidate_id"))

        try:
            api.patch_research_queue(str(queue_item["id"]), {"status": "in-progress"})
            result = api.run_agent({"target_type": target_type, "target_id": target_id})
            verdict = result["report"].get("verdict") or "unknown"
            verdict_counts[f"{target_type}:{verdict}"] += 1

            if target_type == "candidate":
                patch, action = _candidate_queue_patch(queue_item, result, today=today, now=now)
                promotion = (result["report"].get("metadata") or {}).get("promotion_signal") or {}
                if promotion.get("ready"):
                    promotion_ready.append(
                        {
                            "candidate": target_id,
                            "report_id": result["report"]["id"],
                            "consecutive_advances": promotion.get("consecutive_advances"),
                        }
                    )
            else:
                patch, action = _project_queue_patch(queue_item, result, today=today, now=now)

            api.patch_research_queue(str(queue_item["id"]), patch)
            results.append(
                {
                    "queue_id": str(queue_item["id"]),
                    "target_type": target_type,
                    "target_id": target_id,
                    "verdict": verdict,
                    "action": action,
                    "summary": result["summary"],
                    "report_id": result["report"]["id"],
                }
            )
        except Exception as exc:
            failures += 1
            safe_error = redact_sensitive_text(str(exc)) or "unknown error"
            api.patch_research_queue(
                str(queue_item["id"]),
                {
                    "status": "pending",
                    "notes": f"{today.isoformat()} failed: {safe_error}",
                },
            )
            results.append(
                {
                    "queue_id": str(queue_item["id"]),
                    "target_type": target_type,
                    "target_id": target_id,
                    "status": "failed",
                    "error": safe_error,
                }
            )

    return {
        "today": today.isoformat(),
        "queue_size": len(queue_items),
        "processed": len([item for item in results if item.get("status") != "failed"]),
        "failures": failures,
        "verdict_counts": dict(sorted(verdict_counts.items())),
        "promotion_ready": promotion_ready,
        "results": results,
    }


def build_active_daily_summary(result: dict[str, Any]) -> str:
    lines = [
        f"Ashrise active daily reminder ({result['today']})",
        f"- queue items due today: {result['queue_size']}",
        f"- processed: {result['processed']}",
        f"- failures: {result['failures']}",
    ]

    if result["verdict_counts"]:
        lines.append("Verdicts:")
        for key, count in result["verdict_counts"].items():
            lines.append(f"- {key} = {count}")

    if result["promotion_ready"]:
        lines.append("Ready to promote:")
        for item in result["promotion_ready"]:
            lines.append(
                f"- {item['candidate']} ({item['consecutive_advances']} advances). "
                f"Approve with POST /candidates/{item['candidate']}/promote"
            )

    for item in result["results"]:
        if item.get("status") == "failed":
            lines.append(f"- failed {item['target_type']} {item['target_id']}: {item['error']}")
            continue
        lines.append(
            f"- {item['target_type']} {item['target_id']} -> {item['verdict']} "
            f"({item['action']})"
        )

    return "\n".join(lines)


def handle_command(
    api: AshriseApiClient,
    text: str,
    *,
    chat_id: str | int,
    message_id: int | None = None,
) -> str:
    command, _, argument_text = text.strip().partition(" ")
    argument = argument_text.strip()

    if command in {"/start", "/help"}:
        return (
            "Comandos disponibles:\n"
            "/estado <proyecto>\n"
            "/ultimo <proyecto>\n"
            "/idea <texto>\n"
            "/candidatas [categoria]\n"
            "/candidata <slug>\n"
            "/auditar <proyecto|candidata>"
        )

    if command == "/estado":
        if not argument:
            return "Uso: /estado <proyecto>"
        return build_estado_message(api, argument)

    if command == "/ultimo":
        if not argument:
            return "Uso: /ultimo <proyecto>"
        return build_ultimo_message(api, argument)

    if command == "/idea":
        if not argument:
            return "Uso: /idea <texto>"
        idea = api.create_idea(
            {
                "raw_text": argument,
                "source": "telegram",
                "source_ref": f"{chat_id}:{message_id or 0}",
                "status": "new",
            }
        )
        return f"Idea creada: {idea['id']}"

    if command == "/candidatas":
        return build_candidates_message(api, category=argument or None)

    if command == "/candidata":
        if not argument:
            return "Uso: /candidata <slug>"
        return build_candidate_message(api, argument)

    if command == "/auditar":
        if not argument:
            return "Uso: /auditar <proyecto|candidata>"
        return build_auditar_message(api, argument)

    return "Comando no reconocido. Usa /help."


def load_offset(cwd: Path | None = None) -> int | None:
    path = telegram_offset_file(cwd)
    if not path.exists():
        return None
    data = load_json(path)
    return int(data.get("offset")) if data.get("offset") is not None else None


def save_offset(offset: int, cwd: Path | None = None):
    save_json(telegram_offset_file(cwd), {"offset": offset})


def remove_offset(cwd: Path | None = None):
    remove_file(telegram_offset_file(cwd))


def run_polling(cwd: Path | None = None, poll_timeout: int = 30):
    working_dir = (cwd or Path.cwd()).resolve()
    token = require_telegram_token()

    with AshriseApiClient() as api, TelegramBotClient(token) as telegram:
        offset = load_offset(working_dir)
        while True:
            updates = telegram.poll_updates(offset=offset, timeout=poll_timeout)
            for update in updates:
                offset = update["update_id"] + 1
                save_offset(offset, working_dir)

                message = update.get("message") or {}
                text = message.get("text")
                chat = message.get("chat") or {}
                if not text or "id" not in chat:
                    continue

                try:
                    response_text = handle_command(
                        api,
                        text,
                        chat_id=chat["id"],
                        message_id=message.get("message_id"),
                    )
                except Exception as exc:
                    response_text = f"Error: {exc}"

                telegram.send_message(chat["id"], response_text)


def send_daily_summary(chat_id: str | int):
    token = require_telegram_token()
    with AshriseApiClient() as api, TelegramBotClient(token) as telegram:
        cycle = run_active_daily_cycle(api)
        text = build_active_daily_summary(cycle)
        send_message_with_notification_event(
            api,
            telegram,
            chat_id=chat_id,
            text=text,
            message_type="active-daily-summary",
            payload_summary={
                "today": cycle["today"],
                "queue_size": cycle["queue_size"],
                "processed": cycle["processed"],
                "failures": cycle["failures"],
                "promotion_ready": len(cycle["promotion_ready"]),
            },
        )


def send_passive_daily_summary(chat_id: str | int):
    token = require_telegram_token()
    with AshriseApiClient() as api, TelegramBotClient(token) as telegram:
        text = build_daily_summary(api)
        send_message_with_notification_event(
            api,
            telegram,
            chat_id=chat_id,
            text=text,
            message_type="passive-daily-summary",
            payload_summary={"kind": "passive-daily-summary"},
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ashrise Telegram bot and reminders")
    subparsers = parser.add_subparsers(dest="command", required=True)

    polling = subparsers.add_parser("polling", help="Run the Telegram bot in polling mode")
    polling.add_argument("--poll-timeout", type=int, default=30)

    reminder = subparsers.add_parser("reminder-once", help="Run the active daily reminder once")
    reminder.add_argument("--chat-id")

    passive = subparsers.add_parser("reminder-passive-once", help="Send the passive daily reminder once")
    passive.add_argument("--chat-id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "polling":
            run_polling(poll_timeout=args.poll_timeout)
            return 0

        if args.command == "reminder-once":
            chat_id = args.chat_id or default_chat_id()
            if not chat_id:
                raise RuntimeError("Missing TELEGRAM_CHAT_ID or --chat-id for reminder-once")
            send_daily_summary(chat_id)
            return 0
        if args.command == "reminder-passive-once":
            chat_id = args.chat_id or default_chat_id()
            if not chat_id:
                raise RuntimeError("Missing TELEGRAM_CHAT_ID or --chat-id for reminder-passive-once")
            send_passive_daily_summary(chat_id)
            return 0
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 1
