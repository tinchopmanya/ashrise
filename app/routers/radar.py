from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
import psycopg
from psycopg import sql

from app.auth import require_bearer_token
from app.db import fetch_all, fetch_one, get_db, insert_row, update_row
from app.schemas import (
    RadarCandidateCreate,
    RadarCandidatePatch,
    RadarConfigPut,
    RadarEvidenceCreate,
    RadarFileImportCreate,
    RadarFileImportPatch,
    RadarPortfolioCompareRequest,
    RadarPromptCreate,
    RadarPromptPatch,
    RadarPromptRender,
    RadarPromptRunPatch,
    RadarPromptVersionCreate,
    RadarSignalCreate,
    RadarSignalPatch,
)


router = APIRouter(prefix="/radar", tags=["radar"], dependencies=[Depends(require_bearer_token)])

ALLOWED_EXPORT_ENTITIES = {"candidates", "evidence", "signals", "prompts", "goldenSet", "config", "multi"}
ALLOWED_SOURCE_TYPES = {"manual_paste", "drag_drop", "api", "file_watcher", "unknown"}
RADAR_REVIEW_VERDICTS = {"ITERATE", "RESEARCH_MORE"}
RADAR_REVIEW_MATURITIES = {"raw_signal", "candidate", "researched"}
RADAR_PROMPT_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_\.]+)\s*}}")
RADAR_CANDIDATE_MUTABLE_FIELDS = {
    "slug",
    "name",
    "summary",
    "hypothesis",
    "focus",
    "scope",
    "maturity",
    "build_level",
    "time_horizon",
    "expected_return",
    "dominant_risk",
    "validation_mode",
    "evidence_requirement",
    "buyer_type",
    "preferred_channel",
    "initial_strategy",
    "scorecard",
    "gates",
    "decision_memo",
    "next_research",
    "kill_criteria",
    "verdict",
    "priority",
    "notes",
    "metadata",
}
RADAR_CANDIDATE_UPDATE_ALIASES = {
    "buildLevel": "build_level",
    "timeHorizon": "time_horizon",
    "expectedReturn": "expected_return",
    "dominantRisk": "dominant_risk",
    "validationMode": "validation_mode",
    "evidenceRequirement": "evidence_requirement",
    "buyerType": "buyer_type",
    "preferredChannel": "preferred_channel",
    "initialStrategy": "initial_strategy",
    "decisionMemo": "decision_memo",
    "nextResearch": "next_research",
    "killCriteria": "kill_criteria",
}


def serialize_radar_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "scorecard": row.get("scorecard") or {},
        "gates": row.get("gates") or {},
        "next_research": row.get("next_research") or {},
        "kill_criteria": row.get("kill_criteria") or {},
        "metadata": row.get("metadata") or {},
    }


def serialize_radar_signal(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
        "tags": row.get("tags") or [],
        "raw_payload": row.get("raw_payload") or None,
        "metadata": row.get("metadata") or {},
    }


def serialize_radar_prompt(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "metadata": row.get("metadata") or {},
    }


def serialize_radar_prompt_version(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "prompt_id": str(row["prompt_id"]),
        "output_schema": row.get("output_schema") or {},
        "variables_schema": row.get("variables_schema") or {},
        "metadata": row.get("metadata") or {},
    }


def serialize_radar_prompt_run(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "prompt_id": str(row["prompt_id"]),
        "prompt_version_id": str(row["prompt_version_id"]),
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
        "apply_log_id": str(row["apply_log_id"]) if row.get("apply_log_id") is not None else None,
    }


def serialize_radar_apply_log(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "candidate_id": str(row["candidate_id"]) if row.get("candidate_id") is not None else None,
        "prompt_id": str(row["prompt_id"]) if row.get("prompt_id") is not None else None,
        "prompt_version_id": str(row["prompt_version_id"]) if row.get("prompt_version_id") is not None else None,
        "json_payload": row.get("json_payload") or {},
        "applied_changes": row.get("applied_changes") or {},
    }


def serialize_radar_file_import(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "apply_log_id": str(row["apply_log_id"]) if row.get("apply_log_id") is not None else None,
        "payload_summary": row.get("payload_summary") or None,
    }


def serialize_radar_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "id": str(row["id"]),
        "candidate_id": str(row["candidate_id"]),
    }


def serialize_radar_config(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "value": row.get("value") or [],
    }


def serialize_portfolio_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "slug": row["slug"],
        "name": row["name"],
        "summary": row.get("summary"),
        "hypothesis": row.get("hypothesis"),
        "focus": row.get("focus"),
        "scope": row.get("scope"),
        "maturity": row.get("maturity"),
        "build_level": row.get("build_level"),
        "dominant_risk": row.get("dominant_risk"),
        "verdict": row.get("verdict"),
        "priority": row.get("priority"),
        "scorecard": row.get("scorecard") or {},
        "gates": row.get("gates") or {},
        "decision_memo": row.get("decision_memo"),
        "next_research": row.get("next_research") or {},
        "kill_criteria": row.get("kill_criteria") or {},
        "evidence_count": int(row.get("evidence_count") or 0),
        "apply_log_count": int(row.get("apply_log_count") or 0),
        "last_apply_at": row.get("last_apply_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def fetch_portfolio_candidates(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return fetch_all(
        conn,
        """
        SELECT
            c.*,
            COALESCE(e.evidence_count, 0)::int AS evidence_count,
            COALESCE(a.apply_log_count, 0)::int AS apply_log_count,
            a.last_apply_at
        FROM radar_candidates c
        LEFT JOIN (
            SELECT candidate_id, COUNT(*)::int AS evidence_count
            FROM radar_evidence
            GROUP BY candidate_id
        ) e ON e.candidate_id = c.id
        LEFT JOIN (
            SELECT candidate_id, COUNT(*)::int AS apply_log_count, MAX(created_at) AS last_apply_at
            FROM radar_apply_logs
            WHERE candidate_id IS NOT NULL
            GROUP BY candidate_id
        ) a ON a.candidate_id = c.id
        ORDER BY c.updated_at DESC, c.slug
        """,
    )


def group_counts(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get(field) or "unassigned"
        counts[str(key)] = counts.get(str(key), 0) + 1
    return [{"value": key, "count": value} for key, value in sorted(counts.items())]


def gates_has_failed_value(gates: dict[str, Any]) -> bool:
    for value in gates.values():
        if value is False:
            return True
        if isinstance(value, str) and value.lower() in {"failed", "fail", "weak", "blocked", "red"}:
            return True
    return False


def gates_incomplete(gates: dict[str, Any]) -> bool:
    return not gates or any(value is None or value == "" for value in gates.values())


def candidate_queue_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    verdict = row.get("verdict")
    maturity = row.get("maturity")
    scorecard = row.get("scorecard") or {}
    gates = row.get("gates") or {}
    evidence_count = int(row.get("evidence_count") or 0)
    if not verdict:
        reasons.append("missing_verdict")
    elif str(verdict).upper() in RADAR_REVIEW_VERDICTS:
        reasons.append("review_verdict")
    if maturity in RADAR_REVIEW_MATURITIES:
        reasons.append("review_maturity")
    if not scorecard:
        reasons.append("missing_scorecard")
    if gates_incomplete(gates):
        reasons.append("incomplete_gates")
    if evidence_count < 1:
        reasons.append("low_evidence")
    return reasons


def build_matrix(rows: list[dict[str, Any]], row_field: str, column_field: str) -> dict[str, Any]:
    row_values = sorted({str(row.get(row_field) or "unassigned") for row in rows})
    column_values = sorted({str(row.get(column_field) or "unassigned") for row in rows})
    cells: list[dict[str, Any]] = []
    for row_value in row_values:
        for column_value in column_values:
            candidates = [
                {"id": str(row["id"]), "slug": row["slug"], "name": row["name"]}
                for row in rows
                if str(row.get(row_field) or "unassigned") == row_value
                and str(row.get(column_field) or "unassigned") == column_value
            ]
            cells.append({"row": row_value, "column": column_value, "count": len(candidates), "candidates": candidates})
    return {"rows": row_values, "columns": column_values, "cells": cells}


def get_radar_candidate_or_404(conn: psycopg.Connection, candidate_id: UUID):
    row = fetch_one(conn, "SELECT * FROM radar_candidates WHERE id = %s", (candidate_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar candidate '{candidate_id}' not found")
    return row


def get_radar_signal_or_404(conn: psycopg.Connection, signal_id: UUID):
    row = fetch_one(conn, "SELECT * FROM radar_signals WHERE id = %s", (signal_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar signal '{signal_id}' not found")
    return row


def get_radar_prompt_or_404(conn: psycopg.Connection, prompt_id: UUID):
    row = fetch_one(conn, "SELECT * FROM radar_prompts WHERE id = %s", (prompt_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar prompt '{prompt_id}' not found")
    return row


def get_radar_prompt_version_or_404(
    conn: psycopg.Connection,
    version_id: UUID,
    *,
    prompt_id: UUID | None = None,
):
    if prompt_id is None:
        row = fetch_one(conn, "SELECT * FROM radar_prompt_versions WHERE id = %s", (version_id,))
    else:
        row = fetch_one(
            conn,
            "SELECT * FROM radar_prompt_versions WHERE id = %s AND prompt_id = %s",
            (version_id, prompt_id),
        )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar prompt version '{version_id}' not found")
    return row


def get_radar_evidence_or_404(conn: psycopg.Connection, evidence_id: UUID):
    row = fetch_one(conn, "SELECT * FROM radar_evidence WHERE id = %s", (evidence_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar evidence '{evidence_id}' not found")
    return row


def get_radar_apply_log_or_404(conn: psycopg.Connection, apply_log_id: UUID):
    row = fetch_one(conn, "SELECT * FROM radar_apply_logs WHERE id = %s", (apply_log_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar apply log '{apply_log_id}' not found")
    return row


def get_radar_prompt_run_or_404(conn: psycopg.Connection, prompt_run_id: UUID):
    row = fetch_one(conn, "SELECT * FROM radar_prompt_runs WHERE id = %s", (prompt_run_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar prompt run '{prompt_run_id}' not found")
    return row


def ensure_radar_candidate_exists(conn: psycopg.Connection, candidate_id: UUID | None):
    if candidate_id is None:
        return
    get_radar_candidate_or_404(conn, candidate_id)


def ensure_unique_radar_candidate_slug(
    conn: psycopg.Connection,
    slug: str,
    *,
    exclude_id: UUID | None = None,
) -> None:
    if exclude_id is None:
        row = fetch_one(conn, "SELECT id FROM radar_candidates WHERE slug = %s", (slug,))
    else:
        row = fetch_one(
            conn,
            "SELECT id FROM radar_candidates WHERE slug = %s AND id <> %s",
            (slug, exclude_id),
        )
    if row is not None:
        raise HTTPException(status_code=409, detail=f"Radar candidate slug '{slug}' already exists")


def ensure_unique_radar_prompt_key(
    conn: psycopg.Connection,
    key: str,
    *,
    exclude_id: UUID | None = None,
) -> None:
    if exclude_id is None:
        row = fetch_one(conn, "SELECT id FROM radar_prompts WHERE key = %s", (key,))
    else:
        row = fetch_one(
            conn,
            "SELECT id FROM radar_prompts WHERE key = %s AND id <> %s",
            (key, exclude_id),
        )
    if row is not None:
        raise HTTPException(status_code=409, detail=f"Radar prompt key '{key}' already exists")


def build_apply_log(
    conn: psycopg.Connection,
    *,
    payload: dict[str, Any],
    candidate_id: UUID | None,
    prompt_id: UUID | None,
    prompt_version_id: UUID | None,
    source_type: str,
    recognized_format: str | None,
    status: str,
    model_used: str | None,
    notes: str | None,
    applied_changes: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    return insert_row(
        conn,
        "radar_apply_logs",
        {
            "candidate_id": candidate_id,
            "prompt_id": prompt_id,
            "prompt_version_id": prompt_version_id,
            "source_type": source_type,
            "recognized_format": recognized_format,
            "status": status,
            "model_used": model_used,
            "notes": notes,
            "json_payload": payload,
            "applied_changes": applied_changes or {},
            "error_message": error_message,
        },
    )


def raise_logged_apply_error(
    conn: psycopg.Connection,
    *,
    status_code: int,
    message: str,
    payload: dict[str, Any],
    candidate_id: UUID | None = None,
    prompt_id: UUID | None = None,
    prompt_version_id: UUID | None = None,
    source_type: str = "unknown",
    recognized_format: str | None = None,
    model_used: str | None = None,
    notes: str | None = None,
) -> None:
    log_row = build_apply_log(
        conn,
        payload=payload,
        candidate_id=candidate_id,
        prompt_id=prompt_id,
        prompt_version_id=prompt_version_id,
        source_type=source_type,
        recognized_format=recognized_format,
        status="failed",
        model_used=model_used,
        notes=notes,
        error_message=message,
    )
    conn.commit()
    raise HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "apply_log_id": str(log_row["id"]),
        },
    )


def normalize_source_type(raw: Any, warnings: list[str]) -> str:
    if isinstance(raw, str) and raw in ALLOWED_SOURCE_TYPES:
        return raw
    if raw is not None:
        warnings.append(f"sourceType '{raw}' no es soportado; se usa 'unknown'.")
        return "unknown"
    return "api"


def prompt_context_value(path: str, *, candidate: dict[str, Any] | None, variables: dict[str, Any]) -> Any:
    parts = path.split(".")
    if not parts:
        return None

    if parts[0] == "candidate":
        current: Any = candidate or {}
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    if parts[0] == "variables":
        current = variables
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    return None


def render_prompt_template(
    template: str,
    *,
    candidate: dict[str, Any] | None,
    variables: dict[str, Any],
) -> tuple[str, list[str]]:
    warnings: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = prompt_context_value(key, candidate=candidate, variables=variables)
        if value is None:
            warnings.append(f"Missing render variable '{key}'.")
            return match.group(0)
        if isinstance(value, (dict, list)):
            return pretty_json_compact(value)
        return str(value)

    return RADAR_PROMPT_PLACEHOLDER_RE.sub(replace, template), sorted(set(warnings))


def pretty_json_compact(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def build_expected_filename(
    *,
    template: str | None,
    prompt: dict[str, Any],
    prompt_run_id: UUID,
    candidate: dict[str, Any] | None,
    variables: dict[str, Any],
) -> tuple[str, list[str]]:
    base_template = template or f"radar_{prompt['key']}_*.json"
    base_template = base_template.replace("{{prompt_run.id}}", str(prompt_run_id))
    base_template = base_template.replace("{{prompt_run.hex}}", prompt_run_id.hex)
    rendered, warnings = render_prompt_template(base_template, candidate=candidate, variables=variables)
    if "*" in rendered:
        rendered = rendered.replace("*", prompt_run_id.hex[:12], 1)
    if not rendered.endswith(".json"):
        rendered = f"{rendered}.json"
    return rendered, warnings


def append_radar_trace_instructions(
    rendered_prompt: str,
    *,
    prompt_run_id: UUID,
    prompt_id: UUID,
    prompt_version_id: UUID,
    candidate_id: UUID | None,
    model_used: str,
    expected_filename: str,
) -> str:
    meta_lines = [
        f'  "promptRunId": "{prompt_run_id}",',
        f'  "promptId": "{prompt_id}",',
        f'  "promptVersionId": "{prompt_version_id}",',
    ]
    if candidate_id is not None:
        meta_lines.append(f'  "candidateId": "{candidate_id}",')
    meta_lines.append(f'  "modelUsed": "{model_used}"')

    return (
        f"{rendered_prompt.rstrip()}\n\n"
        "---\n"
        "Radar import requirements:\n"
        "Return only valid JSON that Radar can import through /radar/import.\n"
        "Ensure the JSON contains this meta object:\n"
        "{\n"
        + "\n".join(meta_lines)
        + "\n}\n"
        f"Save/download the result as: {expected_filename}\n"
    )


def parse_datetime_value(value: Any, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a valid ISO datetime") from exc
    raise ValueError(f"{field_name} must be a valid ISO datetime")


def normalize_candidate_updates(updates: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    patch: dict[str, Any] = {}
    applied: list[str] = []
    warnings: list[str] = []

    for key, value in updates.items():
        normalized_key = RADAR_CANDIDATE_UPDATE_ALIASES.get(key, key)
        if normalized_key in RADAR_CANDIDATE_MUTABLE_FIELDS:
            patch[normalized_key] = value
            applied.append(normalized_key)
        else:
            warnings.append(f"Ignored unknown candidate update field '{key}'.")

    return patch, sorted(set(applied)), warnings


def normalize_evidence_entries(raw_entries: list[Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"evidence[{index}] must be an object")

        entry = RadarEvidenceCreate(
            kind=raw_entry.get("kind") or raw_entry.get("type") or "note",
            title=raw_entry.get("title"),
            url=raw_entry.get("url"),
            source_name=raw_entry.get("source_name") or raw_entry.get("sourceName"),
            source_tier=raw_entry.get("source_tier") or raw_entry.get("sourceTier"),
            claim=raw_entry.get("claim"),
            confidence=raw_entry.get("confidence"),
            date_accessed=raw_entry.get("date_accessed") or raw_entry.get("dateAccessed"),
            notes=raw_entry.get("notes") or raw_entry.get("value"),
        )
        entries.append(entry.model_dump(exclude_unset=True))
    return entries


def extract_apply_context(payload: dict[str, Any]) -> tuple[str, str | None, dict[str, Any], list[str]]:
    warnings: list[str] = []

    if payload.get("_radar_export") is True:
        entity = payload.get("_entity")
        if entity not in ALLOWED_EXPORT_ENTITIES:
            raise ValueError(
                "`_entity` must be one of: candidates, evidence, signals, prompts, goldenSet, config, multi."
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("Radar wrapper `data` must be a JSON object in Fase 2.")

        if any(key in data for key in ("meta", "updates", "scorecard", "gates", "evidence")):
            return "wrapper", entity, data, warnings

        if entity == "candidates":
            candidate_id = data.get("candidateId") or data.get("candidate_id")
            return "wrapper", entity, {"meta": {"candidateId": candidate_id}, "updates": data}, warnings

        if entity == "evidence":
            candidate_id = data.get("candidateId") or data.get("candidate_id")
            evidence_items = data.get("evidence")
            if isinstance(evidence_items, list):
                return "wrapper", entity, {"meta": {"candidateId": candidate_id}, "evidence": evidence_items}, warnings
            if any(key in data for key in ("kind", "claim", "title", "url", "sourceName", "source_name")):
                return "wrapper", entity, {"meta": {"candidateId": candidate_id}, "evidence": [data]}, warnings

        raise ValueError(
            "Radar wrapper recognized, but this phase only supports candidate/evidence apply payloads inside `data`."
        )

    if isinstance(payload.get("meta"), dict) and any(
        key in payload for key in ("updates", "scorecard", "gates", "evidence")
    ):
        return "update", None, payload, warnings

    raise ValueError(
        "Unrecognized Radar JSON payload. Expected either a wrapper with "
        "`_radar_export`, `_entity`, `data` or an update payload with `meta` and `updates`/`scorecard`/`gates`/`evidence`."
    )


def resolve_references(
    conn: psycopg.Connection,
    *,
    payload: dict[str, Any],
    source_type: str,
    recognized_format: str,
    meta: dict[str, Any],
    notes: str | None,
    model_used: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    candidate_row = None
    prompt_row = None
    prompt_version_row = None

    candidate_ref = meta.get("candidateId") or meta.get("candidate_id")
    prompt_ref = meta.get("promptId") or meta.get("prompt_id")
    prompt_version_ref = meta.get("promptVersionId") or meta.get("prompt_version_id")

    if candidate_ref is not None:
        try:
            candidate_row = get_radar_candidate_or_404(conn, UUID(str(candidate_ref)))
        except (ValueError, HTTPException):
            raise_logged_apply_error(
                conn,
                status_code=404,
                message=f"Radar candidate '{candidate_ref}' not found",
                payload=payload,
                source_type=source_type,
                recognized_format=recognized_format,
                model_used=model_used,
                notes=notes,
            )

    if prompt_ref is not None:
        try:
            prompt_row = get_radar_prompt_or_404(conn, UUID(str(prompt_ref)))
        except (ValueError, HTTPException):
            raise_logged_apply_error(
                conn,
                status_code=404,
                message=f"Radar prompt '{prompt_ref}' not found",
                payload=payload,
                candidate_id=UUID(str(candidate_row["id"])) if candidate_row is not None else None,
                source_type=source_type,
                recognized_format=recognized_format,
                model_used=model_used,
                notes=notes,
            )

    if prompt_version_ref is not None:
        try:
            prompt_version_uuid = UUID(str(prompt_version_ref))
        except ValueError:
            prompt_version_uuid = None
        prompt_version_row = (
            fetch_one(conn, "SELECT * FROM radar_prompt_versions WHERE id = %s", (prompt_version_uuid,))
            if prompt_version_uuid is not None
            else None
        )
        if prompt_version_row is None:
            raise_logged_apply_error(
                conn,
                status_code=404,
                message=f"Radar prompt version '{prompt_version_ref}' not found",
                payload=payload,
                candidate_id=UUID(str(candidate_row["id"])) if candidate_row is not None else None,
                prompt_id=UUID(str(prompt_row["id"])) if prompt_row is not None else None,
                source_type=source_type,
                recognized_format=recognized_format,
                model_used=model_used,
                notes=notes,
            )

    return candidate_row, prompt_row, prompt_version_row


def resolve_prompt_run_reference(
    conn: psycopg.Connection,
    *,
    meta: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any] | None:
    prompt_run_ref = meta.get("promptRunId") or meta.get("prompt_run_id")
    if prompt_run_ref is None:
        return None
    try:
        return get_radar_prompt_run_or_404(conn, UUID(str(prompt_run_ref)))
    except (ValueError, HTTPException):
        warnings.append(f"Radar promptRunId '{prompt_run_ref}' was not found; apply continues without prompt-run linkage.")
        return None


def build_apply_result(
    *,
    mode: str,
    candidate_id: str | None,
    updates_applied: list[str],
    evidence_created: int,
    warnings: list[str],
    apply_log_id: str,
    dry_run: bool,
    prompt_run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": mode,
        "candidate_id": candidate_id,
        "updates_applied": updates_applied,
        "evidence_created": evidence_created,
        "warnings": warnings,
        "apply_log_id": apply_log_id,
        "dry_run": dry_run,
        "prompt_run_id": prompt_run_id,
    }


@router.get("/candidates")
def list_radar_candidates(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_all(conn, "SELECT * FROM radar_candidates ORDER BY created_at DESC, slug")
    return [serialize_radar_candidate(row) for row in rows]


@router.post("/candidates", status_code=201)
def create_radar_candidate(
    payload: RadarCandidateCreate,
    conn: psycopg.Connection = Depends(get_db),
):
    ensure_unique_radar_candidate_slug(conn, payload.slug)
    row = insert_row(conn, "radar_candidates", payload.model_dump(exclude_none=True))
    return serialize_radar_candidate(row)


@router.get("/candidates/{candidate_id}")
def get_radar_candidate(candidate_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    return serialize_radar_candidate(get_radar_candidate_or_404(conn, candidate_id))


@router.patch("/candidates/{candidate_id}")
def patch_radar_candidate(
    candidate_id: UUID,
    payload: RadarCandidatePatch,
    conn: psycopg.Connection = Depends(get_db),
):
    current = get_radar_candidate_or_404(conn, candidate_id)
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != current["slug"]:
        ensure_unique_radar_candidate_slug(conn, data["slug"], exclude_id=candidate_id)
    row = update_row(conn, "radar_candidates", {"id": candidate_id}, data)
    assert row is not None
    return serialize_radar_candidate(row)


@router.delete("/candidates/{candidate_id}", status_code=204)
def delete_radar_candidate(candidate_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    deleted = fetch_one(conn, "DELETE FROM radar_candidates WHERE id = %s RETURNING id", (candidate_id,))
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Radar candidate '{candidate_id}' not found")
    return Response(status_code=204)


@router.get("/candidates/{candidate_id}/evidence")
def list_radar_candidate_evidence(candidate_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    get_radar_candidate_or_404(conn, candidate_id)
    rows = fetch_all(
        conn,
        "SELECT * FROM radar_evidence WHERE candidate_id = %s ORDER BY created_at DESC, id DESC",
        (candidate_id,),
    )
    return [serialize_radar_evidence(row) for row in rows]


@router.post("/candidates/{candidate_id}/evidence", status_code=201)
def create_radar_candidate_evidence(
    candidate_id: UUID,
    payload: RadarEvidenceCreate,
    conn: psycopg.Connection = Depends(get_db),
):
    get_radar_candidate_or_404(conn, candidate_id)
    row = insert_row(
        conn,
        "radar_evidence",
        {
            "candidate_id": candidate_id,
            **payload.model_dump(exclude_unset=True),
        },
    )
    return serialize_radar_evidence(row)


@router.delete("/evidence/{evidence_id}", status_code=204)
def delete_radar_evidence(evidence_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    get_radar_evidence_or_404(conn, evidence_id)
    conn.execute("DELETE FROM radar_evidence WHERE id = %s", (evidence_id,))
    return Response(status_code=204)


@router.get("/signals")
def list_radar_signals(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_all(conn, "SELECT * FROM radar_signals ORDER BY created_at DESC, id DESC")
    return [serialize_radar_signal(row) for row in rows]


@router.post("/signals", status_code=201)
def create_radar_signal(payload: RadarSignalCreate, conn: psycopg.Connection = Depends(get_db)):
    ensure_radar_candidate_exists(conn, payload.candidate_id)
    row = insert_row(conn, "radar_signals", payload.model_dump(exclude_unset=True))
    return serialize_radar_signal(row)


@router.patch("/signals/{signal_id}")
def patch_radar_signal(
    signal_id: UUID,
    payload: RadarSignalPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    get_radar_signal_or_404(conn, signal_id)
    data = payload.model_dump(exclude_unset=True)
    ensure_radar_candidate_exists(conn, data.get("candidate_id"))
    row = update_row(conn, "radar_signals", {"id": signal_id}, data)
    assert row is not None
    return serialize_radar_signal(row)


@router.delete("/signals/{signal_id}", status_code=204)
def delete_radar_signal(signal_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    deleted = fetch_one(conn, "DELETE FROM radar_signals WHERE id = %s RETURNING id", (signal_id,))
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Radar signal '{signal_id}' not found")
    return Response(status_code=204)


@router.get("/prompts")
def list_radar_prompts(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_all(
        conn,
        """
        SELECT
            p.*,
            latest.version AS latest_version,
            latest.is_active AS latest_version_is_active,
            latest.created_at AS latest_version_created_at
        FROM radar_prompts p
        LEFT JOIN LATERAL (
            SELECT version, is_active, created_at
            FROM radar_prompt_versions
            WHERE prompt_id = p.id
            ORDER BY version DESC, created_at DESC
            LIMIT 1
        ) latest ON true
        ORDER BY p.created_at DESC, p.key
        """,
    )
    return [serialize_radar_prompt(row) for row in rows]


@router.post("/prompts", status_code=201)
def create_radar_prompt(payload: RadarPromptCreate, conn: psycopg.Connection = Depends(get_db)):
    ensure_unique_radar_prompt_key(conn, payload.key)
    row = insert_row(conn, "radar_prompts", payload.model_dump(exclude_unset=True))
    return serialize_radar_prompt(row)


@router.get("/prompts/{prompt_id}")
def get_radar_prompt(prompt_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    return serialize_radar_prompt(get_radar_prompt_or_404(conn, prompt_id))


@router.patch("/prompts/{prompt_id}")
def patch_radar_prompt(
    prompt_id: UUID,
    payload: RadarPromptPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    current = get_radar_prompt_or_404(conn, prompt_id)
    data = payload.model_dump(exclude_unset=True)
    if "key" in data and data["key"] != current["key"]:
        ensure_unique_radar_prompt_key(conn, data["key"], exclude_id=prompt_id)
    row = update_row(conn, "radar_prompts", {"id": prompt_id}, data)
    assert row is not None
    return serialize_radar_prompt(row)


@router.delete("/prompts/{prompt_id}", status_code=204)
def delete_radar_prompt(prompt_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    deleted = fetch_one(conn, "DELETE FROM radar_prompts WHERE id = %s RETURNING id", (prompt_id,))
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Radar prompt '{prompt_id}' not found")
    return Response(status_code=204)


@router.get("/prompts/{prompt_id}/versions")
def list_radar_prompt_versions(prompt_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    get_radar_prompt_or_404(conn, prompt_id)
    rows = fetch_all(
        conn,
        "SELECT * FROM radar_prompt_versions WHERE prompt_id = %s ORDER BY version DESC, created_at DESC",
        (prompt_id,),
    )
    return [serialize_radar_prompt_version(row) for row in rows]


@router.post("/prompts/{prompt_id}/versions", status_code=201)
def create_radar_prompt_version(
    prompt_id: UUID,
    payload: RadarPromptVersionCreate,
    conn: psycopg.Connection = Depends(get_db),
):
    get_radar_prompt_or_404(conn, prompt_id)
    requested_version = payload.version
    if requested_version is None:
        next_row = fetch_one(
            conn,
            "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM radar_prompt_versions WHERE prompt_id = %s",
            (prompt_id,),
        )
        requested_version = next_row["next_version"]
    else:
        existing = fetch_one(
            conn,
            "SELECT id FROM radar_prompt_versions WHERE prompt_id = %s AND version = %s",
            (prompt_id, requested_version),
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Radar prompt version {requested_version} already exists for prompt '{prompt_id}'",
            )

    if payload.is_active:
        conn.execute("UPDATE radar_prompt_versions SET is_active = false WHERE prompt_id = %s", (prompt_id,))

    row = insert_row(
        conn,
        "radar_prompt_versions",
        {
            **payload.model_dump(exclude_unset=True),
            "prompt_id": prompt_id,
            "version": requested_version,
        },
    )
    return serialize_radar_prompt_version(row)


@router.post("/prompts/{prompt_id}/versions/{version_id}/render", status_code=201)
def render_radar_prompt_version(
    prompt_id: UUID,
    version_id: UUID,
    payload: RadarPromptRender,
    conn: psycopg.Connection = Depends(get_db),
):
    prompt_row = get_radar_prompt_or_404(conn, prompt_id)
    version_row = get_radar_prompt_version_or_404(conn, version_id, prompt_id=prompt_id)
    candidate_row = get_radar_candidate_or_404(conn, payload.candidate_id) if payload.candidate_id is not None else None

    prompt_run_id = uuid4()
    rendered_body, render_warnings = render_prompt_template(
        version_row["body"],
        candidate=candidate_row,
        variables=payload.variables,
    )
    expected_filename, filename_warnings = build_expected_filename(
        template=version_row.get("filename_pattern"),
        prompt=prompt_row,
        prompt_run_id=prompt_run_id,
        candidate=candidate_row,
        variables=payload.variables,
    )
    warnings = sorted(set([*render_warnings, *filename_warnings]))
    model_used = payload.model_label or payload.target_tool
    final_prompt = append_radar_trace_instructions(
        rendered_body,
        prompt_run_id=prompt_run_id,
        prompt_id=prompt_id,
        prompt_version_id=version_id,
        candidate_id=payload.candidate_id,
        model_used=model_used,
        expected_filename=expected_filename,
    )

    row = insert_row(
        conn,
        "radar_prompt_runs",
        {
            "id": prompt_run_id,
            "prompt_id": prompt_id,
            "prompt_version_id": version_id,
            "candidate_id": payload.candidate_id,
            "target_tool": payload.target_tool,
            "model_label": payload.model_label,
            "rendered_prompt": final_prompt,
            "expected_filename": expected_filename,
            "status": "created",
            "notes": payload.notes,
        },
    )

    return {
        "ok": True,
        "prompt_run_id": str(row["id"]),
        "rendered_prompt": final_prompt,
        "expected_filename": expected_filename,
        "target_tool": payload.target_tool,
        "warnings": warnings,
    }


@router.get("/config")
def list_radar_config(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_all(conn, "SELECT * FROM radar_config ORDER BY key")
    return [serialize_radar_config(row) for row in rows]


@router.put("/config/{key}")
def put_radar_config(
    key: str,
    payload: RadarConfigPut,
    conn: psycopg.Connection = Depends(get_db),
):
    existing = fetch_one(conn, "SELECT * FROM radar_config WHERE key = %s", (key,))
    data = payload.model_dump(exclude_unset=True)
    if existing is None:
        row = insert_row(conn, "radar_config", {"key": key, **data})
    else:
        row = update_row(conn, "radar_config", {"key": key}, data)
        assert row is not None
    return serialize_radar_config(row)


@router.get("/prompt-runs")
def list_radar_prompt_runs(
    candidate_id: UUID | None = None,
    prompt_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    conn: psycopg.Connection = Depends(get_db),
):
    where_clauses: list[str] = []
    params: list[Any] = []

    if candidate_id is not None:
        where_clauses.append("candidate_id = %s")
        params.append(candidate_id)
    if prompt_id is not None:
        where_clauses.append("prompt_id = %s")
        params.append(prompt_id)
    if status:
        where_clauses.append("status = %s")
        params.append(status)

    query = "SELECT * FROM radar_prompt_runs"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit)

    rows = fetch_all(conn, query, tuple(params))
    return [serialize_radar_prompt_run(row) for row in rows]


@router.get("/prompt-runs/{prompt_run_id}")
def get_radar_prompt_run(prompt_run_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    return serialize_radar_prompt_run(get_radar_prompt_run_or_404(conn, prompt_run_id))


@router.patch("/prompt-runs/{prompt_run_id}")
def patch_radar_prompt_run(
    prompt_run_id: UUID,
    payload: RadarPromptRunPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "apply_log_id" in data and data["apply_log_id"] is not None:
        get_radar_apply_log_or_404(conn, data["apply_log_id"])
    row = update_row(conn, "radar_prompt_runs", {"id": prompt_run_id}, data)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar prompt run '{prompt_run_id}' not found")
    return serialize_radar_prompt_run(row)


@router.post("/prompt-runs/{prompt_run_id}/mark-copied")
def mark_radar_prompt_run_copied(prompt_run_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    get_radar_prompt_run_or_404(conn, prompt_run_id)
    row = update_row(conn, "radar_prompt_runs", {"id": prompt_run_id}, {"status": "waiting_import"})
    assert row is not None
    return serialize_radar_prompt_run(row)


@router.post("/prompt-runs/{prompt_run_id}/cancel")
def cancel_radar_prompt_run(prompt_run_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    get_radar_prompt_run_or_404(conn, prompt_run_id)
    row = update_row(conn, "radar_prompt_runs", {"id": prompt_run_id}, {"status": "cancelled"})
    assert row is not None
    return serialize_radar_prompt_run(row)


@router.get("/portfolio/overview")
def get_radar_portfolio_overview(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_portfolio_candidates(conn)
    without_verdict = [row for row in rows if not row.get("verdict")]
    without_evidence = [row for row in rows if int(row.get("evidence_count") or 0) == 0]
    failed_gates = [row for row in rows if gates_has_failed_value(row.get("gates") or {})]
    return {
        "total_candidates": len(rows),
        "count_by_verdict": group_counts(rows, "verdict"),
        "count_by_maturity": group_counts(rows, "maturity"),
        "count_by_focus": group_counts(rows, "focus"),
        "count_by_scope": group_counts(rows, "scope"),
        "count_by_dominant_risk": group_counts(rows, "dominant_risk"),
        "count_by_build_level": group_counts(rows, "build_level"),
        "candidates_without_verdict": [serialize_portfolio_candidate(row) for row in without_verdict],
        "candidates_without_evidence": [serialize_portfolio_candidate(row) for row in without_evidence],
        "candidates_with_failed_gates": [serialize_portfolio_candidate(row) for row in failed_gates],
        "recently_updated_candidates": [serialize_portfolio_candidate(row) for row in rows[:8]],
    }


@router.get("/portfolio/matrix/focus-scope")
def get_radar_portfolio_focus_scope_matrix(conn: psycopg.Connection = Depends(get_db)):
    return build_matrix(fetch_portfolio_candidates(conn), "focus", "scope")


@router.get("/portfolio/matrix/maturity-verdict")
def get_radar_portfolio_maturity_verdict_matrix(conn: psycopg.Connection = Depends(get_db)):
    return build_matrix(fetch_portfolio_candidates(conn), "maturity", "verdict")


@router.get("/portfolio/risk-distribution")
def get_radar_portfolio_risk_distribution(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_portfolio_candidates(conn)
    risks: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        risk = str(row.get("dominant_risk") or "unassigned")
        risks.setdefault(risk, []).append(serialize_portfolio_candidate(row))
    return [
        {"dominant_risk": risk, "count": len(candidates), "candidates": candidates}
        for risk, candidates in sorted(risks.items())
    ]


@router.get("/portfolio/selection-queue")
def get_radar_portfolio_selection_queue(conn: psycopg.Connection = Depends(get_db)):
    rows = fetch_portfolio_candidates(conn)
    items = []
    for row in rows:
        reasons = candidate_queue_reasons(row)
        if reasons:
            items.append({**serialize_portfolio_candidate(row), "reasons": reasons})
    return items


@router.post("/portfolio/compare")
def compare_radar_portfolio_candidates(
    payload: RadarPortfolioCompareRequest,
    conn: psycopg.Connection = Depends(get_db),
):
    candidate_ids = [str(candidate_id) for candidate_id in payload.candidate_ids]
    rows = fetch_all(
        conn,
        """
        SELECT
            c.*,
            COALESCE(e.evidence_count, 0)::int AS evidence_count,
            COALESCE(a.apply_log_count, 0)::int AS apply_log_count,
            a.last_apply_at
        FROM radar_candidates c
        LEFT JOIN (
            SELECT candidate_id, COUNT(*)::int AS evidence_count
            FROM radar_evidence
            GROUP BY candidate_id
        ) e ON e.candidate_id = c.id
        LEFT JOIN (
            SELECT candidate_id, COUNT(*)::int AS apply_log_count, MAX(created_at) AS last_apply_at
            FROM radar_apply_logs
            WHERE candidate_id IS NOT NULL
            GROUP BY candidate_id
        ) a ON a.candidate_id = c.id
        WHERE c.id = ANY(%s::uuid[])
        ORDER BY c.updated_at DESC, c.slug
        """,
        (candidate_ids,),
    )
    found_ids = {str(row["id"]) for row in rows}
    missing_ids = [candidate_id for candidate_id in candidate_ids if candidate_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Radar candidates not found: {', '.join(missing_ids)}")
    return {"items": [serialize_portfolio_candidate(row) for row in rows]}


@router.get("/file-imports")
def list_radar_file_imports(
    status: str | None = None,
    file_hash: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    conn: psycopg.Connection = Depends(get_db),
):
    where_clauses: list[str] = []
    params: list[Any] = []
    if status:
        where_clauses.append("status = %s")
        params.append(status)
    if file_hash:
        where_clauses.append("file_hash = %s")
        params.append(file_hash)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = fetch_all(
        conn,
        f"SELECT * FROM radar_file_imports {where_sql} ORDER BY created_at DESC LIMIT %s",
        [*params, limit],
    )
    return [serialize_radar_file_import(row) for row in rows]


@router.post("/file-imports", status_code=201)
def create_radar_file_import(payload: RadarFileImportCreate, conn: psycopg.Connection = Depends(get_db)):
    if payload.apply_log_id is not None:
        get_radar_apply_log_or_404(conn, payload.apply_log_id)
    row = insert_row(
        conn,
        "radar_file_imports",
        {
            "filename": payload.filename,
            "original_path": payload.original_path,
            "stored_path": payload.stored_path,
            "file_hash": payload.file_hash,
            "status": payload.status,
            "apply_log_id": payload.apply_log_id,
            "payload_summary": payload.payload_summary,
            "error_message": payload.error_message,
            "processed_at": datetime.now(timezone.utc) if payload.status != "pending" else None,
        },
    )
    return serialize_radar_file_import(row)


@router.get("/file-imports/{file_import_id}")
def get_radar_file_import(file_import_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    row = fetch_one(conn, "SELECT * FROM radar_file_imports WHERE id = %s", (file_import_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar file import '{file_import_id}' not found")
    return serialize_radar_file_import(row)


@router.patch("/file-imports/{file_import_id}")
def patch_radar_file_import(
    file_import_id: UUID,
    payload: RadarFileImportPatch,
    conn: psycopg.Connection = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if "apply_log_id" in data and data["apply_log_id"] is not None:
        get_radar_apply_log_or_404(conn, data["apply_log_id"])
    if data.get("status") in {"processed", "failed", "duplicate"} and "processed_at" not in data:
        data["processed_at"] = datetime.now(timezone.utc)
    row = update_row(conn, "radar_file_imports", {"id": file_import_id}, data)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Radar file import '{file_import_id}' not found")
    return serialize_radar_file_import(row)


@router.get("/apply-logs")
def list_radar_apply_logs(
    candidate_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    conn: psycopg.Connection = Depends(get_db),
):
    where_clauses: list[str] = []
    params: list[Any] = []

    if candidate_id is not None:
        where_clauses.append("candidate_id = %s")
        params.append(candidate_id)
    if status:
        where_clauses.append("status = %s")
        params.append(status)

    query = "SELECT * FROM radar_apply_logs"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY created_at DESC, id DESC LIMIT %s"
    params.append(limit)

    rows = fetch_all(conn, query, tuple(params))
    return [serialize_radar_apply_log(row) for row in rows]


@router.get("/apply-logs/{apply_log_id}")
def get_radar_apply_log(apply_log_id: UUID, conn: psycopg.Connection = Depends(get_db)):
    return serialize_radar_apply_log(get_radar_apply_log_or_404(conn, apply_log_id))


@router.post("/apply-json", status_code=201)
def apply_radar_json(
    payload: dict[str, Any],
    dry_run: bool = False,
    conn: psycopg.Connection = Depends(get_db),
):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Radar apply-json expects a JSON object")

    try:
        mode, entity, working_payload, warnings = extract_apply_context(payload)
    except ValueError as exc:
        raise_logged_apply_error(
            conn,
            status_code=422,
            message=str(exc),
            payload=payload,
            source_type="api",
        )

    meta = working_payload.get("meta") if isinstance(working_payload.get("meta"), dict) else {}
    notes = meta.get("notes") if isinstance(meta.get("notes"), str) else None
    model_used = meta.get("modelUsed") if isinstance(meta.get("modelUsed"), str) else None
    source_type = normalize_source_type(meta.get("sourceType") or meta.get("source_type"), warnings)
    recognized_format = "wrapper" if mode == "wrapper" else "update"
    prompt_run_row = resolve_prompt_run_reference(conn, meta=meta, warnings=warnings)
    if prompt_run_row is not None:
        if meta.get("candidateId") is None and meta.get("candidate_id") is None and prompt_run_row.get("candidate_id") is not None:
            meta["candidateId"] = str(prompt_run_row["candidate_id"])
        if meta.get("promptId") is None and meta.get("prompt_id") is None:
            meta["promptId"] = str(prompt_run_row["prompt_id"])
        if meta.get("promptVersionId") is None and meta.get("prompt_version_id") is None:
            meta["promptVersionId"] = str(prompt_run_row["prompt_version_id"])
        if model_used is None:
            model_used = prompt_run_row.get("model_label") or prompt_run_row.get("target_tool")

    candidate_row, prompt_row, prompt_version_row = resolve_references(
        conn,
        payload=payload,
        source_type=source_type,
        recognized_format=recognized_format,
        meta=meta,
        notes=notes,
        model_used=model_used,
    )

    updates = working_payload.get("updates") if isinstance(working_payload.get("updates"), dict) else {}
    scorecard = working_payload.get("scorecard") if isinstance(working_payload.get("scorecard"), dict) else None
    gates = working_payload.get("gates") if isinstance(working_payload.get("gates"), dict) else None
    raw_evidence = working_payload.get("evidence") if isinstance(working_payload.get("evidence"), list) else []

    candidate_patch, updates_applied, patch_warnings = normalize_candidate_updates(updates)
    warnings.extend(patch_warnings)

    if scorecard is not None:
        candidate_patch["scorecard"] = scorecard
        updates_applied.append("scorecard")
    if gates is not None:
        candidate_patch["gates"] = gates
        updates_applied.append("gates")

    try:
        evidence_entries = normalize_evidence_entries(raw_evidence)
    except ValueError as exc:
        raise_logged_apply_error(
            conn,
            status_code=422,
            message=str(exc),
            payload=payload,
            candidate_id=UUID(str(candidate_row["id"])) if candidate_row is not None else None,
            prompt_id=UUID(str(prompt_row["id"])) if prompt_row is not None else None,
            prompt_version_id=UUID(str(prompt_version_row["id"])) if prompt_version_row is not None else None,
            source_type=source_type,
            recognized_format=recognized_format,
            model_used=model_used,
            notes=notes,
        )

    if (candidate_patch or evidence_entries) and candidate_row is None:
        raise_logged_apply_error(
            conn,
            status_code=422,
            message="Radar apply-json requires `meta.candidateId` when updates, scorecard, gates or evidence are present.",
            payload=payload,
            prompt_id=UUID(str(prompt_row["id"])) if prompt_row is not None else None,
            prompt_version_id=UUID(str(prompt_version_row["id"])) if prompt_version_row is not None else None,
            source_type=source_type,
            recognized_format=recognized_format,
            model_used=model_used,
            notes=notes,
        )

    if not candidate_patch and not evidence_entries and entity not in {"config"}:
        raise_logged_apply_error(
            conn,
            status_code=422,
            message="Radar apply-json did not find supported updates or evidence to apply.",
            payload=payload,
            candidate_id=UUID(str(candidate_row["id"])) if candidate_row is not None else None,
            prompt_id=UUID(str(prompt_row["id"])) if prompt_row is not None else None,
            prompt_version_id=UUID(str(prompt_version_row["id"])) if prompt_version_row is not None else None,
            source_type=source_type,
            recognized_format=recognized_format,
            model_used=model_used,
            notes=notes,
        )

    candidate_id = UUID(str(candidate_row["id"])) if candidate_row is not None else None
    prompt_id = UUID(str(prompt_row["id"])) if prompt_row is not None else None
    prompt_version_id = UUID(str(prompt_version_row["id"])) if prompt_version_row is not None else None

    applied_changes = {
        "entity": entity or "update",
        "updates_applied": sorted(set(updates_applied)),
        "evidence_count": len(evidence_entries),
        "warnings": warnings,
    }
    prompt_run_id = UUID(str(prompt_run_row["id"])) if prompt_run_row is not None else None

    if dry_run:
        log_row = build_apply_log(
            conn,
            payload=payload,
            candidate_id=candidate_id,
            prompt_id=prompt_id,
            prompt_version_id=prompt_version_id,
            source_type=source_type,
            recognized_format=recognized_format,
            status="dry_run",
            model_used=model_used,
            notes=notes,
            applied_changes=applied_changes,
        )
        return build_apply_result(
            mode=mode,
            candidate_id=str(candidate_id) if candidate_id is not None else None,
            updates_applied=sorted(set(updates_applied)),
            evidence_created=0,
            warnings=warnings,
            apply_log_id=str(log_row["id"]),
            dry_run=True,
            prompt_run_id=str(prompt_run_id) if prompt_run_id is not None else None,
        )

    if candidate_id is not None and candidate_patch:
        updated_candidate = update_row(conn, "radar_candidates", {"id": candidate_id}, candidate_patch)
        assert updated_candidate is not None

    evidence_created = 0
    for evidence_entry in evidence_entries:
        insert_row(
            conn,
            "radar_evidence",
            {
                "candidate_id": candidate_id,
                **evidence_entry,
            },
        )
        evidence_created += 1

    log_row = build_apply_log(
        conn,
        payload=payload,
        candidate_id=candidate_id,
        prompt_id=prompt_id,
        prompt_version_id=prompt_version_id,
        source_type=source_type,
        recognized_format=recognized_format,
        status="applied",
        model_used=model_used,
        notes=notes,
        applied_changes=applied_changes,
    )
    if prompt_run_id is not None:
        update_row(
            conn,
            "radar_prompt_runs",
            {"id": prompt_run_id},
            {"status": "applied", "apply_log_id": UUID(str(log_row["id"]))},
        )

    return build_apply_result(
        mode=mode,
        candidate_id=str(candidate_id) if candidate_id is not None else None,
        updates_applied=sorted(set(updates_applied)),
        evidence_created=evidence_created,
        warnings=warnings,
        apply_log_id=str(log_row["id"]),
        dry_run=False,
        prompt_run_id=str(prompt_run_id) if prompt_run_id is not None else None,
    )
