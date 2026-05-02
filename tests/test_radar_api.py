from uuid import UUID


def test_health_still_works(app_client, auth_headers):
    response = app_client.get("/health", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_radar_openapi_and_seeded_config(app_client, auth_headers):
    openapi_response = app_client.get("/openapi.json", headers=auth_headers)
    assert openapi_response.status_code == 200
    paths = openapi_response.json()["paths"]
    assert "/radar/candidates" in paths
    assert "/radar/apply-json" in paths
    assert "/radar/candidates/{candidate_id}/evidence" in paths
    assert "/radar/apply-logs" in paths
    assert "/radar/prompt-runs" in paths
    assert "/radar/file-imports" in paths
    assert "/radar/portfolio/overview" in paths
    assert "/radar/portfolio/compare" in paths

    config_response = app_client.get("/radar/config", headers=auth_headers)
    assert config_response.status_code == 200
    payload = config_response.json()
    keys = {item["key"] for item in payload}
    assert "focus" in keys
    assert "scope" in keys
    assert "initial_strategy" in keys


def create_candidate(app_client, auth_headers, slug: str):
    response = app_client.post(
        "/radar/candidates",
        headers=auth_headers,
        json={
            "slug": slug,
            "name": slug.replace("-", " ").title(),
            "summary": "Local discovery candidate",
            "maturity": "candidate",
        },
    )
    assert response.status_code == 201
    return response.json()


def create_prompt_with_version(app_client, auth_headers, key: str):
    prompt_response = app_client.post(
        "/radar/prompts",
        headers=auth_headers,
        json={
            "key": key,
            "title": key.replace("-", " ").title(),
            "prompt_type": "discovery",
            "description": "Prompt run test",
        },
    )
    assert prompt_response.status_code == 201
    prompt = prompt_response.json()

    version_response = app_client.post(
        f"/radar/prompts/{prompt['id']}/versions",
        headers=auth_headers,
        json={
            "body": "Research {{candidate.name}} / {{candidate.slug}} with {{variables.angle}}.",
            "variables_schema": {"angle": {"type": "string"}},
            "output_schema": {"meta": {"promptRunId": "string"}},
            "filename_pattern": "radar_candidate_*.json",
            "is_active": True,
        },
    )
    assert version_response.status_code == 201
    return prompt, version_response.json()


def test_radar_candidates_create_and_list(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "radar-quick-win")
    assert candidate["slug"] == "radar-quick-win"

    list_response = app_client.get("/radar/candidates", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(item["id"] == candidate["id"] for item in list_response.json())


def test_radar_candidate_patch_get_and_strategy_fields(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "strategy-target")

    patch_response = app_client.patch(
        f"/radar/candidates/{candidate['id']}",
        headers=auth_headers,
        json={
            "verdict": "iterate",
            "priority": 3,
            "focus": "quick_win",
            "scope": "uruguay",
            "maturity": "researched",
            "dominant_risk": "sales_risk",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["verdict"] == "iterate"
    assert patched["priority"] == 3
    assert patched["focus"] == "quick_win"
    assert patched["dominant_risk"] == "sales_risk"

    get_response = app_client.get(f"/radar/candidates/{candidate['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["maturity"] == "researched"


def test_radar_prompts_list_create_and_versions(app_client, auth_headers):
    create_response = app_client.post(
        "/radar/prompts",
        headers=auth_headers,
        json={
            "key": "radar-kill-prompt",
            "title": "Radar Kill Prompt",
            "prompt_type": "kill",
            "description": "Strict kill evaluation",
            "metadata": {"tags": ["kill", "candidate"]},
        },
    )
    assert create_response.status_code == 201
    prompt = create_response.json()

    version_response = app_client.post(
        f"/radar/prompts/{prompt['id']}/versions",
        headers=auth_headers,
        json={
            "body": "Evaluate this candidate and return Radar JSON.",
            "output_schema": {"_radar_export": True, "_entity": "candidates"},
            "filename_pattern": "radar_candidate_*.json",
            "is_active": True,
        },
    )
    assert version_response.status_code == 201
    version = version_response.json()
    assert version["version"] == 1
    assert version["is_active"] is True

    list_versions_response = app_client.get(f"/radar/prompts/{prompt['id']}/versions", headers=auth_headers)
    assert list_versions_response.status_code == 200
    assert list_versions_response.json()[0]["id"] == version["id"]

    list_response = app_client.get("/radar/prompts", headers=auth_headers)
    assert list_response.status_code == 200
    listed_prompt = next(item for item in list_response.json() if item["id"] == prompt["id"])
    assert listed_prompt["latest_version"] == 1
    assert listed_prompt["latest_version_is_active"] is True


def test_radar_prompt_render_creates_prompt_run_with_candidate_and_variables(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "render-target")
    prompt, version = create_prompt_with_version(app_client, auth_headers, "render-prompt")

    response = app_client.post(
        f"/radar/prompts/{prompt['id']}/versions/{version['id']}/render",
        headers=auth_headers,
        json={
            "candidate_id": candidate["id"],
            "target_tool": "chatgpt_web",
            "model_label": "GPT-5.5 Thinking",
            "variables": {"angle": "buyer pain"},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["target_tool"] == "chatgpt_web"
    assert candidate["name"] in payload["rendered_prompt"]
    assert "buyer pain" in payload["rendered_prompt"]
    assert f'"promptRunId": "{payload["prompt_run_id"]}"' in payload["rendered_prompt"]
    assert f'"promptId": "{prompt["id"]}"' in payload["rendered_prompt"]
    assert f'"promptVersionId": "{version["id"]}"' in payload["rendered_prompt"]
    assert f'"candidateId": "{candidate["id"]}"' in payload["rendered_prompt"]
    assert "Guardar" not in payload["rendered_prompt"]
    assert payload["expected_filename"].startswith("radar_candidate_")
    assert "{{prompt_run" not in payload["expected_filename"]

    run_response = app_client.get(f"/radar/prompt-runs/{payload['prompt_run_id']}", headers=auth_headers)
    assert run_response.status_code == 200
    run = run_response.json()
    assert run["status"] == "created"
    assert run["candidate_id"] == candidate["id"]
    assert run["model_label"] == "GPT-5.5 Thinking"


def test_radar_prompt_run_mark_copied_and_list(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "copy-run-target")
    prompt, version = create_prompt_with_version(app_client, auth_headers, "copy-run-prompt")

    render_response = app_client.post(
        f"/radar/prompts/{prompt['id']}/versions/{version['id']}/render",
        headers=auth_headers,
        json={"candidate_id": candidate["id"], "target_tool": "claude_web", "variables": {"angle": "risk"}},
    )
    assert render_response.status_code == 201
    prompt_run_id = render_response.json()["prompt_run_id"]

    copied_response = app_client.post(f"/radar/prompt-runs/{prompt_run_id}/mark-copied", headers=auth_headers)
    assert copied_response.status_code == 200
    assert copied_response.json()["status"] == "waiting_import"

    list_response = app_client.get(
        f"/radar/prompt-runs?candidate_id={candidate['id']}&status=waiting_import&limit=5",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    assert any(item["id"] == prompt_run_id for item in list_response.json())


def test_radar_apply_json_with_prompt_run_links_apply_log(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "prompt-run-apply-target")
    prompt, version = create_prompt_with_version(app_client, auth_headers, "prompt-run-apply-prompt")
    render_response = app_client.post(
        f"/radar/prompts/{prompt['id']}/versions/{version['id']}/render",
        headers=auth_headers,
        json={
            "candidate_id": candidate["id"],
            "target_tool": "chatgpt_web",
            "model_label": "ChatGPT Web",
            "variables": {"angle": "pricing"},
        },
    )
    assert render_response.status_code == 201
    prompt_run_id = render_response.json()["prompt_run_id"]

    apply_response = app_client.post(
        "/radar/apply-json",
        headers=auth_headers,
        json={
            "meta": {
                "promptRunId": prompt_run_id,
                "candidateId": candidate["id"],
                "promptId": prompt["id"],
                "promptVersionId": version["id"],
                "modelUsed": "ChatGPT Web",
            },
            "updates": {"summary": "Linked prompt run summary"},
        },
    )
    assert apply_response.status_code == 201
    payload = apply_response.json()
    assert payload["prompt_run_id"] == prompt_run_id

    run_response = app_client.get(f"/radar/prompt-runs/{prompt_run_id}", headers=auth_headers)
    assert run_response.status_code == 200
    prompt_run = run_response.json()
    assert prompt_run["status"] == "applied"
    assert prompt_run["apply_log_id"] == payload["apply_log_id"]

    log_response = app_client.get(f"/radar/apply-logs/{payload['apply_log_id']}", headers=auth_headers)
    assert log_response.status_code == 200
    apply_log = log_response.json()
    assert apply_log["prompt_id"] == prompt["id"]
    assert apply_log["prompt_version_id"] == version["id"]


def test_radar_apply_json_unknown_prompt_run_warns_but_applies(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "unknown-run-target")
    unknown_prompt_run_id = "00000000-0000-0000-0000-000000000123"

    response = app_client.post(
        "/radar/apply-json",
        headers=auth_headers,
        json={
            "meta": {
                "candidateId": candidate["id"],
                "promptRunId": unknown_prompt_run_id,
            },
            "updates": {"summary": "Applied despite unknown prompt run"},
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["prompt_run_id"] is None
    assert any(unknown_prompt_run_id in warning for warning in payload["warnings"])

    refreshed = app_client.get(f"/radar/candidates/{candidate['id']}", headers=auth_headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["summary"] == "Applied despite unknown prompt run"


def test_radar_apply_json_update_logs_and_applies_candidate_and_evidence(app_client, auth_headers, db_conn):
    candidate = create_candidate(app_client, auth_headers, "apply-target")

    response = app_client.post(
        "/radar/apply-json",
        headers=auth_headers,
        json={
            "meta": {
                "candidateId": candidate["id"],
                "modelUsed": "ChatGPT Web",
                "notes": "Manual apply test",
                "sourceType": "manual_paste",
            },
            "updates": {
                "summary": "After apply",
                "focus": "quick_win",
                "scope": "latam",
                "decisionMemo": "Strong operator pain with clear wedge.",
                "nextResearch": {"next": ["buyer interviews"]},
                "killCriteria": {"must_prove": "willingness_to_pay"},
                "verdict": "iterate",
                "priority": 4,
            },
            "scorecard": {"confidence": 0.72},
            "gates": {"problem_validated": False},
            "evidence": [
                {
                    "kind": "web_note",
                    "title": "Buyer quote",
                    "claim": "Ops teams still reconcile manually.",
                    "sourceName": "ChatGPT synthesis",
                    "sourceTier": "secondary",
                    "confidence": 0.64,
                    "notes": "Synthetic evidence",
                }
            ],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["mode"] == "update"
    assert payload["candidate_id"] == candidate["id"]
    assert "decision_memo" in payload["updates_applied"]
    assert payload["evidence_created"] == 1

    refreshed = app_client.get(f"/radar/candidates/{candidate['id']}", headers=auth_headers)
    assert refreshed.status_code == 200
    refreshed_candidate = refreshed.json()
    assert refreshed_candidate["summary"] == "After apply"
    assert refreshed_candidate["focus"] == "quick_win"
    assert refreshed_candidate["decision_memo"] == "Strong operator pain with clear wedge."
    assert refreshed_candidate["next_research"]["next"] == ["buyer interviews"]
    assert refreshed_candidate["kill_criteria"]["must_prove"] == "willingness_to_pay"
    assert refreshed_candidate["verdict"] == "iterate"
    assert refreshed_candidate["priority"] == 4
    assert refreshed_candidate["scorecard"]["confidence"] == 0.72

    evidence_rows = db_conn.execute(
        "SELECT * FROM radar_evidence WHERE candidate_id = %s",
        (UUID(candidate["id"]),),
    ).fetchall()
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["kind"] == "web_note"

    apply_log = db_conn.execute(
        "SELECT * FROM radar_apply_logs WHERE id = %s",
        (UUID(payload["apply_log_id"]),),
    ).fetchone()
    assert apply_log is not None
    assert apply_log["status"] == "applied"
    assert apply_log["source_type"] == "manual_paste"
    assert apply_log["model_used"] == "ChatGPT Web"
    assert apply_log["json_payload"]["meta"]["candidateId"] == candidate["id"]


def test_radar_apply_json_invalid_format_returns_clear_error_and_logs_failed(app_client, auth_headers, db_conn):
    response = app_client.post(
        "/radar/apply-json",
        headers=auth_headers,
        json={"hello": "world"},
    )
    assert response.status_code == 422
    payload = response.json()["detail"]
    assert "Unrecognized Radar JSON payload" in payload["message"]

    apply_log = db_conn.execute(
        "SELECT * FROM radar_apply_logs WHERE id = %s",
        (UUID(payload["apply_log_id"]),),
    ).fetchone()
    assert apply_log is not None
    assert apply_log["status"] == "failed"
    assert "Unrecognized Radar JSON payload" in apply_log["error_message"]


def test_radar_apply_json_dry_run_does_not_modify_candidate(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "dry-run-target")

    response = app_client.post(
        "/radar/apply-json?dry_run=true",
        headers=auth_headers,
        json={
            "meta": {
                "candidateId": candidate["id"],
                "modelUsed": "Claude Web",
                "sourceType": "drag_drop",
            },
            "updates": {
                "summary": "This should not persist",
                "decisionMemo": "Preview only",
            },
            "evidence": [{"kind": "note", "notes": "Preview evidence"}],
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["candidate_id"] == candidate["id"]
    assert "summary" in payload["updates_applied"]
    assert "decision_memo" in payload["updates_applied"]
    assert payload["evidence_created"] == 0

    refreshed = app_client.get(f"/radar/candidates/{candidate['id']}", headers=auth_headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["summary"] == "Local discovery candidate"
    assert refreshed.json()["decision_memo"] is None

    evidence_response = app_client.get(f"/radar/candidates/{candidate['id']}/evidence", headers=auth_headers)
    assert evidence_response.status_code == 200
    assert evidence_response.json() == []


def test_radar_candidate_evidence_endpoints(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "evidence-target")

    create_response = app_client.post(
        f"/radar/candidates/{candidate['id']}/evidence",
        headers=auth_headers,
        json={
            "kind": "article",
            "title": "Manual source",
            "url": "https://example.com/source",
            "claim": "SMEs still rely on spreadsheets",
            "confidence": 0.55,
        },
    )
    assert create_response.status_code == 201
    evidence = create_response.json()

    list_response = app_client.get(f"/radar/candidates/{candidate['id']}/evidence", headers=auth_headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == evidence["id"]

    delete_response = app_client.delete(f"/radar/evidence/{evidence['id']}", headers=auth_headers)
    assert delete_response.status_code == 204

    list_after_delete = app_client.get(f"/radar/candidates/{candidate['id']}/evidence", headers=auth_headers)
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


def test_radar_apply_logs_endpoint_filters(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "logs-target")

    response = app_client.post(
        "/radar/apply-json",
        headers=auth_headers,
        json={
            "meta": {
                "candidateId": candidate["id"],
                "sourceType": "manual_paste",
            },
            "updates": {
                "summary": "Logged summary",
            },
        },
    )
    assert response.status_code == 201
    apply_log_id = response.json()["apply_log_id"]

    list_response = app_client.get(
        f"/radar/apply-logs?candidate_id={candidate['id']}&status=applied&limit=5",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    logs = list_response.json()
    assert any(item["id"] == apply_log_id for item in logs)

    detail_response = app_client.get(f"/radar/apply-logs/{apply_log_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["candidate_id"] == candidate["id"]


def test_radar_file_imports_endpoints(app_client, auth_headers):
    create_response = app_client.post(
        "/radar/file-imports",
        headers=auth_headers,
        json={
            "filename": "radar_file_imports_test.json",
            "original_path": "data/radar/inbox/radar_file_imports_test.json",
            "file_hash": "abc123",
            "status": "pending",
        },
    )
    assert create_response.status_code == 201
    file_import = create_response.json()
    assert file_import["filename"] == "radar_file_imports_test.json"
    assert file_import["status"] == "pending"

    patch_response = app_client.patch(
        f"/radar/file-imports/{file_import['id']}",
        headers=auth_headers,
        json={
            "status": "failed",
            "stored_path": "data/radar/failed/radar_file_imports_test.json",
            "error_message": "invalid json",
            "payload_summary": {"error": "invalid json"},
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["status"] == "failed"
    assert patched["processed_at"] is not None

    list_response = app_client.get("/radar/file-imports?status=failed&file_hash=abc123&limit=5", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(item["id"] == file_import["id"] for item in list_response.json())

    detail_response = app_client.get(f"/radar/file-imports/{file_import['id']}", headers=auth_headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["error_message"] == "invalid json"


def test_radar_file_imports_reject_invalid_payload(app_client, auth_headers):
    response = app_client.post(
        "/radar/file-imports",
        headers=auth_headers,
        json={
            "filename": "radar_missing_hash.json",
            "status": "processed",
        },
    )
    assert response.status_code == 422


def test_radar_apply_json_accepts_file_watcher_source_type(app_client, auth_headers):
    candidate = create_candidate(app_client, auth_headers, "file-watcher-source")

    response = app_client.post(
        "/radar/apply-json",
        headers=auth_headers,
        json={
            "meta": {
                "candidateId": candidate["id"],
                "sourceType": "file_watcher",
            },
            "updates": {
                "summary": "Imported from local inbox",
            },
        },
    )
    assert response.status_code == 201
    apply_log_id = response.json()["apply_log_id"]

    detail_response = app_client.get(f"/radar/apply-logs/{apply_log_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["source_type"] == "file_watcher"


def seed_portfolio_candidate(app_client, auth_headers, slug: str, patch: dict):
    candidate = create_candidate(app_client, auth_headers, slug)
    response = app_client.patch(
        f"/radar/candidates/{candidate['id']}",
        headers=auth_headers,
        json=patch,
    )
    assert response.status_code == 200
    return response.json()


def test_radar_portfolio_overview_counts_and_flags(app_client, auth_headers):
    advanced = seed_portfolio_candidate(
        app_client,
        auth_headers,
        "portfolio-advanced",
        {
            "verdict": "ADVANCE",
            "focus": "quick_win",
            "scope": "uruguay",
            "maturity": "researched",
            "dominant_risk": "sales_risk",
            "build_level": "standalone_product",
            "gates": {"buyer": "passed"},
        },
    )
    seed_portfolio_candidate(
        app_client,
        auth_headers,
        "portfolio-failed-gates",
        {
            "verdict": "KILL",
            "focus": "moonshot",
            "scope": "global",
            "maturity": "candidate",
            "dominant_risk": "technical_risk",
            "build_level": "agent_workflow",
            "gates": {"data": "failed"},
        },
    )
    seed_portfolio_candidate(
        app_client,
        auth_headers,
        "portfolio-missing-verdict",
        {
            "focus": "quick_win",
            "scope": "latam",
            "maturity": "raw_signal",
            "dominant_risk": "market_risk",
            "build_level": "service_offer",
        },
    )

    evidence_response = app_client.post(
        f"/radar/candidates/{advanced['id']}/evidence",
        headers=auth_headers,
        json={"kind": "interview", "title": "Buyer signal", "claim": "Buyer confirmed urgency."},
    )
    assert evidence_response.status_code == 201

    response = app_client.get("/radar/portfolio/overview", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_candidates"] >= 3
    verdict_counts = {item["value"]: item["count"] for item in payload["count_by_verdict"]}
    assert verdict_counts["ADVANCE"] >= 1
    assert any(item["slug"] == "portfolio-missing-verdict" for item in payload["candidates_without_verdict"])
    assert any(item["slug"] == "portfolio-failed-gates" for item in payload["candidates_with_failed_gates"])


def test_radar_portfolio_matrices_risk_queue_and_compare(app_client, auth_headers):
    first = seed_portfolio_candidate(
        app_client,
        auth_headers,
        "portfolio-compare-one",
        {
            "verdict": "ITERATE",
            "focus": "quick_win",
            "scope": "uruguay",
            "maturity": "candidate",
            "dominant_risk": "market_risk",
            "scorecard": {"market": 7},
            "gates": {"problem": None},
            "decision_memo": "Needs one more data probe.",
        },
    )
    second = seed_portfolio_candidate(
        app_client,
        auth_headers,
        "portfolio-compare-two",
        {
            "verdict": "PARK",
            "focus": "research_bet",
            "scope": "global",
            "maturity": "researched",
            "dominant_risk": "data_risk",
            "scorecard": {"market": 4},
            "gates": {"problem": "passed"},
        },
    )

    focus_scope = app_client.get("/radar/portfolio/matrix/focus-scope", headers=auth_headers)
    assert focus_scope.status_code == 200
    assert any(cell["row"] == "quick_win" and cell["column"] == "uruguay" and cell["count"] >= 1 for cell in focus_scope.json()["cells"])

    maturity_verdict = app_client.get("/radar/portfolio/matrix/maturity-verdict", headers=auth_headers)
    assert maturity_verdict.status_code == 200
    assert any(cell["row"] == "candidate" and cell["column"] == "ITERATE" and cell["count"] >= 1 for cell in maturity_verdict.json()["cells"])

    risks = app_client.get("/radar/portfolio/risk-distribution", headers=auth_headers)
    assert risks.status_code == 200
    assert any(item["dominant_risk"] == "market_risk" and item["count"] >= 1 for item in risks.json())

    queue = app_client.get("/radar/portfolio/selection-queue", headers=auth_headers)
    assert queue.status_code == 200
    queued = {item["slug"]: item["reasons"] for item in queue.json()}
    assert "portfolio-compare-one" in queued
    assert "review_verdict" in queued["portfolio-compare-one"]
    assert "incomplete_gates" in queued["portfolio-compare-one"]

    compare = app_client.post(
        "/radar/portfolio/compare",
        headers=auth_headers,
        json={"candidate_ids": [first["id"], second["id"]]},
    )
    assert compare.status_code == 200
    compared = {item["slug"]: item for item in compare.json()["items"]}
    assert compared["portfolio-compare-one"]["scorecard"]["market"] == 7
    assert compared["portfolio-compare-two"]["verdict"] == "PARK"


def test_radar_portfolio_compare_rejects_missing_candidate(app_client, auth_headers):
    response = app_client.post(
        "/radar/portfolio/compare",
        headers=auth_headers,
        json={"candidate_ids": ["00000000-0000-0000-0000-000000000001"]},
    )
    assert response.status_code == 404
