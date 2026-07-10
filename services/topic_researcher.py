"""Поиск проверенных фактов: Flash + Google Search (Pro не поддерживает поиск на free tier)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from google.genai import errors, types

from config import (
    GEMINI_MAX_429_RETRIES,
    GEMINI_MAX_RETRIES,
    GEMINI_MAX_RETRY_DELAY_SEC,
    GEMINI_RESEARCH_FALLBACK_MODELS,
    GEMINI_RESEARCH_MODEL,
)
from services.gemini_grounding import extract_sources
from services.gemini_registry import GeminiKeyError, GeminiPurpose, get_gemini_client
from services.gemini_retry import call_with_retries, get_error_code, models_to_try

logger = logging.getLogger(__name__)

_SWITCH_MODEL_CODES = {429, 404, 503, 504}

RESEARCH_PROMPT = """Собери материал из интернета для короткого вирусного Shorts (~45 сек).

Тема автора:
{idea}

Ищи в новостях, tech-изданиях, официальных пресс-релизах, Wikipedia, Reddit/HN — где есть конкретика.
Приоритет: Reuters, Bloomberg, TechCrunch, The Verge, Ars Technica, официальные блоги компаний, court filings.

Верни СПРАВКУ для сценариста (по-русски, без воды):
КТО: имя, один возраст для сценария, роль, компания
СЮЖЕТ: что произошло — главное действие
КОГДА: год, дата или период
ЦИФРЫ: суммы, сроки, метрики (только если нашёл в источниках)
КАК: схема, механизм, технология — коротко
ИТОГ: чем закончилось / что сейчас
УГОЛ ДЛЯ SHORTS: один шокирующий факт для хука
ВОЗРАСТ ДЛЯ СЦЕНАРИЯ: один возраст героя (если в источниках несколько — выбери один и укажи почему)

Правила:
- Пиши то, что реально нашёл. Не выдумывай цифры и имена.
- Не давай два разных возраста одного человека без пояснения — выбери один для Shorts.
- Если тема автора неточная (другое имя, похожая история) — найди ближайший реальный кейс и опиши его честно.
- Не пиши «НЕ ПОДТВЕРЖДЕНО» и не отказывайся от поиска. Лучше дай лучшее совпадение из источников.
- Не пиши сценарий — только справку для сценариста."""

NEWS_RESEARCH_PROMPT = """Собери материал из интернета для новостного Shorts (~45 сек).

Тема и ТЗ автора:
{idea}

Ищи: Reuters, Bloomberg, TechCrunch, The Verge, Ars Technica, официальные блоги, HN, Reddit.

Верни СПРАВКУ для сценариста (по-русски, без воды):
СОБЫТИЕ: что случилось, кто, когда, сумма/масштаб
ПУНКТЫ ИЗ ЗАПРОСА АВТОРА: перечисли, что автор просит раскрыть — и факты по КАЖДОМУ пункту
ДЛЯ ПОЛЬЗОВАТЕЛЕЙ/РАЗРАБОТЧИКОВ: что меняется для тех, кто пользуется продуктом
РИСКИ: конфиденциальность, цены, нейтральность, зависимость — только из источников
ИНТЕГРАЦИЯ: связь с экосистемой (xAI, Colossus и т.д.) если есть в источниках
НЮАНС: что продукт/компания продолжают развиваться (релизы, фичи)
УГОЛ ДЛЯ ХУКА: один шокирующий факт

Правила:
- Главное — ответить на запрос автора, не уводи в биографию CEO и случайные детали.
- Пиши то, что нашёл. Не выдумывай цифры и «могло провалиться» без источника.
- Не пиши «НЕ ПОДТВЕРЖДЕНО». Дай лучшее совпадение из источников.
- Не пиши сценарий — только справку."""

BRAINSTORM_RESEARCH_PROMPT = """Найди в интернете актуальную информацию по запросу автора для brainstorm Shorts (~45 сек).

Запрос автора:
{idea}

Ищи: Google News, TechCrunch, The Verge, Bloomberg, Reuters, официальные блоги компаний, X/Twitter, Hacker News.

Верни СПРАВКУ для продюсера (по-русски, кратко):
ПОДТВЕРЖДЕНО: что из запроса реально произошло (факты, даты, суммы, стороны сделки)
ЕСЛИ НЕТ ТОЧНОГО СОВПАДЕНИЯ: что реально есть в этой теме (близкие новости, слухи, опровержения)
ЦИФРЫ И ИМЕНА: только из источников
УГЛЫ ДЛЯ SHORTS: 2–3 сильных угла для ролика в формате новости/истории/фишки

Правила:
- Сначала ищи именно то, о чём спрашивает автор. Не подменяй тему другой без объяснения.
- Если сделки/события нет — напиши честно, но дай что нашёл по теме (инвестиции, партнёрства, релизы).
- Не выдумывай цифры. Не пиши «НЕ ПОДТВЕРЖДЕНО» и не отказывайся от поиска.
- Не пиши сценарий — только справку."""


@dataclass(frozen=True)
class TopicResearch:
    brief: str
    sources: tuple[str, ...] = ()


class TopicResearcherError(Exception):
    pass


class TopicResearcher:
    def __init__(self) -> None:
        try:
            self._client = get_gemini_client(GeminiPurpose.RESEARCH)
        except GeminiKeyError as exc:
            raise TopicResearcherError(str(exc)) from exc

    async def research(
        self,
        idea: str,
        *,
        prompt_template: str = RESEARCH_PROMPT,
    ) -> TopicResearch:
        idea = idea.strip()
        if not idea:
            raise TopicResearcherError("Тема не может быть пустой")

        prompt = prompt_template.format(idea=idea)
        config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        last_error: Exception | None = None

        for model in models_to_try(GEMINI_RESEARCH_MODEL, GEMINI_RESEARCH_FALLBACK_MODELS):
            try:
                async def _invoke(model: str = model) -> types.GenerateContentResponse:
                    return await self._client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )

                response = await call_with_retries(
                    _invoke,
                    label=f"research:{model}",
                    max_retries=GEMINI_MAX_RETRIES,
                    max_delay_sec=GEMINI_MAX_RETRY_DELAY_SEC,
                    max_429_retries=GEMINI_MAX_429_RETRIES,
                )
                brief = (response.text or "").strip()  # type: ignore[union-attr]
                if not brief:
                    raise TopicResearcherError("Поиск фактов вернул пустой ответ")

                sources = extract_sources(response)  # type: ignore[arg-type]
                if model != GEMINI_RESEARCH_MODEL:
                    logger.warning("Факты найдены через запасную модель: %s", model)
                return TopicResearch(brief=brief, sources=sources)
            except TopicResearcherError:
                raise
            except (errors.ClientError, errors.ServerError) as exc:
                last_error = exc
                code = get_error_code(exc)
                if code in _SWITCH_MODEL_CODES:
                    logger.warning(
                        "Модель %s недоступна для поиска (код %s), пробую следующую",
                        model,
                        code,
                    )
                    continue
                raise TopicResearcherError(f"Ошибка поиска фактов: {exc}") from exc
            except Exception as exc:
                raise TopicResearcherError(f"Ошибка поиска фактов: {exc}") from exc

        raise TopicResearcherError(f"Не удалось найти факты: {last_error}")

    async def research_brainstorm(self, idea: str) -> TopicResearch:
        return await self.research(idea, prompt_template=BRAINSTORM_RESEARCH_PROMPT)

    async def research_news(self, idea: str) -> TopicResearch:
        return await self.research(idea, prompt_template=NEWS_RESEARCH_PROMPT)
