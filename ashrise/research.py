from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, date, datetime
import os
import re
from typing import Any
import unicodedata
from urllib.parse import urlparse

import httpx

from ashrise.langfuse_support import get_langfuse_client, record_research_trace
from ashrise.sanitization import redact_sensitive_text, sanitize_for_metadata


TAVILY_BASE_URL = "https://api.tavily.com"
TAVILY_SEARCH_PATH = "/search"
TAVILY_MAX_RESULTS = 5
DEFAULT_OPERATION_TIMEOUT = 10.0
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_COUNT = 5
GENERIC_PROVIDER_NAMES = {"generic", "remote"}
EXCLUDED_COMPETITOR_NAMES = {
    "brave",
    "chatgpt",
    "crunchbase",
    "capterra",
    "forbes",
    "g2",
    "google",
    "linkedin",
    "medium",
    "reddit",
    "software advice",
    "softwareadvice",
    "tavily",
    "wikipedia",
    "youtube",
}
AI_SIGNAL_TOKENS = {
    "agent",
    "agents",
    "ai",
    "artificial intelligence",
    "automation",
    "autonomous",
    "copilot",
    "genai",
    "generative ai",
    "llm",
}
STRONG_STACK_RISK_TOKENS = {
    "deprecated",
    "deprecation",
    "discontinued",
    "eol",
    "end-of-life",
    "legacy",
    "sunset",
}
WEAK_STACK_RISK_TOKENS = {
    "breaking change",
    "migration",
    "rewrite",
    "security patch",
}
PROVIDER_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "con",
    "de",
    "del",
    "el",
    "en",
    "for",
    "la",
    "las",
    "los",
    "of",
    "para",
    "the",
    "un",
    "una",
    "y",
}
PROVIDER_QUERY_NOISE_TOKENS = {
    "actual",
    "current",
    "demo",
    "demostrable",
    "diferenciacion",
    "focus",
    "foco",
    "milestone",
    "mvp",
    "next",
    "paso",
    "polish",
    "priority",
    "proximo",
    "pulido",
    "roadmap",
    "ship",
    "sprint",
    "step",
    "todo",
    "v1",
    "v2",
}
_RESEARCH_TRACE_CONTEXT: ContextVar["ResearchTraceContext | None"] = ContextVar(
    "ashrise_research_trace_context",
    default=None,
)
TAVILY_COUNTRY_MAP = {
    "ar": "argentina",
    "br": "brazil",
    "cl": "chile",
    "co": "colombia",
    "es": "spain",
    "mx": "mexico",
    "pe": "peru",
    "pt": "portugal",
    "us": "united states",
    "uy": "uruguay",
}


@dataclass(frozen=True)
class ResearchSettings:
    provider: str
    base_url: str | None
    api_key: str | None
    project_id: str | None
    timeout: float
    region: str
    country: str
    search_lang: str

    @classmethod
    def from_env(cls) -> "ResearchSettings":
        provider = (os.getenv("ASHRISE_RESEARCH_PROVIDER") or "stub").strip().lower()
        base_url = (os.getenv("ASHRISE_RESEARCH_BASE_URL") or "").strip() or None
        if provider == "tavily" and base_url is None:
            base_url = TAVILY_BASE_URL
        elif provider == "brave" and base_url is None:
            base_url = BRAVE_SEARCH_URL

        return cls(
            provider=provider,
            base_url=base_url,
            api_key=(os.getenv("ASHRISE_RESEARCH_API_KEY") or "").strip() or None,
            project_id=(os.getenv("ASHRISE_RESEARCH_PROJECT_ID") or "").strip() or None,
            timeout=float(os.getenv("ASHRISE_RESEARCH_TIMEOUT", str(DEFAULT_OPERATION_TIMEOUT))),
            region=(os.getenv("ASHRISE_RESEARCH_REGION") or "LATAM").strip() or "LATAM",
            country=(os.getenv("ASHRISE_RESEARCH_COUNTRY") or "UY").strip() or "UY",
            search_lang=(os.getenv("ASHRISE_RESEARCH_SEARCH_LANG") or "es").strip() or "es",
        )


@dataclass(frozen=True)
class ResearchTraceContext:
    run_id: str
    target_type: str
    target_id: str
    prompt_ref: str | None = None


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
    "langfuse": ("stable", "Langfuse ya cubre prompts y trazabilidad minima del stack local."),
    "telegram": ("stable", "Polling simple es suficiente para el volumen actual."),
    "docker": ("stable", "Docker Compose mantiene el flujo repo-local reproducible."),
}


def _normalize(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def _simplify_provider_query(query: str) -> str:
    ascii_query = (
        unicodedata.normalize("NFKD", query)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    tokens = re.findall(r"[a-z0-9]+", ascii_query)
    simplified: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        if token in seen:
            continue
        if token in PROVIDER_QUERY_STOPWORDS or token in PROVIDER_QUERY_NOISE_TOKENS:
            continue
        if len(token) < 2:
            continue
        seen.add(token)
        simplified.append(token)
        if len(simplified) >= 8:
            break

    return " ".join(simplified)


def _profile_for_topic(topic: str) -> dict[str, Any]:
    normalized = _normalize(topic)
    for profile in STUB_PROFILES:
        if any(keyword in normalized for keyword in profile["keywords"]):
            return profile
    return DEFAULT_PROFILE


def _provider_missing_reason(settings: ResearchSettings) -> str | None:
    if settings.provider == "stub":
        return None
    if settings.provider == "tavily":
        if not settings.api_key:
            return "Tavily requiere ASHRISE_RESEARCH_API_KEY."
        return None
    if settings.provider == "brave":
        if not settings.api_key:
            return "Brave Search requiere ASHRISE_RESEARCH_API_KEY."
        return None
    if settings.provider in GENERIC_PROVIDER_NAMES:
        if not settings.base_url or not settings.api_key:
            return "El provider generico requiere ASHRISE_RESEARCH_BASE_URL y ASHRISE_RESEARCH_API_KEY."
        return None
    return f"Provider de research '{settings.provider}' no soportado; usando fallback stub."


def _freshness_for_days(recency_days: int) -> str:
    if recency_days <= 1:
        return "pd"
    if recency_days <= 7:
        return "pw"
    if recency_days <= 31:
        return "pm"
    return "py"


def _time_range_for_days(recency_days: int) -> str | None:
    if recency_days <= 0:
        return None
    if recency_days <= 1:
        return "day"
    if recency_days <= 7:
        return "week"
    if recency_days <= 31:
        return "month"
    return "year"


def _days_from_age(value: Any, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return default

    match = re.search(r"(\d+)\s+(hour|day|week|month|year)", value.lower())
    if not match:
        return default

    amount = int(match.group(1))
    unit = match.group(2)
    if unit == "hour":
        return 0
    if unit == "day":
        return amount
    if unit == "week":
        return amount * 7
    if unit == "month":
        return amount * 30
    if unit == "year":
        return amount * 365
    return default


def _days_from_published_date(value: Any, default: int) -> int:
    if not isinstance(value, str) or not value.strip():
        return default

    normalized = value.strip().replace("Z", "+00:00")
    try:
        published_at = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            published_at = datetime.combine(date.fromisoformat(value[:10]), datetime.min.time(), tzinfo=UTC)
        except ValueError:
            return default

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - published_at.astimezone(UTC)).days)


def _country_for_tavily(country: str) -> str | None:
    normalized = country.strip().lower()
    if not normalized:
        return None
    if len(normalized) == 2:
        return TAVILY_COUNTRY_MAP.get(normalized)
    return normalized


def _trace_provider_usage(
    *,
    provider: str,
    operation: str,
    query: str,
    metadata: dict[str, Any],
    output_payload: dict[str, Any],
):
    context = _RESEARCH_TRACE_CONTEXT.get()
    if context is None:
        return

    client = get_langfuse_client()
    record_research_trace(
        client,
        run_id=context.run_id,
        target_type=context.target_type,
        target_id=context.target_id,
        prompt_ref=context.prompt_ref,
        provider=provider,
        operation=operation,
        input_payload=sanitize_for_metadata({"query": query}),
        output_payload=sanitize_for_metadata(output_payload),
        metadata=sanitize_for_metadata(metadata),
    )


@contextmanager
def research_trace_context(
    *,
    run_id: str,
    target_type: str,
    target_id: str,
    prompt_ref: str | None = None,
) -> Iterator[None]:
    token = _RESEARCH_TRACE_CONTEXT.set(
        ResearchTraceContext(
            run_id=run_id,
            target_type=target_type,
            target_id=target_id,
            prompt_ref=prompt_ref,
        )
    )
    try:
        yield
    finally:
        _RESEARCH_TRACE_CONTEXT.reset(token)


def _build_stub_search_results(
    query: str,
    *,
    fallback_reason: str | None = None,
) -> list[dict[str, Any]]:
    profile = _profile_for_topic(query)
    results: list[dict[str, Any]] = []
    for row in profile["search_results"]:
        result = dict(row)
        result["provider"] = "stub"
        result["fallback"] = True
        result["query"] = query
        if fallback_reason:
            result["fallback_reason"] = redact_sensitive_text(fallback_reason)
        results.append(result)
    return results


def _build_stub_competitors(
    topic: str,
    *,
    region: str,
    fallback_reason: str | None = None,
) -> list[dict[str, Any]]:
    profile = _profile_for_topic(topic)
    competitors: list[dict[str, Any]] = []
    for row in profile["competitors"]:
        competitor = dict(row)
        competitor["provider"] = "stub"
        competitor["fallback"] = True
        competitor["search_region"] = region
        if fallback_reason:
            competitor["fallback_reason"] = redact_sensitive_text(fallback_reason)
        competitors.append(competitor)
    return competitors


def _build_stub_ai_risk(topic: str, *, fallback_reason: str | None = None) -> dict[str, Any]:
    profile = _profile_for_topic(topic)
    result = dict(profile["ai_risk"])
    result["provider"] = "stub"
    result["fallback"] = True
    result["topic"] = topic
    if fallback_reason:
        result["fallback_reason"] = redact_sensitive_text(fallback_reason)
    return result


def _tokenize_name(value: str) -> str:
    cleaned = re.split(r"[-|:]", value, maxsplit=1)[0]
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    return " ".join(cleaned.split())


def _hostname_label(url: str) -> str | None:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return None
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if "." not in hostname:
        return hostname
    label = hostname.split(".")[0]
    return label.replace("-", " ").strip()


def _candidate_competitor_names(result: dict[str, Any]) -> list[str]:
    names: list[str] = []
    title = result.get("title")
    if isinstance(title, str) and title:
        names.append(_tokenize_name(title))
    url = result.get("url")
    if isinstance(url, str) and url:
        hostname_label = _hostname_label(url)
        if hostname_label:
            names.append(hostname_label)
    return names


def _clean_competitor_name(value: str) -> str | None:
    name = _normalize(value)
    if not name or len(name) < 3:
        return None
    if name in EXCLUDED_COMPETITOR_NAMES:
        return None
    if any(token in name for token in ("review", "search", "news", "list of", "top ")):
        return None
    return " ".join(part.capitalize() for part in name.split())


def _extract_competitors_from_results(
    topic: str,
    region: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    competitors: list[dict[str, Any]] = []
    normalized_topic = _normalize(topic)

    for result in results:
        for raw_name in _candidate_competitor_names(result):
            name = _clean_competitor_name(raw_name)
            if not name:
                continue
            normalized_name = _normalize(name)
            if normalized_name in seen or normalized_name in normalized_topic:
                continue
            seen.add(normalized_name)
            competitors.append(
                {
                    "name": name,
                    "region": region,
                    "why_it_matters": result.get("snippet") or "Aparece repetido en resultados del mercado relevante.",
                    "provider": result.get("provider", "stub"),
                    "fallback": bool(result.get("fallback")),
                    "search_region": region,
                }
            )
            if len(competitors) >= 3:
                return competitors
    return competitors


def _ai_risk_from_results(topic: str, results: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not results:
        return None

    score = 0
    evidence: list[str] = []
    for result in results[:3]:
        text = " ".join(
            str(part)
            for part in [
                result.get("title", ""),
                result.get("snippet", ""),
            ]
        ).lower()
        matches = sorted(token for token in AI_SIGNAL_TOKENS if token in text)
        if matches:
            score += len(matches)
            evidence.append(result.get("title") or result.get("snippet") or "market signal")

    if score >= 4:
        level = "high"
        summary = (
            f"Hay senales externas fuertes de que {topic} ya convive con tooling IA/automation bastante visible."
        )
    elif score >= 2:
        level = "medium-high"
        summary = f"Se ve presion de IA generica sobre {topic}, aunque todavia no es absorcion total."
    elif score >= 1:
        level = "medium"
        summary = f"Empieza a verse IA generica entrando en {topic}; conviene diferenciar mejor el wedge."
    else:
        return None

    return {
        "risk_level": level,
        "summary": summary,
        "provider": results[0].get("provider", "stub"),
        "fallback": bool(results[0].get("fallback")),
        "topic": topic,
        "signals": evidence[:3],
    }


def _normalize_brave_rows(payload: dict[str, Any], query: str, recency_days: int) -> list[dict[str, Any]]:
    web_payload = payload.get("web") if isinstance(payload, dict) else None
    rows = web_payload.get("results") if isinstance(web_payload, dict) else None
    if not isinstance(rows, list):
        return []

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_rows.append(
            {
                "title": row.get("title") or query,
                "url": row.get("url") or "https://search.brave.com",
                "snippet": row.get("description") or "",
                "extra_snippets": row.get("extra_snippets") or [],
                "published_days_ago": _days_from_age(row.get("age"), recency_days),
                "provider": "brave",
                "fallback": False,
                "query": query,
            }
        )
    return normalized_rows


def _normalize_tavily_rows(payload: dict[str, Any], query: str, recency_days: int) -> list[dict[str, Any]]:
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_rows.append(
            {
                "title": row.get("title") or query,
                "url": row.get("url") or f"{TAVILY_BASE_URL}/search",
                "snippet": row.get("content") or "",
                "published_days_ago": _days_from_published_date(row.get("published_date"), recency_days),
                "provider": "tavily",
                "fallback": False,
                "query": query,
                "score": row.get("score"),
            }
        )
    return normalized_rows


def _tavily_search(query: str, recency_days: int, settings: ResearchSettings) -> list[dict[str, Any]]:
    request_body: dict[str, Any] = {
        "query": query,
        "search_depth": "basic",
        "max_results": TAVILY_MAX_RESULTS,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
    }
    time_range = _time_range_for_days(recency_days)
    if time_range:
        request_body["time_range"] = time_range

    country = _country_for_tavily(settings.country)
    if country:
        request_body["country"] = country

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.api_key or ''}",
    }
    if settings.project_id:
        headers["X-Project-ID"] = settings.project_id

    with httpx.Client(timeout=settings.timeout) as client:
        response = client.post(
            f"{(settings.base_url or TAVILY_BASE_URL).rstrip('/')}{TAVILY_SEARCH_PATH}",
            json=request_body,
            headers=headers,
        )
        response.raise_for_status()
        return _normalize_tavily_rows(response.json(), query, recency_days)


def _brave_web_search(query: str, recency_days: int, settings: ResearchSettings) -> list[dict[str, Any]]:
    params = {
        "q": query,
        "count": BRAVE_COUNT,
        "freshness": _freshness_for_days(recency_days),
        "country": settings.country,
        "search_lang": settings.search_lang,
        "extra_snippets": "true",
    }
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": settings.api_key or "",
    }

    with httpx.Client(timeout=settings.timeout) as client:
        response = client.get(settings.base_url or BRAVE_SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()
        return _normalize_brave_rows(response.json(), query, recency_days)


def _generic_remote_search(query: str, recency_days: int, settings: ResearchSettings) -> list[dict[str, Any]]:
    with httpx.Client(timeout=settings.timeout) as client:
        response = client.get(
            f"{(settings.base_url or '').rstrip('/')}/search",
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
        return []

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
                "query": query,
            }
        )
    return normalized_rows


def _provider_search(
    query: str,
    recency_days: int,
    settings: ResearchSettings,
    *,
    operation: str,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if settings.provider == "stub":
        return None, None

    missing_reason = _provider_missing_reason(settings)
    if missing_reason:
        return None, missing_reason

    def _request(request_query: str) -> list[dict[str, Any]]:
        if settings.provider == "tavily":
            return _tavily_search(request_query, recency_days, settings)
        if settings.provider == "brave":
            return _brave_web_search(request_query, recency_days, settings)
        if settings.provider in GENERIC_PROVIDER_NAMES:
            return _generic_remote_search(request_query, recency_days, settings)
        raise ValueError(f"Provider de research '{settings.provider}' no soportado; usando fallback stub.")

    attempted_queries = [query]
    simplified_query = _simplify_provider_query(query)
    if simplified_query and simplified_query != query:
        attempted_queries.append(simplified_query)

    try:
        for request_query in attempted_queries:
            results = _request(request_query)
            if results:
                trace_metadata = {
                    "result_count": len(results),
                    "fallback": False,
                    "attempted_queries": attempted_queries,
                    "request_query": request_query,
                }
                if settings.project_id:
                    trace_metadata["provider_project_id"] = settings.project_id
                _trace_provider_usage(
                    provider=settings.provider,
                    operation=operation,
                    query=query,
                    metadata=trace_metadata,
                    output_payload={"result_count": len(results)},
                )
                return results, None

        empty_reason = (
            f"El provider {settings.provider} no devolvio resultados utiles para la query; usando fallback stub."
        )
        trace_metadata = {
            "fallback": True,
            "error": empty_reason,
            "empty_result": True,
            "attempted_queries": attempted_queries,
        }
        if settings.project_id:
            trace_metadata["provider_project_id"] = settings.project_id
        _trace_provider_usage(
            provider=settings.provider,
            operation=operation,
            query=query,
            metadata=trace_metadata,
            output_payload={"result_count": 0, "error": empty_reason},
        )
        return None, empty_reason
    except Exception as exc:  # pragma: no cover - network/failure path exercised through API fallback tests
        safe_error = redact_sensitive_text(str(exc))
        trace_metadata = {"fallback": True, "error": safe_error}
        if settings.project_id:
            trace_metadata["provider_project_id"] = settings.project_id
        _trace_provider_usage(
            provider=settings.provider,
            operation=operation,
            query=query,
            metadata=trace_metadata,
            output_payload={"result_count": 0, "error": safe_error},
        )
        return None, safe_error


def web_search(query: str, recency_days: int = 30) -> list[dict[str, Any]]:
    settings = ResearchSettings.from_env()
    remote, fallback_reason = _provider_search(query, recency_days, settings, operation="web_search")
    if remote:
        return remote
    return _build_stub_search_results(query, fallback_reason=fallback_reason)


def find_competitors(topic: str, region: str = "LATAM") -> list[dict[str, Any]]:
    settings = ResearchSettings.from_env()
    provider_region = region or settings.region
    query = f"{topic} competitors software {provider_region}"
    remote, fallback_reason = _provider_search(query, 30, settings, operation="find_competitors")
    if remote:
        competitors = _extract_competitors_from_results(topic, provider_region, remote)
        if competitors:
            return competitors
        fallback_reason = "El provider no devolvio competidores claros; usando fallback stub."

    return _build_stub_competitors(topic, region=provider_region, fallback_reason=fallback_reason)


def check_ai_encroachment(topic: str) -> dict[str, Any]:
    settings = ResearchSettings.from_env()
    query = f"{topic} AI automation LLM copilots"
    remote, fallback_reason = _provider_search(query, 30, settings, operation="check_ai_encroachment")
    if remote:
        risk = _ai_risk_from_results(topic, remote)
        if risk is not None:
            return risk
        fallback_reason = "El provider no devolvio senales suficientes de AI encroachment; usando fallback stub."

    return _build_stub_ai_risk(topic, fallback_reason=fallback_reason)


def _provider_stack_finding(tech: str, settings: ResearchSettings) -> dict[str, Any] | None:
    query = f"{tech} roadmap adoption stability deprecation"
    remote, fallback_reason = _provider_search(query, 365, settings, operation="assess_stack")
    if not remote:
        return None if fallback_reason is None else {"fallback_reason": fallback_reason}

    first = remote[0]
    snippet = " ".join(
        str(part)
        for part in [first.get("title", ""), first.get("snippet", "")]
    ).lower()
    status, finding = STACK_NOTES.get(
        _normalize(tech),
        ("watch", f"{tech} no tiene regla explicita; conviene revisarlo con evidencia externa."),
    )

    if any(token in snippet for token in STRONG_STACK_RISK_TOKENS):
        status = "avoid-now"
    elif any(token in snippet for token in WEAK_STACK_RISK_TOKENS) and status == "stable":
        status = "watch"

    provider_finding = first.get("snippet") or finding
    return {
        "technology": tech,
        "status": status,
        "finding": provider_finding,
        "provider": first.get("provider", settings.provider),
        "fallback": False,
        "evidence_url": first.get("url"),
    }


def assess_stack(tech_list: list[str]) -> list[dict[str, Any]]:
    if not tech_list:
        return [
            {
                "technology": "unknown",
                "status": "needs-input",
                "finding": "No hay stack explicito; se usa fallback para no bloquear la auditoria.",
                "provider": "stub",
                "fallback": True,
            }
        ]

    settings = ResearchSettings.from_env()
    findings: list[dict[str, Any]] = []
    fallback_reasons: list[str] = []
    for tech in tech_list:
        provider_finding = None
        if settings.provider != "stub":
            provider_finding = _provider_stack_finding(tech, settings)

        if provider_finding and "technology" in provider_finding:
            findings.append(provider_finding)
            continue

        if provider_finding and provider_finding.get("fallback_reason"):
            fallback_reasons.append(provider_finding["fallback_reason"])

        normalized = _normalize(tech)
        status, finding = STACK_NOTES.get(
            normalized,
            ("watch", f"{tech} no tiene regla explicita; conviene revisarlo con evidencia externa cuando exista provider."),
        )
        row = {
            "technology": tech,
            "status": status,
            "finding": finding,
            "provider": "stub",
            "fallback": True,
        }
        if fallback_reasons:
            row["fallback_reason"] = fallback_reasons[-1]
        findings.append(row)
    return findings
