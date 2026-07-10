"""Профили озвучки ElevenLabs по рубрикам."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    ELEVENLABS_SIMILARITY_BOOST,
    ELEVENLABS_SPEED,
    ELEVENLABS_STABILITY,
    ELEVENLABS_STYLE,
)
from services.script_rubrics import ScriptRubric


@dataclass(frozen=True)
class ElevenLabsVoiceSettings:
    stability: float
    similarity_boost: float
    style: float
    speed: float


def _default_settings() -> ElevenLabsVoiceSettings:
    return ElevenLabsVoiceSettings(
        stability=ELEVENLABS_STABILITY,
        similarity_boost=ELEVENLABS_SIMILARITY_BOOST,
        style=ELEVENLABS_STYLE,
        speed=ELEVENLABS_SPEED,
    )


def voice_settings_for_rubric(rubric: ScriptRubric | str | None) -> ElevenLabsVoiceSettings:
    """Tips — эталон из .env. News — спокойнее: меньше театра и чуть медленнее."""
    if isinstance(rubric, str):
        try:
            rubric = ScriptRubric(rubric)
        except ValueError:
            return _default_settings()

    if rubric is ScriptRubric.NEWS:
        return ElevenLabsVoiceSettings(
            stability=max(ELEVENLABS_STABILITY, 0.56),
            similarity_boost=ELEVENLABS_SIMILARITY_BOOST,
            style=min(ELEVENLABS_STYLE, 0.48),
            speed=min(ELEVENLABS_SPEED, 1.05),
        )

    return _default_settings()
