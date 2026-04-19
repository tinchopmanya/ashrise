from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


def runtime_root(cwd: Path | None = None) -> Path:
    base_dir = (cwd or Path.cwd()).resolve()
    root = base_dir / ".ashrise"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _worktree_hash(cwd: Path | None = None) -> str:
    base_dir = (cwd or Path.cwd()).resolve()
    return hashlib.sha1(base_dir.as_posix().encode("utf-8")).hexdigest()[:10]


def session_file(project_id: str, cwd: Path | None = None) -> Path:
    path = runtime_root(cwd) / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{project_id}-{_worktree_hash(cwd)}.json"


def transcript_file(project_id: str, cwd: Path | None = None) -> Path:
    path = runtime_root(cwd) / "transcripts"
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return path / f"{project_id}-{timestamp}.log"


def telegram_offset_file(cwd: Path | None = None) -> Path:
    return runtime_root(cwd) / "telegram-offset.json"


def save_json(path: Path, payload: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def remove_file(path: Path):
    if path.exists():
        path.unlink()
