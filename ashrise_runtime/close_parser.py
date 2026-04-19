from __future__ import annotations

import re
import textwrap
from typing import Any

import yaml


ASHRISE_CLOSE_PATTERN = re.compile(
    r"```ashrise-close[ \t]*\r?\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_ashrise_close_block(text: str) -> str:
    match = ASHRISE_CLOSE_PATTERN.search(text)
    if not match:
        raise ValueError("No ashrise-close block found in transcript")

    return match.group(1)


def parse_ashrise_close(text: str) -> dict[str, Any]:
    block = textwrap.dedent(extract_ashrise_close_block(text)).strip()

    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in ashrise-close block: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("ashrise-close block must contain a YAML object")

    if not isinstance(data.get("run"), dict):
        raise ValueError("ashrise-close block requires a run section")

    if not isinstance(data.get("state_update"), dict):
        raise ValueError("ashrise-close block requires a state_update section")

    run = data["run"]
    for required_key in ("status", "summary", "files_touched", "diff_stats", "next_step_proposed"):
        if required_key not in run:
            raise ValueError(f"run.{required_key} is required in ashrise-close")

    if not isinstance(run["files_touched"], list):
        raise ValueError("run.files_touched must be a list")

    if not isinstance(run["diff_stats"], dict):
        raise ValueError("run.diff_stats must be an object")

    handoffs = data.get("handoffs", [])
    decisions = data.get("decisions", [])

    if handoffs is None:
        handoffs = []
    if decisions is None:
        decisions = []

    if not isinstance(handoffs, list):
        raise ValueError("handoffs must be a list when present")
    if not isinstance(decisions, list):
        raise ValueError("decisions must be a list when present")

    data["handoffs"] = handoffs
    data["decisions"] = decisions
    return data
