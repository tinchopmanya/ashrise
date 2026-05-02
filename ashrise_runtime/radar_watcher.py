from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any

import httpx


LOGGER = logging.getLogger("ashrise.radar_watcher")
MAX_FILE_BYTES = 5 * 1024 * 1024
STABLE_CHECK_SECONDS = 0.6


@dataclass(frozen=True)
class RadarWatcherSettings:
    watch_dir: Path
    processed_dir: Path
    failed_dir: Path
    base_url: str
    token: str
    poll_interval: float = 2.0
    max_file_bytes: int = MAX_FILE_BYTES

    @classmethod
    def from_env(cls) -> "RadarWatcherSettings":
        repo_root = Path(__file__).resolve().parents[1]
        watch_dir = Path(os.getenv("RADAR_WATCH_DIR") or repo_root / "data" / "radar" / "inbox")
        processed_dir = Path(os.getenv("RADAR_PROCESSED_DIR") or repo_root / "data" / "radar" / "processed")
        failed_dir = Path(os.getenv("RADAR_FAILED_DIR") or repo_root / "data" / "radar" / "failed")
        base_url = os.getenv("ASHRISE_BASE_URL", "http://localhost:8080").rstrip("/")
        token = os.getenv("ASHRISE_TOKEN", "dev-token")
        poll_interval = float(os.getenv("RADAR_WATCH_POLL_SECONDS", "2"))
        return cls(
            watch_dir=watch_dir,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
            base_url=base_url,
            token=token,
            poll_interval=poll_interval,
        )


@dataclass(frozen=True)
class ProcessResult:
    status: str
    filename: str
    destination: Path | None
    apply_log_id: str | None = None
    file_import_id: str | None = None
    error_message: str | None = None


class RadarWatcherClient:
    def __init__(self, base_url: str, token: str, client: httpx.Client | None = None):
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "RadarWatcherClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def request(self, method: str, path: str, **kwargs) -> Any:
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            detail = response.text
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict) and payload.get("detail") is not None:
                detail = json.dumps(payload["detail"], ensure_ascii=False)
            raise RuntimeError(f"{method} {path} failed: HTTP {response.status_code}: {detail}")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def find_imports_by_hash(self, file_hash: str) -> list[dict[str, Any]]:
        return self.request("GET", "/radar/file-imports", params={"file_hash": file_hash, "limit": 100})

    def create_file_import(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/radar/file-imports", json=payload)

    def patch_file_import(self, file_import_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", f"/radar/file-imports/{file_import_id}", json=payload)

    def apply_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/radar/apply-json", json=payload)


def ensure_directories(settings: RadarWatcherSettings) -> None:
    for path in (settings.watch_dir, settings.processed_dir, settings.failed_dir):
        path.mkdir(parents=True, exist_ok=True)


def is_radar_json_candidate(path: Path) -> bool:
    return path.is_file() and not path.is_symlink() and path.name.startswith("radar_") and path.suffix.lower() == ".json"


def wait_until_stable(path: Path, delay_seconds: float = STABLE_CHECK_SECONDS) -> None:
    first_size = path.stat().st_size
    time.sleep(delay_seconds)
    second_size = path.stat().st_size
    if first_size != second_size:
        raise RuntimeError("file is still being written")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(1, 1000):
        next_candidate = directory / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise RuntimeError(f"cannot allocate destination for {filename}")


def move_file(path: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(destination_dir, path.name)
    shutil.move(str(path), str(destination))
    return destination


def with_file_watcher_source(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    if next_payload.get("_radar_export") is True and isinstance(next_payload.get("data"), dict):
        data = dict(next_payload["data"])
        meta = data.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        else:
            meta = dict(meta)
        meta.setdefault("sourceType", "file_watcher")
        data["meta"] = meta
        next_payload["data"] = data
        return next_payload

    meta = next_payload.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    else:
        meta = dict(meta)
    meta.setdefault("sourceType", "file_watcher")
    next_payload["meta"] = meta
    return next_payload


def payload_summary(payload: dict[str, Any], apply_result: dict[str, Any] | None = None) -> dict[str, Any]:
    working_payload = payload.get("data") if payload.get("_radar_export") is True and isinstance(payload.get("data"), dict) else payload
    meta = working_payload.get("meta") if isinstance(working_payload.get("meta"), dict) else {}
    return {
        "entity": payload.get("_entity"),
        "candidate_id": meta.get("candidateId") or meta.get("candidate_id") or (apply_result or {}).get("candidate_id"),
        "prompt_run_id": meta.get("promptRunId") or meta.get("prompt_run_id") or (apply_result or {}).get("prompt_run_id"),
        "mode": (apply_result or {}).get("mode"),
        "updates_applied": (apply_result or {}).get("updates_applied", []),
        "evidence_created": (apply_result or {}).get("evidence_created"),
    }


def register_failed_import(
    *,
    client: RadarWatcherClient,
    path: Path,
    file_hash: str,
    error_message: str,
    failed_path: Path,
    file_import_id: str | None,
) -> dict[str, Any]:
    payload = {
        "status": "failed",
        "stored_path": str(failed_path),
        "error_message": error_message[:2000],
        "payload_summary": {"error": error_message[:500]},
    }
    if file_import_id:
        return client.patch_file_import(file_import_id, payload)
    return client.create_file_import(
        {
            "filename": path.name,
            "original_path": str(path),
            "stored_path": str(failed_path),
            "file_hash": file_hash,
            **payload,
        }
    )


def process_file(path: Path, *, settings: RadarWatcherSettings, client: RadarWatcherClient) -> ProcessResult:
    if not is_radar_json_candidate(path):
        return ProcessResult(status="ignored", filename=path.name, destination=None)
    if not path.resolve().is_relative_to(settings.watch_dir.resolve()):
        return ProcessResult(status="ignored", filename=path.name, destination=None, error_message="outside watch dir")

    file_import_id: str | None = None
    file_hash = ""
    try:
        wait_until_stable(path)
        file_size = path.stat().st_size
        if file_size > settings.max_file_bytes:
            raise RuntimeError(f"file exceeds max size {settings.max_file_bytes} bytes")

        file_hash = file_sha256(path)
        previous_imports = [
            item for item in client.find_imports_by_hash(file_hash) if item.get("status") in {"processed", "duplicate"}
        ]
        if previous_imports:
            duplicate_path = move_file(path, settings.processed_dir)
            duplicate = client.create_file_import(
                {
                    "filename": path.name,
                    "original_path": str(path),
                    "stored_path": str(duplicate_path),
                    "file_hash": file_hash,
                    "status": "duplicate",
                    "payload_summary": {"duplicate_of": previous_imports[0]["id"]},
                }
            )
            return ProcessResult(
                status="duplicate",
                filename=path.name,
                destination=duplicate_path,
                file_import_id=duplicate["id"],
            )

        pending = client.create_file_import(
            {
                "filename": path.name,
                "original_path": str(path),
                "file_hash": file_hash,
                "status": "pending",
            }
        )
        file_import_id = pending["id"]

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise RuntimeError("Radar JSON file must contain a JSON object")
        payload = with_file_watcher_source(payload)
        apply_result = client.apply_json(payload)
        processed_path = move_file(path, settings.processed_dir)
        updated = client.patch_file_import(
            file_import_id,
            {
                "status": "processed",
                "stored_path": str(processed_path),
                "apply_log_id": apply_result.get("apply_log_id"),
                "payload_summary": payload_summary(payload, apply_result),
            },
        )
        return ProcessResult(
            status="processed",
            filename=path.name,
            destination=processed_path,
            apply_log_id=updated.get("apply_log_id"),
            file_import_id=updated["id"],
        )
    except Exception as exc:
        error_message = str(exc)
        LOGGER.exception("Radar watcher failed to process %s: %s", path, error_message)
        failed_path = path
        if path.exists():
            try:
                failed_path = move_file(path, settings.failed_dir)
            except Exception as move_exc:
                error_message = f"{error_message}; also failed to move file: {move_exc}"
        if not file_hash and failed_path.exists():
            try:
                file_hash = file_sha256(failed_path)
            except Exception:
                file_hash = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
        try:
            file_import = register_failed_import(
                client=client,
                path=path,
                file_hash=file_hash or hashlib.sha256(str(path).encode("utf-8")).hexdigest(),
                error_message=error_message,
                failed_path=failed_path,
                file_import_id=file_import_id,
            )
            file_import_id = file_import["id"]
        except Exception:
            LOGGER.exception("Radar watcher failed to register failed import for %s", path)
        return ProcessResult(
            status="failed",
            filename=path.name,
            destination=failed_path,
            file_import_id=file_import_id,
            error_message=error_message,
        )


def iter_inbox_files(watch_dir: Path) -> list[Path]:
    return sorted(path for path in watch_dir.iterdir() if is_radar_json_candidate(path))


def run_once(settings: RadarWatcherSettings, client: RadarWatcherClient) -> list[ProcessResult]:
    ensure_directories(settings)
    results: list[ProcessResult] = []
    for path in iter_inbox_files(settings.watch_dir):
        result = process_file(path, settings=settings, client=client)
        if result.status != "ignored":
            LOGGER.info("Radar file %s -> %s", result.filename, result.status)
        results.append(result)
    return results


def run_forever(settings: RadarWatcherSettings) -> None:
    ensure_directories(settings)
    with RadarWatcherClient(settings.base_url, settings.token) as client:
        LOGGER.info("Watching Radar inbox: %s", settings.watch_dir)
        while True:
            run_once(settings, client)
            time.sleep(settings.poll_interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process radar_*.json files from the local Radar inbox.")
    parser.add_argument("--once", action="store_true", help="Process current inbox once and exit.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = RadarWatcherSettings.from_env()
    if args.once:
        with RadarWatcherClient(settings.base_url, settings.token) as client:
            results = run_once(settings, client)
        for result in results:
            print(f"{result.filename}: {result.status}")
        return 0
    run_forever(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
