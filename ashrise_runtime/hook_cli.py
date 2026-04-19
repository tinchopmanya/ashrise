from __future__ import annotations

import argparse
from datetime import UTC, datetime
import os
from pathlib import Path
import sys
from typing import Any

import yaml

from ashrise_runtime.api_client import AshriseApiClient
from ashrise_runtime.close_parser import parse_ashrise_close
from ashrise_runtime.session_store import load_json, remove_file, save_json, session_file


def compact_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if state is None:
        return None

    keys = [
        "project_state_code",
        "current_focus",
        "current_milestone",
        "roadmap_version",
        "roadmap_ref",
        "next_step",
        "blockers",
        "open_questions",
    ]
    return {key: state.get(key) for key in keys if key in state}


def compact_audit(audit: dict[str, Any] | None) -> dict[str, Any] | None:
    if audit is None:
        return None

    keys = ["id", "verdict", "confidence", "summary", "created_at", "roadmap_ref"]
    return {key: audit.get(key) for key in keys if key in audit}


def compact_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    keys = ["id", "to_actor", "reason", "message", "status", "created_at"]
    return {key: handoff.get(key) for key in keys if key in handoff}


def format_session_context(
    project_id: str,
    run_id: str,
    state: dict[str, Any] | None,
    audit: dict[str, Any] | None,
    handoffs: list[dict[str, Any]],
) -> str:
    payload = {
        "ashrise_context": {
            "project_id": project_id,
            "run_id": run_id,
            "state": compact_state(state),
            "latest_audit": compact_audit(audit),
            "open_handoffs": [compact_handoff(item) for item in handoffs],
        }
    }
    body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False).strip()
    return f"```yaml\n{body}\n```"


def perform_session_start(
    project_id: str,
    *,
    agent: str = "codex",
    mode: str = "implement",
    prompt_ref: str | None = None,
    cwd: Path | None = None,
    force: bool = False,
    client: AshriseApiClient | None = None,
) -> dict[str, Any]:
    working_dir = (cwd or Path.cwd()).resolve()
    session_path = session_file(project_id, working_dir)

    if session_path.exists() and not force:
        raise RuntimeError(
            f"Session file already exists at {session_path}. "
            "Run session-stop first or use --force."
        )

    if session_path.exists() and force:
        remove_file(session_path)

    owns_client = client is None
    api = client or AshriseApiClient()
    try:
        run = api.create_run(
            {
                "project_id": project_id,
                "agent": agent,
                "mode": mode,
                "prompt_ref": prompt_ref,
                "worktree_path": str(working_dir),
                "metadata": {
                    "source": "ashrise-hook",
                    "cwd": str(working_dir),
                },
            }
        )
        state = api.get_state(project_id, allow_404=True)
        audit = api.get_audit(project_id)
        handoffs = api.get_handoffs(project_id, status="open")

        save_json(
            session_path,
            {
                "project_id": project_id,
                "run_id": run["id"],
                "agent": agent,
                "mode": mode,
                "prompt_ref": prompt_ref,
                "worktree_path": str(working_dir),
                "started_at": run["started_at"],
            },
        )

        context_text = format_session_context(project_id, run["id"], state, audit, handoffs)
        return {
            "run": run,
            "state": state,
            "audit": audit,
            "handoffs": handoffs,
            "context_text": context_text,
            "session_file": str(session_path),
        }
    finally:
        if owns_client:
            api.close()


def merge_items(existing: list[Any], additions: list[Any], clear_ids: list[str]) -> list[Any]:
    keep: list[Any] = []
    clear_set = {str(item) for item in clear_ids}

    for item in existing:
        if isinstance(item, dict) and item.get("id") is not None:
            if str(item["id"]) in clear_set:
                continue
        elif str(item) in clear_set:
            continue
        keep.append(item)

    keep.extend(additions)
    return keep


def build_state_payload(
    existing_state: dict[str, Any] | None,
    state_update: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"last_run_id": run_id}

    for field in ("current_focus", "current_milestone", "next_step"):
        if field in state_update:
            payload[field] = state_update[field]

    existing_blockers = list((existing_state or {}).get("blockers") or [])
    existing_questions = list((existing_state or {}).get("open_questions") or [])

    blockers_add = list(state_update.get("blockers_add") or [])
    blockers_clear = list(state_update.get("blockers_clear") or [])
    questions_add = list(state_update.get("open_questions_add") or [])
    questions_clear = list(state_update.get("open_questions_clear") or [])

    if blockers_add or blockers_clear:
        payload["blockers"] = merge_items(existing_blockers, blockers_add, blockers_clear)

    if questions_add or questions_clear:
        payload["open_questions"] = merge_items(existing_questions, questions_add, questions_clear)

    return payload


def read_transcript_text(transcript: str | None = None, text: str | None = None) -> str:
    if text is not None:
        return text

    if transcript:
        return Path(transcript).read_text(encoding="utf-8")

    if not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped.strip():
            return piped

    raise RuntimeError("Provide --transcript, --text, or pipe transcript text into stdin.")


def perform_session_stop(
    project_id: str,
    *,
    transcript: str | None = None,
    text: str | None = None,
    cwd: Path | None = None,
    client: AshriseApiClient | None = None,
) -> dict[str, Any]:
    working_dir = (cwd or Path.cwd()).resolve()
    session_path = session_file(project_id, working_dir)
    if not session_path.exists():
        raise RuntimeError(f"No active session file found for project '{project_id}' at {session_path}")

    session_data = load_json(session_path)
    close_payload = parse_ashrise_close(read_transcript_text(transcript=transcript, text=text))

    owns_client = client is None
    api = client or AshriseApiClient()
    try:
        run_payload = close_payload["run"]
        run_patch = {
            "status": run_payload["status"],
            "summary": run_payload["summary"],
            "files_touched": run_payload["files_touched"],
            "diff_stats": run_payload["diff_stats"],
            "next_step_proposed": run_payload["next_step_proposed"],
            "worktree_path": session_data.get("worktree_path"),
        }
        run = api.patch_run(session_data["run_id"], run_patch)

        existing_state = api.get_state(project_id, allow_404=True)
        state_payload = build_state_payload(existing_state, close_payload["state_update"], session_data["run_id"])
        state = api.put_state(project_id, state_payload)

        created_handoffs = []
        for handoff in close_payload.get("handoffs", []):
            created_handoffs.append(
                api.create_handoff(
                    {
                        "project_id": project_id,
                        "from_run_id": session_data["run_id"],
                        "from_actor": session_data.get("agent", "codex"),
                        "to_actor": handoff["to_actor"],
                        "reason": handoff["reason"],
                        "message": handoff["message"],
                        "context_refs": handoff.get("context_refs", []),
                        "status": "open",
                    }
                )
            )

        created_decisions = []
        for decision in close_payload.get("decisions", []):
            created_decisions.append(
                api.create_decision(
                    {
                        "project_id": project_id,
                        "title": decision["title"],
                        "context": decision["context"],
                        "decision": decision["decision"],
                        "consequences": decision.get("consequences"),
                        "alternatives": decision.get("alternatives", []),
                        "created_by": session_data.get("agent", "codex"),
                    }
                )
            )

        remove_file(session_path)
        return {
            "run": run,
            "state": state,
            "handoffs": created_handoffs,
            "decisions": created_decisions,
        }
    finally:
        if owns_client:
            api.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ashrise-hook", description="Ashrise session lifecycle helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("session-start", help="Open an Ashrise run and print context")
    start_parser.add_argument("--project", required=True)
    start_parser.add_argument("--agent", default="codex")
    start_parser.add_argument("--mode", default="implement")
    start_parser.add_argument("--prompt-ref")
    start_parser.add_argument("--force", action="store_true")

    stop_parser = subparsers.add_parser("session-stop", help="Close an Ashrise run from transcript output")
    stop_parser.add_argument("--project", required=True)
    stop_parser.add_argument("--transcript")
    stop_parser.add_argument("--text")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "session-start":
            result = perform_session_start(
                args.project,
                agent=args.agent,
                mode=args.mode,
                prompt_ref=args.prompt_ref,
                force=args.force,
            )
            print(result["context_text"])
            return 0

        if args.command == "session-stop":
            result = perform_session_stop(
                args.project,
                transcript=args.transcript,
                text=args.text,
            )
            print(
                yaml.safe_dump(
                    {
                        "run_id": result["run"]["id"],
                        "state_project": result["state"]["project_id"],
                        "handoffs_created": len(result["handoffs"]),
                        "decisions_created": len(result["decisions"]),
                    },
                    sort_keys=False,
                    allow_unicode=False,
                ).strip()
            )
            return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 1
