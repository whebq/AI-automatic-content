"""Типы постов для Telegram-канала."""

from __future__ import annotations

from enum import Enum

BTN_POST_TOPIC = "📰 Пост на тему"
BTN_POST_VIDEO = "🎬 Пост к ролику"

POST_TYPE_BUTTON_TEXTS = (BTN_POST_TOPIC, BTN_POST_VIDEO)


class ChannelPostType(str, Enum):
    TOPIC = "topic"
    VIDEO = "video"


class VideoPostKind(str, Enum):
    NEWS = "news"
    TIPS = "tips"


POST_TYPE_LABELS: dict[ChannelPostType, str] = {
    ChannelPostType.TOPIC: "📰 Пост на тему",
    ChannelPostType.VIDEO: "🎬 Пост к ролику",
}

VIDEO_KIND_LABELS: dict[VideoPostKind, str] = {
    VideoPostKind.NEWS: "новость",
    VideoPostKind.TIPS: "фишка",
}

POST_TYPE_BUTTONS: dict[str, ChannelPostType] = {
    BTN_POST_TOPIC: ChannelPostType.TOPIC,
    BTN_POST_VIDEO: ChannelPostType.VIDEO,
}


def post_type_from_button(text: str) -> ChannelPostType | None:
    return POST_TYPE_BUTTONS.get(text.strip())


_NEWS_MARKERS = (
    "покуп",
    "сделк",
    "приобрет",
    "выкуп",
    "миллиард",
    "маск",
    "spacex",
    "спейс",
    "новост",
    "аналит",
    "ipo",
    "инвестиц",
    "слияни",
    "поглощ",
    "запуск",
    "релиз",
    "вышел",
    "объявил",
)
_TIPS_MARKERS = (
    "установ",
    "скачай",
    "репозитори",
    "github",
    "npm",
    "pip",
    "skill",
    "как пользов",
    "лайфхак",
    "инструмент",
    "openclaw",
    "playwright",
    "remotion",
    "попробуй",
    "команда",
)


def infer_video_post_kind(
    topic: str,
    script: str | None = None,
    *,
    rubric: str | None = None,
) -> VideoPostKind:
    """Новостной ролик → аналитика. Фишка/репо → установка и инструкция."""
    if rubric == "news":
        return VideoPostKind.NEWS
    if rubric == "tips":
        return VideoPostKind.TIPS
    if rubric == "story":
        return VideoPostKind.NEWS

    text = f"{topic}\n{script or ''}".lower()
    news_score = sum(1 for marker in _NEWS_MARKERS if marker in text)
    tips_score = sum(1 for marker in _TIPS_MARKERS if marker in text)
    if news_score > tips_score:
        return VideoPostKind.NEWS
    if tips_score > news_score:
        return VideoPostKind.TIPS
    return VideoPostKind.NEWS


TOPIC_POST_RESEARCH_PROMPT = """Собери материал из интернета для поста в Telegram-канале про AI / крипто / IT.

Тема автора:
{idea}

Ищи: TechCrunch, The Verge, Ars Technica, Bloomberg, Reuters, официальные блоги компаний, GitHub, HN, X.

Верни СПРАВКУ (по-русски):
СУТЬ: главная новость или инсайт в 2–3 предложениях
ФАКТЫ: цифры, даты, имена — только из источников
ЦИТАТА: одна яркая цитата из статьи/поста (если есть)
ССЫЛКИ: 2–4 релевантных URL (официальные сайты, репо, статьи)
УГОЛ: почему это интересно аудитории разработчиков / IT

Правила:
- Не выдумывай факты. Не пиши «не подтверждено».
- Не пиши готовый пост — только справку."""

VIDEO_TIPS_RESEARCH_PROMPT = """Собери материал для поста к Shorts-ролику про ИНСТРУМЕНТ / ФИШКУ / РЕПО.

Тема / сценарий ролика:
{idea}

Ищи: официальный сайт, GitHub, npm/pip, документация, skills, blog.

Верни СПРАВКУ (по-русски):
О ЧЁМ РОЛИК: одно предложение
ССЫЛКИ: URL (сайт, репо, docs, marketplace)
УСТАНОВКА: команда из официальной документации (если есть)
ШАГИ: 2–4 шага «как попробовать»
ПРОМПТЫ/КЕЙСЫ: 2–3 примера использования
СОВЕТ: один лайфхак

Правила:
- Только проверенные ссылки. Не выдумывай команды.
- Не пиши готовый пост — только справку."""

VIDEO_NEWS_RESEARCH_PROMPT = """Собери материал для поста к НОВОСТНОМУ Shorts-ролику.

Тема / сценарий ролика:
{idea}

Ищи: Reuters, Bloomberg, TechCrunch, The Verge, Ars Technica, официальные пресс-релизы, HN.

Верни СПРАВКУ (по-русски):
СОБЫТИЕ: что случилось, кто, когда, сумма/масштаб
СМЫСЛ ДЛЯ РАЗРАБОТЧИКОВ: что это значит пользователям продукта
РИСКИ/НЮАНСЫ: конфиденциальность, цены, нейтральность — из источников
ССЫЛКИ: 3–5 статей и первоисточников (НЕ ссылка на скачивание продукта)
ЦИТАТА: одна из статей (если есть)

Правила:
- Это НОВОСТЬ, не туториал. Не ищи «как установить» и docs продукта.
- Не выдумывай факты. Не пиши готовый пост — только справку."""

VIDEO_POST_RESEARCH_PROMPT = VIDEO_TIPS_RESEARCH_PROMPT

_CONCISE_STYLE = """
СТИЛЬ (обязательно):
- Плотно, как заметка в Telegram — без пресс-релиза и воды
- Предложения по 10–16 слов. Абзац — 2–3 предложения
- Без штампов: «ошеломляющий», «беспрецедентный», «укрепляет позиции», «в рамках сделки»
- Не повторяй заголовок в первом абзаце другими словами
- Второстепенное (IPO, даты закрытия, биографии) — только если критично для смысла
"""

_CHANNEL_PHILOSOPHY = """
ВОРОНКА КОНТЕНТА:
- TikTok/Shorts — поверхностный хук, рекламирует Telegram
- Telegram — здесь полный разбор, смысл, ссылки, инструкции
- НЕ отправляй читателя в Shorts/TikTok за подробностями — всё важное пиши В ЭТОМ посте
- ЗАПРЕЩЕНО: «подробнее в Shorts», «смотри ролик», «разобрал в TikTok», «в видео рассказал»
"""


def build_topic_post_prompt(
    *,
    idea: str,
    research_brief: str | None,
    channel_handle: str,
) -> str:
    research_block = (
        f"СПРАВКА ИЗ ИНТЕРНЕТА:\n{research_brief.strip()}\n\n"
        if research_brief and research_brief.strip()
        else ""
    )
    return f"""Ты — автор Telegram-канала про AI / IT / крипто.

{research_block}Тема поста:
{idea.strip()}

Напиши пост в стиле tech-блога: живо, плотно, без воды.
{_CHANNEL_PHILOSOPHY}
{_CONCISE_STYLE}
СТРУКТУРА:
1. Жирный заголовок — один тезис (<b>...</b>)
2. 3 коротких абзаца: суть → что значит → нюанс или риск
3. Опционально: короткая цитата в <blockquote> (до 25 слов)
4. Короткая реплика в конце (одно предложение)
5. Подпись ТОЧНО (копируй символ в символ): {channel_handle}

ФОРМАТ:
- Только HTML для Telegram: <b>, <i>, <a href="URL">текст</a>, <blockquote>
- Абзацы — пустой строкой, БЕЗ <p>, <div>, <br>
- Длина: 600–950 символов. НЕ длиннее 950.

Верни ТОЛЬКО текст поста."""


def build_video_tips_post_prompt(
    *,
    idea: str,
    research_brief: str | None,
    channel_handle: str,
    video_script: str | None = None,
) -> str:
    research_block = (
        f"СПРАВКА ИЗ ИНТЕРНЕТА:\n{research_brief.strip()}\n\n"
        if research_brief and research_brief.strip()
        else ""
    )
    script_block = (
        f"СЦЕНАРИЙ TIKTOK (поверхностный хук — раскрой глубже в посте):\n{video_script.strip()}\n\n"
        if video_script and video_script.strip()
        else ""
    )
    return f"""Ты — автор Telegram-канала про AI / IT. Пишешь ПОЛНЫЙ пост про инструмент / фишку.

{research_block}{script_block}Тема:
{idea.strip()}

Сценарий TikTok — только тизер. В Telegram дай всё нужное: установка, ссылки, как пользоваться.
{_CHANNEL_PHILOSOPHY}
{_CONCISE_STYLE}
СТРУКТУРА:
1. 1 абзац (2 предложения): что за инструмент и зачем он разработчику
2. Команда установки в <pre><code>команда</code></pre>
3. 2–3 ссылки: <a href="URL">название</a>
4. 1–2 кейса — жирный заголовок + короткий промпт в <blockquote>
5. <b>Совет:</b> одно предложение
6. Подпись ТОЧНО (копируй символ в символ): {channel_handle}

ЗАПРЕЩЕНО: новостной тон, сделки, отсылки к Shorts/TikTok.

ФОРМАТ:
- Только HTML для Telegram: <b>, <i>, <a>, <blockquote>, <code>, <pre>
- Длина: 800–1200 символов. НЕ длиннее 1200.

Верни ТОЛЬКО текст поста."""


def build_video_news_post_prompt(
    *,
    idea: str,
    research_brief: str | None,
    channel_handle: str,
    video_script: str | None = None,
) -> str:
    research_block = (
        f"СПРАВКА ИЗ ИНТЕРНЕТА:\n{research_brief.strip()}\n\n"
        if research_brief and research_brief.strip()
        else ""
    )
    script_block = (
        f"СЦЕНАРИЙ TIKTOK (поверхностный хук — раскрой глубже в посте):\n{video_script.strip()}\n\n"
        if video_script and video_script.strip()
        else ""
    )
    return f"""Ты — автор Telegram-канала про AI / IT. Пишешь ПОЛНЫЙ разбор новости.

{research_block}{script_block}Тема:
{idea.strip()}

Сценарий TikTok — только тизер. В Telegram объясни смысл, последствия и риски для разработчиков.
{_CHANNEL_PHILOSOPHY}
Это НОВОСТЬ (сделка, релиз, событие) — НЕ туториал по продукту.
{_CONCISE_STYLE}
СТРУКТУРА (строго):
1. <b>Заголовок</b> — одна строка, суть + цифра
2. Абзац 1 (2–3 предложения): что случилось, кто, на каких условиях
3. Абзац 2 (2–3 предложения): что это значит для разработчиков / пользователей продукта
4. Абзац 3 (2 предложения): риски и один нюанс (данные, цены, нейтральность)
5. «Источники:» + 2–3 ссылки <a href="URL">издание</a>
6. Подпись ТОЧНО (копируй символ в символ): {channel_handle}

ЗАПРЕЩЕНО:
- Больше 3 абзацев текста (кроме блока источников)
- Длинные цитаты CEO (макс. 20 слов в <blockquote> или без цитаты)
- Установка, curl, скачивание, tutorial
- IPO, «закрытие сделки в 2026», биографии, антимонопольные простыни
- Повтор одной мысли разными словами
- Любые отсылки к Shorts, TikTok, «смотри ролик», «подробнее в видео»

ФОРМАТ:
- Только HTML: <b>, <a>, <blockquote> (опционально, коротко)
- Длина: 550–900 символов. НЕ длиннее 900.

Верни ТОЛЬКО текст поста."""


def build_video_post_prompt(
    *,
    idea: str,
    research_brief: str | None,
    channel_handle: str,
    video_script: str | None = None,
    video_kind: VideoPostKind = VideoPostKind.TIPS,
) -> str:
    if video_kind is VideoPostKind.NEWS:
        return build_video_news_post_prompt(
            idea=idea,
            research_brief=research_brief,
            channel_handle=channel_handle,
            video_script=video_script,
        )
    return build_video_tips_post_prompt(
        idea=idea,
        research_brief=research_brief,
        channel_handle=channel_handle,
        video_script=video_script,
    )
