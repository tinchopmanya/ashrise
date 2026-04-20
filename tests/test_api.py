from datetime import date
from uuid import uuid4

from psycopg.types.json import Jsonb


def test_auth_required(app_client):
    response = app_client.get("/health")
    assert response.status_code == 401


def test_health_and_projects_listing(app_client, auth_headers):
    health = app_client.get("/health", headers=auth_headers)
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    projects = app_client.get("/projects", headers=auth_headers)
    assert projects.status_code == 200
    assert len(projects.json()) >= 14
    assert any(item["id"] == "ashrise" for item in projects.json())
    assert any(item["id"] == "procurement-core" for item in projects.json())

    filtered = app_client.get(
        "/projects",
        headers=auth_headers,
        params={"host_machine": "notebook-procurement"},
    )
    assert filtered.status_code == 200
    assert filtered.json()
    assert all(item["host_machine"] == "notebook-procurement" for item in filtered.json())


def test_project_detail_and_state_update(app_client, auth_headers):
    detail = app_client.get("/projects/procurement-core", headers=auth_headers)
    assert detail.status_code == 200
    project = detail.json()
    assert project["id"] == "procurement-core"
    assert any(child["id"] == "procurement-licitaciones" for child in project["children"])

    state = app_client.get("/state/procurement-core", headers=auth_headers)
    assert state.status_code == 200
    assert state.json()["project_state_code"] == 1

    updated = app_client.put(
        "/state/procurement-core",
        headers=auth_headers,
        json={
            "current_focus": "Sprint 2 API",
            "next_step": "Ship FastAPI",
            "blockers": [{"id": "none", "reason": "validated"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["current_focus"] == "Sprint 2 API"
    assert updated.json()["blockers"][0]["id"] == "none"


def test_runs_flow(app_client, auth_headers):
    created = app_client.post(
        "/runs",
        headers=auth_headers,
        json={
            "project_id": "ashrise",
            "agent": "codex",
            "mode": "implement",
            "worktree_path": "C:/dev/src/ashrise",
        },
    )
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "running"

    listing = app_client.get("/runs/ashrise", headers=auth_headers, params={"limit": 5})
    assert listing.status_code == 200
    assert any(item["id"] == run["id"] for item in listing.json())

    patched = app_client.patch(
        f"/runs/{run['id']}",
        headers=auth_headers,
        json={
            "status": "completed",
            "summary": "Sprint 2 run complete",
            "files_touched": ["app/main.py"],
            "diff_stats": {"added": 10, "removed": 2},
        },
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "completed"
    assert patched.json()["ended_at"] is not None


def test_handoffs_flow(app_client, auth_headers):
    created = app_client.post(
        "/handoffs",
        headers=auth_headers,
        json={
            "project_id": "ashrise",
            "from_actor": "codex",
            "to_actor": "human:martin",
            "reason": "needs-human-review",
            "message": "Need approval for roadmap impact",
            "context_refs": ["files:README.md:1"],
        },
    )
    assert created.status_code == 201
    handoff = created.json()

    open_items = app_client.get("/handoffs/ashrise", headers=auth_headers)
    assert open_items.status_code == 200
    assert any(item["id"] == handoff["id"] for item in open_items.json())

    resolved = app_client.patch(
        f"/handoffs/{handoff['id']}",
        headers=auth_headers,
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None


def test_decisions_and_audit(app_client, auth_headers):
    created = app_client.post(
        "/decisions",
        headers=auth_headers,
        json={
            "project_id": "ashrise",
            "title": "Use FastAPI with psycopg",
            "context": "Need a minimal Sprint 2 API",
            "decision": "Use direct SQL without ORM",
            "alternatives": [{"title": "SQLAlchemy", "why_rejected": "Too much for Sprint 2"}],
        },
    )
    assert created.status_code == 201
    decision = created.json()

    listing = app_client.get("/decisions/ashrise", headers=auth_headers)
    assert listing.status_code == 200
    assert any(item["id"] == decision["id"] for item in listing.json())

    audit = app_client.get("/audit/ashrise", headers=auth_headers)
    assert audit.status_code == 200
    assert audit.json() is None


def test_ideas_flow(app_client, auth_headers):
    created = app_client.post(
        "/ideas",
        headers=auth_headers,
        json={
            "raw_text": "Document Sprint 2 curl examples",
            "source": "cli",
            "tags": ["docs", "api"],
        },
    )
    assert created.status_code == 201
    idea = created.json()
    assert idea["status"] == "new"

    listing = app_client.get("/ideas", headers=auth_headers, params={"status": "new"})
    assert listing.status_code == 200
    assert any(item["id"] == idea["id"] for item in listing.json())

    patched = app_client.patch(
        f"/ideas/{idea['id']}",
        headers=auth_headers,
        json={"status": "triaged", "triage_notes": "Ready for Sprint 3"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "triaged"
    assert patched.json()["triaged_at"] is not None


def test_candidates_and_research_flow(app_client, auth_headers, db_conn):
    initial = app_client.get("/candidates", headers=auth_headers)
    assert initial.status_code == 200

    slug = f"candidate-{uuid4().hex[:8]}"
    created = app_client.post(
        "/candidates",
        headers=auth_headers,
        json={
            "slug": slug,
            "name": "Candidate Test",
            "category": "learning",
            "hypothesis": "Useful for Sprint 2 testing",
            "kill_criteria": [{"id": "obsolete-tech", "type": "hard"}],
        },
    )
    assert created.status_code == 201
    candidate = created.json()

    patched = app_client.patch(
        f"/candidates/{candidate['id']}",
        headers=auth_headers,
        json={"status": "investigating", "priority": 2},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "investigating"

    fetched = app_client.get(f"/candidates/{candidate['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["slug"] == slug

    db_conn.execute(
        """
        INSERT INTO candidate_research_reports (
            candidate_id,
            verdict,
            confidence,
            summary,
            competitors_found,
            market_signals,
            stack_findings,
            kill_criteria_hits,
            sub_gap_proposals,
            proposed_next_steps,
            evidence_refs,
            candidate_snapshot,
            metadata
        )
        VALUES (
            %s, 'advance', 0.80, 'Looks promising',
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            candidate["id"],
            Jsonb([{"name": "Example Competitor"}]),
            Jsonb([{"signal": "market pull"}]),
            Jsonb([{"finding": "simple stack"}]),
            Jsonb([]),
            Jsonb([]),
            Jsonb(["keep researching"]),
            Jsonb([]),
            Jsonb({"slug": slug}),
            Jsonb({}),
        ),
    )

    research = app_client.get(f"/candidates/{candidate['id']}/research", headers=auth_headers)
    assert research.status_code == 200
    assert research.json()["verdict"] == "advance"


def test_research_queue_due_today(app_client, auth_headers, db_conn):
    slug = f"queue-{uuid4().hex[:8]}"
    created = app_client.post(
        "/candidates",
        headers=auth_headers,
        json={
            "slug": slug,
            "name": "Queue Candidate",
            "category": "small-quickwin",
            "hypothesis": "Queue coverage",
        },
    )
    assert created.status_code == 201
    candidate = created.json()

    db_conn.execute(
        """
        INSERT INTO research_queue (
            candidate_id,
            queue_type,
            priority,
            scheduled_for,
            recurrence,
            status,
            notes
        )
        VALUES (%s, 'initial-research', 2, %s, 'once', 'pending', 'Due now')
        """,
        (candidate["id"], date.today()),
    )

    queue = app_client.get("/research-queue", headers=auth_headers, params={"due": "today"})
    assert queue.status_code == 200
    assert any(item["candidate_id"] == candidate["id"] for item in queue.json())

    queue_id = next(item["id"] for item in queue.json() if item["candidate_id"] == candidate["id"])
    patched = app_client.patch(
        f"/research-queue/{queue_id}",
        headers=auth_headers,
        json={
            "status": "done",
            "last_report_id": str(uuid4()),
            "notes": "Processed by reminder",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "done"
    assert patched.json()["notes"] == "Processed by reminder"
