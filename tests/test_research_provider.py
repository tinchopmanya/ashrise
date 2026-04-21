from __future__ import annotations

from contextlib import contextmanager

import httpx

from ashrise.research import (
    ResearchSettings,
    _tavily_search,
    assess_stack,
    check_ai_encroachment,
    find_competitors,
    research_trace_context,
    web_search,
)


def _fake_tavily_search(query, recency_days, settings):
    normalized = query.lower()
    if "competitors software" in normalized:
        return [
            {
                "title": "Veritrade procurement intelligence",
                "url": "https://veritradecorp.com/licitaciones",
                "snippet": "Veritrade ofrece monitoreo regional de procurement y comercio exterior.",
                "published_days_ago": 4,
                "provider": "tavily",
                "fallback": False,
                "query": query,
            },
            {
                "title": "Smartdata procurement monitoring",
                "url": "https://smartdata.example/procurement",
                "snippet": "SmartDATA cubre alertas y analitica para licitaciones publicas.",
                "published_days_ago": 7,
                "provider": "tavily",
                "fallback": False,
                "query": query,
            },
        ]
    if "ai automation llm" in normalized:
        return [
            {
                "title": "AI copilots for procurement teams",
                "url": "https://ai-tools.example/copilots",
                "snippet": "AI automation and LLM copilots already summarize procurement workflows.",
                "published_days_ago": 2,
                "provider": "tavily",
                "fallback": False,
                "query": query,
            }
        ]
    if "roadmap adoption stability deprecation" in normalized:
        tech = query.split(" roadmap", 1)[0]
        return [
            {
                "title": f"{tech} adoption remains stable",
                "url": f"https://example.com/{tech.lower()}",
                "snippet": f"{tech} keeps stable adoption with active maintenance and no deprecation notice.",
                "published_days_ago": 10,
                "provider": "tavily",
                "fallback": False,
                "query": query,
            }
        ]
    return [
        {
            "title": "Procurement intelligence market keeps moving",
            "url": "https://market.example/procurement",
            "snippet": "Regional procurement intelligence still shows manual workflows and room for specialized tooling.",
            "published_days_ago": 5,
            "provider": "tavily",
            "fallback": False,
            "query": query,
        }
    ]


class _FakeObservation:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeLangfuseClient:
    def __init__(self):
        self.observations = []

    def create_trace_id(self, seed):
        return f"trace-{seed}"

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        self.observations.append(kwargs)
        yield _FakeObservation()

    def flush(self):
        return None


class _FakeTavilyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_research_provider_uses_tavily_when_configured(monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-test-key")
    monkeypatch.setattr("ashrise.research._tavily_search", _fake_tavily_search)

    search = web_search("procurement licitaciones uruguay")
    competitors = find_competitors("procurement licitaciones uruguay")
    encroachment = check_ai_encroachment("procurement licitaciones uruguay")
    stack = assess_stack(["FastAPI"])

    assert search[0]["provider"] == "tavily"
    assert search[0]["fallback"] is False
    assert competitors[0]["provider"] == "tavily"
    assert competitors[0]["name"] == "Veritrade Procurement Intelligence"
    assert encroachment["provider"] == "tavily"
    assert encroachment["risk_level"] == "high"
    assert stack[0]["provider"] == "tavily"
    assert stack[0]["fallback"] is False


def test_tavily_search_sends_bearer_and_optional_project_id(monkeypatch):
    captured = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeTavilyResponse(
                {
                    "results": [
                        {
                            "title": "Procurement intelligence in LATAM",
                            "url": "https://example.com/procurement",
                            "content": "Procurement intelligence remains active in LATAM.",
                            "published_date": "2026-04-18T12:00:00Z",
                            "score": 0.91,
                        }
                    ]
                }
            )

    monkeypatch.setattr("ashrise.research.httpx.Client", _FakeClient)

    settings = ResearchSettings(
        provider="tavily",
        base_url="https://api.tavily.com",
        api_key="tvly-test-key",
        project_id="ashrise-dev",
        timeout=5.0,
        region="LATAM",
        country="UY",
        search_lang="es",
    )

    results = _tavily_search("procurement licitaciones uruguay", 7, settings)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"]["Authorization"] == "Bearer tvly-test-key"
    assert captured["headers"]["X-Project-ID"] == "ashrise-dev"
    assert captured["json"]["query"] == "procurement licitaciones uruguay"
    assert captured["json"]["time_range"] == "week"
    assert captured["json"]["country"] == "uruguay"
    assert captured["json"]["search_depth"] == "basic"
    assert captured["json"]["include_answer"] is False
    assert results[0]["provider"] == "tavily"
    assert results[0]["fallback"] is False


def test_research_trace_context_records_langfuse_metadata(monkeypatch):
    fake_client = _FakeLangfuseClient()
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-test-key")
    monkeypatch.setenv("ASHRISE_RESEARCH_PROJECT_ID", "ashrise-dev")
    monkeypatch.setattr("ashrise.research._tavily_search", _fake_tavily_search)
    monkeypatch.setattr("ashrise.research.get_langfuse_client", lambda: fake_client)

    with research_trace_context(
        run_id="run-123",
        target_type="project",
        target_id="procurement-core",
        prompt_ref="langfuse:auditor-project@v1",
    ):
        web_search("procurement licitaciones uruguay")

    assert len(fake_client.observations) == 1
    metadata = fake_client.observations[0]["metadata"]
    assert metadata["run_id"] == "run-123"
    assert metadata["target_type"] == "project"
    assert metadata["target_id"] == "procurement-core"
    assert metadata["prompt_ref"] == "langfuse:auditor-project@v1"
    assert metadata["provider"] == "tavily"
    assert metadata["operation"] == "web_search"
    assert metadata["provider_project_id"] == "ashrise-dev"


def test_web_search_falls_back_to_stub_when_tavily_fails(monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-test-key")

    def _boom(query, recency_days, settings):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("ashrise.research._tavily_search", _boom)

    results = web_search("procurement licitaciones uruguay")

    assert results[0]["provider"] == "stub"
    assert results[0]["fallback"] is True
    assert "provider unavailable" in results[0]["fallback_reason"]


def test_web_search_redacts_secrets_when_tavily_fails(monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-real-key")
    monkeypatch.setenv("ASHRISE_TOKEN", "super-secret-token")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-local-secret")

    def _boom(query, recency_days, settings):
        raise RuntimeError(
            "provider unavailable Authorization: Bearer super-secret-token "
            "api_key=tvly-real-key secret_key=sk-lf-local-secret"
        )

    monkeypatch.setattr("ashrise.research._tavily_search", _boom)

    results = web_search("procurement licitaciones uruguay")
    reason = results[0]["fallback_reason"]

    assert "[REDACTED]" in reason
    assert "super-secret-token" not in reason
    assert "tvly-real-key" not in reason
    assert "sk-lf-local-secret" not in reason


def test_agent_run_falls_back_to_stub_when_tavily_fails(app_client, auth_headers, monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-test-key")

    def _boom(query, recency_days, settings):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("ashrise.research._tavily_search", _boom)

    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["report"]["metadata"]["research_provider"] == "stub"
    assert payload["report"]["metadata"]["research_fallback"] is True
    assert "provider unavailable" in payload["report"]["metadata"]["research_fallback_reason"]


def test_agent_run_redacts_secrets_in_research_fallback_metadata(app_client, auth_headers, monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-real-key")
    monkeypatch.setenv("ASHRISE_RESEARCH_PROJECT_ID", "ashrise-dev")
    monkeypatch.setenv("ASHRISE_TOKEN", "super-secret-token")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-local-secret")

    def _boom(query, recency_days, settings):
        raise RuntimeError(
            "provider unavailable Authorization: Bearer super-secret-token "
            "api_key=tvly-real-key X-Project-ID=ashrise-dev secret_key=sk-lf-local-secret"
        )

    monkeypatch.setattr("ashrise.research._tavily_search", _boom)

    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    reason = response.json()["report"]["metadata"]["research_fallback_reason"]

    assert "[REDACTED]" in reason
    assert "super-secret-token" not in reason
    assert "tvly-real-key" not in reason
    assert "sk-lf-local-secret" not in reason
    assert "ashrise-dev" in reason


def test_agent_run_persists_tavily_when_provider_returns_results_after_query_simplification(
    app_client,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-test-key")

    def _fake_search_with_empty_noisy_query(query, recency_days, settings):
        normalized = query.lower()
        if any(token in normalized for token in ("mvp", "demostrable", "pulido")):
            return []
        return _fake_tavily_search(query, recency_days, settings)

    monkeypatch.setattr("ashrise.research._tavily_search", _fake_search_with_empty_noisy_query)

    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["report"]["metadata"]["research_provider"] == "tavily"
    assert payload["report"]["metadata"]["research_fallback"] is False
    assert payload["report"]["metadata"]["research_fallback_reason"] is None
    assert payload["report"]["evidence_refs"][0]["provider"] == "tavily"


def test_agent_run_sets_fallback_reason_when_provider_returns_empty_results(
    app_client,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "tvly-test-key")
    monkeypatch.setattr("ashrise.research._tavily_search", lambda query, recency_days, settings: [])

    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["report"]["metadata"]["research_provider"] == "stub"
    assert payload["report"]["metadata"]["research_fallback"] is True
    assert "no devolvio resultados utiles" in payload["report"]["metadata"]["research_fallback_reason"]
