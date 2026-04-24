from datetime import UTC, datetime, timedelta
from uuid import uuid4

from psycopg.types.json import Jsonb


def test_dashboard_overview_happy_path(app_client, auth_headers, db_conn):
    run_id = uuid4()
    handoff_id = uuid4()
    audit_id = uuid4()
    idea_id = uuid4()
    candidate_id = uuid4()
    report_id = uuid4()
    queue_id = uuid4()

    db_conn.execute(
        """
        INSERT INTO runs (id, project_id, agent, mode, status, summary, prompt_ref, langfuse_trace_id)
        VALUES (%s, 'ashrise', 'codex', 'implement', 'completed', 'Dashboard seed run', 'langfuse:auditor-project@v1', 'trace-1')
        """,
        (run_id,),
    )
    db_conn.execute(
        """
        INSERT INTO handoffs (id, project_id, from_actor, to_actor, reason, message, status)
        VALUES (%s, 'ashrise', 'codex', 'human:martin', 'needs-human-review', 'Review dashboard contract', 'open')
        """,
        (handoff_id,),
    )
    db_conn.execute(
        """
        INSERT INTO audit_reports (id, project_id, verdict, confidence, summary, findings)
        VALUES (%s, 'ashrise', 'keep', 0.85, 'Healthy dashboard rollout', %s)
        """,
        (audit_id, Jsonb([{"title": "Looks good"}])),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status)
        VALUES (%s, 'ashrise', 'Dashboard polish idea', 'cli', 'new')
        """,
        (idea_id,),
    )
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, priority, importance, estimated_size, metadata
        )
        VALUES (
            %s, 'dashboard-candidate', 'Dashboard Candidate', 'learning', 'Validate dashboard rollout', 'promising', 2, 2, 1,
            %s
        )
        """,
        (candidate_id, Jsonb({"promotion": {"ready": True}})),
    )
    db_conn.execute(
        """
        INSERT INTO candidate_research_reports (
            id, candidate_id, verdict, confidence, summary,
            competitors_found, market_signals, stack_findings, kill_criteria_hits,
            sub_gap_proposals, proposed_next_steps, evidence_refs, candidate_snapshot, metadata
        )
        VALUES (
            %s, %s, 'advance', 0.78, 'Good fit for promotion',
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            report_id,
            candidate_id,
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb(["promote when ready"]),
            Jsonb([]),
            Jsonb({"slug": "dashboard-candidate"}),
            Jsonb({}),
        ),
    )
    db_conn.execute(
        """
        INSERT INTO research_queue (id, candidate_id, queue_type, priority, scheduled_for, recurrence, status)
        VALUES (%s, %s, 'initial-research', 2, DATE '2000-01-01', 'once', 'pending')
        """,
        (queue_id, candidate_id),
    )

    response = app_client.get("/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["kpis"]["active_projects"] >= 1
    assert payload["kpis"]["runs_today"] >= 1
    assert payload["kpis"]["open_handoffs"] >= 1
    assert payload["kpis"]["ideas_new"] >= 1
    assert payload["kpis"]["queue_due_today"] >= 1
    assert payload["kpis"]["candidates_ready_to_promote"] >= 1
    assert len(payload["weekly_evolution"]) == 7
    assert all("date" in bucket for bucket in payload["weekly_evolution"])
    assert any(item["id"] == str(run_id) for item in payload["latest_runs"])
    assert any(item["id"] == str(handoff_id) for item in payload["open_handoffs"])
    assert any(item["id"] == str(audit_id) for item in payload["latest_audits"])
    assert payload["health_summary"]["api"]["status"] == "ok"
    assert payload["health_summary"]["db"]["status"] == "ok"
    assert payload["health_summary"]["telegram_bot"]["status"] == "unknown"


def test_dashboard_overview_zero_activity_has_seven_buckets(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM handoffs")
    db_conn.execute("DELETE FROM runs")
    db_conn.execute("DELETE FROM audit_reports")
    db_conn.execute("DELETE FROM ideas")

    response = app_client.get("/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["weekly_evolution"]) == 7
    assert all(bucket["runs"] == 0 for bucket in payload["weekly_evolution"])
    assert all(bucket["handoffs_opened"] == 0 for bucket in payload["weekly_evolution"])
    assert all(bucket["handoffs_resolved"] == 0 for bucket in payload["weekly_evolution"])
    assert all(bucket["audits"] == 0 for bucket in payload["weekly_evolution"])
    assert all(bucket["ideas"] == 0 for bucket in payload["weekly_evolution"])


def test_dashboard_projects_list_and_filters(app_client, auth_headers, db_conn):
    project_id = f"dashboard-{uuid4().hex[:8]}"
    run_id = uuid4()
    audit_id = uuid4()
    handoff_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, host_machine, status, priority, importance, size_scope, progress_pct)
        VALUES (%s, 'Dashboard Project', 'project', 'i7-main', 'active', 1, 2, 1, 42)
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO project_state (project_id, current_focus, current_milestone, next_step, updated_at)
        VALUES (%s, 'Ship dashboard', 'Sprint 6', 'Verify overview screen', %s)
        """,
        (project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO runs (id, project_id, agent, mode, status, summary, started_at)
        VALUES (%s, %s, 'codex', 'implement', 'completed', 'Delivered dashboard list', %s)
        """,
        (run_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO audit_reports (id, project_id, verdict, confidence, summary, findings, created_at)
        VALUES (%s, %s, 'keep', 0.7, 'Looks stable', %s, %s)
        """,
        (audit_id, project_id, Jsonb([]), now),
    )
    db_conn.execute(
        """
        INSERT INTO handoffs (id, project_id, from_actor, to_actor, reason, message, status, created_at)
        VALUES (%s, %s, 'codex', 'human:martin', 'needs-human-review', 'Double-check UI polish', 'open', %s)
        """,
        (handoff_id, project_id, now),
    )

    response = app_client.get("/dashboard/projects", headers=auth_headers, params={"q": "Dashboard"})
    assert response.status_code == 200

    payload = response.json()
    project = next(item for item in payload if item["id"] == project_id)
    assert project["host_machine"] == "i7-main"
    assert project["current_focus"] == "Ship dashboard"
    assert project["next_step"] == "Verify overview screen"
    assert project["open_handoffs_count"] == 1
    assert project["last_run_at"] is not None
    assert project["last_audit_at"] is not None


def test_dashboard_project_detail_happy_path(app_client, auth_headers, db_conn):
    project_id = f"detail-{uuid4().hex[:8]}"
    candidate_id = uuid4()
    decision_id = uuid4()
    handoff_id = uuid4()
    run_id = uuid4()
    audit_id = uuid4()
    idea_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, host_machine, status, priority, importance, size_scope, progress_pct)
        VALUES (%s, 'Detail Project', 'project', 'notebook-procurement', 'active', 2, 3, 2, 55)
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO project_state (
            project_id, current_focus, current_milestone, roadmap_ref,
            project_state_code, next_step, blockers, open_questions, updated_at
        )
        VALUES (%s, 'Focus detail screen', 'Sprint 6', 'ROADMAP.md#dashboard', 2, 'Review detail tabs', %s, %s, %s)
        """,
        (project_id, Jsonb([{"id": "b1"}]), Jsonb([{"id": "q1"}]), now),
    )
    db_conn.execute(
        """
        INSERT INTO runs (
            id, project_id, agent, mode, status, summary, started_at, ended_at, prompt_ref, langfuse_trace_id,
            files_touched, diff_stats
        )
        VALUES (
            %s, %s, 'codex', 'implement', 'completed', 'Built detail page', %s, %s, 'langfuse:auditor-project@v1',
            'trace-detail', %s, %s
        )
        """,
        (run_id, project_id, now, now, Jsonb(["a.tsx", "b.tsx"]), Jsonb({"added": 12, "removed": 2})),
    )
    db_conn.execute(
        """
        INSERT INTO handoffs (id, project_id, from_actor, to_actor, reason, message, status, created_at)
        VALUES (%s, %s, 'codex', 'human:martin', 'needs-human-review', 'Check detail screen', 'open', %s)
        """,
        (handoff_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO decisions (id, project_id, title, context, decision, consequences, status, created_at)
        VALUES (%s, %s, 'Keep tabs read-only', 'V1A scope', 'No write actions', 'Lower risk', 'active', %s)
        """,
        (decision_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO audit_reports (id, project_id, verdict, confidence, summary, findings, created_at)
        VALUES (%s, %s, 'keep', 0.91, 'Detail screen is healthy', %s, %s)
        """,
        (audit_id, project_id, Jsonb([{"title": "Strong"}]), now),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, %s, 'Add detail page polish', 'cli', 'triaged', %s)
        """,
        (idea_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, promoted_to_project_id
        )
        VALUES (%s, 'detail-candidate', 'Detail Candidate', 'learning', 'Track relation to project', 'promoted', %s)
        """,
        (candidate_id, project_id),
    )

    response = app_client.get(f"/dashboard/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["project"]["id"] == project_id
    assert payload["state"]["current_focus"] == "Focus detail screen"
    assert payload["state"]["blockers"][0]["id"] == "b1"
    assert payload["latest_audit"]["id"] == str(audit_id)
    assert payload["recent_runs"][0]["id"] == str(run_id)
    assert payload["recent_runs"][0]["files_touched"] == 2
    assert payload["open_handoffs"][0]["id"] == str(handoff_id)
    assert payload["decisions"][0]["id"] == str(decision_id)
    assert payload["related_research"][0]["id"] == str(candidate_id)
    assert payload["related_ideas"][0]["id"] == str(idea_id)


def test_dashboard_project_detail_not_found(app_client, auth_headers):
    response = app_client.get("/dashboard/projects/does-not-exist", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Project does-not-exist not found"}


def test_dashboard_project_detail_with_empty_related_data(app_client, auth_headers, db_conn):
    project_id = f"empty-{uuid4().hex[:8]}"

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Empty Dashboard Project', 'project', 'paused')
        """,
        (project_id,),
    )

    response = app_client.get(f"/dashboard/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["project"]["id"] == project_id
    assert payload["state"]["current_focus"] is None
    assert payload["state"]["blockers"] == []
    assert payload["latest_audit"] is None
    assert payload["recent_runs"] == []
    assert payload["open_handoffs"] == []
    assert payload["decisions"] == []
    assert payload["related_research"] == []
    assert payload["related_ideas"] == []


def test_dashboard_project_graph_happy_path(app_client, auth_headers, db_conn):
    project_id = f"graph-{uuid4().hex[:8]}"
    candidate_id = uuid4()
    decision_id = uuid4()
    open_handoff_id = uuid4()
    resolved_handoff_id = uuid4()
    run_id = uuid4()
    resolver_run_id = uuid4()
    audit_id = uuid4()
    idea_id = uuid4()
    task_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, host_machine, status, priority, importance, size_scope, progress_pct)
        VALUES (%s, 'Graph Project', 'project', 'i7-main', 'active', 2, 3, 2, 61)
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO runs (id, project_id, agent, mode, status, summary, started_at, ended_at, prompt_ref, langfuse_trace_id)
        VALUES
            (%s, %s, 'codex', 'implement', 'completed', 'Built graph endpoint', %s, %s, 'langfuse:auditor-project@v1', 'trace-graph'),
            (%s, %s, 'auditor', 'audit', 'completed', 'Resolved handoff', %s, %s, 'langfuse:auditor-project@v1', 'trace-resolver')
        """,
        (run_id, project_id, now, now, resolver_run_id, project_id, now, now),
    )
    db_conn.execute(
        """
        INSERT INTO handoffs (
            id, project_id, from_run_id, from_actor, to_actor, reason, message, status, created_at,
            resolved_at, resolved_by_run_id
        )
        VALUES
            (%s, %s, %s, 'codex', 'human:martin', 'needs-human-review', 'Check graph semantics', 'open', %s, NULL, NULL),
            (%s, %s, %s, 'codex', 'auditor', 'pass-to-reviewer', 'Audit the graph response', 'resolved', %s, %s, %s)
        """,
        (open_handoff_id, project_id, run_id, now, resolved_handoff_id, project_id, run_id, now, now, resolver_run_id),
    )
    db_conn.execute(
        """
        INSERT INTO decisions (id, project_id, title, context, decision, consequences, status, created_at)
        VALUES (%s, %s, 'Use radial graph fallback', 'Need low-risk F3A graph', 'SVG radial for now', 'Force layout deferred', 'active', %s)
        """,
        (decision_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO audit_reports (id, project_id, verdict, confidence, summary, findings, created_at)
        VALUES (%s, %s, 'keep', 0.88, 'Graph foundation is healthy', %s, %s)
        """,
        (audit_id, project_id, Jsonb([]), now),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, %s, 'Project graph should surface task relations', 'cli', 'triaged', %s)
        """,
        (idea_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, promoted_to_project_id
        )
        VALUES (%s, 'graph-candidate', 'Graph Candidate', 'learning', 'Track project relation', 'promoted', %s)
        """,
        (candidate_id, project_id),
    )
    db_conn.execute(
        """
        INSERT INTO tasks (
            id, idea_id, project_id, candidate_id, title, status, priority, position, tags, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, 'Connect graph node panel', 'ready', 2, 0, %s, %s, %s)
        """,
        (task_id, idea_id, project_id, candidate_id, ["dashboard", "graph"], now, now),
    )

    response = app_client.get(f"/dashboard/projects/{project_id}/graph", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    nodes = {node["id"]: node for node in payload["nodes"]}
    edges = {(edge["from"], edge["to"], edge["kind"]) for edge in payload["edges"]}

    project_node_id = f"project:{project_id}"
    run_node_id = f"run:{run_id}"
    resolver_run_node_id = f"run:{resolver_run_id}"
    open_handoff_node_id = f"handoff:{open_handoff_id}"
    resolved_handoff_node_id = f"handoff:{resolved_handoff_id}"
    decision_node_id = f"decision:{decision_id}"
    candidate_node_id = f"candidate:{candidate_id}"
    idea_node_id = f"idea:{idea_id}"
    task_node_id = f"task:{task_id}"
    audit_node_id = f"audit:{audit_id}"

    assert nodes[project_node_id]["label"] == "Graph Project"
    assert nodes[project_node_id]["meta"] == {
        "status": "active",
        "host_machine": "i7-main",
        "progress_pct": 61,
    }
    assert nodes[run_node_id]["label"] == "codex · implement"
    assert nodes[run_node_id]["meta"]["langfuse_trace_id"] == "trace-graph"
    assert nodes[open_handoff_node_id]["label"] == "codex -> human:martin"
    assert nodes[open_handoff_node_id]["meta"]["reason"] == "needs-human-review"
    assert nodes[decision_node_id]["label"] == "Use radial graph fallback"
    assert nodes[candidate_node_id]["label"] == "Graph Candidate"
    assert nodes[idea_node_id]["label"].startswith("Project graph should surface")
    assert nodes[task_node_id]["label"] == "Connect graph node panel"
    assert nodes[task_node_id]["meta"] == {
        "status": "ready",
        "priority": 2,
        "position": 0,
    }
    assert nodes[audit_node_id]["label"] == "keep"
    assert nodes[audit_node_id]["meta"]["confidence"] == 0.88

    assert (run_node_id, project_node_id, "touches") in edges
    assert (resolver_run_node_id, project_node_id, "touches") in edges
    assert (open_handoff_node_id, project_node_id, "relates_to") in edges
    assert (resolved_handoff_node_id, project_node_id, "relates_to") in edges
    assert (run_node_id, open_handoff_node_id, "produced") in edges
    assert (run_node_id, resolved_handoff_node_id, "produced") in edges
    assert (resolved_handoff_node_id, resolver_run_node_id, "resolved_by") in edges
    assert (decision_node_id, project_node_id, "relates_to") in edges
    assert (candidate_node_id, project_node_id, "promoted_from") in edges
    assert (idea_node_id, project_node_id, "relates_to") in edges
    assert (task_node_id, project_node_id, "touches") in edges
    assert (task_node_id, idea_node_id, "relates_to") in edges
    assert (task_node_id, candidate_node_id, "relates_to") in edges
    assert (audit_node_id, project_node_id, "audits") in edges


def test_dashboard_project_graph_not_found(app_client, auth_headers):
    response = app_client.get("/dashboard/projects/does-not-exist/graph", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Project does-not-exist not found"}


def test_dashboard_project_graph_central_node_only_when_no_relations(app_client, auth_headers, db_conn):
    project_id = f"graph-empty-{uuid4().hex[:8]}"
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, host_machine, status, progress_pct)
        VALUES (%s, 'Lonely Graph Project', 'project', 'i7-main', 'paused', 12)
        """,
        (project_id,),
    )

    response = app_client.get(f"/dashboard/projects/{project_id}/graph", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["edges"] == []


def test_dashboard_actions_run_agent_happy_path(app_client, auth_headers, monkeypatch):
    monkeypatch.delenv("ASHRISE_RESEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_BASE_URL", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_API_KEY", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_PROJECT_ID", raising=False)

    response = app_client.post(
        "/dashboard/actions/run-agent",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["target_type"] == "project"
    assert payload["target_id"] == "procurement-licitaciones"
    assert payload["report_type"] == "audit_report"
    assert payload["run"]["agent"] == "auditor"
    assert payload["report"]["project_id"] == "procurement-licitaciones"


def test_dashboard_actions_run_agent_invalid_target_type(app_client, auth_headers):
    response = app_client.post(
        "/dashboard/actions/run-agent",
        headers=auth_headers,
        json={"target_type": "idea", "target_id": "ashrise"},
    )
    assert response.status_code == 422


def test_dashboard_actions_run_agent_missing_target_returns_404(app_client, auth_headers):
    response = app_client.post(
        "/dashboard/actions/run-agent",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "missing-project"},
    )
    assert response.status_code == 404


def test_dashboard_actions_run_agent_candidate_happy_path(app_client, auth_headers, db_conn, monkeypatch):
    monkeypatch.delenv("ASHRISE_RESEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_BASE_URL", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_API_KEY", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_PROJECT_ID", raising=False)

    candidate_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, problem_desc, status, metadata
        )
        VALUES (
            %s, 'candidate-run-agent', 'Candidate Run Agent', 'learning',
            'Validate the candidate investigate wrapper', 'Need a safe dashboard action', 'proposed', %s
        )
        """,
        (candidate_id, Jsonb({})),
    )

    response = app_client.post(
        "/dashboard/actions/run-agent",
        headers=auth_headers,
        json={"target_type": "candidate", "target_id": "candidate-run-agent"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["target_type"] == "candidate"
    assert payload["target_id"] == "candidate-run-agent"
    assert payload["report_type"] == "candidate_research_report"
    assert payload["run"]["agent"] == "investigator"
    assert payload["report"]["candidate_id"] == str(candidate_id)


def test_dashboard_actions_run_agent_missing_candidate_returns_404(app_client, auth_headers):
    response = app_client.post(
        "/dashboard/actions/run-agent",
        headers=auth_headers,
        json={"target_type": "candidate", "target_id": "missing-candidate"},
    )
    assert response.status_code == 404


def test_dashboard_actions_resolve_handoff_happy_path(app_client, auth_headers, db_conn):
    handoff_id = uuid4()

    db_conn.execute(
        """
        INSERT INTO handoffs (id, project_id, from_actor, to_actor, reason, message, status)
        VALUES (%s, 'ashrise', 'codex', 'human:martin', 'needs-human-review', 'Review safe dashboard writes', 'open')
        """,
        (handoff_id,),
    )

    response = app_client.post(
        "/dashboard/actions/resolve-handoff",
        headers=auth_headers,
        json={"handoff_id": str(handoff_id), "resolution_note": "Checked from dashboard UI"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == str(handoff_id)
    assert payload["status"] == "resolved"
    assert payload["resolved_at"] is not None
    assert "Resolution note: Checked from dashboard UI" in payload["message"]


def test_dashboard_actions_resolve_handoff_not_found(app_client, auth_headers):
    response = app_client.post(
        "/dashboard/actions/resolve-handoff",
        headers=auth_headers,
        json={"handoff_id": str(uuid4()), "resolution_note": "No-op"},
    )
    assert response.status_code == 404


def test_dashboard_actions_resolve_handoff_rejects_already_resolved(app_client, auth_headers, db_conn):
    handoff_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO handoffs (id, project_id, from_actor, to_actor, reason, message, status, resolved_at)
        VALUES (%s, 'ashrise', 'codex', 'human:martin', 'needs-human-review', 'Already done', 'resolved', %s)
        """,
        (handoff_id, now),
    )

    response = app_client.post(
        "/dashboard/actions/resolve-handoff",
        headers=auth_headers,
        json={"handoff_id": str(handoff_id), "resolution_note": "Should fail"},
    )
    assert response.status_code == 409


def test_dashboard_actions_requeue_happy_path(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    queue_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO vertical_candidates (id, slug, name, category, hypothesis, status)
        VALUES (%s, 'queue-candidate', 'Queue Candidate', 'learning', 'Keep queue writes simple', 'promising')
        """,
        (candidate_id,),
    )
    db_conn.execute(
        """
        INSERT INTO research_queue (
            id, candidate_id, queue_type, priority, scheduled_for, recurrence, status, last_run_at, notes
        )
        VALUES (%s, %s, 'follow-up', 2, DATE '2000-01-01', 'weekly', 'done', %s, 'old note')
        """,
        (queue_id, candidate_id, now),
    )

    response = app_client.post(
        "/dashboard/actions/requeue",
        headers=auth_headers,
        json={
            "queue_id": str(queue_id),
            "scheduled_for": "2026-05-01T15:30:00Z",
            "notes": "Retry after dashboard review",
        },
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == str(queue_id)
    assert payload["status"] == "pending"
    assert payload["scheduled_for"] == "2026-05-01"
    assert payload["notes"] == "Retry after dashboard review"


def test_dashboard_actions_requeue_not_found(app_client, auth_headers):
    response = app_client.post(
        "/dashboard/actions/requeue",
        headers=auth_headers,
        json={"queue_id": str(uuid4()), "scheduled_for": "2026-05-01T00:00:00Z"},
    )
    assert response.status_code == 404


def test_ideas_triage_endpoint_happy_path(app_client, auth_headers):
    created = app_client.post(
        "/ideas",
        headers=auth_headers,
        json={
            "raw_text": "Connect idea triage from dashboard",
            "source": "cli",
            "tags": ["dashboard", "triage"],
        },
    )
    assert created.status_code == 201
    idea = created.json()

    patched = app_client.patch(
        f"/ideas/{idea['id']}/triage",
        headers=auth_headers,
        json={
            "project_id": "ashrise",
            "status": "triaged",
            "triage_notes": "Assigned from dashboard F4A",
            "promoted_to": "project:ashrise",
        },
    )
    assert patched.status_code == 200
    payload = patched.json()

    assert payload["project_id"] == "ashrise"
    assert payload["status"] == "triaged"
    assert payload["triage_notes"] == "Assigned from dashboard F4A"
    assert payload["promoted_to"] == "project:ashrise"
    assert payload["triaged_at"] is not None


def test_ideas_triage_endpoint_rejects_missing_project(app_client, auth_headers):
    created = app_client.post(
        "/ideas",
        headers=auth_headers,
        json={
            "raw_text": "Broken triage assignment",
            "source": "cli",
        },
    )
    assert created.status_code == 201
    idea = created.json()

    patched = app_client.patch(
        f"/ideas/{idea['id']}/triage",
        headers=auth_headers,
        json={"project_id": "missing-project", "status": "triaged"},
    )
    assert patched.status_code == 404


def test_decisions_create_happy_path_for_dashboard_ui(app_client, auth_headers):
    created = app_client.post(
        "/decisions",
        headers=auth_headers,
        json={
            "project_id": "ashrise",
            "title": "Open F4A with safe write actions",
            "context": "Dashboard now needs low-risk operational actions",
            "decision": "Expose run-agent, resolve-handoff and idea triage from UI first",
            "consequences": "Higher operability without opening broad editing yet",
            "created_by": "codex",
        },
    )
    assert created.status_code == 201
    payload = created.json()

    assert payload["project_id"] == "ashrise"
    assert payload["title"] == "Open F4A with safe write actions"
    assert payload["created_by"] == "codex"


def test_promote_candidate_happy_path_for_dashboard_ui(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    candidate_slug = f"promote-{uuid4().hex[:8]}"

    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, priority, importance, estimated_size, metadata
        )
        VALUES (
            %s, %s, 'Promote Candidate', 'learning', 'Ready for project creation', 'promising', 2, 3, 1, %s
        )
        """,
        (candidate_id, candidate_slug, Jsonb({"promotion": {"ready": True}})),
    )

    response = app_client.post(
        f"/candidates/{candidate_slug}/promote",
        headers=auth_headers,
        json={
            "project_id": f"candidate-project-{uuid4().hex[:8]}",
            "name": "Promoted Project",
            "host_machine": "i7-main",
            "kind": "project",
        },
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["project"]["name"] == "Promoted Project"
    assert payload["candidate"]["status"] == "promoted"
    assert payload["candidate"]["promoted_to_project_id"] == payload["project"]["id"]
    state = db_conn.execute(
        "SELECT current_focus, next_step FROM project_state WHERE project_id = %s",
        (payload["project"]["id"],),
    ).fetchone()
    assert state is not None
    assert state["current_focus"].startswith("Kickoff from candidate")


def test_promote_candidate_rejects_invalid_payload(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    candidate_slug = f"promote-invalid-{uuid4().hex[:8]}"

    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, metadata
        )
        VALUES (%s, %s, 'Promote Invalid Candidate', 'learning', 'Needs payload validation', 'promising', %s)
        """,
        (candidate_id, candidate_slug, Jsonb({"promotion": {"ready": True}})),
    )

    response = app_client.post(
        f"/candidates/{candidate_slug}/promote",
        headers=auth_headers,
        json={"name": "Missing project id"},
    )
    assert response.status_code == 422


def test_promote_candidate_rejects_already_promoted(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    candidate_slug = f"promote-conflict-{uuid4().hex[:8]}"

    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, promoted_to_project_id, metadata
        )
        VALUES (
            %s, %s, 'Already Promoted Candidate', 'learning', 'Conflict branch', 'promoted', 'ashrise', %s
        )
        """,
        (candidate_id, candidate_slug, Jsonb({"promotion": {"ready": True}})),
    )

    response = app_client.post(
        f"/candidates/{candidate_slug}/promote",
        headers=auth_headers,
        json={"project_id": f"duplicate-project-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 409


def test_dashboard_research_overview_empty_db(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM research_queue")
    db_conn.execute("DELETE FROM candidate_research_reports")
    db_conn.execute("DELETE FROM vertical_candidates")

    response = app_client.get("/dashboard/research/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["kpis"] == {
        "ready_to_promote": 0,
        "queue_due_today": 0,
        "pending_queue_total": 0,
    }
    assert payload["ready_to_promote"] == []
    assert payload["candidates"] == []
    assert payload["queue"] == []
    assert payload["recent_reports"] == []


def test_dashboard_research_overview_happy_path(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    report_id = uuid4()
    queue_id = uuid4()

    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, priority, importance, estimated_size, metadata
        )
        VALUES (
            %s, 'research-ready', 'Research Ready', 'learning', 'Looks promising', 'promising', 1, 1, 2, %s
        )
        """,
        (candidate_id, Jsonb({"promotion": {"ready": True}})),
    )
    db_conn.execute(
        """
        INSERT INTO candidate_research_reports (
            id, candidate_id, verdict, confidence, summary,
            competitors_found, market_signals, stack_findings, kill_criteria_hits,
            sub_gap_proposals, proposed_next_steps, evidence_refs, candidate_snapshot, metadata
        )
        VALUES (
            %s, %s, 'advance', 0.92, 'Promote this candidate',
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            report_id,
            candidate_id,
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb(["promote"]),
            Jsonb([]),
            Jsonb({"slug": "research-ready"}),
            Jsonb({}),
        ),
    )
    db_conn.execute(
        """
        INSERT INTO research_queue (id, candidate_id, queue_type, priority, scheduled_for, recurrence, status)
        VALUES (%s, %s, 'initial-research', 1, DATE '2000-01-01', 'once', 'pending')
        """,
        (queue_id, candidate_id),
    )

    response = app_client.get("/dashboard/research/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["kpis"]["ready_to_promote"] >= 1
    assert payload["kpis"]["queue_due_today"] >= 1
    assert payload["kpis"]["pending_queue_total"] >= 1
    assert any(item["id"] == str(candidate_id) for item in payload["ready_to_promote"])
    assert any(item["id"] == str(candidate_id) for item in payload["candidates"])
    assert any(item["id"] == str(queue_id) for item in payload["queue"])
    queue_item = next(item for item in payload["queue"] if item["id"] == str(queue_id))
    assert queue_item["notes"] is None
    assert any(item["id"] == str(report_id) for item in payload["recent_reports"])


def test_dashboard_runs_recent_and_detail_happy_path(app_client, auth_headers, db_conn):
    project_id = f"runs-{uuid4().hex[:8]}"
    run_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Runs Project', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO runs (
            id, project_id, agent, agent_version, mode, prompt_ref, worktree_path,
            status, summary, started_at, ended_at, files_touched, diff_stats,
            next_step_proposed, cost_usd, langfuse_trace_id, metadata
        )
        VALUES (
            %s, %s, 'codex', 'gpt-5.4', 'implement', 'langfuse:auditor-project@v1', 'C:/wt/runs',
            'completed', 'Delivered runs page', %s, %s, %s, %s, 'Ship handoffs page', 1.2345, 'trace-runs', %s
        )
        """,
        (
            run_id,
            project_id,
            now,
            now,
            Jsonb(["dashboard-ui/src/app.tsx", "app/routers/dashboard.py"]),
            Jsonb({"added": 22, "removed": 3}),
            Jsonb({"prompt_source": "langfuse"}),
        ),
    )

    recent_response = app_client.get(
        "/dashboard/runs/recent",
        headers=auth_headers,
        params={"project_id": project_id},
    )
    assert recent_response.status_code == 200

    recent_payload = recent_response.json()
    assert len(recent_payload) == 1
    assert recent_payload[0]["id"] == str(run_id)
    assert recent_payload[0]["project_name"] == "Runs Project"
    assert recent_payload[0]["files_touched_count"] == 2
    assert recent_payload[0]["files_touched"] is None
    assert recent_payload[0]["langfuse_trace_id"] == "trace-runs"

    detail_response = app_client.get(f"/dashboard/runs/{run_id}", headers=auth_headers)
    assert detail_response.status_code == 200

    detail_payload = detail_response.json()
    assert detail_payload["id"] == str(run_id)
    assert detail_payload["files_touched"] == ["dashboard-ui/src/app.tsx", "app/routers/dashboard.py"]
    assert detail_payload["diff_stats"] == {"added": 22, "removed": 3}
    assert detail_payload["metadata"] == {"prompt_source": "langfuse"}
    assert detail_payload["cost_usd"] == 1.2345


def test_dashboard_runs_recent_empty_and_run_detail_not_found(app_client, auth_headers):
    recent_response = app_client.get(
        "/dashboard/runs/recent",
        headers=auth_headers,
        params={"agent": "__nobody__"},
    )
    assert recent_response.status_code == 200
    assert recent_response.json() == []

    missing_id = uuid4()
    detail_response = app_client.get(f"/dashboard/runs/{missing_id}", headers=auth_headers)
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": f"Run {missing_id} not found"}


def test_dashboard_langfuse_endpoints_happy_path(app_client, auth_headers, db_conn, monkeypatch):
    project_id = f"langfuse-{uuid4().hex[:8]}"
    run_traced_id = uuid4()
    run_fallback_id = uuid4()
    run_error_id = uuid4()
    now = datetime.now(UTC)

    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://langfuse-web:3000")
    db_conn.execute("DELETE FROM handoffs")
    db_conn.execute("DELETE FROM runs")

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Langfuse Project', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO runs (
            id, project_id, agent, mode, status, summary, started_at, ended_at,
            prompt_ref, langfuse_trace_id, metadata
        )
        VALUES
            (%s, %s, 'auditor', 'audit', 'completed', 'Healthy traced run', %s, %s, 'langfuse:auditor-project@v1', 'trace-happy', %s),
            (%s, %s, 'auditor', 'audit', 'completed', 'Prompt fallback run', %s, %s, 'langfuse:auditor-project@v1', 'trace-fallback', %s),
            (%s, %s, 'investigator', 'investigate', 'failed', 'Trace error run', %s, %s, 'langfuse:investigator-candidate@v1', NULL, %s)
        """,
        (
            run_traced_id,
            project_id,
            now - timedelta(minutes=20),
            now - timedelta(minutes=19),
            Jsonb({"prompt_source": "langfuse", "prompt_fallback": False, "langfuse_status": "traced"}),
            run_fallback_id,
            project_id,
            now - timedelta(minutes=10),
            now - timedelta(minutes=9),
            Jsonb({"prompt_source": "langfuse-fallback", "prompt_fallback": True, "langfuse_status": "traced"}),
            run_error_id,
            project_id,
            now - timedelta(minutes=5),
            now - timedelta(minutes=4),
            Jsonb({"prompt_source": "repo-local", "langfuse_status": "trace-error", "langfuse_error": "timeout contacting langfuse"}),
        ),
    )

    summary_response = app_client.get("/dashboard/langfuse/summary", headers=auth_headers)
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["langfuse_base_url"] == "http://localhost:3000"
    assert summary_payload["kpis"] == {
        "observed_runs": 3,
        "unique_prompts": 2,
        "traced_runs": 2,
        "fallback_runs": 1,
        "error_runs": 1,
    }
    assert any(item["source"] == "langfuse" and item["count"] == 1 for item in summary_payload["prompt_sources"])
    assert any(item["source"] == "langfuse-fallback" and item["count"] == 1 for item in summary_payload["prompt_sources"])
    assert any(item["status"] == "traced" and item["count"] == 2 for item in summary_payload["langfuse_statuses"])
    assert summary_payload["recent_fallbacks"][0]["run_id"] == str(run_fallback_id)
    assert summary_payload["recent_errors"][0]["run_id"] == str(run_error_id)

    prompts_response = app_client.get("/dashboard/langfuse/prompts", headers=auth_headers)
    assert prompts_response.status_code == 200
    prompts_payload = prompts_response.json()
    assert prompts_payload["langfuse_base_url"] == "http://localhost:3000"
    assert len(prompts_payload["items"]) == 2
    auditor_prompt = next(item for item in prompts_payload["items"] if item["prompt_ref"] == "langfuse:auditor-project@v1")
    assert auditor_prompt["runs_count"] == 2
    assert auditor_prompt["last_prompt_source"] == "langfuse-fallback"
    assert auditor_prompt["last_prompt_fallback"] is True

    traces_response = app_client.get(
        "/dashboard/langfuse/traces",
        headers=auth_headers,
        params={"prompt_source": "langfuse-fallback"},
    )
    assert traces_response.status_code == 200
    traces_payload = traces_response.json()
    assert traces_payload["langfuse_base_url"] == "http://localhost:3000"
    assert len(traces_payload["items"]) == 1
    assert traces_payload["items"][0]["run_id"] == str(run_fallback_id)
    assert traces_payload["items"][0]["prompt_fallback"] is True
    assert traces_payload["items"][0]["langfuse_status"] == "traced"


def test_dashboard_langfuse_endpoints_empty(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM handoffs")
    db_conn.execute("DELETE FROM runs")

    summary_response = app_client.get("/dashboard/langfuse/summary", headers=auth_headers)
    assert summary_response.status_code == 200
    assert summary_response.json()["kpis"] == {
        "observed_runs": 0,
        "unique_prompts": 0,
        "traced_runs": 0,
        "fallback_runs": 0,
        "error_runs": 0,
    }

    prompts_response = app_client.get("/dashboard/langfuse/prompts", headers=auth_headers)
    assert prompts_response.status_code == 200
    assert prompts_response.json()["items"] == []

    traces_response = app_client.get("/dashboard/langfuse/traces", headers=auth_headers)
    assert traces_response.status_code == 200
    assert traces_response.json()["items"] == []


def test_dashboard_handoffs_open_happy_path_and_empty_filter(app_client, auth_headers, db_conn):
    project_id = f"handoff-{uuid4().hex[:8]}"
    handoff_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Handoff Project', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO runs (id, project_id, agent, mode, status, summary, started_at)
        VALUES (%s, %s, 'codex', 'implement', 'completed', 'Prepared handoff', %s)
        """,
        (run_id, project_id, now),
    )
    db_conn.execute(
        """
        INSERT INTO handoffs (
            id, project_id, from_run_id, from_actor, to_actor, reason, message, context_refs,
            status, created_at
        )
        VALUES (
            %s, %s, %s, 'codex', 'human:martin', 'needs-human-review', 'Check the read-only inbox', %s,
            'open', %s
        )
        """,
        (handoff_id, project_id, run_id, Jsonb(["files:dashboard-ui/src/app.tsx:1-20"]), now),
    )

    response = app_client.get(
        "/dashboard/handoffs/open",
        headers=auth_headers,
        params={"project_id": project_id},
    )
    assert response.status_code == 200

    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(handoff_id)
    assert payload[0]["project_name"] == "Handoff Project"
    assert payload[0]["from_run_id"] == str(run_id)
    assert payload[0]["context_refs"] == ["files:dashboard-ui/src/app.tsx:1-20"]
    assert payload[0]["resolved_at"] is None

    empty_response = app_client.get(
        "/dashboard/handoffs/open",
        headers=auth_headers,
        params={"to_actor": "nobody"},
    )
    assert empty_response.status_code == 200
    assert empty_response.json() == []


def test_dashboard_ideas_overview_happy_path(app_client, auth_headers, db_conn):
    project_id = f"ideas-{uuid4().hex[:8]}"
    first_idea_id = uuid4()
    second_idea_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Ideas Project', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, tags, status, created_at)
        VALUES (%s, %s, 'Dashboard visual polish', 'cli', %s, 'new', %s)
        """,
        (first_idea_id, project_id, ["dashboard", "ui"], now),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, promoted_to, triage_notes, created_at, triaged_at)
        VALUES (%s, %s, 'Promote this idea to a project', 'telegram', 'promoted', 'project:ashrise', 'Approved', %s, %s)
        """,
        (second_idea_id, project_id, now, now),
    )

    response = app_client.get("/dashboard/ideas/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["kpis"]["total"] >= 2
    assert payload["kpis"]["new"] >= 1
    assert payload["kpis"]["promoted"] >= 1
    assert payload["sources"]["cli"] >= 1
    assert payload["sources"]["telegram"] >= 1
    assert any(item["id"] == str(first_idea_id) for item in payload["ideas"])
    promoted = next(item for item in payload["ideas"] if item["id"] == str(second_idea_id))
    assert promoted["project_name"] == "Ideas Project"
    assert promoted["promoted_to"] == "project:ashrise"


def test_dashboard_ideas_overview_empty_db(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM ideas")

    response = app_client.get("/dashboard/ideas/overview", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["kpis"] == {
        "total": 0,
        "new": 0,
        "triaged": 0,
        "promoted": 0,
        "discarded": 0,
    }
    assert payload["sources"] == {
        "telegram": 0,
        "whatsapp": 0,
        "cli": 0,
        "web": 0,
        "other": 0,
    }
    assert payload["ideas"] == []


def test_dashboard_system_health_unknown_when_probe_missing(app_client, auth_headers, monkeypatch):
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("ASHRISE_DOCKER", raising=False)

    response = app_client.get("/dashboard/system/health", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["api"]["status"] == "ok"
    assert payload["db"]["status"] == "ok"
    assert payload["langfuse"] == {"status": "unknown", "note": "not configured"}
    assert payload["telegram_bot"] == {"status": "unknown", "note": "probe not implemented"}
    assert payload["cron_scheduler"] == {"status": "unknown", "note": "probe not implemented"}


def test_dashboard_cors_allows_local_spa_origin(app_client):
    response = app_client.options(
        "/dashboard/overview",
        headers={
            "Origin": "http://127.0.0.1:4173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"


def test_project_state_update_happy_path(app_client, auth_headers, db_conn):
    project_id = f"state-edit-{uuid4().hex[:8]}"
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Project State Edit', 'project', 'active')
        """,
        (project_id,),
    )

    response = app_client.put(
        f"/state/{project_id}",
        headers=auth_headers,
        json={
            "current_focus": "Close F5A safely",
            "current_milestone": "Dashboard Phase 5",
            "next_step": "Validate refresh and persistence",
            "blockers": ["Waiting for final UI check"],
            "open_questions": ["Should F5B open candidate editing deeper?"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_focus"] == "Close F5A safely"
    assert payload["current_milestone"] == "Dashboard Phase 5"
    assert payload["next_step"] == "Validate refresh and persistence"
    assert payload["blockers"] == ["Waiting for final UI check"]
    assert payload["open_questions"] == ["Should F5B open candidate editing deeper?"]


def test_project_state_update_invalid_payload(app_client, auth_headers, db_conn):
    project_id = f"state-invalid-{uuid4().hex[:8]}"
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Project State Invalid', 'project', 'active')
        """,
        (project_id,),
    )

    response = app_client.put(
        f"/state/{project_id}",
        headers=auth_headers,
        json={"blockers": "not-a-list"},
    )
    assert response.status_code == 422


def test_project_state_update_missing_project(app_client, auth_headers):
    response = app_client.put(
        "/state/missing-project",
        headers=auth_headers,
        json={"current_focus": "Missing"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Project 'missing-project' not found"}


def test_project_metadata_patch_happy_path(app_client, auth_headers, db_conn):
    project_id = f"project-patch-{uuid4().hex[:8]}"
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status, priority, importance, host_machine, progress_pct)
        VALUES (%s, 'Project Patch', 'project', 'paused', 2, 2, 'old-host', 12)
        """,
        (project_id,),
    )

    response = app_client.patch(
        f"/projects/{project_id}",
        headers=auth_headers,
        json={
            "status": "active",
            "priority": 4,
            "importance": 5,
            "host_machine": "i7-main",
            "progress_pct": 67,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "active"
    assert payload["priority"] == 4
    assert payload["importance"] == 5
    assert payload["host_machine"] == "i7-main"
    assert payload["progress_pct"] == 67


def test_candidate_metadata_patch_happy_path(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, problem_desc, status, priority, importance, estimated_size
        )
        VALUES (
            %s, 'candidate-editable', 'Candidate Editable', 'learning', 'Old hypothesis', 'Old problem',
            'investigating', 2, 3, 1
        )
        """,
        (candidate_id,),
    )

    response = app_client.patch(
        "/candidates/candidate-editable",
        headers=auth_headers,
        json={
            "status": "promising",
            "priority": 5,
            "importance": 4,
            "estimated_size": 3,
            "hypothesis": "New hypothesis",
            "problem_desc": "New problem statement",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "promising"
    assert payload["priority"] == 5
    assert payload["importance"] == 4
    assert payload["estimated_size"] == 3
    assert payload["hypothesis"] == "New hypothesis"
    assert payload["problem_desc"] == "New problem statement"


def test_candidate_metadata_patch_invalid_payload(app_client, auth_headers, db_conn):
    candidate_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status
        )
        VALUES (
            %s, 'candidate-invalid-edit', 'Candidate Invalid Edit', 'learning', 'Hypothesis', 'proposed'
        )
        """,
        (candidate_id,),
    )

    response = app_client.patch(
        "/candidates/candidate-invalid-edit",
        headers=auth_headers,
        json={"estimated_size": 8},
    )
    assert response.status_code == 422


def test_decision_supersede_happy_path(app_client, auth_headers, db_conn):
    project_id = f"decision-supersede-{uuid4().hex[:8]}"
    decision_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Decision Supersede Project', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO decisions (id, project_id, title, context, decision, consequences, status, created_by)
        VALUES (%s, %s, 'Old decision', 'Original context', 'Original decision', 'Original consequences', 'active', 'human:martin')
        """,
        (decision_id, project_id),
    )

    response = app_client.post(
        f"/decisions/{decision_id}/supersede",
        headers=auth_headers,
        json={
            "title": "Replacement decision",
            "context": "Updated context",
            "decision": "Use safer edit forms",
            "consequences": "Lower risk rollout",
            "status": "active",
            "created_by": "dashboard-ui",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Replacement decision"
    assert payload["supersedes"] == str(decision_id)
    assert payload["status"] == "active"
    assert payload["created_by"] == "dashboard-ui"

    previous = db_conn.execute("SELECT status FROM decisions WHERE id = %s", (decision_id,)).fetchone()
    assert previous["status"] == "superseded"


def test_decision_supersede_conflict_when_already_superseded(app_client, auth_headers, db_conn):
    project_id = f"decision-superseded-{uuid4().hex[:8]}"
    decision_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Decision Already Superseded', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO decisions (id, project_id, title, context, decision, status)
        VALUES (%s, %s, 'Old superseded decision', 'Context', 'Decision', 'superseded')
        """,
        (decision_id, project_id),
    )

    response = app_client.post(
        f"/decisions/{decision_id}/supersede",
        headers=auth_headers,
        json={
            "title": "Replacement decision",
            "context": "Updated context",
            "decision": "Try again",
        },
    )
    assert response.status_code == 409


def test_notification_event_persisted_for_telegram_idea_capture(app_client, auth_headers, db_conn):
    table = db_conn.execute("SELECT to_regclass('public.notification_events') AS table_name").fetchone()
    assert table["table_name"] == "notification_events"

    response = app_client.post(
        "/ideas",
        headers=auth_headers,
        json={
            "raw_text": "Nueva idea desde Telegram",
            "source": "telegram",
            "source_ref": "123:456",
            "status": "new",
        },
    )
    assert response.status_code == 201
    idea = response.json()

    event = db_conn.execute(
        """
        SELECT channel, direction, idea_id, message_type, delivery_status, external_ref
        FROM notification_events
        WHERE idea_id = %s
        """,
        (idea["id"],),
    ).fetchone()
    assert event is not None
    assert event["channel"] == "telegram"
    assert event["direction"] == "inbound"
    assert str(event["idea_id"]) == idea["id"]
    assert event["message_type"] == "idea-capture"
    assert event["delivery_status"] == "received"
    assert event["external_ref"] == "123:456"


def test_dashboard_notifications_empty(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM notification_events")
    response = app_client.get("/dashboard/notifications", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == {
        "total": 0,
        "telegram": 0,
        "inbound": 0,
        "outbound": 0,
        "delivered": 0,
        "failed": 0,
    }
    assert payload["items"] == []


def test_dashboard_notification_detail_missing(app_client, auth_headers):
    response = app_client.get(f"/dashboard/notifications/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_dashboard_telegram_summary_happy_path(app_client, auth_headers, db_conn):
    idea_id = uuid4()
    outbound_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO ideas (id, raw_text, source, status)
        VALUES (%s, 'Idea seed for notifications', 'telegram', 'new')
        """,
        (idea_id,),
    )
    db_conn.execute(
        """
        INSERT INTO notification_events (
            id, channel, direction, idea_id, message_type, delivery_status, summary, payload_summary, delivered_at
        )
        VALUES (
            %s, 'telegram', 'outbound', %s, 'active-daily-summary', 'delivered', 'Sent active daily summary', %s, NOW()
        )
        """,
        (outbound_id, idea_id, Jsonb({"chat_id": "123", "processed": 2})),
    )
    app_client.post(
        "/ideas",
        headers=auth_headers,
        json={
            "raw_text": "Inbound idea from telegram",
            "source": "telegram",
            "source_ref": "10:20",
        },
    )

    response = app_client.get("/dashboard/telegram/summary", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["kpis"]["total_events"] >= 2
    assert payload["kpis"]["inbound_events"] >= 1
    assert payload["kpis"]["outbound_events"] >= 1
    assert any(item["message_type"] == "active-daily-summary" for item in payload["message_types"])
    assert payload["recent_events"]


def test_dashboard_system_jobs_and_integrations(app_client, auth_headers, db_conn):
    run_id = uuid4()
    db_conn.execute(
        """
        INSERT INTO runs (id, project_id, agent, mode, status, summary, started_at, metadata)
        VALUES (%s, 'ashrise', 'investigator', 'weekly', 'completed', 'Weekly batch seed', NOW(), %s)
        """,
        (run_id, Jsonb({"langfuse_status": "traced", "prompt_source": "langfuse"})),
    )
    db_conn.execute(
        """
        INSERT INTO notification_events (
            id, channel, direction, message_type, delivery_status, summary, payload_summary, delivered_at
        )
        VALUES (
            %s, 'telegram', 'outbound', 'passive-daily-summary', 'delivered', 'Sent passive daily summary', %s, NOW()
        )
        """,
        (uuid4(), Jsonb({"chat_id": "321"})),
    )

    jobs_response = app_client.get("/dashboard/system/jobs", headers=auth_headers)
    assert jobs_response.status_code == 200
    jobs_payload = jobs_response.json()
    assert any(item["key"] == "telegram-passive-daily-summary" for item in jobs_payload["items"])
    assert any(item["key"] == "weekly-agent-batch" for item in jobs_payload["items"])

    integrations_response = app_client.get("/dashboard/system/integrations", headers=auth_headers)
    assert integrations_response.status_code == 200
    integrations_payload = integrations_response.json()
    assert any(item["key"] == "telegram" for item in integrations_payload["items"])
    assert any(item["key"] == "langfuse" for item in integrations_payload["items"])


def test_dashboard_activity_feed_happy_path_filters_and_cursor(app_client, auth_headers, db_conn):
    project_id = f"activity-{uuid4().hex[:8]}"
    other_project_id = f"activity-{uuid4().hex[:8]}"
    run_id = uuid4()
    handoff_id = uuid4()
    decision_id = uuid4()
    audit_id = uuid4()
    idea_id = uuid4()
    task_id = uuid4()
    candidate_id = uuid4()
    research_id = uuid4()
    notification_id = uuid4()
    now = datetime.now(UTC)

    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Activity Project', 'project', 'active')
        """,
        (project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO projects (id, name, kind, status)
        VALUES (%s, 'Other Activity Project', 'project', 'active')
        """,
        (other_project_id,),
    )
    db_conn.execute(
        """
        INSERT INTO vertical_candidates (
            id, slug, name, category, hypothesis, status, promoted_to_project_id
        )
        VALUES (
            %s, 'activity-candidate', 'Activity Candidate', 'learning', 'Feed test candidate', 'promising', %s
        )
        """,
        (candidate_id, project_id),
    )
    db_conn.execute(
        """
        INSERT INTO ideas (id, project_id, raw_text, source, status, created_at)
        VALUES (%s, %s, 'Consolidate activity feed view', 'telegram', 'triaged', %s)
        """,
        (idea_id, project_id, now - timedelta(minutes=5)),
    )
    db_conn.execute(
        """
        INSERT INTO tasks (
            id, idea_id, project_id, candidate_id, title, description, status, position, created_at, updated_at
        )
        VALUES (
            %s, %s, %s, %s, 'Wire feed table', 'Connect backend and detail panel', 'progress', 0, %s, %s
        )
        """,
        (task_id, idea_id, project_id, candidate_id, now - timedelta(minutes=4), now - timedelta(minutes=4)),
    )
    db_conn.execute(
        """
        INSERT INTO runs (id, project_id, agent, mode, status, summary, started_at, ended_at)
        VALUES (%s, %s, 'codex', 'implement', 'completed', 'Built activity feed endpoint', %s, %s)
        """,
        (run_id, project_id, now - timedelta(minutes=1), now - timedelta(minutes=1)),
    )
    db_conn.execute(
        """
        INSERT INTO handoffs (id, project_id, from_actor, to_actor, reason, message, status, created_at)
        VALUES (%s, %s, 'codex', 'human:martin', 'needs-human-review', 'Review the activity feed polish', 'open', %s)
        """,
        (handoff_id, project_id, now - timedelta(minutes=2)),
    )
    db_conn.execute(
        """
        INSERT INTO decisions (id, project_id, title, context, decision, consequences, status, created_by, created_at)
        VALUES (
            %s, %s, 'Keep activity read-only', 'F7A scope', 'No new write actions in this turn',
            'Lower rollout risk', 'active', 'codex', %s
        )
        """,
        (decision_id, project_id, now - timedelta(minutes=3)),
    )
    db_conn.execute(
        """
        INSERT INTO audit_reports (id, project_id, verdict, confidence, summary, findings, created_at)
        VALUES (%s, %s, 'keep', 0.88, 'Activity feed looks stable', %s, %s)
        """,
        (audit_id, project_id, Jsonb([]), now - timedelta(minutes=6)),
    )
    db_conn.execute(
        """
        INSERT INTO candidate_research_reports (
            id, candidate_id, verdict, confidence, summary,
            competitors_found, market_signals, stack_findings, kill_criteria_hits,
            sub_gap_proposals, proposed_next_steps, evidence_refs, candidate_snapshot, metadata, created_at
        )
        VALUES (
            %s, %s, 'advance', 0.81, 'Research says keep pushing the dashboard',
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            research_id,
            candidate_id,
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            Jsonb(["Activity feed next"]),
            Jsonb([]),
            Jsonb({"slug": "activity-candidate"}),
            Jsonb({}),
            now - timedelta(minutes=7),
        ),
    )
    db_conn.execute(
        """
        INSERT INTO notification_events (
            id, channel, direction, project_id, candidate_id, run_id, idea_id, task_id,
            message_type, delivery_status, summary, payload_summary, created_at, delivered_at
        )
        VALUES (
            %s, 'telegram', 'outbound', %s, %s, %s, %s, %s,
            'active-daily-summary', 'delivered', 'Sent daily activity digest', %s, %s, %s
        )
        """,
        (
            notification_id,
            project_id,
            candidate_id,
            run_id,
            idea_id,
            task_id,
            Jsonb({"chat_id": "123", "items": 4}),
            now,
            now,
        ),
    )

    response = app_client.get(
        "/dashboard/activity-feed",
        headers=auth_headers,
        params={"limit": 5, "project_id": project_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"]
    assert payload["items"][0]["kind"] == "notification"
    kinds = {item["kind"] for item in payload["items"]}
    assert "run" in kinds
    assert payload["next_cursor"] is not None

    run_item = next(item for item in payload["items"] if item["kind"] == "run" and item["run_id"] == str(run_id))
    assert run_item["project_id"] == project_id
    assert run_item["run_id"] == str(run_id)
    assert run_item["route"] == "/dashboard/runs"
    assert run_item["actor"] == "codex"

    filtered_response = app_client.get(
        "/dashboard/activity-feed",
        headers=auth_headers,
        params={"kind": "decision", "project_id": project_id},
    )
    assert filtered_response.status_code == 200
    filtered_payload = filtered_response.json()
    assert len(filtered_payload["items"]) == 1
    assert filtered_payload["items"][0]["id"] == str(decision_id)
    assert filtered_payload["items"][0]["route"] == f"/dashboard/projects/{project_id}"

    candidate_response = app_client.get(
        "/dashboard/activity-feed",
        headers=auth_headers,
        params={"candidate_id": str(candidate_id), "kind": "research_report"},
    )
    assert candidate_response.status_code == 200
    candidate_payload = candidate_response.json()
    assert len(candidate_payload["items"]) == 1
    assert candidate_payload["items"][0]["id"] == str(research_id)
    assert candidate_payload["items"][0]["verdict"] == "advance"

    cursor_response = app_client.get(
        "/dashboard/activity-feed",
        headers=auth_headers,
        params={"limit": 5, "project_id": project_id, "cursor": payload["next_cursor"]},
    )
    assert cursor_response.status_code == 200
    cursor_payload = cursor_response.json()
    assert all(item["id"] != payload["items"][0]["id"] for item in cursor_payload["items"])


def test_dashboard_activity_feed_empty(app_client, auth_headers, db_conn):
    db_conn.execute("DELETE FROM notification_events")
    db_conn.execute("DELETE FROM candidate_research_reports")
    db_conn.execute("DELETE FROM tasks")
    db_conn.execute("DELETE FROM ideas")
    db_conn.execute("DELETE FROM audit_reports")
    db_conn.execute("DELETE FROM decisions")
    db_conn.execute("DELETE FROM handoffs")
    db_conn.execute("DELETE FROM runs")

    response = app_client.get("/dashboard/activity-feed", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"items": [], "next_cursor": None}
