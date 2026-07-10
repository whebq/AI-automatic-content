"""Разбивка таймингов: word-by-word → фразы 3–5 слов для pill-субтитров."""

import asyncio
import re

from config import SUBTITLE_MAX_WORDS_ON_SCREEN, SUBTITLE_PHRASE_TARGET_WORDS
from models import ScriptMeta, SubtitleSegment, WordTiming

_PAUSE_PUNCTUATION = re.compile(r"[.!?…]\s*")
_EMPHASIS_PATTERN = re.compile(r"[«\"']([^»\"']+)[»\"']|(\b[A-ZА-ЯЁ]{2,}\b)")


def extract_script_meta(script: str) -> ScriptMeta:
    """Извлекает маркеры пауз и акцентов для будущего ElevenLabs."""
    pauses: list[float] = []
    emphasis: list[str] = []

    for match in _EMPHASIS_PATTERN.finditer(script):
        phrase = match.group(1) or match.group(2)
        if phrase:
            emphasis.append(phrase.strip())

    for index, char in enumerate(script):
        if char in ".!?…":
            pauses.append(round(index / max(len(script), 1) * 30, 2))

    return ScriptMeta(
        script=script,
        pause_after_seconds=tuple(pauses[:12]),
        emphasis_phrases=tuple(emphasis[:8]),
    )


def words_from_boundaries(boundaries: list[dict]) -> list[WordTiming]:
    ticks_per_second = 10_000_000
    words: list[WordTiming] = []

    for item in boundaries:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        start = item["offset"] / ticks_per_second
        end = (item["offset"] + item["duration"]) / ticks_per_second
        words.append(WordTiming(text=text, start=start, end=end))

    return words


def build_display_segments(
    words: list[WordTiming],
    *,
    max_words: int = SUBTITLE_MAX_WORDS_ON_SCREEN,
    target_words: int = SUBTITLE_PHRASE_TARGET_WORDS,
) -> list[SubtitleSegment]:
    """Собирает pill-субтитры: фразы по 3–5 слов (как в референсе)."""
    if not words:
        return []

    segments: list[SubtitleSegment] = []
    index = 0
    target_words = max(2, min(target_words, max_words))

    while index < len(words):
        chunk_end = min(index + target_words, len(words))
        chunk = words[index:chunk_end]

        # Расширяем до границы предложения, если фраза короткая
        if chunk_end < len(words) and len(chunk) < target_words:
            while chunk_end < len(words) and len(chunk) < max_words:
                if _ends_sentence(chunk[-1].text):
                    break
                chunk.append(words[chunk_end])
                chunk_end += 1

        # Сжимаем, если следующее слово явно начало новой мысли после точки
        if len(chunk) > 2 and chunk_end < len(words) and _ends_sentence(chunk[-2].text):
            chunk = chunk[:-1]
            chunk_end -= 1

        text = " ".join(word.text for word in chunk).strip()
        segments.append(
            SubtitleSegment(
                text=text,
                start=chunk[0].start,
                end=chunk[-1].end,
            )
        )
        index = chunk_end

    return _ensure_min_duration(segments, min_duration=0.35)


def _ends_sentence(token: str) -> bool:
    return bool(token) and token[-1] in ".!?…"


def _ensure_min_duration(
    segments: list[SubtitleSegment],
    min_duration: float,
) -> list[SubtitleSegment]:
    if not segments:
        return segments

    fixed: list[SubtitleSegment] = []
    for segment in segments:
        duration = segment.end - segment.start
        if duration < min_duration:
            fixed.append(
                SubtitleSegment(
                    text=segment.text,
                    start=segment.start,
                    end=segment.start + min_duration,
                )
            )
        else:
            fixed.append(segment)

    return fixed


def estimate_words_from_text(text: str, duration: float) -> list[WordTiming]:
    """Пропорциональная оценка word-by-word таймингов, если TTS не отдал boundaries."""
    tokens = re.findall(r"\S+", text)
    if not tokens or duration <= 0:
        return []

    weights = [max(len(token), 1) for token in tokens]
    total_weight = sum(weights)
    words: list[WordTiming] = []
    cursor = 0.0

    for token, weight in zip(tokens, weights):
        token_duration = duration * (weight / total_weight)
        words.append(WordTiming(text=token, start=cursor, end=cursor + token_duration))
        cursor += token_duration

    if words:
        last = words[-1]
        words[-1] = WordTiming(text=last.text, start=last.start, end=duration)

    return words


async def estimate_words_from_audio(text: str, audio_path: str) -> list[WordTiming]:
    def _read_duration() -> float:
        from moviepy import AudioFileClip

        with AudioFileClip(audio_path) as audio:
            return float(audio.duration or 0)

    try:
        duration = await asyncio.to_thread(_read_duration)
    except Exception:
        return []

    return estimate_words_from_text(text, duration)
