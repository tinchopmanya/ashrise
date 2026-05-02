import json

from ashrise_runtime.radar_watcher import RadarWatcherSettings, process_file


class FakeRadarWatcherClient:
    def __init__(self, *, previous_imports=None, apply_error: Exception | None = None):
        self.previous_imports = previous_imports or []
        self.apply_error = apply_error
        self.created = []
        self.patched = []
        self.applied_payloads = []

    def find_imports_by_hash(self, file_hash):
        return self.previous_imports

    def create_file_import(self, payload):
        item = {"id": f"import-{len(self.created) + 1}", **payload}
        self.created.append(item)
        return item

    def patch_file_import(self, file_import_id, payload):
        item = {"id": file_import_id, **payload}
        self.patched.append(item)
        return item

    def apply_json(self, payload):
        self.applied_payloads.append(payload)
        if self.apply_error is not None:
            raise self.apply_error
        return {
            "ok": True,
            "mode": "update",
            "candidate_id": payload.get("meta", {}).get("candidateId"),
            "prompt_run_id": payload.get("meta", {}).get("promptRunId"),
            "apply_log_id": "apply-log-1",
            "updates_applied": ["summary"],
            "evidence_created": 0,
        }


def make_settings(tmp_path):
    return RadarWatcherSettings(
        watch_dir=tmp_path / "inbox",
        processed_dir=tmp_path / "processed",
        failed_dir=tmp_path / "failed",
        base_url="http://localhost:8080",
        token="dev-token",
        poll_interval=0.01,
    )


def test_radar_watcher_processes_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr("ashrise_runtime.radar_watcher.wait_until_stable", lambda path: None)
    settings = make_settings(tmp_path)
    settings.watch_dir.mkdir(parents=True)
    payload = {
        "meta": {"candidateId": "candidate-1", "promptRunId": "prompt-run-1"},
        "updates": {"summary": "from file"},
    }
    source = settings.watch_dir / "radar_valid.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    client = FakeRadarWatcherClient()

    result = process_file(source, settings=settings, client=client)

    assert result.status == "processed"
    assert result.destination is not None
    assert result.destination.parent == settings.processed_dir
    assert not source.exists()
    assert client.applied_payloads[0]["meta"]["sourceType"] == "file_watcher"
    assert client.patched[0]["status"] == "processed"
    assert client.patched[0]["apply_log_id"] == "apply-log-1"


def test_radar_watcher_invalid_json_goes_to_failed(tmp_path, monkeypatch):
    monkeypatch.setattr("ashrise_runtime.radar_watcher.wait_until_stable", lambda path: None)
    settings = make_settings(tmp_path)
    settings.watch_dir.mkdir(parents=True)
    source = settings.watch_dir / "radar_invalid.json"
    source.write_text("{not valid", encoding="utf-8")
    client = FakeRadarWatcherClient()

    result = process_file(source, settings=settings, client=client)

    assert result.status == "failed"
    assert result.destination is not None
    assert result.destination.parent == settings.failed_dir
    assert client.patched[0]["status"] == "failed"
    assert client.applied_payloads == []


def test_radar_watcher_ignores_non_radar_files(tmp_path, monkeypatch):
    monkeypatch.setattr("ashrise_runtime.radar_watcher.wait_until_stable", lambda path: None)
    settings = make_settings(tmp_path)
    settings.watch_dir.mkdir(parents=True)
    source = settings.watch_dir / "notes.json"
    source.write_text("{}", encoding="utf-8")
    client = FakeRadarWatcherClient()

    result = process_file(source, settings=settings, client=client)

    assert result.status == "ignored"
    assert source.exists()
    assert client.created == []


def test_radar_watcher_duplicate_hash_moves_to_processed(tmp_path, monkeypatch):
    monkeypatch.setattr("ashrise_runtime.radar_watcher.wait_until_stable", lambda path: None)
    settings = make_settings(tmp_path)
    settings.watch_dir.mkdir(parents=True)
    source = settings.watch_dir / "radar_duplicate.json"
    source.write_text(json.dumps({"meta": {"candidateId": "candidate-1"}, "updates": {"summary": "dup"}}), encoding="utf-8")
    client = FakeRadarWatcherClient(previous_imports=[{"id": "existing-import", "status": "processed"}])

    result = process_file(source, settings=settings, client=client)

    assert result.status == "duplicate"
    assert result.destination is not None
    assert result.destination.parent == settings.processed_dir
    assert client.created[0]["status"] == "duplicate"
    assert client.created[0]["payload_summary"]["duplicate_of"] == "existing-import"
    assert client.applied_payloads == []
