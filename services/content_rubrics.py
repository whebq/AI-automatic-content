"""Промпты brainstorm и вспомогательные блоки."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.reference_style import reference_style_prompt_block

if TYPE_CHECKING:
    from services.script_rubrics import ScriptRubric

REFERENCE_STYLE_BLOCK = reference_style_prompt_block()

_BRAINSTORM_BASE = """Ты — креативный продюсер Shorts про автоматизацию, ИИ, код, no-code и личный бренд.

{reference_style}

{reference_rubric_block}

Формат ролика УЖЕ выбран: {rubric_label}. Не предлагай другие форматы.

Твоя задача:
- Помочь автору придумать, про ЧТО снять ролик в этом формате (~45 сек).
- Опирайся на СПРАВКУ ИЗ ИНТЕРНЕТА ниже — это результат свежего поиска.
- Отвечай по запросу автора: если он просит конкретную новость — разбирай её, а не предлагай случайные другие темы.
- Если точного события нет — честно скажи и предложи угол по ближайшим реальным фактам из справки.
- Задавай уточняющие вопросы, предлагай 1–2 сильных угла.
- Пиши коротко (до 120 слов), без воды.
- НЕ пиши готовый сценарий — только идеи, углы, факты."""

_BRAINSTORM_RUBRIC_HINTS = {
    "story": (
        "Фокус: кейс человека или компании с сюжетом — кто, что сделал, как, чем кончилось.\n"
        "Уточняй: герой, суммы, поворот, как раскрыли."
    ),
    "news": (
        "Фокус: событие «прямо сейчас» — что случилось, масштаб, почему важно, куда катится.\n"
        "Уточняй: продукт/компания, цифры, безумные примеры, актуальность."
    ),
    "tips": (
        "Фокус: конкретный сайт, репо, плагин или лайфхак — какую боль решает и как пользоваться.\n"
        "НЕ уводи в биографию основателя или историю создания компании.\n"
        "Уточняй: название инструмента, шаг/команда, результат для зрителя."
    ),
}

_SUMMARIZE_BASE = """На основе диалога сформулируй финальный ПРОМПТ для генерации сценария.

Формат ролика (строго): {rubric_label}
{rubric_rules}

Диалог:
{history}

Верни СТРОГО текст промпта: 2–4 ёмких предложения.
Промпт — это ТЗ для сценариста: о чём ролик, ключевые факты/шаги, угол подачи.
Без пояснений, без кавычек, без слова «промпт». Только текст."""

_SUMMARIZE_RULES = {
    "story": (
        "Промпт для ИСТОРИИ: герой, возраст/роль, что сделал, схема, цифры, развязка.\n"
        "Можно упомянуть хук-угол («украл X у Y», «как обманул систему»)."
    ),
    "news": (
        "Промпт для НОВОСТИ: что случилось, кто/что затронуто, цифры, почему сейчас, куда движется."
    ),
    "tips": (
        "Промпт для ФИШКИ/САЙТА/РЕПО: название инструмента, боль зрителя, как работает, "
        "пример использования, главный плюс.\n"
        "ЗАПРЕЩЕНО в промпте: биография основателя, «история создания компании», "
        "формат «на этой фотографии [имя]» — это другой формат."
    ),
}

BRAINSTORM_INTRO_BY_RUBRIC = {
    "story": (
        "💡 Придумываем тему для <b>📖 Истории</b>.\n\n"
        "Расскажи, про кого или какой кейс интересует — помогу выбрать угол, факты и хук.\n"
        "Перед ответом ищу информацию в интернете.\n"
        "Сценарий не пишу, только идею. Когда готов — «📝 Сформировать промпт»."
    ),
    "news": (
        "💡 Придумываем тему для <b>📰 Новости</b>.\n\n"
        "Что происходит в нише — помогу выбрать событие, угол и почему это важно сейчас.\n"
        "Перед ответом ищу актуальную информацию в интернете.\n"
        "Когда готов — «📝 Сформировать промпт»."
    ),
    "tips": (
        "💡 Придумываем тему для <b>💡 Фишки / сайта</b>.\n\n"
        "Опиши область: инструмент, репо, сайт — помогу сформулировать, что показать и какую боль закрыть.\n"
        "Перед ответом ищу актуальную информацию в интернете.\n"
        "Не биография компании, а конкретная фишка. Когда готов — «📝 Сформировать промпт»."
    ),
}


def format_brainstorm_history(history: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in history:
        role = "Автор" if item.get("role") == "user" else "Продюсер"
        content = (item.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(диалог пуст)"


def format_research_block(
    research_brief: str | None = None,
    *,
    use_search: bool = False,
) -> str:
    brief = (research_brief or "").strip()
    if brief:
        return (
            "СПРАВКА ИЗ ПОИСКА (факты для сюжета — имена, суммы, хронология):\n"
            f"{brief}\n"
            "Используй факты из справки. Запрос автора — угол подачи.\n"
        )
    if use_search:
        return (
            "Сначала найди в интернете материал по теме.\n"
            "Опирайся на найденное, не выдумывай цифры.\n"
        )
    return ""


def format_brainstorm_research_query(
    user_message: str,
    history: list[dict[str, str]],
) -> str:
    dialog = format_brainstorm_history(history)
    if dialog == "(диалог пуст)":
        return user_message.strip()
    return (
        f"Контекст обсуждения:\n{dialog}\n\n"
        f"Текущий запрос автора:\n{user_message.strip()}"
    )


def brainstorm_system_prompt(rubric: ScriptRubric, research_brief: str | None = None) -> str:
    from services.script_rubrics import RUBRIC_LABELS, load_rubric_reference_block

    return (
        _BRAINSTORM_BASE.format(
            reference_style=REFERENCE_STYLE_BLOCK,
            reference_rubric_block=load_rubric_reference_block(rubric),
            rubric_label=RUBRIC_LABELS[rubric],
        )
        + "\n\n"
        + _BRAINSTORM_RUBRIC_HINTS[rubric.value]
        + "\n\n"
        + format_research_block(research_brief)
    )


def brainstorm_summarize_prompt(
    rubric: ScriptRubric,
    history: str,
    *,
    research_brief: str | None = None,
) -> str:
    from services.script_rubrics import RUBRIC_LABELS

    return (
        _SUMMARIZE_BASE.format(
            rubric_label=RUBRIC_LABELS[rubric],
            rubric_rules=_SUMMARIZE_RULES[rubric.value],
            history=history,
        )
        + "\n\n"
        + format_research_block(research_brief)
    )
