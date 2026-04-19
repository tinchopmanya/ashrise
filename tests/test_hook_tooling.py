from pathlib import Path

import pytest

from ashrise_runtime.close_parser import parse_ashrise_close
from ashrise_runtime.hook_cli import perform_session_start, perform_session_stop
from ashrise_runtime.session_store import session_file


class FakeAshriseClient:
    def __init__(self):
        self.created_runs = []
        self.patched_runs = []
        self.state_updates = []
        self.created_handoffs = []
        self.created_decisions = []
        self.state = {
            "project_id": "ashrise",
            "current_focus": "Sprint 2",
            "current_milestone": "Sprint 2",
            "next_step": "Sprint 3",
            "blockers": [{"id": "old-blocker", "reason": "legacy"}],
            "open_questions": ["old-question"],
        }

    def close(self):
        return None

    def create_run(self, payload):
        self.created_runs.append(payload)
        return {
            "id": "run-123",
            "started_at": "2026-04-20T10:00:00+00:00",
            **payload,
        }

    def get_state(self, project_id, allow_404=False):
        return dict(self.state)

    def get_audit(self, project_id):
        return {
            "id": "audit-1",
            "verdict": "keep",
            "summary": "Looks fine",
            "created_at": "2026-04-19T09:00:00+00:00",
        }

    def get_handoffs(self, project_id, status="open"):
        return [{"id": "handoff-1", "to_actor": "codex", "reason": "other", "message": "Ping", "status": status}]

    def patch_run(self, run_id, payload):
        self.patched_runs.append((run_id, payload))
        return {"id": run_id, **payload}

    def put_state(self, project_id, payload):
        self.state_updates.append((project_id, payload))
        self.state.update(payload)
        return dict(self.state)

    def create_handoff(self, payload):
        self.created_handoffs.append(payload)
        return payload

    def create_decision(self, payload):
        self.created_decisions.append(payload)
        return payload


def test_parse_ashrise_close_block():
    text = """
    hello
    ```ashrise-close
    run:
      status: completed
      summary: done
      files_touched: []
      diff_stats:
        added: 1
        removed: 0
        files: 1
      next_step_proposed: next
    state_update:
      current_focus: test
      current_milestone: null
      next_step: next
      blockers_add: []
      blockers_clear: []
      open_questions_add: []
      open_questions_clear: []
    ```
    """
    parsed = parse_ashrise_close(text)
    assert parsed["run"]["status"] == "completed"
    assert parsed["state_update"]["current_focus"] == "test"


def test_perform_session_start_creates_run_and_session_file(tmp_path: Path):
    client = FakeAshriseClient()
    result = perform_session_start("ashrise", cwd=tmp_path, client=client)

    assert result["run"]["id"] == "run-123"
    assert "ashrise_context" in result["context_text"]
    assert session_file("ashrise", tmp_path).exists()
    assert client.created_runs[0]["project_id"] == "ashrise"


def test_perform_session_stop_updates_run_state_handoffs_and_decisions(tmp_path: Path):
    client = FakeAshriseClient()
    perform_session_start("ashrise", cwd=tmp_path, client=client)

    transcript = """
    final output
    ```ashrise-close
    run:
      status: completed
      summary: Sprint 3 done
      files_touched:
        - scripts/ashrise-hook.py
      diff_stats:
        added: 10
        removed: 1
        files: 2
      next_step_proposed: ship it
    state_update:
      current_focus: Sprint 3
      current_milestone: Sprint 3
      next_step: Sprint 4
      blockers_add:
        - id: fresh-blocker
          reason: needs review
      blockers_clear:
        - old-blocker
      open_questions_add:
        - new-question
      open_questions_clear:
        - old-question
    handoffs:
      - to_actor: human:martin
        reason: needs-human-review
        message: revisar release
        context_refs:
          - files:README.md:1
    decisions:
      - title: keep polling
        context: sprint 3
        decision: use polling bot
        consequences: simple setup
        alternatives:
          - title: webhook
            why_rejected: not needed
    ```
    """

    result = perform_session_stop("ashrise", cwd=tmp_path, client=client, text=transcript)

    assert result["run"]["status"] == "completed"
    assert client.patched_runs[0][0] == "run-123"
    state_payload = client.state_updates[0][1]
    assert state_payload["last_run_id"] == "run-123"
    assert state_payload["blockers"] == [{"id": "fresh-blocker", "reason": "needs review"}]
    assert state_payload["open_questions"] == ["new-question"]
    assert client.created_handoffs[0]["project_id"] == "ashrise"
    assert client.created_decisions[0]["title"] == "keep polling"
    assert not session_file("ashrise", tmp_path).exists()


def test_session_stop_requires_close_block(tmp_path: Path):
    client = FakeAshriseClient()
    perform_session_start("ashrise", cwd=tmp_path, client=client)

    with pytest.raises(ValueError):
        perform_session_stop("ashrise", cwd=tmp_path, client=client, text="missing block")
