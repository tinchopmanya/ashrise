from ashrise.research import assess_stack, check_ai_encroachment, find_competitors, web_search


def test_agent_run_project_persists_audit_and_updates_state(app_client, auth_headers):
    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["report_type"] == "audit_report"
    assert payload["run"]["agent"] == "auditor"
    assert payload["report"]["project_id"] == "procurement-licitaciones"
    assert payload["report"]["metadata"]["research_provider"] == "stub"
    assert payload["run"]["metadata"]["langfuse_status"] == "disabled"
    assert payload["run"]["langfuse_trace_id"] is None
    assert payload["report"]["metadata"]["prompt_ref"] == "langfuse:auditor-project@v1"

    latest = app_client.get("/audit/procurement-licitaciones", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["id"] == payload["report"]["id"]

    state = app_client.get("/state/procurement-licitaciones", headers=auth_headers)
    assert state.status_code == 200
    assert state.json()["last_audit_id"] == payload["report"]["id"]


def test_agent_run_candidate_persists_report_and_updates_last_research(app_client, auth_headers, db_conn):
    created = app_client.post(
        "/candidates",
        headers=auth_headers,
        json={
            "slug": "latam-procurement-watch",
            "name": "LATAM Procurement Watch",
            "category": "small-quickwin",
            "parent_group": "osla",
            "hypothesis": "Small quick win for procurement tracking in LATAM",
        },
    )
    assert created.status_code == 201

    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "candidate", "target_id": "latam-procurement-watch"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["report_type"] == "candidate_research_report"
    assert payload["run"]["agent"] == "investigator"
    assert payload["report"]["metadata"]["research_provider"] == "stub"
    assert payload["report"]["kill_template_id"] is not None
    assert payload["report"]["metadata"]["prompt_ref"] == "langfuse:investigator-candidate@v1"
    assert payload["run"]["metadata"]["langfuse_status"] == "disabled"

    latest = app_client.get("/candidates/latam-procurement-watch/research", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["id"] == payload["report"]["id"]

    row = db_conn.execute(
        "SELECT last_research_id FROM vertical_candidates WHERE slug = %s",
        ("latam-procurement-watch",),
    ).fetchone()
    assert str(row["last_research_id"]) == payload["report"]["id"]


def test_agent_run_missing_target_returns_404(app_client, auth_headers):
    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "missing-project"},
    )
    assert response.status_code == 404


def test_research_stub_fallback_without_provider(monkeypatch):
    monkeypatch.delenv("ASHRISE_RESEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_BASE_URL", raising=False)
    monkeypatch.delenv("ASHRISE_RESEARCH_API_KEY", raising=False)

    search = web_search("procurement licitaciones uruguay")
    competitors = find_competitors("procurement licitaciones uruguay")
    encroachment = check_ai_encroachment("avatar lip sync")
    stack = assess_stack([])

    assert search[0]["provider"] == "stub"
    assert competitors[0]["provider"] == "stub"
    assert encroachment["provider"] == "stub"
    assert stack[0]["provider"] == "stub"


def test_candidate_reaches_promotion_ready_after_three_consecutive_advances(
    app_client,
    auth_headers,
    monkeypatch,
):
    created = app_client.post(
        "/candidates",
        headers=auth_headers,
        json={
            "slug": "promotion-ready-candidate",
            "name": "Promotion Ready Candidate",
            "category": "learning",
            "parent_group": "osla-learning",
            "hypothesis": "Learning observability for portfolio operations",
        },
    )
    assert created.status_code == 201

    monkeypatch.setattr(
        "ashrise.unified_agent._candidate_verdict",
        lambda candidate, kill_hits, ai_risk: (
            "advance",
            0.83,
            [{"title": "keep going", "why": "still promising"}],
        ),
    )

    for _ in range(3):
        response = app_client.post(
            "/agent/run",
            headers=auth_headers,
            json={"target_type": "candidate", "target_id": "promotion-ready-candidate"},
        )
        assert response.status_code == 200
        assert response.json()["report"]["verdict"] == "advance"

    candidate = app_client.get("/candidates/promotion-ready-candidate", headers=auth_headers)
    assert candidate.status_code == 200
    payload = candidate.json()
    assert payload["status"] == "promising"
    assert payload["metadata"]["promotion"]["ready"] is True
    assert payload["metadata"]["promotion"]["consecutive_advances"] == 3

    latest = app_client.get("/candidates/promotion-ready-candidate/research", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["metadata"]["promotion_signal"]["ready"] is True


def test_candidate_promotion_creates_project_and_marks_candidate_promoted(
    app_client,
    auth_headers,
    db_conn,
    monkeypatch,
):
    created = app_client.post(
        "/candidates",
        headers=auth_headers,
        json={
            "slug": "approval-candidate",
            "name": "Approval Candidate",
            "category": "learning",
            "parent_group": "osla-learning",
            "hypothesis": "Learning telemetry patterns for audit-heavy products",
        },
    )
    assert created.status_code == 201

    monkeypatch.setattr(
        "ashrise.unified_agent._candidate_verdict",
        lambda candidate, kill_hits, ai_risk: (
            "advance",
            0.86,
            [{"title": "keep going", "why": "enough evidence"}],
        ),
    )

    for _ in range(3):
        response = app_client.post(
            "/agent/run",
            headers=auth_headers,
            json={"target_type": "candidate", "target_id": "approval-candidate"},
        )
        assert response.status_code == 200

    promoted = app_client.post(
        "/candidates/approval-candidate/promote",
        headers=auth_headers,
        json={
            "project_id": "approval-candidate-project",
            "name": "Approval Candidate Project",
            "host_machine": "i7-main",
        },
    )
    assert promoted.status_code == 201
    payload = promoted.json()
    assert payload["project"]["id"] == "approval-candidate-project"
    assert payload["candidate"]["status"] == "promoted"
    assert payload["candidate"]["promoted_to_project_id"] == "approval-candidate-project"

    project = app_client.get("/projects/approval-candidate-project", headers=auth_headers)
    assert project.status_code == 200
    assert project.json()["promoted_from_candidate_id"] == created.json()["id"]

    state = app_client.get("/state/approval-candidate-project", headers=auth_headers)
    assert state.status_code == 200
    assert state.json()["project_state_code"] == 1

    candidate_row = db_conn.execute(
        "SELECT status, promoted_to_project_id FROM vertical_candidates WHERE slug = %s",
        ("approval-candidate",),
    ).fetchone()
    assert candidate_row["status"] == "promoted"
    assert candidate_row["promoted_to_project_id"] == "approval-candidate-project"
