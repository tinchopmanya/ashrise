from datetime import UTC, date, datetime, timedelta

from ashrise_runtime.telegram_bot import build_daily_summary, handle_command


class FakeTelegramApiClient:
    def __init__(self):
        self.created_ideas = []

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
        return [{"id": "q1"}, {"id": "q2"}]

    def list_projects(self, status=None):
        return [{"id": "ashrise"}, {"id": "procurement-core"}]

    def get_audit(self, project_id):
        if project_id == "ashrise":
            return None
        old = datetime.now(UTC) - timedelta(days=10)
        return {"created_at": old.isoformat()}

    def run_agent(self, payload):
        return {
            "target_type": payload["target_type"],
            "target_id": payload["target_id"],
            "report_type": "audit_report",
            "summary": "Audit complete",
            "run": {"id": "run-1", "status": "completed"},
            "report": {"verdict": "keep", "confidence": 0.74},
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
    assert "research_queue pending due today: 2" in summary
    assert "active projects without audit in last 7 days: 2" in summary


def test_handle_command_runs_auditar():
    api = FakeTelegramApiClient()
    response = handle_command(api, "/auditar procurement-core", chat_id=1, message_id=1)
    assert "Audit complete" in response
    assert "run-1" in response
