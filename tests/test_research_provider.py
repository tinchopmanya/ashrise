from __future__ import annotations

from contextlib import contextmanager

import httpx

from ashrise.research import assess_stack, check_ai_encroachment, find_competitors, research_trace_context, web_search


def _fake_brave_search(query, recency_days, settings):
    normalized = query.lower()
    if "competitors software" in normalized:
        return [
            {
                "title": "Veritrade procurement intelligence",
                "url": "https://veritradecorp.com/licitaciones",
                "snippet": "Veritrade ofrece monitoreo regional de procurement y comercio exterior.",
                "published_days_ago": 4,
                "provider": "brave",
                "fallback": False,
                "query": query,
            },
            {
                "title": "Smartdata procurement monitoring",
                "url": "https://smartdata.example/procurement",
                "snippet": "SmartDATA cubre alertas y analitica para licitaciones publicas.",
                "published_days_ago": 7,
                "provider": "brave",
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
                "provider": "brave",
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
                "provider": "brave",
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
            "provider": "brave",
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


def test_research_provider_uses_brave_when_configured(monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "brave")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "brave-test-key")
    monkeypatch.setattr("ashrise.research._brave_web_search", _fake_brave_search)

    search = web_search("procurement licitaciones uruguay")
    competitors = find_competitors("procurement licitaciones uruguay")
    encroachment = check_ai_encroachment("procurement licitaciones uruguay")
    stack = assess_stack(["FastAPI"])

    assert search[0]["provider"] == "brave"
    assert search[0]["fallback"] is False
    assert competitors[0]["provider"] == "brave"
    assert competitors[0]["name"] == "Veritrade Procurement Intelligence"
    assert encroachment["provider"] == "brave"
    assert encroachment["risk_level"] == "high"
    assert stack[0]["provider"] == "brave"
    assert stack[0]["fallback"] is False


def test_research_trace_context_records_langfuse_metadata(monkeypatch):
    fake_client = _FakeLangfuseClient()
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "brave")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "brave-test-key")
    monkeypatch.setattr("ashrise.research._brave_web_search", _fake_brave_search)
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
    assert metadata["provider"] == "brave"
    assert metadata["operation"] == "web_search"


def test_agent_run_falls_back_to_stub_when_real_provider_fails(app_client, auth_headers, monkeypatch):
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "brave")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "brave-test-key")

    def _boom(query, recency_days, settings):
        raise httpx.ConnectError("provider unavailable")

    monkeypatch.setattr("ashrise.research._brave_web_search", _boom)

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
    monkeypatch.setenv("ASHRISE_RESEARCH_PROVIDER", "brave")
    monkeypatch.setenv("ASHRISE_RESEARCH_API_KEY", "brave-real-key")
    monkeypatch.setenv("ASHRISE_TOKEN", "super-secret-token")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-local-secret")

    def _boom(query, recency_days, settings):
        raise RuntimeError(
            "provider unavailable Authorization: Bearer super-secret-token "
            "X-Subscription-Token=brave-real-key secret_key=sk-lf-local-secret"
        )

    monkeypatch.setattr("ashrise.research._brave_web_search", _boom)

    response = app_client.post(
        "/agent/run",
        headers=auth_headers,
        json={"target_type": "project", "target_id": "procurement-licitaciones"},
    )
    assert response.status_code == 200
    reason = response.json()["report"]["metadata"]["research_fallback_reason"]

    assert "[REDACTED]" in reason
    assert "super-secret-token" not in reason
    assert "brave-real-key" not in reason
    assert "sk-lf-local-secret" not in reason
