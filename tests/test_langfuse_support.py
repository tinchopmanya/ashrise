from ashrise.langfuse_support import PROMPT_DEFINITIONS, resolve_prompt, sync_prompts


class _FakePrompt:
    def __init__(self, prompt: str, *, is_fallback: bool):
        self.prompt = prompt
        self.is_fallback = is_fallback


class _FakeLangfuseClient:
    def __init__(self):
        self.created: list[str] = []

    def get_prompt(self, name, label=None, fallback=None, fetch_timeout_seconds=None, max_retries=None):
        return _FakePrompt(fallback or "", is_fallback=True)

    def create_prompt(self, name, prompt, type="text", labels=None, commit_message=None):
        self.created.append(name)

    def flush(self):
        return None


def test_resolve_prompt_falls_back_to_repo_local_without_langfuse_env(monkeypatch):
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    prompt = resolve_prompt("auditor-project@v1", client=None)
    assert prompt.prompt_ref == "langfuse:auditor-project@v1"
    assert prompt.source == "repo-local"
    assert "auditor-project" in prompt.text


def test_sync_prompts_registers_all_critical_prompts():
    client = _FakeLangfuseClient()
    results = sync_prompts(client)

    assert len(results) == len(PROMPT_DEFINITIONS)
    assert set(client.created) == set(PROMPT_DEFINITIONS)
