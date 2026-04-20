from __future__ import annotations

import os
import re
from typing import Any


SECRET_ENV_NAMES = (
    "ASHRISE_TOKEN",
    "ASHRISE_RESEARCH_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
)
SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)([a-z0-9._\-]+)"),
    re.compile(r"(?i)(x-subscription-token\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(secret[_-]?key\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s,;]+)"),
)


def redact_sensitive_text(value: str | None) -> str | None:
    if value is None:
        return None

    redacted = value
    for env_name in SECRET_ENV_NAMES:
        env_value = (os.getenv(env_name) or "").strip()
        if env_value and len(env_value) >= 4:
            redacted = redacted.replace(env_value, "[REDACTED]")

    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def sanitize_for_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_for_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_metadata(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value
