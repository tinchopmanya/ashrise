from datetime import UTC, date, datetime, timedelta

from ashrise_runtime.telegram_bot import (
    build_active_daily_summary,
    build_daily_summary,
    handle_command,
    run_active_daily_cycle,
)


class FakeTelegramApiClient:
    def __init__(self):
        self.created_ideas = []
        self.queue_patches = []

    def get_project(self, project_id):
        return {"id": project_id, "name": "Ashrise", "status": "active", "kind": "project"}

    def get_state(self, project_id, allow_404=False):
        return {
            "project_id": project_id,
            "current_focus": "Sprint 3",
            "current_milestone": "Sprint 3",
            "next_step": "Ship bot",
        }

    def get_runs(self, project_id, limit=1):
        return [
            {
                "status": "completed",
                "started_at": "2026-04-20T09:00:00+00:00",
                "ended_at": "2026-04-20T09:30:00+00:00",
                "summary": "All green",
            }
        ]

    def create_idea(self, payload):
        self.created_ideas.append(payload)
        return {"id": "idea-1", **payload}

    def list_candidates(self, category=None):
        rows = [
            {"slug": "cand-a", "status": "proposed", "category": "learning"},
            {"slug": "cand-b", "status": "investigating", "category": "small-quickwin"},
        ]
        if category:
            return [item for item in rows if item["category"] == category]
        return rows

    def get_candidate(self, candidate_ref):
        return {
            "slug": candidate_ref,
            "name": "Candidate A",
            "status": "investigating",
            "category": "learning",
            "hypothesis": "Useful learning project",
        }

    def get_candidate_research(self, candidate_ref):
        return {"verdict": "advance", "confidence": 0.8, "summary": "Looks solid"}

    def get_research_queue(self, due=None):
        if due == "today":
            return [
                {
                    "id": "q1",
                    "candidate_id": "cand-advance",
                    "project_id": None,
                    "status": "pending",
                    "scheduled_for": "2026-04-20",
                    "recurrence": "weekly",
                },
                {
                    "id": "q2",
                    "candidate_id": "cand-kill",
                    "project_id": None,
                    "status": "pending",
                    "scheduled_for": "2026-04-20",
                    "recurrence": "weekly",
                },
                {
                    "id": "q3",
                    "candidate_id": None,
                    "project_id": "procurement-core",
                    "status": "pending",
                    "scheduled_for": "2026-04-20",
                    "recurrence": "weekly",
                },
            ]
        return [{"id": "q1"}, {"id": "q2"}]

    def patch_research_queue(self, queue_id, payload):
        self.queue_patches.append((queue_id, payload))
        return {"id": queue_id, **payload}

    def list_projects(self, status=None):
        return [{"id": "ashrise"}, {"id": "procurement-core"}]

    def get_audit(self, project_id):
        if project_id == "ashrise":
            return None
        old = datetime.now(UTC) - timedelta(days=10)
        return {"created_at": old.isoformat()}

    def run_agent(self, payload):
        if payload["target_id"] == "cand-advance":
            return {
                "target_type": "candidate",
                "target_id": "cand-advance",
                "report_type": "candidate_research_report",
                "summary": "Advance complete",
                "run": {"id": "run-advance", "status": "completed"},
                "report": {
                    "id": "report-advance",
                    "verdict": "advance",
                    "confidence": 0.82,
                    "metadata": {"promotion_signal": {"ready": True, "consecutive_advances": 3}},
                },
            }
        if payload["target_id"] == "cand-kill":
            return {
                "target_type": "candidate",
                "target_id": "cand-kill",
                "report_type": "candidate_research_report",
                "summary": "Kill complete",
                "run": {"id": "run-kill", "status": "completed"},
                "report": {
                    "id": "report-kill",
                    "verdict": "kill",
                    "confidence": 0.91,
                    "metadata": {"promotion_signal": {"ready": False, "consecutive_advances": 0}},
                },
            }
        return {
            "target_type": payload["target_type"],
            "target_id": payload["target_id"],
            "report_type": "audit_report",
            "summary": "Audit complete",
            "run": {"id": "run-1", "status": "completed"},
            "report": {"id": "report-project", "verdict": "keep", "confidence": 0.74, "metadata": {}},
        }


def test_handle_command_creates_idea():
    api = FakeTelegramApiClient()
    response = handle_command(api, "/idea revisar roadmap", chat_id=123, message_id=77)
    assert "Idea creada" in response
    assert api.created_ideas[0]["source"] == "telegram"


def test_handle_command_returns_candidate_details():
    api = FakeTelegramApiClient()
    response = handle_command(api, "/candidata cand-a", chat_id=1, message_id=1)
    assert "Candidate A" in response
    assert "advance" in response


def test_build_daily_summary_counts_pending_and_stale():
    api = FakeTelegramApiClient()
    summary = build_daily_summary(api, today=date(2026, 4, 20))
    assert "research_queue pending due today: 3" in summary
    assert "active projects without audit in last 7 days: 2" in summary


def test_handle_command_runs_auditar():
    api = FakeTelegramApiClient()
    response = handle_command(api, "/auditar procurement-core", chat_id=1, message_id=1)
    assert "Audit complete" in response
    assert "run-1" in response


def test_run_active_daily_cycle_updates_queue_and_reports_promotion_ready():
    api = FakeTelegramApiClient()
    result = run_active_daily_cycle(api, today=date(2026, 4, 20))

    assert result["processed"] == 3
    assert result["failures"] == 0
    assert result["verdict_counts"]["candidate:advance"] == 1
    assert result["verdict_counts"]["candidate:kill"] == 1
    assert result["verdict_counts"]["project:keep"] == 1
    assert result["promotion_ready"][0]["candidate"] == "cand-advance"

    patches = {queue_id: payload for queue_id, payload in api.queue_patches if "last_report_id" in payload}
    assert patches["q1"]["status"] == "done"
    assert patches["q2"]["status"] == "done"
    assert patches["q3"]["status"] == "pending"
    assert patches["q3"]["scheduled_for"] == "2026-04-27"


def test_build_active_daily_summary_mentions_ready_candidates():
    summary = build_active_daily_summary(
        {
            "today": "2026-04-20",
            "queue_size": 1,
            "processed": 1,
            "failures": 0,
            "verdict_counts": {"candidate:advance": 1},
            "promotion_ready": [{"candidate": "cand-advance", "consecutive_advances": 3}],
            "results": [
                {
                    "target_type": "candidate",
                    "target_id": "cand-advance",
                    "verdict": "advance",
                    "action": "ready",
                }
            ],
        }
    )
    assert "Ready to promote" in summary
    assert "cand-advance" in summary


def test_run_active_daily_cycle_resets_failed_queue_item_and_redacts_error():
    class FailingTelegramApiClient(FakeTelegramApiClient):
        def run_agent(self, payload):
            raise RuntimeError("Authorization: Bearer super-secret-token api_key=brave-real-key")

    api = FailingTelegramApiClient()
    result = run_active_daily_cycle(api, today=date(2026, 4, 20))

    assert result["processed"] == 0
    assert result["failures"] == 3
    failed_items = [item for item in result["results"] if item.get("status") == "failed"]
    assert failed_items
    assert all("[REDACTED]" in item["error"] for item in failed_items)
    assert all("super-secret-token" not in item["error"] for item in failed_items)

    reset_patches = [payload for _, payload in api.queue_patches if payload.get("status") == "pending"]
    assert reset_patches
    assert all("[REDACTED]" in patch["notes"] for patch in reset_patches)
    assert all("brave-real-key" not in patch["notes"] for patch in reset_patches)
