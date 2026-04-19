from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
import os
from pathlib import Path
import sys
import time
from typing import Any

import httpx

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
        self.call("sendMessage", {"chat_id": chat_id, "text": text})


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
        telegram.send_message(chat_id, build_daily_summary(api))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ashrise Telegram bot and reminders")
    subparsers = parser.add_subparsers(dest="command", required=True)

    polling = subparsers.add_parser("polling", help="Run the Telegram bot in polling mode")
    polling.add_argument("--poll-timeout", type=int, default=30)

    reminder = subparsers.add_parser("reminder-once", help="Send the passive daily reminder once")
    reminder.add_argument("--chat-id")

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
    except KeyboardInterrupt:
        print("Stopped.", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 1
