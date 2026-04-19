from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from ashrise_runtime.hook_cli import perform_session_start, perform_session_stop
from ashrise_runtime.session_store import transcript_file


def read_prompt(prompt_file: str | None, prompt_text: str | None) -> str | None:
    if prompt_file and prompt_text:
        raise RuntimeError("Use either --prompt-file or --prompt-text, not both")

    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")

    return prompt_text


def build_stdin_payload(context_text: str, prompt_text: str | None) -> str | None:
    if prompt_text is None:
        return None

    return (
        "[Ashrise Session Context]\n"
        f"{context_text}\n\n"
        "[Task]\n"
        f"{prompt_text}\n"
    )


def stream_command(
    command: list[str],
    *,
    stdin_text: str | None,
    transcript_path: Path,
    env: dict[str, str],
    cwd: Path,
) -> int:
    with transcript_path.open("w", encoding="utf-8") as handle:
        handle.write("[Command]\n")
        handle.write(" ".join(command) + "\n\n")

        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if stdin_text is not None and process.stdin is not None:
            process.stdin.write(stdin_text)
            process.stdin.close()

        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            handle.write(line)

        return process.wait()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Codex with Ashrise lifecycle helpers")
    parser.add_argument("--project", required=True)
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--mode", default="implement")
    parser.add_argument("--prompt-file")
    parser.add_argument("--prompt-text")
    parser.add_argument("--transcript")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]

    if not command:
        print("Error: provide the Codex command after --", file=sys.stderr)
        return 1

    working_dir = Path.cwd().resolve()
    prompt_text = read_prompt(args.prompt_file, args.prompt_text)
    transcript_path = Path(args.transcript) if args.transcript else transcript_file(args.project, working_dir)

    try:
        start_result = perform_session_start(
            args.project,
            agent=args.agent,
            mode=args.mode,
            cwd=working_dir,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["ASHRISE_SESSION_CONTEXT"] = start_result["context_text"]
    env["ASHRISE_RUN_ID"] = start_result["run"]["id"]
    env["ASHRISE_PROJECT_ID"] = args.project

    stdin_text = build_stdin_payload(start_result["context_text"], prompt_text)
    exit_code = stream_command(command, stdin_text=stdin_text, transcript_path=transcript_path, env=env, cwd=working_dir)

    try:
        perform_session_stop(args.project, transcript=str(transcript_path), cwd=working_dir)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return exit_code
