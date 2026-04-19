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

