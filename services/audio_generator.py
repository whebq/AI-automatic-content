"""Озвучка и тайминги: делегирует TTS-провайдеру, готов к ElevenLabs."""

import logging
from pathlib import Path

from config import TTS_PROVIDER
from models import AudioResult, ScriptMeta, SubtitleSegment, WordTiming
from services.script_sanitizer import script_lines_to_speech
from services.script_rubrics import ScriptRubric
from services.timing import extract_script_meta
from services.tts_provider import TTSProviderError, get_tts_provider
from services.tts_voice import voice_settings_for_rubric

logger = logging.getLogger(__name__)


class AudioGeneratorError(Exception):
    pass


class AudioGenerator:
    def __init__(self) -> None:
        self._provider = get_tts_provider(TTS_PROVIDER)

    async def generate(
        self,
        text: str,
        output_path: Path,
        *,
        rubric: ScriptRubric | str | None = None,
    ) -> AudioResult:
        text = text.strip()
        if not text:
            raise AudioGeneratorError("Текст для озвучки не может быть пустым")

        rubric_key = rubric.value if isinstance(rubric, ScriptRubric) else rubric
        meta = extract_script_meta(text)
        tts_text = script_lines_to_speech(text, rubric=rubric_key)
        voice_settings = voice_settings_for_rubric(rubric)

        try:
            result = await self._provider.synthesize(
                tts_text,
                output_path,
                meta=meta,
                voice_settings=voice_settings,
            )
        except TTSProviderError as exc:
            raise AudioGeneratorError(str(exc)) from exc

        if not result.segments:
            raise AudioGeneratorError("Не удалось построить тайминги субтитров")

        logger.info(
            "Озвучка (%s): %d слов, %d экранных фрагментов, rubric=%s",
            result.provider,
            len(result.words),
            len(result.segments),
            rubric_key or "default",
        )
        return result

    @staticmethod
    def segments_only(result: AudioResult) -> list[SubtitleSegment]:
        return result.segments

    @staticmethod
    def words_only(result: AudioResult) -> list[WordTiming]:
        return result.words
