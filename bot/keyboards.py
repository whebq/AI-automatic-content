from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from config import TELEGRAM_CHANNEL_ID
from services.channel_post_types import BTN_POST_TOPIC, BTN_POST_VIDEO

# Главное меню
BTN_GENERATE_VIDEO = "🚀 Сгенерировать видео"
BTN_BRAINSTORM_TOPIC = "💡 Придумать тему"
BTN_VOICE_SCRIPT = "🎙 Озвучить сценарий"
BTN_CHANNEL_POST = "📝 Сделать пост"
BTN_HELP = "📖 Инструкция"
BTN_MAIN_MENU = "📱 Главное меню"

# Форматы ролика
BTN_RUBRIC_STORY = "📖 История"
BTN_RUBRIC_NEWS = "📰 Новость"
BTN_RUBRIC_TIPS = "💡 Фишка / репо"

RUBRIC_BUTTONS = (BTN_RUBRIC_STORY, BTN_RUBRIC_NEWS, BTN_RUBRIC_TIPS)
MAIN_MENU_BUTTONS = (
    BTN_GENERATE_VIDEO,
    BTN_BRAINSTORM_TOPIC,
    BTN_VOICE_SCRIPT,
    BTN_CHANNEL_POST,
    BTN_HELP,
)

CB_BRAINSTORM_GENERATE = "brainstorm_generate"
CB_BRAINSTORM_RUN = "brainstorm_run"
CB_EDIT_SCRIPT = "edit_script"
CB_MAIN_MENU = "main_menu"
CB_POST_PUBLISH = "post_publish"
CB_POST_REGENERATE = "post_regenerate"
CB_POST_EDIT = "post_edit"
CB_POST_FROM_VIDEO = "post_from_video"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_GENERATE_VIDEO), KeyboardButton(text=BTN_BRAINSTORM_TOPIC)],
            [KeyboardButton(text=BTN_VOICE_SCRIPT), KeyboardButton(text=BTN_CHANNEL_POST)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def nav_keyboard() -> ReplyKeyboardMarkup:
    """Только возврат в меню — для шагов ввода текста."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_MAIN_MENU)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def rubric_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_RUBRIC_STORY), KeyboardButton(text=BTN_RUBRIC_NEWS)],
            [KeyboardButton(text=BTN_RUBRIC_TIPS)],
            [KeyboardButton(text=BTN_MAIN_MENU)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def channel_post_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_POST_TOPIC), KeyboardButton(text=BTN_POST_VIDEO)],
            [KeyboardButton(text=BTN_MAIN_MENU)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def post_video_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Откорректировать сценарий", callback_data=CB_EDIT_SCRIPT)],
            [InlineKeyboardButton(text="📝 Пост к ролику", callback_data=CB_POST_FROM_VIDEO)],
            [InlineKeyboardButton(text=BTN_MAIN_MENU, callback_data=CB_MAIN_MENU)],
        ]
    )


def brainstorm_reply_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Сформировать промпт", callback_data=CB_BRAINSTORM_GENERATE)],
            [InlineKeyboardButton(text=BTN_MAIN_MENU, callback_data=CB_MAIN_MENU)],
        ]
    )


def brainstorm_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Сгенерировать видео", callback_data=CB_BRAINSTORM_RUN)],
            [InlineKeyboardButton(text=BTN_MAIN_MENU, callback_data=CB_MAIN_MENU)],
        ]
    )


def channel_post_preview_keyboard(*, has_video_session: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if has_video_session:
        rows.append(
            [InlineKeyboardButton(text="🎬 Пост к текущему ролику", callback_data=CB_POST_FROM_VIDEO)],
        )
    if TELEGRAM_CHANNEL_ID:
        rows.append(
            [InlineKeyboardButton(text="📤 Опубликовать в канал", callback_data=CB_POST_PUBLISH)],
        )
    rows.extend(
        [
            [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data=CB_POST_REGENERATE)],
            [InlineKeyboardButton(text="✏️ Отредактировать текст", callback_data=CB_POST_EDIT)],
            [InlineKeyboardButton(text=BTN_MAIN_MENU, callback_data=CB_MAIN_MENU)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
