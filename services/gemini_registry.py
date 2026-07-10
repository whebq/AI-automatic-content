"""Ключи и клиенты Gemini по назначению — один ключ на задачу, без путаницы."""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache

from google import genai

from config import (
    GEMINI_API_KEY,
    GEMINI_BRAINSTORM_API_KEY,
    GEMINI_CHANNEL_POST_API_KEY,
    GEMINI_RESEARCH_API_KEY,
    GEMINI_SCRIPT_API_KEY,
)

logger = logging.getLogger(__name__)


class GeminiPurpose(str, Enum):
    RESEARCH = "research"
    SCRIPT = "script"
    BRAINSTORM = "brainstorm"
    CHANNEL_POST = "channel_post"


_PURPOSE_LABELS: dict[GeminiPurpose, str] = {
    GeminiPurpose.RESEARCH: "поиск фактов",
    GeminiPurpose.SCRIPT: "сценарий",
    GeminiPurpose.BRAINSTORM: "брейншторм",
    GeminiPurpose.CHANNEL_POST: "пост в канал",
}

_ENV_BY_PURPOSE: dict[GeminiPurpose, str] = {
    GeminiPurpose.RESEARCH: "GEMINI_RESEARCH_API_KEY",
    GeminiPurpose.SCRIPT: "GEMINI_SCRIPT_API_KEY",
    GeminiPurpose.BRAINSTORM: "GEMINI_BRAINSTORM_API_KEY",
    GeminiPurpose.CHANNEL_POST: "GEMINI_CHANNEL_POST_API_KEY",
}

_KEY_BY_PURPOSE: dict[GeminiPurpose, str] = {
    GeminiPurpose.RESEARCH: GEMINI_RESEARCH_API_KEY,
    GeminiPurpose.SCRIPT: GEMINI_SCRIPT_API_KEY,
    GeminiPurpose.BRAINSTORM: GEMINI_BRAINSTORM_API_KEY,
    GeminiPurpose.CHANNEL_POST: GEMINI_CHANNEL_POST_API_KEY,
}


class GeminiKeyError(Exception):
    pass


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{'*' * (len(key) - 4)}{key[-4:]}"


def resolve_api_key(purpose: GeminiPurpose) -> str:
    specific = _KEY_BY_PURPOSE.get(purpose, "").strip()
    if specific:
        return specific
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    env_name = _ENV_BY_PURPOSE[purpose]
    raise GeminiKeyError(
        f"Нет API-ключа для «{_PURPOSE_LABELS[purpose]}»: "
        f"задай {env_name} или GEMINI_API_KEY в .env"
    )


def uses_same_api_key(left: GeminiPurpose, right: GeminiPurpose) -> bool:
    return resolve_api_key(left) == resolve_api_key(right)


@lru_cache(maxsize=len(GeminiPurpose))
def get_gemini_client(purpose: GeminiPurpose) -> genai.Client:
    return genai.Client(api_key=resolve_api_key(purpose))


def log_gemini_key_layout() -> None:
    lines: list[str] = []
    for purpose in GeminiPurpose:
        specific = _KEY_BY_PURPOSE[purpose].strip()
        source = _ENV_BY_PURPOSE[purpose] if specific else "GEMINI_API_KEY (fallback)"
        lines.append(
            f"  {_PURPOSE_LABELS[purpose]}: {mask_api_key(resolve_api_key(purpose))} ← {source}"
        )
    logger.info("Gemini API-ключи:\n%s", "\n".join(lines))
