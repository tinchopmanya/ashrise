from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import httpx


@dataclass(frozen=True)
class ResearchSettings:
    provider: str
    base_url: str | None
    api_key: str | None
    timeout: float

    @classmethod
    def from_env(cls) -> "ResearchSettings":
        return cls(
            provider=(os.getenv("ASHRISE_RESEARCH_PROVIDER") or "stub").strip().lower(),
            base_url=(os.getenv("ASHRISE_RESEARCH_BASE_URL") or "").strip() or None,
            api_key=(os.getenv("ASHRISE_RESEARCH_API_KEY") or "").strip() or None,
            timeout=float(os.getenv("ASHRISE_RESEARCH_TIMEOUT", "10")),
        )


STUB_PROFILES = [
    {
        "keywords": ("licit", "procurement", "tender", "aduana"),
        "search_results": [
            {
                "title": "Veritrade licitaciones y comercio exterior",
                "url": "stub://veritrade-licitaciones",
                "snippet": "Suite regional con foco en datos de comercio y monitoreo competitivo para procurement LATAM.",
                "published_days_ago": 12,
            },
            {
                "title": "SmartDATA public procurement intelligence",
                "url": "stub://smartdata-procurement",
                "snippet": "Oferta centrada en monitoreo, alertas y analitica de licitaciones publicas.",
                "published_days_ago": 19,
            },
            {
                "title": "Equipos siguen resolviendo compliance con hojas y alertas manuales",
                "url": "stub://manual-procurement-ops",
                "snippet": "Persisten flujos manuales para seguimiento de pliegos, fechas y validacion regulatoria.",
                "published_days_ago": 7,
            },
        ],
        "competitors": [
            {
                "name": "Veritrade",
                "region": "LATAM",
                "why_it_matters": "Tiene marca y datasets regionales utiles para intelligence comercial.",
            },
            {
                "name": "SmartDATA",
                "region": "LATAM",
                "why_it_matters": "Compite en monitoreo y alertas para licitaciones publicas.",
            },
        ],
        "ai_risk": {
            "risk_level": "medium",
            "summary": "Los LLMs ayudan a resumir pliegos, pero no reemplazan monitoreo regulatorio ni flujo operativo continuo.",
        },
    },
    {
        "keywords": ("neytiri", "avatar", "lip", "video", "voice"),
        "search_results": [
            {
                "title": "HeyGen acelera video avatar con templates listos",
                "url": "stub://heygen-avatar",
                "snippet": "El mercado de avatar video ya tiene tooling muy accesible con buena UX.",
                "published_days_ago": 9,
            },
            {
                "title": "Synthesia consolida training y avatar corporate",
                "url": "stub://synthesia-training",
                "snippet": "La propuesta corporate madura sube la vara para features genericas de avatar.",
                "published_days_ago": 15,
            },
            {
                "title": "D-ID sigue cubriendo talking head y lip sync basico",
                "url": "stub://did-talking-head",
                "snippet": "La funcionalidad base esta bastante comoditizada por proveedores listos para usar.",
                "published_days_ago": 21,
            },
        ],
        "competitors": [
            {
                "name": "HeyGen",
                "region": "Global",
                "why_it_matters": "Empuja fuerte en avatar video y simplifica el baseline de producto.",
            },
            {
                "name": "Synthesia",
                "region": "Global",
                "why_it_matters": "Tiene distribucion y casos enterprise que levantan la expectativa del usuario.",
            },
            {
                "name": "D-ID",
                "region": "Global",
                "why_it_matters": "Cubre talking heads y lip sync listo para integrar.",
            },
        ],
        "ai_risk": {
            "risk_level": "high",
            "summary": "El valor base de avatar y lip-sync esta siendo absorbido por plataformas generalistas y APIs listas para usar.",
        },
    },
    {
        "keywords": ("quick win", "small-qw", "vertical", "search", "continue search"),
        "search_results": [
            {
                "title": "Consultorias chicas siguen comprando discovery acelerado",
                "url": "stub://quickwin-discovery",
                "snippet": "Sigue habiendo demanda por nichos pequenos si la entrega encuentra una wedge concreta.",
                "published_days_ago": 13,
            },
            {
                "title": "Exploding Topics y discovery tools elevan el baseline",
                "url": "stub://discovery-tools",
                "snippet": "La competencia indirecta viene de herramientas que priorizan tendencias y tracking simple.",
                "published_days_ago": 16,
            },
        ],
        "competitors": [
            {
                "name": "Exploding Topics",
                "region": "Global",
                "why_it_matters": "Compite en discovery y priorizacion temprana de oportunidades.",
            },
            {
                "name": "consultoria manual especializada",
                "region": "LATAM",
                "why_it_matters": "Sigue capturando proyectos pequenos cuando el wedge es muy especifico.",
            },
        ],
        "ai_risk": {
            "risk_level": "medium-high",
            "summary": "Los LLMs simplifican discovery generico; el valor aparece cuando hay criterio, nicho y seguimiento operativo.",
        },
    },
]

DEFAULT_PROFILE = {
    "search_results": [
        {
            "title": "Mercado con herramientas y trabajo manual coexistiendo",
            "url": "stub://generic-market-signal",
            "snippet": "Todavia hay espacio para propuestas concretas si el problema esta bien acotado.",
            "published_days_ago": 10,
        }
    ],
    "competitors": [
        {
            "name": "flujo manual interno",
            "region": "LATAM",
            "why_it_matters": "En muchos nichos el competidor real sigue siendo resolver el problema a mano.",
        }
    ],
    "ai_risk": {
        "risk_level": "medium",
        "summary": "La IA generica cubre partes del trabajo, pero suele faltar packaging y contexto de dominio.",
    },
}

STACK_NOTES = {
    "fastapi": ("stable", "FastAPI sigue siendo una opcion ligera y estable para servicios internos."),
    "postgres": ("stable", "Postgres 15+ cubre bien el scope del workflow y auditoria."),
    "temporal": ("avoid-now", "Temporal agrega complejidad operativa que el roadmap posterga."),
    "langfuse": ("later", "Langfuse entra despues; por ahora conviene dejar solo prompt_ref."),
    "telegram": ("stable", "Polling simple es suficiente para el volumen actual."),
    "docker": ("stable", "Docker Compose mantiene el flujo repo-local reproducible."),
}


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _profile_for_topic(topic: str) -> dict[str, Any]:
    normalized = _normalize(topic)
    for profile in STUB_PROFILES:
        if any(keyword in normalized for keyword in profile["keywords"]):
            return profile
    return DEFAULT_PROFILE


def _remote_search(query: str, recency_days: int, settings: ResearchSettings) -> list[dict[str, Any]] | None:
    if settings.provider == "stub" or not settings.base_url or not settings.api_key:
        return None

    with httpx.Client(timeout=settings.timeout) as client:
        response = client.get(
            f"{settings.base_url.rstrip('/')}/search",
            params={"q": query, "recency_days": recency_days},
            headers={"Authorization": f"Bearer {settings.api_key}"},
        )
        response.raise_for_status()
        payload = response.json()

    if isinstance(payload, dict):
        rows = payload.get("results")
    else:
        rows = payload

    if not isinstance(rows, list):
        return None

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_rows.append(
            {
                "title": row.get("title") or row.get("name") or query,
                "url": row.get("url") or row.get("link") or "remote://search-result",
                "snippet": row.get("snippet") or row.get("summary") or "",
                "published_days_ago": row.get("published_days_ago") or row.get("age_days") or recency_days,
                "provider": settings.provider,
                "fallback": False,
            }
        )
    return normalized_rows or None


def web_search(query: str, recency_days: int = 30) -> list[dict[str, Any]]:
    settings = ResearchSettings.from_env()
    try:
        remote = _remote_search(query, recency_days, settings)
    except Exception as exc:  # pragma: no cover - exercised via fallback path
        remote = None
        fallback_reason = str(exc)
    else:
        fallback_reason = None

    if remote:
        return remote

    profile = _profile_for_topic(query)
    results: list[dict[str, Any]] = []
    for row in profile["search_results"]:
        result = dict(row)
        result["provider"] = "stub"
        result["fallback"] = True
        result["query"] = query
        if fallback_reason:
            result["fallback_reason"] = fallback_reason
        results.append(result)
    return results


def find_competitors(topic: str, region: str = "LATAM") -> list[dict[str, Any]]:
    profile = _profile_for_topic(topic)
    competitors: list[dict[str, Any]] = []
    for row in profile["competitors"]:
        competitor = dict(row)
        competitor["provider"] = "stub"
        competitor["search_region"] = region
        competitors.append(competitor)
    return competitors


def check_ai_encroachment(topic: str) -> dict[str, Any]:
    profile = _profile_for_topic(topic)
    result = dict(profile["ai_risk"])
    result["provider"] = "stub"
    result["topic"] = topic
    return result


def assess_stack(tech_list: list[str]) -> list[dict[str, Any]]:
    if not tech_list:
        return [
            {
                "technology": "unknown",
                "status": "needs-input",
                "finding": "No hay stack explicito; se usa fallback para no bloquear la auditoria.",
                "provider": "stub",
            }
        ]

    findings: list[dict[str, Any]] = []
    for tech in tech_list:
        normalized = _normalize(tech)
        status, finding = STACK_NOTES.get(
            normalized,
            ("watch", f"{tech} no tiene regla explicita; conviene revisarlo con evidencia externa cuando exista provider."),
        )
        findings.append(
            {
                "technology": tech,
                "status": status,
                "finding": finding,
                "provider": "stub",
            }
        )
    return findings

