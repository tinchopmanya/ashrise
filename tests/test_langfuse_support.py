from ashrise.langfuse_support import (
    PROMPT_DEFINITIONS,
    resolve_langfuse_base_url,
    resolve_prompt,
    runtime_prompt_label,
    sync_prompts,
)


class _FakePrompt:
    def __init__(self, name: str, prompt: str, *, version: int = 0, labels=None, is_fallback: bool):
        self.name = name
        self.prompt = prompt
        self.version = version
        self.labels = list(labels or [])
        self.is_fallback = is_fallback


class _FakeLangfuseClient:
    def __init__(self):
        self.created: list[str] = []
        self.updated: list[tuple[str, int, list[str]]] = []
        self.prompts: dict[str, list[_FakePrompt]] = {}

    def get_prompt(self, name, label=None, fallback=None, fetch_timeout_seconds=None, max_retries=None):
        effective_label = label or "production"
        versions = self.prompts.get(name, [])
        selected = None
        if effective_label == "latest" and versions:
            selected = versions[-1]
        else:
            for prompt in versions:
                if effective_label in prompt.labels:
                    selected = prompt
                    break

        if selected is not None:
            return _FakePrompt(
                selected.name,
                selected.prompt,
                version=selected.version,
                labels=selected.labels,
                is_fallback=False,
            )

        return _FakePrompt(
            name,
            fallback or "",
            version=0,
            labels=[effective_label] if label else [],
            is_fallback=True,
        )

    def create_prompt(self, name, prompt, type="text", labels=None, commit_message=None):
        self.created.append(name)
        versions = self.prompts.setdefault(name, [])
        for existing in versions:
            existing.labels = [item for item in existing.labels if item != "latest"]
        version = len(versions) + 1
        versions.append(_FakePrompt(name, prompt, version=version, labels=[*(labels or []), "latest"], is_fallback=False))

    def update_prompt(self, name, version, new_labels=None):
        self.updated.append((name, version, list(new_labels or [])))
        versions = self.prompts.get(name, [])
        for existing in versions:
            if existing.version != version:
                existing.labels = [item for item in existing.labels if item not in set(new_labels or [])]
        for existing in versions:
            if existing.version == version:
                existing.labels = sorted(set(existing.labels) | set(new_labels or []))
                return existing
        raise AssertionError(f"Prompt {name}@{version} not found")

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


def test_resolve_prompt_uses_production_label():
    client = _FakeLangfuseClient()
    client.create_prompt(
        name="auditor-project@v1",
        prompt="prompt from langfuse",
        labels=["production"],
    )

    prompt = resolve_prompt("auditor-project@v1", client=client)

    assert prompt.source == "langfuse"
    assert prompt.is_fallback is False
    assert prompt.text == "prompt from langfuse"


def test_sync_prompts_relabels_latest_prompt_when_runtime_label_is_missing():
    client = _FakeLangfuseClient()
    definition = PROMPT_DEFINITIONS["auditor-project@v1"]
    source_text = definition.source_path.read_text(encoding="utf-8").strip()
    client.create_prompt(
        name="auditor-project@v1",
        prompt=source_text,
        labels=[],
    )
    client.prompts["auditor-project@v1"][0].labels = ["latest"]

    results = sync_prompts(client)

    assert {"name": "auditor-project@v1", "status": "relabeled"} in results
    assert ("auditor-project@v1", 1, [runtime_prompt_label(definition)]) in client.updated
    prompt = resolve_prompt("auditor-project@v1", client=client)
    assert prompt.source == "langfuse"
    assert prompt.is_fallback is False


def test_resolve_langfuse_base_url_rewrites_localhost_inside_docker(monkeypatch):
    monkeypatch.setenv("ASHRISE_DOCKER", "1")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")

    assert resolve_langfuse_base_url() == "http://langfuse-web:3000"


def test_resolve_langfuse_base_url_keeps_explicit_remote_host(monkeypatch):
    monkeypatch.setenv("ASHRISE_DOCKER", "1")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://langfuse.ts.net:3000")

    assert resolve_langfuse_base_url() == "http://langfuse.ts.net:3000"
