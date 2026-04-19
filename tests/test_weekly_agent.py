from ashrise_runtime.weekly_agent import collect_targets, run_weekly_job


class FakeWeeklyApi:
    def list_projects(self, status=None):
        assert status == "active"
        return [
            {"id": "procurement-licitaciones"},
            {"id": "procurement-core"},
            {"id": "osla-small-qw"},
        ]

    def get_research_queue(self, due=None):
        assert due is None
        return [
            {"status": "pending", "project_id": "procurement-core", "candidate_id": None},
            {"status": "pending", "project_id": None, "candidate_id": "cand-1"},
            {"status": "done", "project_id": "ignored-project", "candidate_id": None},
        ]

    def run_agent(self, payload):
        return {
            "report_type": "audit_report" if payload["target_type"] == "project" else "candidate_research_report",
            "summary": f"done {payload['target_id']}",
            "run": {"status": "completed"},
            "report": {"id": f"report-{payload['target_id']}"},
        }


def test_collect_targets_prioritizes_seed_targets_and_dedupes():
    api = FakeWeeklyApi()
    targets = collect_targets(api)
    assert targets[:3] == [
        ("project", "procurement-licitaciones"),
        ("project", "neytiri"),
        ("project", "osla-small-qw"),
    ]
    assert targets.count(("project", "procurement-core")) == 1
    assert ("candidate", "cand-1") in targets


def test_run_weekly_job_executes_targets():
    api = FakeWeeklyApi()
    result = run_weekly_job(api)
    assert result["failures"] == 0
    assert any(item["target_id"] == "cand-1" for item in result["results"])
