"""Общая логика повторов для Gemini API."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

from google.genai import errors

logger = logging.getLogger(__name__)

_RETRY_DELAY_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_SWITCH_MODEL_CODES = {429, 404, 503, 504}


def get_error_code(exc: Exception) -> int | None:
    if isinstance(exc, (errors.ClientError, errors.ServerError)):
        return exc.code
    return None


def parse_retry_delay(error: Exception, attempt: int, *, max_delay_sec: float) -> float:
    message = str(error)
    match = _RETRY_DELAY_RE.search(message)
    if match:
        return min(float(match.group(1)), max_delay_sec)
    return min(3.0 * (2 ** (attempt - 1)), max_delay_sec)


async def call_with_retries(
    call: Callable[[], Awaitable[object]],
    *,
    label: str,
    max_retries: int,
    max_delay_sec: float,
    max_429_retries: int = 1,
) -> object:
    last_error: Exception | None = None
    retries_429 = 0

    for attempt in range(1, max_retries + 1):
        try:
            return await call()
        except (errors.ClientError, errors.ServerError) as exc:
            last_error = exc
            code = get_error_code(exc)
            if code not in _RETRYABLE_CODES or attempt >= max_retries:
                raise

            if code == 429:
                retries_429 += 1
                if retries_429 > max_429_retries:
                    raise

            delay = parse_retry_delay(exc, attempt, max_delay_sec=max_delay_sec)
            logger.warning(
                "Gemini %s для %s, повтор %s/%s через %.1f сек",
                code,
                label,
                attempt,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)

    raise last_error or RuntimeError(f"Gemini call failed: {label}")


def models_to_try(primary: str, fallbacks: list[str]) -> list[str]:
    ordered: list[str] = []
    for model in [primary, *fallbacks]:
        if model and model not in ordered:
            ordered.append(model)
    return ordered
