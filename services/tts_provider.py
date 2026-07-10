"""Абстракция TTS: ElevenLabs (живой голос) или edge-tts (бесплатный fallback)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

import edge_tts
import httpx
from edge_tts.exceptions import NoAudioReceived

from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL,
    ELEVENLABS_SIMILARITY_BOOST,
    ELEVENLABS_SPEED,
    ELEVENLABS_STABILITY,
    ELEVENLABS_STYLE,
    ELEVENLABS_VOICE_ID,
    TTS_VOICE,
)
from models import AudioResult, ScriptMeta, WordTiming
from services.tts_voice import ElevenLabsVoiceSettings, voice_settings_for_rubric
from services.timing import build_display_segments, estimate_words_from_audio, words_from_boundaries

logger = logging.getLogger(__name__)

_MAX_EDGE_RETRIES = 3
_ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class TTSProviderError(Exception):
    pass


class BaseTTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        script: str,
        output_path: Path,
        meta: ScriptMeta | None = None,
        *,
        voice_settings: ElevenLabsVoiceSettings | None = None,
    ) -> AudioResult:
        raise NotImplementedError


def _words_from_character_alignment(alignment: dict) -> list[WordTiming]:
    characters: list[str] = alignment.get("characters") or []
    starts: list[float] = alignment.get("character_start_times_seconds") or []
    ends: list[float] = alignment.get("character_end_times_seconds") or []
    if not characters or len(characters) != len(starts) or len(characters) != len(ends):
        return []

    words: list[WordTiming] = []
    buffer: list[str] = []
    word_start: float | None = None
    word_end: float | None = None

    def flush() -> None:
        nonlocal buffer, word_start, word_end
        if not buffer or word_start is None or word_end is None:
            buffer = []
            word_start = None
            word_end = None
            return
        text = "".join(buffer).strip()
        if text:
            words.append(WordTiming(text=text, start=word_start, end=word_end))
        buffer = []
        word_start = None
        word_end = None

    for char, start, end in zip(characters, starts, ends):
        if char.isspace():
            flush()
            continue
        if word_start is None:
            word_start = float(start)
        word_end = float(end)
        buffer.append(char)

    flush()
    return words


class EdgeTTSProvider(BaseTTSProvider):
    """Бесплатный edge-tts с word boundaries."""

    async def _stream_to_file(
        self,
        script: str,
        output_path: Path,
        *,
        boundary: str | None = "WordBoundary",
    ) -> list[dict]:
        communicate = edge_tts.Communicate(
            script,
            TTS_VOICE,
            **({"boundary": boundary} if boundary else {}),
        )
        boundaries: list[dict] = []

        with output_path.open("wb") as audio_file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    boundaries.append(
                        {
                            "offset": chunk["offset"],
                            "duration": chunk["duration"],
                            "text": chunk["text"],
                        }
                    )

        return boundaries

    async def synthesize(
        self,
        script: str,
        output_path: Path,
        meta: ScriptMeta | None = None,
        *,
        voice_settings: ElevenLabsVoiceSettings | None = None,
    ) -> AudioResult:
        del meta, voice_settings
        script = script.strip()
        if not script:
            raise TTSProviderError("Пустой текст для озвучки")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        boundaries: list[dict] = []
        last_error: Exception | None = None

        for attempt in range(1, _MAX_EDGE_RETRIES + 1):
            try:
                if output_path.exists():
                    output_path.unlink()
                boundaries = await self._stream_to_file(script, output_path)
                last_error = None
                break
            except NoAudioReceived as exc:
                last_error = exc
                logger.warning(
                    "edge-tts NoAudioReceived, попытка %s/%s",
                    attempt,
                    _MAX_EDGE_RETRIES,
                )
                await asyncio.sleep(min(1.5 * attempt, 4.0))
            except Exception as exc:
                logger.exception("edge-tts error")
                raise TTSProviderError(f"Ошибка edge-tts: {exc}") from exc

        if last_error is not None:
            raise TTSProviderError(
                "edge-tts не отдал аудио после нескольких попыток. Повтори через минуту."
            ) from last_error

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise TTSProviderError("edge-tts не создал аудиофайл")

        words = words_from_boundaries(boundaries)
        if not words:
            logger.warning("WordBoundary пуст — оцениваю тайминги по длительности аудио")
            words = await estimate_words_from_audio(script, str(output_path))

        if not words:
            raise TTSProviderError("Не удалось получить word-by-word тайминги")

        segments = build_display_segments(words)
        return AudioResult(
            audio_path=str(output_path),
            words=words,
            segments=segments,
            provider="edge-tts",
        )


class ElevenLabsProvider(BaseTTSProvider):
    """ElevenLabs TTS — живой голос для Shorts."""

    @staticmethod
    def _humanize_error(status_code: int, body: str) -> str:
        detail_message = ""
        detail_status = ""
        try:
            payload = json.loads(body)
            detail = payload.get("detail") or {}
            if isinstance(detail, dict):
                detail_message = str(detail.get("message") or "")
                detail_status = str(detail.get("status") or "")
        except ValueError:
            pass

        if detail_status == "missing_permissions":
            return (
                "У API-ключа ElevenLabs нет нужных прав. "
                "Создай новый ключ: Settings → API Keys → Create → включи «Text to Speech» "
                "и «Voices Read». Замени ELEVENLABS_API_KEY в .env"
            )
        if detail_status == "paid_plan_required" or status_code == 402:
            return (
                "Голос из библиотеки (Denophine) недоступен через API на бесплатном плане ElevenLabs. "
                "Варианты: 1) оформить подписку ElevenLabs, 2) сменить ELEVENLABS_VOICE_ID на "
                "встроенный голос (premade), 3) поставить TTS_PROVIDER=edge в .env"
            )
        if status_code == 401:
            if detail_message:
                return f"ElevenLabs отклонил ключ: {detail_message}"
            return "Неверный ElevenLabs API key. Проверь ELEVENLABS_API_KEY в .env"
        if status_code == 404:
            return "Голос не найден. Проверь ELEVENLABS_VOICE_ID в .env"
        if status_code == 429:
            return "Лимит ElevenLabs исчерпан. Подожди или пополни кредиты на elevenlabs.io"
        if status_code == 422:
            return f"ElevenLabs отклонил запрос: {body[:200]}"
        return f"Ошибка ElevenLabs API ({status_code}): {body[:200]}"

    async def synthesize(
        self,
        script: str,
        output_path: Path,
        meta: ScriptMeta | None = None,
        *,
        voice_settings: ElevenLabsVoiceSettings | None = None,
    ) -> AudioResult:
        del meta
        script = script.strip()
        if not script:
            raise TTSProviderError("Пустой текст для озвучки")
        if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
            raise TTSProviderError(
                "ElevenLabs не настроен. Задай ELEVENLABS_API_KEY и ELEVENLABS_VOICE_ID в .env"
            )

        settings = voice_settings or voice_settings_for_rubric(None)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()

        url = f"{_ELEVENLABS_API_URL}/{ELEVENLABS_VOICE_ID}/with-timestamps"
        payload = {
            "text": script,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {
                "stability": settings.stability,
                "similarity_boost": settings.similarity_boost,
                "style": settings.style,
                "use_speaker_boost": True,
            },
            "speed": settings.speed,
        }
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise TTSProviderError(f"Не удалось связаться с ElevenLabs: {exc}") from exc

        if response.status_code != 200:
            raise TTSProviderError(
                self._humanize_error(response.status_code, response.text)
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise TTSProviderError("ElevenLabs вернул некорректный ответ") from exc

        audio_b64 = data.get("audio_base64")
        if not audio_b64:
            raise TTSProviderError("ElevenLabs не вернул аудио")

        output_path.write_bytes(base64.b64decode(audio_b64))
        if output_path.stat().st_size == 0:
            raise TTSProviderError("ElevenLabs создал пустой аудиофайл")

        alignment = data.get("alignment") or data.get("normalized_alignment") or {}
        words = _words_from_character_alignment(alignment)
        if not words:
            logger.warning("ElevenLabs alignment пуст — оцениваю тайминги по длительности")
            words = await estimate_words_from_audio(script, str(output_path))

        if not words:
            raise TTSProviderError("Не удалось построить тайминги озвучки")

        segments = build_display_segments(words)
        logger.info(
            "ElevenLabs: model=%s, voice=%s, stability=%.2f, style=%.2f, speed=%.2f",
            ELEVENLABS_MODEL,
            ELEVENLABS_VOICE_ID[:8],
            settings.stability,
            settings.style,
            settings.speed,
        )
        return AudioResult(
            audio_path=str(output_path),
            words=words,
            segments=segments,
            provider="elevenlabs",
        )


def get_tts_provider(name: str) -> BaseTTSProvider:
    if name == "elevenlabs":
        return ElevenLabsProvider()
    return EdgeTTSProvider()
