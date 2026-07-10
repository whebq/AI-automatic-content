"""Рубрики сценариев — отдельный промпт под каждый формат Shorts."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from config import BASE_DIR
from services.content_rubrics import format_research_block
from services.reference_style import reference_style_prompt_block

RUBRICS_DIR = BASE_DIR / "assets" / "references" / "rubrics"

REFERENCE_STYLE_BLOCK = reference_style_prompt_block()

_SHARED_TAIL = """
Запрос автора:
{idea}

ОБЩИЕ ПРАВИЛА:
- Верни ТОЛЬКО текст для озвучки. Без отказов и пояснений.
- Цифры словами: «двадцать пять лет», «сорок шесть миллионов долларов».
- Бренды и латиница — по-русски для озвучки: Курсор, Спейс Икс, икс эй ай, Телеграм, АйОС.
- Длина: ОБЯЗАТЕЛЬНО {min_words}–{max_words} слов (~{target_duration_sec} сек). НЕ короче {min_words} слов.
- 14–18 фраз. Каждая фраза — законченная мысль (4–8 слов), не обрывок из двух слов.
- Макс. 3–4 «!» на весь текст. Без «!?», эмодзи, хештегов.

ЗАПРЕЩЕНО: вода, списки, ремарки в скобках, арабские цифры.
Каждая фраза с новой строки."""

_NEWS_TAIL = """
ДОПОЛНИТЕЛЬНО ДЛЯ НОВОСТИ:
- Запрос автора в конце — это ТЗ. Раскрой КАЖДЫЙ его пункт отдельной фразой.
- Тон спокойный, как в «Фишке» — уверенно, без крика. Макс. 2 «!» на весь текст.
- Фразы по 5–10 слов — законченная мысль со связкой «но», «поэтому», «в итоге».
- Фокус: что случилось → что это значит для зрителя → риски → нюанс.
- Не выдумывай факты, которых нет в запросе и справке."""

_STORY_BODY = """Ты — сценарист вирусных Shorts. Формат: 📖 ИСТОРИЯ С ФАКТАМИ.

{reference_style}

{reference_rubric_block}

{research_block}
ЗАДАЧА: расскажи историю как цельный сюжет, а не набор фактов.
Зритель после ролика пересказывает: кто → что сделал → как → чем кончилось.

ДУГА (14–18 фраз, строго по порядку):
1. ХУК — якорь «На этой фотографии [имя]» + возраст + шокирующая цифра; затем «Как такое могло произойти?»
2. СИСТЕМА — как устроен мир/процесс до преступления (1–2 фразы простым языком).
3. ПОВОРОТ — неожиданная связь, лазейка, доступ (короткий удар: «Чью компанию? Папы [имя].»).
4. СХЕМА — что сделал шаг за шагом, куда ушли деньги (3–4 фразы).
5. ХВАСТОВСТВО — прямая речь или цитата героя (1 фраза).
6. ОШИБКА — как сам себя спалил (1–2 фразы).
7. РАССЛЕДОВАНИЕ → АРЕСТ — кто заметил, дата, место, что нашли (2–3 фразы).
8. CTA — «Подпишись, у нас тут истории, которые хочется пересказывать друзьям.»

АНТИ-ПАТТЕРН (как в плохом ролике):
- «Как украли миллионы?» / «У Маршалов США!» — две строки вместо одной мысли.
- Список фактов без связки: Lamborghini, Telegram, ZachXBT — без «поэтому», «в итоге», «но».
- Слишком короткий текст на 25 сек вместо 45.

ХОРОШО (структура, не копируй факты):
Как сотрудник подрядчика украл сорок шесть миллионов у Маршалов?
Джон Дагита. Двадцать пять лет. Сын директора IT-подрядчика.
Компания обслуживала криптокошельки арестованных активов США.
Он переводил монеты на свои кошельки три месяца подряд.
Всего вывел сорок шесть миллионов долларов.
Потратил на Lamborghini и редкие ники в Telegram.
Хвастался переводами в закрытом чате с друзьями.
Криптоаналитик ZachXBT заметил цепочку транзакций.
Полиция задержала его на Сент-Мартене в марте.
Сейчас ждёт экстрадиции в США по обвинению в краже.
Хочешь больше таких схем? Жду в Telegram!"""

_NEWS_BODY = """Ты — сценарист вирусных Shorts. Формат: 📰 НОВОСТЬ.

{reference_rubric_block}

{research_block}
ЗАДАЧА: как в рубрике «Фишка» — запрос автора это ТЗ, раскрой его по пунктам.
Зритель после ролика понимает: что случилось → что это значит лично для него → чем грозит.

ГЛАВНЫЙ ПРИОРИТЕТ (как в удачной «Фишке»):
- Читай «Запрос автора» внизу — каждый пункт (конфиденциальность, цена, нейтральность, интеграция…) = минимум одна фраза.
- Не подменяй тему драмой, возрастами основателей и выдуманными деталями («сделка могла провалиться»).
- Обращайся к зрителю: «если ты пишешь код в Cursor», «многих волнует».

ДУГА (14–18 фраз):
1. ХУК — «Прямо сейчас» + суть события одной связной фразой.
2. ФАКТ — кто, что сделал, главная цифра внутри фразы (не отдельной строкой).
3. ВОПРОС ЗРИТЕЛЮ — «А что это значит для тебя?» / «Почему разработчики обеспокоены?»
4. СМЫСЛ (4–6 фраз) — раскрой пункты из запроса автора и справки: интеграция с xAI/Colossus, данные, цена, нейтральность, потеря независимости. Связки между фразами.
5. НЮАНС — «но» продукт продолжает развиваться (конкретика из запроса: мобильное приложение и т.д.).
6. CTA — «Все ссылки в Telegram-канале. Сохраняй.»

ДВА ПОДТИПА (выбирай по теме):
A) Сделка/аналитика — фокус «что значит для пользователя» (как в запросе автора).
B) Безумный эксперимент — нарастание хаоса, мини-эпизоды (как MoltBook в референсе).

СВЯЗКИ: «поэтому», «но», «раньше», «теперь», «в итоге», «а что это значит».
ТОН: спокойный уверенный, как в рубрике «Фишка» — без крика. Макс. 2 «!» на весь текст.

ЗАПРЕЩЕНО:
- Игнорировать пункты из запроса автора.
- Выдумывать факты не из справки (возраст основателя, альтернативные суммы сделки).
- Обрывки пресс-релиза: имя / дата / компания — отдельными строками.
- Список компаний без смысла для зрителя."""

_TIPS_BODY = """Ты — сценарист вирусных Shorts. Формат: 💡 ФИШКА / САЙТ / РЕПО.

{reference_style}

{reference_rubric_block}

{research_block}
ЗАДАЧА: боль → решение → как пользоваться → результат. Зритель хочет попробовать сам.
ПРИОРИТЕТ: для этой рубрики нельзя уходить в биографию и историю компании.
Если тема про инструмент/сайт/репо, говори только о том, ЧТО это и КАК использовать.

ДУГА (12–18 фраз, демо ИЛИ туториал):
1. ХУК — «Оказывается, существует…» или «Нашёл способ…» + обещание без кода/за N минут.
2. БОЛЬ — что раньше было сложно/долго (1 фраза).
3. ИНСТРУМЕНТ — название сайта, репо, команды (1–2 фразы).
4. КАК — пример промта или пошаговые команды (3–5 коротких фраз).
5. РЕЗУЛЬТАТ — что получишь на выходе, главный плюс (шаблон, кастомизация).
6. CTA — «Гайд в Telegram-канале. Сохраняй, иначе забудешь.»

ЗАПРЕЩЕНО в формате «Фишка/сайт/репо»:
- «На этой фотографии [имя]», возраст, история детства/карьеры основателя.
- Оценка компании, инвестиции, биография CEO — если это не ключ к использованию инструмента.
- Формат «как он/она создал(а) компанию».

Не выдумывай несуществующие репозитории. Если в справке есть ссылка/название — используй их."""


class ScriptRubric(str, Enum):
    STORY = "story"
    NEWS = "news"
    TIPS = "tips"


RUBRIC_BUTTONS: dict[str, ScriptRubric] = {
    "📖 История": ScriptRubric.STORY,
    "📰 Новость": ScriptRubric.NEWS,
    "💡 Фишка / репо": ScriptRubric.TIPS,
}

RUBRIC_LABELS: dict[ScriptRubric, str] = {
    ScriptRubric.STORY: "📖 История",
    ScriptRubric.NEWS: "📰 Новость",
    ScriptRubric.TIPS: "💡 Фишка / репо",
}

_BODY_BY_RUBRIC = {
    ScriptRubric.STORY: _STORY_BODY,
    ScriptRubric.NEWS: _NEWS_BODY,
    ScriptRubric.TIPS: _TIPS_BODY,
}


def rubric_from_button(text: str) -> ScriptRubric | None:
    return RUBRIC_BUTTONS.get(text.strip())


def load_rubric_reference_block(rubric: ScriptRubric) -> str:
    """Блок стиля из файла (после загрузки референсов) или заглушка."""
    path = RUBRICS_DIR / rubric.value / "style_block.txt"
    if path.is_file():
        content = path.read_text(encoding="utf-8").strip()
        if content:
            return f"РЕФЕРЕНС РУБРИКИ ({RUBRIC_LABELS[rubric]}):\n{content}\n"
    return (
        f"РЕФЕРЕНС РУБРИКИ ({RUBRIC_LABELS[rubric]}): "
        "эталонные ролики в assets/references/rubrics/ — добавь style_block.txt.\n"
    )


def load_news_golden_script() -> str:
    """Эталонный сценарий новости (SpaceX/Cursor) — тон, структура, TTS-формулировки."""
    path = RUBRICS_DIR / "news" / "golden_script_spacex_cursor.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def build_script_prompt(
    rubric: ScriptRubric,
    *,
    idea: str,
    research_brief: str | None,
    min_words: int,
    max_words: int,
    target_duration_sec: int,
) -> str:
    body = _BODY_BY_RUBRIC[rubric]
    reference_style = (
        ""
        if rubric in {ScriptRubric.TIPS, ScriptRubric.NEWS}
        else REFERENCE_STYLE_BLOCK
    )
    tail = _SHARED_TAIL.format(
        idea=idea.strip(),
        min_words=min_words,
        max_words=max_words,
        target_duration_sec=target_duration_sec,
    )
    if rubric is ScriptRubric.NEWS:
        tail += _NEWS_TAIL
    golden_block = ""
    if rubric is ScriptRubric.NEWS:
        golden = load_news_golden_script()
        if golden:
            golden_block = (
                "\nХОРОШО — эталонный сценарий (не копируй факты, копируй структуру, тон и TTS-формулировки):\n"
                f"{golden}\n"
            )
    return (
        body.format(
            reference_style=reference_style,
            reference_rubric_block=load_rubric_reference_block(rubric),
            research_block=format_research_block(research_brief),
            idea=idea.strip(),
            min_words=min_words,
            max_words=max_words,
            target_duration_sec=target_duration_sec,
        )
        + golden_block
        + tail
    )


def build_revision_prompt(
    rubric: ScriptRubric,
    *,
    script: str,
    feedback: str,
    research_brief: str | None,
    min_words: int,
    max_words: int,
    target_duration_sec: int,
) -> str:
    reference_style = (
        ""
        if rubric in {ScriptRubric.TIPS, ScriptRubric.NEWS}
        else REFERENCE_STYLE_BLOCK
    )
    news_extra = (
        "\nДля новости: убери обрывки пресс-релиза, добавь связки и одну линию нарастания."
        if rubric is ScriptRubric.NEWS
        else ""
    )
    return f"""Ты — сценарист вирусных Shorts. Формат: {RUBRIC_LABELS[rubric]}.

{reference_style}

{format_research_block(research_brief)}
Текущий сценарий:
{script.strip()}

Правки автора:
{feedback.strip()}

Перепиши сценарий. Сохрани формат рубрики. Убери воду, добавь сюжет и связки между фразами.{news_extra}
ОБЯЗАТЕЛЬНО {min_words}–{max_words} слов (~{target_duration_sec} сек). Цифры словами.
Верни только текст. Каждая фраза с новой строки."""
