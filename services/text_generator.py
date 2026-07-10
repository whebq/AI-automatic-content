import logging
import re
from dataclasses import dataclass

from google import genai
from google.genai import errors, types

from config import (
    GEMINI_FALLBACK_MODELS,
    GEMINI_MAX_429_RETRIES,
    GEMINI_MAX_RETRIES,
    GEMINI_MAX_RETRY_DELAY_SEC,
    GEMINI_MODEL,
    GEMINI_SCRIPT_FALLBACK_MODELS,
    GEMINI_SCRIPT_MODEL,
    SCRIPT_MIN_WORDS,
)
from services.gemini_registry import GeminiKeyError, GeminiPurpose, get_gemini_client
from services.content_rubrics import (
    brainstorm_summarize_prompt,
    brainstorm_system_prompt,
    format_brainstorm_history,
    format_brainstorm_research_query,
)
from services.script_rubrics import ScriptRubric, build_revision_prompt, build_script_prompt
from services.gemini_retry import (
    call_with_retries,
    get_error_code,
    models_to_try,
)

logger = logging.getLogger(__name__)

_SWITCH_MODEL_CODES = {429, 404, 503, 504}


class TextGeneratorError(Exception):
    pass


@dataclass(frozen=True)
class ScriptGenerationResult:
    script: str
    sources: tuple[str, ...] = ()


def _humanize_gemini_error(exc: Exception) -> str:
    code = get_error_code(exc)

    if code == 429:
        return (
            "Исчерпана квота Gemini API.\n\n"
            "• Подожди 1–2 минуты (лимит в минуту) или до полуночи по Pacific Time (дневной лимит).\n"
            "• На скриншоте ai.dev/rate-limit: если красный RPD у 2.5 Flash — переключи в .env на "
            "gemini-2.5-flash-lite для поиска и сценария.\n"
            "• Лимиты: https://ai.dev/rate-limit"
        )
    if code == 503:
        return (
            "Сервер Gemini перегружен (503). Подожди 30–60 секунд и попробуй снова."
        )
    if code == 504:
        return "Gemini не ответил вовремя (таймаут). Попробуй ещё раз через минуту."
    if code == 404:
        return "Модель недоступна для этого API-ключа. Проверь GEMINI_MODEL в .env"
    if code == 400:
        return "Некорректный запрос к Gemini API. Проверь API-ключ в .env"
    if code == 403:
        return "Доступ к Gemini API запрещён. Проверь API-ключ и права проекта"
    if code is not None:
        return f"Ошибка Gemini API (код {code})"

    return f"Ошибка Gemini API: {exc}"


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


class TextGenerator:
    def __init__(self) -> None:
        try:
            self._script_client = get_gemini_client(GeminiPurpose.SCRIPT)
            self._brainstorm_client = get_gemini_client(GeminiPurpose.BRAINSTORM)
        except GeminiKeyError as exc:
            raise TextGeneratorError(str(exc)) from exc

    async def _call_model(
        self,
        prompt: str,
        *,
        client: genai.Client,
        primary_model: str,
        fallback_models: list[str],
        label: str,
        config: types.GenerateContentConfig | None = None,
    ) -> types.GenerateContentResponse:
        last_error: Exception | None = None

        for model in models_to_try(primary_model, fallback_models):
            try:
                async def _invoke(model: str = model) -> types.GenerateContentResponse:
                    return await client.aio.models.generate_content(
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
                if model != primary_model:
                    logger.warning("%s через запасную модель: %s", label, model)
                return response  # type: ignore[return-value]
            except (errors.ClientError, errors.ServerError) as exc:
                last_error = exc
                code = get_error_code(exc)
                if code in _SWITCH_MODEL_CODES:
                    logger.warning(
                        "Модель %s недоступна (код %s), пробую следующую",
                        model,
                        code,
                    )
                    continue
                raise TextGeneratorError(_humanize_gemini_error(exc)) from exc
            except Exception as exc:
                raise TextGeneratorError(_humanize_gemini_error(exc)) from exc

        raise TextGeneratorError(_humanize_gemini_error(last_error or Exception("Неизвестная ошибка")))

    async def _generate(
        self,
        prompt: str,
        *,
        client: genai.Client,
        primary_model: str,
        fallback_models: list[str],
        label: str,
        config: types.GenerateContentConfig | None = None,
    ) -> str:
        response = await self._call_model(
            prompt,
            client=client,
            primary_model=primary_model,
            fallback_models=fallback_models,
            label=label,
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise TextGeneratorError(f"Gemini вернул пустой ответ ({label})")
        return text

    async def brainstorm_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        *,
        rubric: ScriptRubric = ScriptRubric.STORY,
        research_brief: str | None = None,
    ) -> str:
        user_message = user_message.strip()
        if not user_message:
            raise TextGeneratorError("Сообщение не может быть пустым")

        dialog = format_brainstorm_history(history)
        prompt = (
            f"{brainstorm_system_prompt(rubric, research_brief)}\n\n"
            f"История диалога:\n{dialog}\n\n"
            f"Новое сообщение автора:\n{user_message}\n\n"
            "Ответь автору кратко (до 120 слов). Разбери его запрос по фактам из справки."
        )
        return await self._generate(
            prompt,
            client=self._brainstorm_client,
            primary_model=GEMINI_MODEL,
            fallback_models=GEMINI_FALLBACK_MODELS,
            label="brainstorm",
        )

    async def summarize_brainstorm(
        self,
        history: list[dict[str, str]],
        *,
        rubric: ScriptRubric = ScriptRubric.STORY,
        research_brief: str | None = None,
    ) -> str:
        if not history:
            raise TextGeneratorError("Сначала обсуди тему с продюсером")

        prompt = brainstorm_summarize_prompt(
            rubric,
            format_brainstorm_history(history),
            research_brief=research_brief,
        )
        topic = await self._generate(
            prompt,
            client=self._brainstorm_client,
            primary_model=GEMINI_MODEL,
            fallback_models=GEMINI_FALLBACK_MODELS,
            label="brainstorm_summary",
        )
        topic = topic.strip().strip('"').strip("'")
        if not topic:
            raise TextGeneratorError("Не удалось сформулировать тему из обсуждения")
        return topic

    async def generate_script(
        self,
        idea: str,
        *,
        rubric: ScriptRubric = ScriptRubric.STORY,
        research_brief: str | None = None,
    ) -> ScriptGenerationResult:
        idea = idea.strip()
        if not idea:
            raise TextGeneratorError("Идея не может быть пустой")

        from config import SCRIPT_MAX_WORDS, SCRIPT_MIN_WORDS, TARGET_VIDEO_DURATION_SEC

        prompt = build_script_prompt(
            rubric,
            idea=idea,
            research_brief=research_brief,
            min_words=SCRIPT_MIN_WORDS,
            max_words=SCRIPT_MAX_WORDS,
            target_duration_sec=int(TARGET_VIDEO_DURATION_SEC),
        )

        response = await self._call_model(
            prompt,
            client=self._script_client,
            primary_model=GEMINI_SCRIPT_MODEL,
            fallback_models=GEMINI_SCRIPT_FALLBACK_MODELS,
            label="script",
        )
        script = (response.text or "").strip()
        if not script:
            raise TextGeneratorError("Gemini вернул пустой сценарий")

        if _word_count(script) < SCRIPT_MIN_WORDS:
            logger.warning(
                "Сценарий короткий (%s слов), повторная генерация",
                _word_count(script),
            )
            script = await self._generate(
                f"{prompt}\n\n"
                f"ВАЖНО: предыдущий ответ слишком короткий ({_word_count(script)} слов). "
                f"Нужно минимум {SCRIPT_MIN_WORDS} слов. Добавь факты в сюжет, без воды.",
                client=self._script_client,
                primary_model=GEMINI_SCRIPT_MODEL,
                fallback_models=GEMINI_SCRIPT_FALLBACK_MODELS,
                label="script_retry",
            )

        return ScriptGenerationResult(script=script)

    async def revise_script(
        self,
        script: str,
        feedback: str,
        *,
        rubric: ScriptRubric = ScriptRubric.STORY,
        research_brief: str | None = None,
    ) -> str:
        script = script.strip()
        feedback = feedback.strip()
        if not script:
            raise TextGeneratorError("Исходный сценарий пустой")
        if not feedback:
            raise TextGeneratorError("Опиши, что нужно изменить")

        from config import SCRIPT_MAX_WORDS, SCRIPT_MIN_WORDS, TARGET_VIDEO_DURATION_SEC

        return await self._generate(
            build_revision_prompt(
                rubric,
                script=script,
                feedback=feedback,
                research_brief=research_brief,
                min_words=SCRIPT_MIN_WORDS,
                max_words=SCRIPT_MAX_WORDS,
                target_duration_sec=int(TARGET_VIDEO_DURATION_SEC),
            ),
            client=self._script_client,
            primary_model=GEMINI_SCRIPT_MODEL,
            fallback_models=GEMINI_SCRIPT_FALLBACK_MODELS,
            label="revision",
        )
