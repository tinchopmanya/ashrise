from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised through integration paths
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - fallback when dependency is absent
    Langfuse = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PromptDefinition:
    name: str
    source_path: Path | None = None
    fallback_text: str = ""
    labels: tuple[str, ...] = ("production",)
    prompt_type: str = "text"


@dataclass(frozen=True)
class ResolvedPrompt:
    name: str
    prompt_ref: str
    text: str
    source: str
    is_fallback: bool
    client_prompt: Any | None = None


PROMPT_DEFINITIONS: dict[str, PromptDefinition] = {
    "kill-vertical-small-qw@v1": PromptDefinition(
        name="kill-vertical-small-qw@v1",
        source_path=REPO_ROOT / "prompts" / "kill-vertical-small-quickwin.md",
    ),
    "kill-vertical-medium-long@v1": PromptDefinition(
        name="kill-vertical-medium-long@v1",
        source_path=REPO_ROOT / "prompts" / "kill-vertical-saas-v2.md",
    ),
    "kill-vertical-unicorn@v1": PromptDefinition(
        name="kill-vertical-unicorn@v1",
        source_path=REPO_ROOT / "prompts" / "kill-vertical-unicorn.md",
    ),
    "kill-vertical-learning@v1": PromptDefinition(
        name="kill-vertical-learning@v1",
        source_path=REPO_ROOT / "prompts" / "evaluate-learning-vertical.md",
    ),
    "kill-vertical-profound-ai@v1": PromptDefinition(
        name="kill-vertical-profound-ai@v1",
        source_path=REPO_ROOT / "prompts" / "evaluate-profound-ai-experiment.md",
    ),
    "kill-vertical-core-sub@v1": PromptDefinition(
        name="kill-vertical-core-sub@v1",
        source_path=REPO_ROOT / "prompts" / "kill-vertical-core-sub.md",
        fallback_text=(
            "# kill-vertical-core-sub\n\n"
            "**Langfuse ref:** `kill-vertical-core-sub@v1`\n"
            "**Aplica a:** sub-verticales derivadas de un core existente.\n\n"
            "Matar por defecto. La sub-vertical solo sobrevive si muestra un wedge claro, "
            "buyers nombrables y una ventaja concreta frente al producto core."
        ),
    ),
    "auditor-project@v1": PromptDefinition(
        name="auditor-project@v1",
        source_path=REPO_ROOT / "prompts" / "auditor-project.md",
    ),
    "investigator-candidate@v1": PromptDefinition(
        name="investigator-candidate@v1",
        source_path=REPO_ROOT / "prompts" / "investigator-candidate.md",
    ),
}


def prompt_ref(name: str) -> str:
    return f"langfuse:{name}"


def load_prompt_source(definition: PromptDefinition) -> str:
    if definition.source_path and definition.source_path.exists():
        return definition.source_path.read_text(encoding="utf-8").strip()
    return definition.fallback_text.strip()


def get_langfuse_client(*, require_config: bool = False):
    base_url = (os.getenv("LANGFUSE_BASE_URL") or "").strip()
    public_key = (os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.getenv("LANGFUSE_SECRET_KEY") or "").strip()

    if not base_url or not public_key or not secret_key:
        if require_config:
            raise RuntimeError(
                "Langfuse requires LANGFUSE_BASE_URL, LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY"
            )
        return None

    if Langfuse is None:
        if require_config:
            raise RuntimeError("langfuse package is not installed in this environment")
        return None

    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
        tracing_enabled=True,
    )


def resolve_prompt(name: str, client: Any | None = None) -> ResolvedPrompt:
    definition = PROMPT_DEFINITIONS.get(name)
    if definition is None:
        return ResolvedPrompt(
            name=name,
            prompt_ref=prompt_ref(name),
            text="",
            source="custom",
            is_fallback=True,
        )

    fallback_text = load_prompt_source(definition)
    if client is None:
        return ResolvedPrompt(
            name=name,
            prompt_ref=prompt_ref(name),
            text=fallback_text,
            source="repo-local",
            is_fallback=True,
        )

    try:
        client_prompt = client.get_prompt(
            name,
            fallback=fallback_text,
            fetch_timeout_seconds=1,
            max_retries=0,
        )
        return ResolvedPrompt(
            name=name,
            prompt_ref=prompt_ref(name),
            text=getattr(client_prompt, "prompt", fallback_text),
            source="langfuse-fallback" if getattr(client_prompt, "is_fallback", False) else "langfuse",
            is_fallback=bool(getattr(client_prompt, "is_fallback", False)),
            client_prompt=client_prompt,
        )
    except Exception as exc:  # pragma: no cover - protected by integration tests
        return ResolvedPrompt(
            name=name,
            prompt_ref=prompt_ref(name),
            text=fallback_text,
            source=f"repo-local-fallback:{exc}",
            is_fallback=True,
        )


def sync_prompts(client: Any | None = None) -> list[dict[str, Any]]:
    owns_client = client is None
    langfuse_client = client or get_langfuse_client(require_config=True)
    results: list[dict[str, Any]] = []

    try:
        for name, definition in PROMPT_DEFINITIONS.items():
            source_text = load_prompt_source(definition)
            existing = langfuse_client.get_prompt(
                name,
                fallback=source_text,
                fetch_timeout_seconds=1,
                max_retries=0,
            )

            if not getattr(existing, "is_fallback", False) and getattr(existing, "prompt", "") == source_text:
                results.append({"name": name, "status": "unchanged"})
                continue

            langfuse_client.create_prompt(
                name=name,
                prompt=source_text,
                type=definition.prompt_type,
                labels=list(definition.labels),
                commit_message="Ashrise Sprint 5 sync",
            )
            results.append(
                {
                    "name": name,
                    "status": "created" if getattr(existing, "is_fallback", False) else "updated",
                }
            )

        try:
            langfuse_client.flush()
        except Exception:  # pragma: no cover - best effort flush
            pass

        return results
    finally:
        if owns_client and langfuse_client is not None:
            try:
                langfuse_client.flush()
            except Exception:
                pass


def record_agent_trace(
    client: Any | None,
    prompt: ResolvedPrompt,
    *,
    run_id: str,
    target_type: str,
    target_id: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str | None, str | None]:
    if client is None or prompt.client_prompt is None:
        return None, "disabled"

    try:
        trace_id = client.create_trace_id(seed=str(run_id))
        with client.start_as_current_observation(
            name=f"ashrise.agent.{target_type}",
            as_type="generation",
            trace_context={"trace_id": trace_id},
            input=input_payload,
            output=output_payload,
            metadata={
                **metadata,
                "run_id": str(run_id),
                "target_type": target_type,
                "target_id": target_id,
                "prompt_ref": prompt.prompt_ref,
            },
            prompt=prompt.client_prompt,
        ):
            pass
        try:
            client.flush()
        except Exception:
            pass
        return trace_id, None
    except Exception as exc:  # pragma: no cover - network/unavailable integration path
        return None, str(exc)


def record_research_trace(
    client: Any | None,
    *,
    run_id: str,
    target_type: str,
    target_id: str,
    prompt_ref: str | None,
    provider: str,
    operation: str,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    if client is None:
        return None, "disabled"

    try:
        trace_id = client.create_trace_id(seed=str(run_id))
        with client.start_as_current_observation(
            name=f"ashrise.research.{provider}.{operation}",
            as_type="generation",
            trace_context={"trace_id": trace_id},
            input=input_payload,
            output=output_payload,
            metadata={
                **(metadata or {}),
                "component": "research-provider",
                "provider": provider,
                "operation": operation,
                "run_id": str(run_id),
                "target_type": target_type,
                "target_id": target_id,
                "prompt_ref": prompt_ref,
            },
        ):
            pass
        try:
            client.flush()
        except Exception:
            pass
        return trace_id, None
    except Exception as exc:  # pragma: no cover - network/unavailable integration path
        return None, str(exc)
