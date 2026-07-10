"""Генерация постов для Telegram-канала: поиск + текст."""

from __future__ import annotations

import logging

from google.genai import errors, types
from google.genai.types import GenerateContentResponse

from config import (
    GEMINI_CHANNEL_POST_FALLBACK_MODELS,
    GEMINI_CHANNEL_POST_MODEL,
    GEMINI_MAX_429_RETRIES,
    GEMINI_MAX_RETRIES,
    GEMINI_MAX_RETRY_DELAY_SEC,
    TELEGRAM_CHANNEL_HANDLE,
)
from services.channel_post_types import (
    TOPIC_POST_RESEARCH_PROMPT,
    VIDEO_NEWS_RESEARCH_PROMPT,
    VIDEO_TIPS_RESEARCH_PROMPT,
    ChannelPostType,
    VideoPostKind,
    build_topic_post_prompt,
    build_video_post_prompt,
    infer_video_post_kind,
)
from services.gemini_grounding import extract_sources
from services.gemini_registry import GeminiKeyError, GeminiPurpose, get_gemini_client
from services.gemini_retry import call_with_retries, get_error_code, models_to_try
from services.telegram_html import normalize_channel_signature, sanitize_telegram_html

logger = logging.getLogger(__name__)

_SWITCH_MODEL_CODES = {429, 404, 503, 504}

_MAX_POST_LEN: dict[str, int] = {
    "topic": 950,
    "video_news": 900,
    "video_tips": 1200,
}


class ChannelPostGeneratorError(Exception):
    pass


class ChannelPostGenerator:
    def __init__(self) -> None:
        try:
            self._client = get_gemini_client(GeminiPurpose.CHANNEL_POST)
        except GeminiKeyError as exc:
            raise ChannelPostGeneratorError(str(exc)) from exc

    async def _generate(
        self,
        prompt: str,
        *,
        label: str,
        use_search: bool = False,
    ) -> tuple[str, tuple[str, ...]]:
        config = None
        if use_search:
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            )

        last_error: Exception | None = None
        for model in models_to_try(
            GEMINI_CHANNEL_POST_MODEL, GEMINI_CHANNEL_POST_FALLBACK_MODELS
        ):
            try:

                async def _invoke(model: str = model) -> types.GenerateContentResponse:
                    return await self._client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )

                response = await call_with_retries(
                    _invoke,
                    label=f"{label}:{model}",
                    max_retries=GEMINI_MAX_RETRIES,
                    max_delay_sec=GEMINI_MAX_RETRY_DELAY_SEC,
                    max_429_retries=GEMINI_MAX_429_RETRIES,
                )
                text = (response.text or "").strip()
                if not text:
                    raise ChannelPostGeneratorError(f"Gemini вернул пустой ответ ({label})")
                sources = extract_sources(response) if use_search else ()
                if model != GEMINI_CHANNEL_POST_MODEL:
                    logger.warning("%s через запасную модель: %s", label, model)
                return text, sources
            except ChannelPostGeneratorError:
                raise
            except (errors.ClientError, errors.ServerError) as exc:
                last_error = exc
                code = get_error_code(exc)
                if code in _SWITCH_MODEL_CODES:
                    logger.warning(
                        "Модель %s недоступна для %s (код %s), пробую следующую",
                        model,
                        label,
                        code,
                    )
                    continue
                raise ChannelPostGeneratorError(f"Ошибка Gemini ({label}): {exc}") from exc
            except Exception as exc:
                raise ChannelPostGeneratorError(f"Ошибка Gemini ({label}): {exc}") from exc

        raise ChannelPostGeneratorError(f"Не удалось выполнить {label}: {last_error}")

    @staticmethod
    def _clean_html_post(text: str) -> str:
        cleaned = sanitize_telegram_html(text)
        return normalize_channel_signature(cleaned, TELEGRAM_CHANNEL_HANDLE)

    async def research(
        self,
        idea: str,
        *,
        post_type: ChannelPostType,
        video_kind: VideoPostKind | None = None,
        video_script: str | None = None,
        rubric: str | None = None,
    ) -> tuple[str, tuple[str, ...]]:
        idea = idea.strip()
        if not idea:
            raise ChannelPostGeneratorError("Тема не может быть пустой")

        if post_type is ChannelPostType.TOPIC:
            template = TOPIC_POST_RESEARCH_PROMPT
        else:
            kind = video_kind or infer_video_post_kind(
                idea, video_script, rubric=rubric
            )
            template = (
                VIDEO_NEWS_RESEARCH_PROMPT
                if kind is VideoPostKind.NEWS
                else VIDEO_TIPS_RESEARCH_PROMPT
            )
        brief, sources = await self._generate(
            template.format(idea=idea),
            label="channel_post_research",
            use_search=True,
        )
        return brief, sources

    async def compose(
        self,
        idea: str,
        *,
        post_type: ChannelPostType,
        research_brief: str | None = None,
        video_script: str | None = None,
        video_kind: VideoPostKind | None = None,
        rubric: str | None = None,
    ) -> tuple[str, VideoPostKind | None]:
        idea = idea.strip()
        if not idea:
            raise ChannelPostGeneratorError("Тема не может быть пустой")

        resolved_kind: VideoPostKind | None = None
        if post_type is ChannelPostType.TOPIC:
            prompt = build_topic_post_prompt(
                idea=idea,
                research_brief=research_brief,
                channel_handle=TELEGRAM_CHANNEL_HANDLE,
            )
        else:
            resolved_kind = video_kind or infer_video_post_kind(
                idea, video_script, rubric=rubric
            )
            prompt = build_video_post_prompt(
                idea=idea,
                research_brief=research_brief,
                channel_handle=TELEGRAM_CHANNEL_HANDLE,
                video_script=video_script,
                video_kind=resolved_kind,
            )

        text, _ = await self._generate(prompt, label="channel_post_compose", use_search=False)
        text = self._clean_html_post(text)

        max_len = _MAX_POST_LEN["topic"]
        if resolved_kind is VideoPostKind.NEWS:
            max_len = _MAX_POST_LEN["video_news"]
        elif resolved_kind is VideoPostKind.TIPS:
            max_len = _MAX_POST_LEN["video_tips"]

        if len(text) > max_len:
            logger.warning("Пост длинный (%s символов), сжимаю до %s", len(text), max_len)
            text, _ = await self._generate(
                f"{prompt}\n\n"
                f"ВАЖНО: предыдущий ответ слишком длинный ({len(text)} символов). "
                f"Сожми до {max_len} символов. Убери воду и повторы.",
                label="channel_post_compose_retry",
                use_search=False,
            )
            text = self._clean_html_post(text)

        return text, resolved_kind

    async def generate(
        self,
        idea: str,
        *,
        post_type: ChannelPostType,
        video_script: str | None = None,
        video_kind: VideoPostKind | None = None,
        rubric: str | None = None,
    ) -> tuple[str, str, tuple[str, ...], VideoPostKind | None]:
        kind = video_kind
        if post_type is ChannelPostType.VIDEO and kind is None:
            kind = infer_video_post_kind(idea, video_script, rubric=rubric)

        brief, sources = await self.research(
            idea,
            post_type=post_type,
            video_kind=kind,
            video_script=video_script,
            rubric=rubric,
        )
        post, resolved_kind = await self.compose(
            idea,
            post_type=post_type,
            research_brief=brief,
            video_script=video_script,
            video_kind=kind,
            rubric=rubric,
        )
        return post, brief, sources, resolved_kind
