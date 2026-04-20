from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException
import psycopg

from ashrise.langfuse_support import ResolvedPrompt, get_langfuse_client, record_agent_trace, resolve_prompt
from ashrise.research import assess_stack, check_ai_encroachment, find_competitors, web_search
from app.db import fetch_all, fetch_one, get_candidate_by_ref, insert_row, update_row, upsert_project_state


PROJECT_PROMPT_NAME = "auditor-project@v1"
CANDIDATE_PROMPT_NAME = "investigator-candidate@v1"
PROJECT_PROMPT_REF = f"langfuse:{PROJECT_PROMPT_NAME}"
CANDIDATE_PROMPT_REF = f"langfuse:{CANDIDATE_PROMPT_NAME}"
INITIAL_PRIORITY_PROJECTS = [
    "procurement-licitaciones",
    "neytiri",
    "osla-small-qw",
    "procurement-core",
    "osla-medium-long",
]


@dataclass
class AgentExecutionResult:
    target_type: Literal["project", "candidate"]
    target_id: str
    run: dict[str, Any]
    report_type: str
    report: dict[str, Any]
    summary: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _tech_list_from_target(*parts: Any) -> list[str]:
    technologies: list[str] = []
    seen: set[str] = set()

    for part in parts:
        if not isinstance(part, (dict, list)):
            continue
        rows = [part] if isinstance(part, dict) else part
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in ("tech_list", "stack", "technologies"):
                values = row.get(key)
                if not isinstance(values, list):
                    continue
                for value in values:
                    if isinstance(value, str) and value and value not in seen:
                        seen.add(value)
                        technologies.append(value)
    return technologies


def _evidence_refs(search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for result in search_results[:3]:
        refs.append(
            {
                "kind": "search",
                "title": result.get("title"),
                "url": result.get("url"),
                "provider": result.get("provider", "stub"),
            }
        )
    return refs


def _market_signals(search_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "signal": result.get("snippet"),
            "source": result.get("title"),
            "provider": result.get("provider", "stub"),
        }
        for result in search_results[:3]
    ]


def _project_summary(
    project: dict[str, Any],
    verdict: str,
    competitors: list[dict[str, Any]],
    ai_risk: dict[str, Any],
) -> str:
    lead = project["name"]
    if verdict == "keep":
        return f"{lead} mantiene un gap valido; hay competencia visible pero el problema sigue necesitando ejecucion de dominio."
    if verdict == "adjust":
        return f"{lead} necesita ajustar el wedge frente a competidores como {competitors[0]['name']} y la presion creciente de IA generica."
    if verdict == "pivot-lite":
        return f"{lead} conviene pivotear en pequeno: la propuesta actual esta comprimida por el mercado y por tooling IA mas generalista."
    return f"{lead} muestra senales para detenerse porque el valor central ya esta demasiado absorbido o sin traccion clara."


def _project_verdict(
    project: dict[str, Any],
    state: dict[str, Any] | None,
    ai_risk: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> tuple[str, float, list[dict[str, Any]]]:
    status = project.get("status")
    progress = project.get("progress_pct") or 0
    risk_level = ai_risk.get("risk_level")
    state_code = (state or {}).get("project_state_code")

    if project["id"] == "neytiri":
        return (
            "pivot-lite",
            0.82,
            [
                {"action": "narrow-scope", "detail": "Explorar sub-gaps concretos donde la capa de avatar no sea la propuesta completa."},
                {"action": "reuse-tech", "detail": "Revisar si algun aprendizaje sirve como capability reutilizable y no como producto standalone."},
            ],
        )

    if status == "paused" and progress < 20 and risk_level == "high":
        return (
            "stop",
            0.76,
            [{"action": "archive", "detail": "Reducir inversion hasta encontrar evidencia nueva o un gap muy especifico."}],
        )

    if status == "paused" or state_code in {3, 4}:
        return (
            "adjust",
            0.68,
            [{"action": "refresh-focus", "detail": "Definir un proximo experimento de bajo costo antes de retomar desarrollo."}],
        )

    if risk_level == "high":
        return (
            "adjust",
            0.7,
            [{"action": "specialize", "detail": "Empujar diferenciacion en datos, regulacion o workflow donde los LLMs no alcancen solos."}],
        )

    return (
        "keep",
        0.78 if project["id"] in INITIAL_PRIORITY_PROJECTS else 0.7,
        [{"action": "keep-going", "detail": "Mantener el foco actual y revisar competidores en el proximo audit semanal."}],
    )


def _candidate_verdict(
    candidate: dict[str, Any],
    kill_hits: list[dict[str, Any]],
    ai_risk: dict[str, Any],
) -> tuple[str, float, list[dict[str, Any]]]:
    hard_hits = [item for item in kill_hits if item.get("type") == "hard"]
    soft_hits = [item for item in kill_hits if item.get("type") != "hard"]
    hypothesis = (candidate.get("hypothesis") or "").lower()

    if len(hard_hits) >= 2:
        return (
            "kill",
            0.8,
            [{"title": "cerrar candidata", "why": "Hay demasiadas condiciones hard golpeadas para justificar otra vuelta."}],
        )
    if len(hard_hits) == 1:
        return (
            "iterate",
            0.69,
            [{"title": "reformular wedge", "why": "Existe una alarma fuerte, pero todavia hay margen para reposicionar el problema."}],
        )
    if (" y " in hypothesis or "/" in hypothesis) and soft_hits:
        return (
            "split",
            0.64,
            [{"title": "dividir hipotesis", "why": "La candidata parece mezclar mas de un problema y conviene separar apuestas."}],
        )
    if ai_risk.get("risk_level") == "high":
        return (
            "park",
            0.61,
            [{"title": "esperar mejor wedge", "why": "La IA generica se esta llevando el baseline y hoy no hay defensa clara."}],
        )
    return (
        "advance",
        0.76,
        [{"title": "seguir investigando", "why": "No hay hits fuertes y todavia se ve espacio para un wedge concreto."}],
    )


def _evaluate_kill_criteria(
    criteria: list[dict[str, Any]],
    *,
    competitors: list[dict[str, Any]],
    ai_risk: dict[str, Any],
    stack_findings: list[dict[str, Any]],
    topic: str,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    normalized_topic = topic.lower()
    stack_has_risk = any(item.get("status") in {"avoid-now", "watch"} for item in stack_findings)

    for criterion in criteria:
        description = (criterion.get("description") or "").lower()
        criterion_id = (criterion.get("id") or "").lower()
        hit_reason: str | None = None

        if any(token in description or token in criterion_id for token in ("ai", "llm", "commodit", "absorption", "encroach")):
            if ai_risk.get("risk_level") == "high":
                hit_reason = ai_risk["summary"]
        elif any(token in description or token in criterion_id for token in ("saturated", "incumbent", "competitor", "moat")):
            if len(competitors) >= 2:
                hit_reason = f"Ya aparecen {len(competitors)} alternativas visibles para el mismo espacio."
        elif any(token in description or token in criterion_id for token in ("obsolete", "declining", "deprecated")):
            if stack_has_risk:
                hit_reason = "El stack o el canal tienen alertas de vigencia que merecen validacion adicional."
        elif "latam" in description or "uruguay" in description:
            if not any(token in normalized_topic for token in ("latam", "uruguay", "aduana", "licit")):
                hit_reason = "La hipotesis aun no muestra una wedge especifica para LATAM/Uruguay."

        if hit_reason:
            hits.append(
                {
                    "criterion_id": criterion.get("id"),
                    "type": criterion.get("type", "soft"),
                    "reason": hit_reason,
                }
            )

    return hits


def _project_findings(
    project: dict[str, Any],
    state: dict[str, Any] | None,
    competitors: list[dict[str, Any]],
    ai_risk: dict[str, Any],
    stack_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings = [
        {
            "title": "current focus",
            "detail": (state or {}).get("current_focus") or "Sin foco explicito en project_state.",
        },
        {
            "title": "competition",
            "detail": f"Competidores visibles: {', '.join(item['name'] for item in competitors[:3])}.",
        },
        {
            "title": "ai encroachment",
            "detail": ai_risk["summary"],
        },
        {
            "title": "stack posture",
            "detail": "; ".join(item["finding"] for item in stack_findings[:2]),
        },
    ]
    if project["id"] in INITIAL_PRIORITY_PROJECTS:
        findings.append(
            {
                "title": "priority target",
                "detail": "El roadmap marca este target en la primera tanda de auditoria semanal.",
            }
        )
    return findings


def _sub_gap_proposals(candidate: dict[str, Any], verdict: str) -> list[dict[str, Any]]:
    if verdict not in {"iterate", "split"}:
        return []

    category = candidate.get("category")
    return [
        {
            "title": f"wedge {category} mas acotado",
            "description": "Bajar el scope a un nicho con buyer y resultado mas claros antes de otra ronda.",
        }
    ]


def _project_topic(project: dict[str, Any], state: dict[str, Any] | None) -> str:
    return " ".join(
        part
        for part in [
            project.get("name"),
            project.get("id"),
            (state or {}).get("current_focus"),
        ]
        if isinstance(part, str) and part
    )


def _candidate_topic(candidate: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [
            candidate.get("name"),
            candidate.get("slug"),
            candidate.get("hypothesis"),
            candidate.get("problem_desc"),
        ]
        if isinstance(part, str) and part
    )


def _resolve_agent_prompt(prompt_ref: str | None, default_name: str):
    if prompt_ref and prompt_ref.startswith("langfuse:"):
        prompt_name = prompt_ref.split(":", 1)[1]
    elif prompt_ref:
        return None, ResolvedPrompt(
            name=prompt_ref,
            prompt_ref=prompt_ref,
            text="",
            source="custom",
            is_fallback=True,
        )
    else:
        prompt_name = default_name

    client = get_langfuse_client()
    return client, resolve_prompt(prompt_name, client=client)


def _create_run(
    conn: psycopg.Connection,
    *,
    project_id: str,
    agent: str,
    mode: str,
    prompt_ref: str,
    target_type: str,
    target_id: str,
    metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "target_type": target_type,
        "target_id": target_id,
        "source": "api:/agent/run",
    }
    if metadata_extra:
        metadata.update(metadata_extra)

    return insert_row(
        conn,
        "runs",
        {
            "project_id": project_id,
            "agent": agent,
            "mode": mode,
            "prompt_ref": prompt_ref,
            "status": "running",
            "metadata": metadata,
        },
    )


def _complete_run(
    conn: psycopg.Connection,
    run: dict[str, Any],
    *,
    summary: str,
    files_touched: list[str],
    diff_stats: dict[str, Any],
    langfuse_trace_id: str | None = None,
    metadata_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(run.get("metadata") or {})
    if metadata_updates:
        metadata.update(metadata_updates)

    completed_run = update_row(
        conn,
        "runs",
        {"id": run["id"]},
        {
            "status": "completed",
            "summary": summary,
            "files_touched": files_touched,
            "diff_stats": diff_stats,
            "next_step_proposed": "Review generated report and decide the next concrete action.",
            "langfuse_trace_id": langfuse_trace_id,
            "metadata": metadata,
        },
    )
    assert completed_run is not None
    return completed_run


def _fail_run(conn: psycopg.Connection, run_id: UUID, error_text: str):
    update_row(
        conn,
        "runs",
        {"id": run_id},
        {
            "status": "failed",
            "summary": error_text[:400],
            "files_touched": [],
            "diff_stats": {"added": 0, "removed": 0, "files": 0},
            "next_step_proposed": "Inspect the failing target and retry after fixing the underlying issue.",
        },
    )


def _report_prompt_metadata(prompt, trace_id: str | None, trace_error: str | None) -> dict[str, Any]:
    if trace_id:
        langfuse_status = "traced"
    elif trace_error == "disabled":
        langfuse_status = "disabled"
    elif trace_error:
        langfuse_status = "trace-error"
    else:
        langfuse_status = "disabled"

    return {
        "prompt_ref": prompt.prompt_ref,
        "prompt_source": prompt.source,
        "prompt_fallback": prompt.is_fallback,
        "langfuse_trace_id": trace_id,
        "langfuse_status": langfuse_status,
        "langfuse_error": trace_error if trace_error and trace_error != "disabled" else None,
    }


def _update_project_state_after_run(
    conn: psycopg.Connection,
    project_id: str,
    *,
    last_run_id: UUID,
    last_audit_id: UUID | None = None,
):
    payload: dict[str, Any] = {"last_run_id": last_run_id}
    if last_audit_id is not None:
        payload["last_audit_id"] = last_audit_id
    upsert_project_state(conn, project_id, payload)


def _candidate_status_for_verdict(verdict: str) -> str:
    if verdict == "advance":
        return "promising"
    if verdict == "park":
        return "paused"
    if verdict == "kill":
        return "killed"
    return "investigating"


def _candidate_promotion_signal(conn: psycopg.Connection, candidate_id: UUID) -> dict[str, Any]:
    rows = fetch_all(
        conn,
        (
            "SELECT id, verdict, confidence, created_at "
            "FROM candidate_research_reports "
            "WHERE candidate_id = %s "
            "ORDER BY created_at DESC "
            "LIMIT 3"
        ),
        (candidate_id,),
    )

    consecutive_advances = 0
    for row in rows:
        if row.get("verdict") == "advance" and _float(row.get("confidence")) > 0.7:
            consecutive_advances += 1
            continue
        break

    ready = len(rows) >= 3 and consecutive_advances >= 3
    latest = rows[0] if rows else None
    return {
        "consecutive_advances": consecutive_advances,
        "ready": ready,
        "latest_report_id": str(latest["id"]) if latest else None,
        "latest_verdict": latest.get("verdict") if latest else None,
        "latest_confidence": _float(latest.get("confidence")) if latest else None,
        "ready_at": datetime.now(UTC).isoformat() if ready else None,
    }


def _update_candidate_after_report(
    conn: psycopg.Connection,
    candidate: dict[str, Any],
    report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    promotion_signal = _candidate_promotion_signal(conn, candidate["id"])
    metadata = dict(candidate.get("metadata") or {})
    metadata["promotion"] = promotion_signal
    metadata["last_research"] = {
        "report_id": str(report["id"]),
        "verdict": report["verdict"],
        "confidence": _float(report.get("confidence")),
    }

    status = _candidate_status_for_verdict(report["verdict"])
    updated = update_row(
        conn,
        "vertical_candidates",
        {"id": candidate["id"]},
        {
            "last_research_id": report["id"],
            "status": status,
            "kill_verdict": {
                "verdict": report["verdict"],
                "confidence": _float(report.get("confidence")),
                "report_id": str(report["id"]),
            },
            "metadata": metadata,
        },
    )
    assert updated is not None
    return updated, promotion_signal


def _project_report(conn: psycopg.Connection, project_id: str, prompt_ref: str | None = None) -> AgentExecutionResult:
    project = fetch_one(conn, "SELECT * FROM projects WHERE id = %s", (project_id,))
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    state = fetch_one(conn, "SELECT * FROM project_state WHERE project_id = %s", (project_id,))
    langfuse_client, prompt = _resolve_agent_prompt(prompt_ref, PROJECT_PROMPT_NAME)
    run = _create_run(
        conn,
        project_id=project_id,
        agent="auditor",
        mode="audit",
        prompt_ref=prompt.prompt_ref,
        target_type="project",
        target_id=project_id,
        metadata_extra={
            "prompt_source": prompt.source,
            "prompt_fallback": prompt.is_fallback,
        },
    )

    try:
        topic = _project_topic(project, state)
        search_results = web_search(topic)
        competitors = find_competitors(topic)
        ai_risk = check_ai_encroachment(topic)
        stack_findings = assess_stack(_tech_list_from_target(project, state))
        verdict, confidence, proposed_changes = _project_verdict(project, state, ai_risk, competitors)
        summary = _project_summary(project, verdict, competitors, ai_risk)
        findings = _project_findings(project, state, competitors, ai_risk, stack_findings)

        report = insert_row(
            conn,
            "audit_reports",
            {
                "project_id": project_id,
                "verdict": verdict,
                "confidence": confidence,
                "summary": summary,
                "findings": findings,
                "proposed_changes": proposed_changes,
                "evidence_refs": _evidence_refs(search_results),
                "roadmap_ref": "ROADMAP.md#sprint-5",
                "state_snapshot": _json_safe({"project": project, "state": state}),
                "metadata": {
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_source": prompt.source,
                    "prompt_fallback": prompt.is_fallback,
                    "research_provider": search_results[0]["provider"] if search_results else "stub",
                    "ai_risk": ai_risk.get("risk_level"),
                    "competitor_count": len(competitors),
                },
            },
        )

        trace_id, trace_error = record_agent_trace(
            langfuse_client,
            prompt,
            run_id=str(run["id"]),
            target_type="project",
            target_id=project_id,
            input_payload=_json_safe({"project": project, "state": state, "topic": topic}),
            output_payload=_json_safe({"summary": summary, "verdict": verdict, "report_id": report["id"]}),
            metadata={
                "project_id": project_id,
                "report_type": "audit_report",
            },
        )
        report_metadata = dict(report.get("metadata") or {})
        report_metadata.update(_report_prompt_metadata(prompt, trace_id, trace_error))
        updated_report = update_row(
            conn,
            "audit_reports",
            {"id": report["id"]},
            {"metadata": report_metadata},
        )
        assert updated_report is not None
        _update_project_state_after_run(conn, project_id, last_run_id=run["id"], last_audit_id=updated_report["id"])

        completed_run = _complete_run(
            conn,
            run,
            summary=summary,
            files_touched=["prompts/auditor-project.md"],
            diff_stats={"added": 0, "removed": 0, "files": 0},
            langfuse_trace_id=trace_id,
            metadata_updates=_report_prompt_metadata(prompt, trace_id, trace_error),
        )
        return AgentExecutionResult(
            target_type="project",
            target_id=project_id,
            run=completed_run,
            report_type="audit_report",
            report=updated_report,
            summary=summary,
        )
    except Exception as exc:
        _fail_run(conn, run["id"], f"Agent run failed: {exc}")
        raise


def _candidate_report(conn: psycopg.Connection, candidate_ref: str, prompt_ref: str | None = None) -> AgentExecutionResult:
    candidate = get_candidate_by_ref(conn, candidate_ref)
    langfuse_client, prompt = _resolve_agent_prompt(prompt_ref, CANDIDATE_PROMPT_NAME)
    run = _create_run(
        conn,
        project_id=candidate.get("parent_group") or "ashrise",
        agent="investigator",
        mode="investigate",
        prompt_ref=prompt.prompt_ref,
        target_type="candidate",
        target_id=candidate_ref,
        metadata_extra={
            "candidate_id": str(candidate["id"]),
            "prompt_source": prompt.source,
            "prompt_fallback": prompt.is_fallback,
        },
    )

    try:
        template = fetch_one(
            conn,
            (
                "SELECT * FROM kill_criteria_templates "
                "WHERE category = %s AND is_active = true "
                "ORDER BY version DESC "
                "LIMIT 1"
            ),
            (candidate["category"],),
        )
        criteria = list(candidate.get("kill_criteria") or [])
        if not criteria and template is not None:
            criteria = list(template.get("criteria") or [])

        topic = _candidate_topic(candidate)
        search_results = web_search(topic)
        competitors = find_competitors(topic)
        ai_risk = check_ai_encroachment(topic)
        stack_findings = assess_stack(_tech_list_from_target(candidate))
        kill_hits = _evaluate_kill_criteria(
            criteria,
            competitors=competitors,
            ai_risk=ai_risk,
            stack_findings=stack_findings,
            topic=topic,
        )
        verdict, confidence, next_steps = _candidate_verdict(candidate, kill_hits, ai_risk)
        summary = (
            f"{candidate['name']} queda en verdict '{verdict}' con {len(kill_hits)} hits relevantes "
            f"y riesgo AI {ai_risk['risk_level']}."
        )
        report = insert_row(
            conn,
            "candidate_research_reports",
            {
                "candidate_id": candidate["id"],
                "verdict": verdict,
                "confidence": confidence,
                "summary": summary,
                "competitors_found": competitors,
                "market_signals": _market_signals(search_results),
                "stack_findings": stack_findings,
                "kill_criteria_hits": kill_hits,
                "ai_encroachment": ai_risk["summary"],
                "sub_gap_proposals": _sub_gap_proposals(candidate, verdict),
                "proposed_next_steps": next_steps,
                "evidence_refs": _evidence_refs(search_results),
                "kill_template_id": template["id"] if template else None,
                "prompt_ref": prompt.prompt_ref,
                "candidate_snapshot": _json_safe(candidate),
                "metadata": {
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_source": prompt.source,
                    "prompt_fallback": prompt.is_fallback,
                    "kill_template_prompt_ref": template.get("prompt_ref") if template else None,
                    "research_provider": search_results[0]["provider"] if search_results else "stub",
                    "criteria_count": len(criteria),
                    "hard_hits": len([item for item in kill_hits if item.get("type") == "hard"]),
                },
            },
        )

        trace_id, trace_error = record_agent_trace(
            langfuse_client,
            prompt,
            run_id=str(run["id"]),
            target_type="candidate",
            target_id=candidate_ref,
            input_payload=_json_safe({"candidate": candidate, "topic": topic, "kill_template": template}),
            output_payload=_json_safe({"summary": summary, "verdict": verdict, "report_id": report["id"]}),
            metadata={
                "candidate_id": str(candidate["id"]),
                "candidate_slug": candidate["slug"],
                "report_type": "candidate_research_report",
            },
        )

        report_metadata = dict(report.get("metadata") or {})
        report_metadata.update(_report_prompt_metadata(prompt, trace_id, trace_error))
        updated_report = update_row(
            conn,
            "candidate_research_reports",
            {"id": report["id"]},
            {"metadata": report_metadata},
        )
        assert updated_report is not None

        updated_candidate, promotion_signal = _update_candidate_after_report(conn, candidate, updated_report)
        report_metadata = dict(updated_report.get("metadata") or {})
        report_metadata["promotion_signal"] = promotion_signal
        updated_report = update_row(
            conn,
            "candidate_research_reports",
            {"id": updated_report["id"]},
            {"metadata": report_metadata},
        )
        assert updated_report is not None

        completed_run = _complete_run(
            conn,
            run,
            summary=summary,
            files_touched=["prompts/investigator-candidate.md"],
            diff_stats={"added": 0, "removed": 0, "files": 0},
            langfuse_trace_id=trace_id,
            metadata_updates={
                **_report_prompt_metadata(prompt, trace_id, trace_error),
                "promotion_ready": promotion_signal["ready"],
                "consecutive_advances": promotion_signal["consecutive_advances"],
                "candidate_status": updated_candidate["status"],
            },
        )
        return AgentExecutionResult(
            target_type="candidate",
            target_id=candidate_ref,
            run=completed_run,
            report_type="candidate_research_report",
            report=updated_report,
            summary=summary,
        )
    except Exception as exc:
        _fail_run(conn, run["id"], f"Agent run failed: {exc}")
        raise


def run_unified_agent(
    conn: psycopg.Connection,
    *,
    target_type: Literal["project", "candidate"],
    target_id: str,
    prompt_ref: str | None = None,
) -> AgentExecutionResult:
    if target_type == "project":
        return _project_report(conn, target_id, prompt_ref=prompt_ref)
    return _candidate_report(conn, target_id, prompt_ref=prompt_ref)


def prioritized_weekly_targets(conn: psycopg.Connection) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(target_type: str, target_id: str | None):
        if not target_id:
            return
        item = (target_type, target_id)
        if item in seen:
            return
        seen.add(item)
        targets.append(item)

    for project_id in INITIAL_PRIORITY_PROJECTS:
        row = fetch_one(conn, "SELECT id FROM projects WHERE id = %s", (project_id,))
        if row:
            add("project", row["id"])

    for row in fetch_all(conn, "SELECT id FROM projects WHERE status = 'active' ORDER BY priority NULLS LAST, created_at, id"):
        add("project", row["id"])

    for row in fetch_all(
        conn,
        (
            "SELECT candidate_id, project_id "
            "FROM research_queue "
            "WHERE status = 'pending' "
            "ORDER BY scheduled_for, priority, created_at"
        ),
    ):
        if row.get("project_id"):
            add("project", row["project_id"])
        if row.get("candidate_id"):
            add("candidate", str(row["candidate_id"]))

    return targets
