from __future__ import annotations

import argparse
import sys
from typing import Any

from ashrise_runtime.api_client import AshriseApiClient, AshriseApiError


INITIAL_PRIORITY_TARGETS = [
    ("project", "procurement-licitaciones"),
    ("project", "neytiri"),
    ("project", "osla-small-qw"),
    ("project", "procurement-core"),
    ("project", "osla-medium-long"),
]


def collect_targets(api: AshriseApiClient) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    targets: list[tuple[str, str]] = []

    def add(target_type: str, target_id: str | None):
        if not target_id:
            return
        key = (target_type, target_id)
        if key in seen:
            return
        seen.add(key)
        targets.append(key)

    for target_type, target_id in INITIAL_PRIORITY_TARGETS:
        add(target_type, target_id)

    for project in api.list_projects(status="active"):
        add("project", project["id"])

    for queue_item in api.get_research_queue():
        if queue_item.get("status") != "pending":
            continue
        add("project", queue_item.get("project_id"))
        candidate_id = queue_item.get("candidate_id")
        if candidate_id:
            add("candidate", str(candidate_id))

    return targets


def run_weekly_job(api: AshriseApiClient) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    failures = 0

    for target_type, target_id in collect_targets(api):
        try:
            payload = api.run_agent({"target_type": target_type, "target_id": target_id})
        except AshriseApiError as exc:
            failures += 1
            results.append(
                {
                    "target_type": target_type,
                    "target_id": target_id,
                    "status": "failed",
                    "error": exc.detail,
                }
            )
            continue

        results.append(
            {
                "target_type": target_type,
                "target_id": target_id,
                "status": payload["run"]["status"],
                "report_type": payload["report_type"],
                "summary": payload["summary"],
                "report_id": payload["report"]["id"],
            }
        )

    return {"failures": failures, "results": results}


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description="Run the weekly Ashrise audit/research batch once")


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)

    try:
        with AshriseApiClient() as api:
            result = run_weekly_job(api)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for item in result["results"]:
        if item["status"] == "failed":
            print(f"[failed] {item['target_type']} {item['target_id']}: {item['error']}")
            continue
        print(
            f"[ok] {item['target_type']} {item['target_id']} -> "
            f"{item['report_type']} {item['report_id']} :: {item['summary']}"
        )

    return 1 if result["failures"] else 0

