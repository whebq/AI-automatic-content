import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.keyboards import (
    BTN_BRAINSTORM_TOPIC,
    BTN_CHANNEL_POST,
    BTN_GENERATE_VIDEO,
    BTN_HELP,
    BTN_MAIN_MENU,
    BTN_VOICE_SCRIPT,
    CB_BRAINSTORM_GENERATE,
    CB_BRAINSTORM_RUN,
    CB_EDIT_SCRIPT,
    CB_MAIN_MENU,
    CB_POST_EDIT,
    CB_POST_FROM_VIDEO,
    CB_POST_PUBLISH,
    CB_POST_REGENERATE,
    brainstorm_prompt_keyboard,
    brainstorm_reply_keyboard,
    channel_post_preview_keyboard,
    channel_post_type_keyboard,
    main_menu_keyboard,
    nav_keyboard,
    post_video_keyboard,
    rubric_keyboard,
)
from bot.states import PanelStates
from config import (
    TELEGRAM_ALLOWED_USER_ID,
    TELEGRAM_CHANNEL_HANDLE,
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHANNEL_NAME,
)
from models import ChannelPostResult, PipelineResult
from pipeline import PipelineError, VideoPipeline
from services.channel_post_types import (
    POST_TYPE_LABELS,
    VIDEO_KIND_LABELS,
    ChannelPostType,
    VideoPostKind,
    infer_video_post_kind,
    post_type_from_button,
)
from services.content_rubrics import BRAINSTORM_INTRO_BY_RUBRIC
from services.script_rubrics import RUBRIC_LABELS, ScriptRubric, rubric_from_button
from services.telegram_html import prepare_channel_post_html

logger = logging.getLogger(__name__)

router = Router()
pipeline = VideoPipeline()

WELCOME_TEXT = (
    "<b>ИИ-агент</b> для генерации контента и ведения соцсетей.\n\n"
    "🚀 Видео — сценарий, озвучка и заготовка для монтажа\n"
    "💡 Тема — подбор идеи с ИИ\n"
    "🎙 Озвучка — готовый текст в mp3\n"
    "📝 Пост — текст для Telegram-канала\n"
    "📖 Инструкция — как писать промпты и пользоваться ботом\n\n"
    "Форматы: История · Новость · Фишка"
)

INSTRUCTION_TEXT = (
    "📖 <b>Как пользоваться ботом</b>\n\n"
    "🚀 <b>Сгенерировать видео</b>\n"
    "Выбери формат → напиши тему одним сообщением → получишь сценарий, mp3 и mp4-заготовку.\n\n"
    "💡 <b>Придумать тему</b>\n"
    "Выбери формат → коротко опиши нишу или идею → когда всё ясно, нажми «Сформировать промпт» → проверь текст и запусти генерацию.\n\n"
    "✍️ <b>Хороший промпт</b>\n"
    "Одна конкретная идея: кто / что случилось / зачем зрителю. Не «сделай про ИИ», а «OpenAI купила X — что это значит для разработчиков».\n\n"
    "🎙 <b>Озвучка</b>\n"
    "Каждая фраза с новой строки, цифры словами, без пояснений в скобках.\n\n"
    "📝 <b>Пост</b>\n"
    "Пост на тему — разбор для канала. Пост к ролику — тема + сценарий Shorts, в Telegram получишь полный текст.\n\n"
    "🎬 <b>Что на выходе</b>\n"
    "Видео с фоном и голосом — это заготовка. Субтитры и вставки добавляешь сам при монтаже.\n\n"
    "📄 Подробная инструкция — в файле <code>instructions.md</code> в репозитории."
)

FLOW_GENERATE = "generate"
FLOW_BRAINSTORM = "brainstorm"

RUBRIC_PROMPT = (
    "🎬 Выбери формат ролика:\n\n"
    "📖 <b>История</b> — кейс человека с фактами и сюжетом (~45 сек)\n"
    "📰 <b>Новость</b> — что случилось и почему важно\n"
    "💡 <b>Фишка / репо</b> — сайт, инструмент, лайфхак"
)

TOPIC_PROMPTS = {
    ScriptRubric.STORY: (
        "📝 Тема для <b>истории</b>. Опиши героя и суть:\n"
        "• «Джон Дагита украл 46 млн у US Marshals — как схема работала»"
    ),
    ScriptRubric.NEWS: (
        "📝 Тема для <b>новости</b>:\n"
        "• «OpenAI выпустила GPT-5 — что изменилось для разработчиков»"
    ),
    ScriptRubric.TIPS: (
        "📝 Тема для <b>фишки</b>:\n"
        "• «Репозиторий на GitHub, который ускоряет монтаж в 10 раз»"
    ),
}

BRAINSTORM_PICK_RUBRIC = (
    "💡 Сначала выбери формат ролика — потом обсудим идею с ИИ-продюсером."
)

BRAINSTORM_PROMPT_READY = (
    "Отредактируй промпт при необходимости и отправь текстом — "
    "или нажми «🚀 Сгенерировать видео»."
)

EDIT_SCRIPT_PROMPT = (
    "✏️ Отправь <b>полный исправленный сценарий</b>.\n\n"
    "• Каждая фраза — с новой строки\n"
    "• Цифры словами: «сорок шесть миллионов»\n"
    "• Без пояснений — только текст для озвучки\n\n"
    "После отправки переозвучу и соберу новое видео."
)

VOICE_SCRIPT_PROMPT = (
    "🎙 Отправь <b>текст сценария</b> для озвучки.\n\n"
    "• Каждая фраза — с новой строки\n"
    "• Цифры словами: «сорок шесть миллионов»\n"
    "• Без пояснений — только текст\n\n"
    "Верну mp3 для монтажа."
)

CHANNEL_POST_TYPE_PROMPT = (
    f"📝 Выбери тип поста для канала <b>{TELEGRAM_CHANNEL_NAME}</b>:\n\n"
    "📰 <b>Пост на тему</b> — разбор новости/инсайта в Telegram\n"
    "🎬 <b>Пост к ролику</b> — полное объяснение темы из TikTok:\n"
    "   · новость → смысл и риски для разработчиков\n"
    "   · фишка → установка, ссылки, как пользоваться"
)

CHANNEL_POST_TOPIC_PROMPT = (
    "📰 Опиши <b>тему поста</b>:\n"
    "• «Anthropic: 80% кода пишет Claude — что это значит»\n"
    "• «Кастомный статус-бар в Claude Code через ccstatusline»"
)

CHANNEL_POST_VIDEO_PROMPT = (
    "🎬 Опиши <b>тему</b> и вставь сценарий из TikTok.\n\n"
    "Первая строка — о чём, дальше — текст сценария.\n\n"
    "TikTok — тизер, Telegram — полный разбор. Бот раскроет тему здесь, без отсылок к ролику."
)

CHANNEL_POST_EDIT_PROMPT = (
    "✏️ Отправь <b>полный текст поста</b> (HTML: &lt;b&gt;, &lt;a&gt;, &lt;blockquote&gt;, &lt;pre&gt;).\n"
    "Без пояснений — только текст для публикации."
)


def _is_allowed_user(user_id: int | None) -> bool:
    return user_id == TELEGRAM_ALLOWED_USER_ID


async def _deny_access(message: Message) -> None:
    await message.answer("У вас нет доступа к этому боту.")


async def _show_main_menu(message: Message, state: FSMContext) -> None:
    old_video = (await state.get_data()).get("video_path")
    if old_video:
        VideoPipeline.cleanup_delivery(old_video)

    await state.clear()
    await state.set_state(PanelStates.main_menu)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


async def _go_main_menu_if_requested(message: Message, state: FSMContext) -> bool:
    """Возврат в главное меню по reply-кнопке. True = обработано."""
    if (message.text or "").strip() != BTN_MAIN_MENU:
        return False
    await _show_main_menu(message, state)
    return True


async def _show_instructions(message: Message) -> None:
    await message.answer(INSTRUCTION_TEXT, reply_markup=main_menu_keyboard())


def _save_session(result: PipelineResult) -> dict:
    return {
        "script": result.script,
        "video_path": result.video_path,
        "audio_path": result.audio_path,
        "idea": result.idea,
        "research_brief": result.research_brief,
        "research_sources": list(result.research_sources),
        "rubric": result.rubric,
    }


def _save_channel_post(result: ChannelPostResult) -> dict:
    return {
        "channel_post_text": result.text,
        "channel_post_type": result.post_type,
        "channel_post_topic": result.topic,
        "channel_post_brief": result.research_brief,
        "channel_post_sources": list(result.research_sources),
        "channel_post_script": result.video_script,
        "channel_post_video_kind": result.video_kind,
    }


def _post_type_from_state(data: dict) -> ChannelPostType:
    raw = data.get("channel_post_type", ChannelPostType.TOPIC.value)
    try:
        return ChannelPostType(raw)
    except ValueError:
        return ChannelPostType.TOPIC


async def _send_video_result(
    bot: Bot,
    chat_id: int,
    result: PipelineResult,
) -> None:
    await bot.send_video(
        chat_id=chat_id,
        video=FSInputFile(result.video_path, filename="result.mp4"),
        caption="✅ Заготовка готова — дальше монтаж и субтитры.",
        reply_markup=post_video_keyboard(),
        supports_streaming=True,
    )

    await bot.send_audio(
        chat_id=chat_id,
        audio=FSInputFile(result.audio_path, filename="voiceover.mp3"),
        caption="🎙 Озвучка (mp3 для монтажа)",
    )

    await bot.send_message(
        chat_id=chat_id,
        text=f"📝 <b>Сценарий:</b>\n\n{result.script}",
    )


async def _finalize_video_update(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    result: PipelineResult,
    status_message: Message,
) -> None:
    data = await state.get_data()
    old_video = data.get("video_path")
    if old_video and old_video != result.video_path:
        VideoPipeline.cleanup_delivery(old_video)

    await status_message.edit_text("📤 Отправляю заготовку...")
    await _send_video_result(bot, chat_id, result)

    await state.update_data(**_save_session(result))
    await state.set_state(PanelStates.main_menu)
    await status_message.delete()
    await bot.send_message(chat_id, "Выбери действие:", reply_markup=main_menu_keyboard())


def _rubric_from_state(data: dict) -> ScriptRubric:
    rubric_raw = data.get("rubric", ScriptRubric.STORY.value)
    try:
        return ScriptRubric(rubric_raw)
    except ValueError:
        return ScriptRubric.STORY


async def _start_rubric_selection(
    message: Message,
    state: FSMContext,
    *,
    flow_mode: str,
    prompt_text: str | None = None,
) -> None:
    await state.set_state(PanelStates.waiting_rubric)
    await state.update_data(flow_mode=flow_mode)
    await message.answer(prompt_text or RUBRIC_PROMPT, reply_markup=rubric_keyboard())


def _session_or_error(data: dict) -> tuple[str, str, str, tuple[str, ...], ScriptRubric] | None:
    script = data.get("script")
    idea = data.get("idea", "")
    if not script:
        return None
    research_brief = data.get("research_brief", "")
    sources = tuple(data.get("research_sources") or ())
    return script, idea, research_brief, sources, _rubric_from_state(data)


async def _run_generation(
    message: Message,
    bot: Bot,
    state: FSMContext,
    idea: str,
    *,
    rubric: ScriptRubric,
) -> None:
    status_message = await message.answer("⏳ Запускаю генерацию...")

    async def on_stage(stage: str) -> None:
        await status_message.edit_text(stage)

    try:
        result = await pipeline.run(idea, on_stage=on_stage, rubric=rubric)
        await _finalize_video_update(bot, message.chat.id, state, result, status_message)
    except PipelineError as exc:
        logger.exception("Pipeline failed at stage: %s", exc.stage)
        await status_message.edit_text(f"❌ Ошибка на этапе «{exc.stage}»:\n{exc}")
        await state.set_state(PanelStates.main_menu)
    except Exception as exc:
        logger.exception("Unexpected pipeline error")
        await status_message.edit_text(f"❌ Непредвиденная ошибка:\n{exc}")
        await state.set_state(PanelStates.main_menu)


async def _safe_status_error(
    status_message: Message,
    bot: Bot,
    chat_id: int,
    text: str,
) -> None:
    try:
        await status_message.edit_text(text)
    except TelegramBadRequest:
        await bot.send_message(chat_id, text)


async def _send_channel_post_preview(
    bot: Bot,
    chat_id: int,
    result: ChannelPostResult,
    *,
    has_video_session: bool = False,
) -> None:
    type_label = POST_TYPE_LABELS.get(
        ChannelPostType(result.post_type), result.post_type
    )
    if result.post_type == ChannelPostType.VIDEO.value and result.video_kind:
        try:
            kind_label = VIDEO_KIND_LABELS[VideoPostKind(result.video_kind)]
            type_label = f"{type_label} · {kind_label}"
        except ValueError:
            pass
    footer = (
        "\n\n<i>Скопируй текст и выложи в канал вручную. "
        "Автопубликация подключится позже.</i>"
        if not TELEGRAM_CHANNEL_ID
        else ""
    )
    post_html = prepare_channel_post_html(result.text, TELEGRAM_CHANNEL_HANDLE)
    header = f"📝 <b>Превью поста</b> ({type_label}):{footer}"
    keyboard = channel_post_preview_keyboard(has_video_session=has_video_session)

    try:
        if len(f"{header}\n\n{post_html}") <= 4096:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{header}\n\n{post_html}",
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return
        await bot.send_message(chat_id, text=header, disable_web_page_preview=True)
        await bot.send_message(
            chat_id=chat_id,
            text=post_html,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except TelegramBadRequest:
        await bot.send_message(
            chat_id=chat_id,
            text=f"{header}\n\n{post_html}",
            reply_markup=keyboard,
            parse_mode=None,
            disable_web_page_preview=True,
        )


async def _run_channel_post(
    message: Message,
    bot: Bot,
    state: FSMContext,
    topic: str,
    *,
    post_type: ChannelPostType,
    video_script: str | None = None,
    rubric: str | None = None,
) -> None:
    status_message = await message.answer("⏳ Генерирую пост...")

    async def on_stage(stage: str) -> None:
        await status_message.edit_text(stage)

    try:
        result = await pipeline.generate_channel_post(
            topic,
            post_type=post_type,
            video_script=video_script,
            rubric=rubric,
            on_stage=on_stage,
        )
        data = await state.get_data()
        has_video = bool(data.get("script"))
        await _send_channel_post_preview(
            bot, message.chat.id, result, has_video_session=has_video
        )
        await status_message.delete()
        sanitized = ChannelPostResult(
            text=prepare_channel_post_html(result.text, TELEGRAM_CHANNEL_HANDLE),
            post_type=result.post_type,
            topic=result.topic,
            research_brief=result.research_brief,
            research_sources=result.research_sources,
            video_script=result.video_script,
            video_kind=result.video_kind,
        )
        await state.update_data(**_save_channel_post(sanitized))
        await state.set_state(PanelStates.main_menu)
        await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())
    except PipelineError as exc:
        logger.exception("Channel post failed at stage: %s", exc.stage)
        await _safe_status_error(
            status_message,
            bot,
            message.chat.id,
            f"❌ Ошибка на этапе «{exc.stage}»:\n{exc}",
        )
        await state.set_state(PanelStates.main_menu)
    except Exception as exc:
        logger.exception("Unexpected channel post error")
        await _safe_status_error(
            status_message,
            bot,
            message.chat.id,
            f"❌ Непредвиденная ошибка:\n{exc}",
        )
        await state.set_state(PanelStates.main_menu)


async def _publish_channel_post(bot: Bot, chat_id: int, post_text: str) -> str | None:
    if not TELEGRAM_CHANNEL_ID:
        return (
            "Канал не настроен. Добавь TELEGRAM_CHANNEL_ID в .env "
            "(ID канала или @username, бот должен быть админом)."
        )
    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=prepare_channel_post_html(post_text, TELEGRAM_CHANNEL_HANDLE),
            disable_web_page_preview=False,
        )
    except Exception as exc:
        logger.exception("Failed to publish channel post")
        return f"Не удалось опубликовать: {exc}"
    return None


async def _run_voice_script(
    message: Message,
    bot: Bot,
    state: FSMContext,
    script: str,
    *,
    rubric: ScriptRubric | None = None,
) -> None:
    status_message = await message.answer("⏳ Озвучиваю сценарий...")

    async def on_stage(stage: str) -> None:
        await status_message.edit_text(stage)

    try:
        audio_path = await pipeline.voice_script(
            script, on_stage=on_stage, rubric=rubric
        )
        await status_message.edit_text("📤 Отправляю озвучку...")
        await bot.send_audio(
            chat_id=message.chat.id,
            audio=FSInputFile(audio_path, filename="voiceover.mp3"),
            caption="🎙 Озвучка готова",
        )
        VideoPipeline.cleanup_delivery(audio_path)
        await status_message.delete()
        await state.set_state(PanelStates.main_menu)
        await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())
    except PipelineError as exc:
        logger.exception("Voice script failed at stage: %s", exc.stage)
        await status_message.edit_text(f"❌ Ошибка на этапе «{exc.stage}»:\n{exc}")
        await state.set_state(PanelStates.main_menu)
    except Exception as exc:
        logger.exception("Unexpected voice script error")
        await status_message.edit_text(f"❌ Непредвиденная ошибка:\n{exc}")
        await state.set_state(PanelStates.main_menu)


async def _run_script_correction(
    message: Message,
    bot: Bot,
    state: FSMContext,
    script: str,
) -> None:
    data = await state.get_data()
    session = _session_or_error(data)
    if session is None:
        await message.answer(
            "Данные ролика устарели. Сгенерируй видео заново.",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(PanelStates.main_menu)
        return

    _, idea, research_brief, research_sources, rubric = session
    status_message = await message.answer("⏳ Переозвучиваю и собираю видео...")

    async def on_stage(stage: str) -> None:
        await status_message.edit_text(stage)

    try:
        result = await pipeline.render_from_script(
            script,
            on_stage=on_stage,
            idea=idea,
            rubric=rubric,
            research_brief=research_brief,
            research_sources=research_sources,
        )
        await _finalize_video_update(bot, message.chat.id, state, result, status_message)
    except PipelineError as exc:
        logger.exception("Script correction failed at stage: %s", exc.stage)
        await status_message.edit_text(f"❌ Ошибка на этапе «{exc.stage}»:\n{exc}")
        await state.set_state(PanelStates.main_menu)
    except Exception as exc:
        logger.exception("Unexpected script correction error")
        await status_message.edit_text(f"❌ Непредвиденная ошибка:\n{exc}")
        await state.set_state(PanelStates.main_menu)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    await _show_main_menu(message, state)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await _show_instructions(message)


@router.message(PanelStates.main_menu, F.text == BTN_HELP)
async def on_help_button(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    await state.set_state(PanelStates.main_menu)
    await _show_instructions(message)


@router.message(PanelStates.main_menu, F.text == BTN_BRAINSTORM_TOPIC)
async def on_brainstorm_start(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    await _start_rubric_selection(
        message, state, flow_mode=FLOW_BRAINSTORM, prompt_text=BRAINSTORM_PICK_RUBRIC
    )


@router.message(PanelStates.brainstorm_chat, F.text)
async def on_brainstorm_message(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    user_message = (message.text or "").strip()
    if not user_message:
        await message.answer(
            "Напиши сообщение текстом — обсудим идею для ролика.",
            reply_markup=nav_keyboard(),
        )
        return

    status_message = await message.answer("🔍 Ищу в интернете...")
    data = await state.get_data()
    history: list[dict[str, str]] = list(data.get("brainstorm_history") or [])
    rubric = _rubric_from_state(data)

    async def on_stage(stage: str) -> None:
        await status_message.edit_text(stage)

    try:
        reply = await pipeline.brainstorm_reply(
            user_message, history, rubric=rubric, on_stage=on_stage
        )
        history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": reply},
            ]
        )
        await state.update_data(brainstorm_history=history)
        await status_message.edit_text(reply, reply_markup=brainstorm_reply_keyboard())
    except PipelineError as exc:
        logger.exception("Brainstorm failed at stage: %s", exc.stage)
        await status_message.edit_text(f"❌ Ошибка на этапе «{exc.stage}»:\n{exc}")
    except Exception as exc:
        logger.exception("Unexpected brainstorm error")
        await status_message.edit_text(f"❌ Непредвиденная ошибка:\n{exc}")


@router.callback_query(F.data == CB_BRAINSTORM_GENERATE)
async def on_brainstorm_generate(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    history: list[dict[str, str]] = list(data.get("brainstorm_history") or [])
    if not history:
        await callback.answer("Сначала напиши хотя бы одно сообщение в чате.", show_alert=True)
        return

    rubric = _rubric_from_state(data)
    await callback.answer()
    if not callback.message:
        return

    status_message = await callback.message.answer("🔍 Ищу в интернете...")

    async def on_stage(stage: str) -> None:
        await status_message.edit_text(stage)

    try:
        topic = await pipeline.summarize_brainstorm(
            history, rubric=rubric, on_stage=on_stage
        )
        await state.update_data(brainstorm_prompt=topic, flow_mode=FLOW_GENERATE)
        await state.set_state(PanelStates.waiting_video_topic)
        await status_message.edit_text(
            f"📝 <b>Промпт для генерации</b> ({RUBRIC_LABELS[rubric]}):\n\n{topic}\n\n"
            f"{BRAINSTORM_PROMPT_READY}",
            reply_markup=brainstorm_prompt_keyboard(),
        )
    except PipelineError as exc:
        logger.exception("Brainstorm summarize failed at stage: %s", exc.stage)
        await status_message.edit_text(f"❌ Ошибка на этапе «{exc.stage}»:\n{exc}")
        await state.set_state(PanelStates.brainstorm_chat)
    except Exception as exc:
        logger.exception("Unexpected brainstorm summarize error")
        await status_message.edit_text(f"❌ Непредвиденная ошибка:\n{exc}")
        await state.set_state(PanelStates.brainstorm_chat)


@router.callback_query(F.data == CB_BRAINSTORM_RUN)
async def on_brainstorm_run(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    topic = (data.get("brainstorm_prompt") or "").strip()
    if not topic:
        await callback.answer("Промпт устарел. Сформируй его заново в чате.", show_alert=True)
        return

    rubric = _rubric_from_state(data)
    await callback.answer()
    if not callback.message:
        return

    await _run_generation(callback.message, bot, state, topic, rubric=rubric)


@router.message(PanelStates.main_menu, F.text == BTN_CHANNEL_POST)
async def on_channel_post_start(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    await state.set_state(PanelStates.waiting_channel_post_type)
    await message.answer(CHANNEL_POST_TYPE_PROMPT, reply_markup=channel_post_type_keyboard())


@router.message(PanelStates.waiting_channel_post_type, F.text)
async def on_channel_post_type_selected(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    post_type = post_type_from_button(message.text or "")
    if post_type is None:
        await message.answer(
            "Выбери тип поста кнопкой ниже.",
            reply_markup=channel_post_type_keyboard(),
        )
        return

    await state.update_data(channel_post_type=post_type.value)
    await state.set_state(PanelStates.waiting_channel_post_topic)
    prompt = (
        CHANNEL_POST_VIDEO_PROMPT
        if post_type is ChannelPostType.VIDEO
        else CHANNEL_POST_TOPIC_PROMPT
    )
    await message.answer(prompt, reply_markup=nav_keyboard())


@router.message(PanelStates.waiting_channel_post_topic, F.text)
async def on_channel_post_topic_received(message: Message, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Тема не может быть пустой.", reply_markup=nav_keyboard())
        return

    data = await state.get_data()
    post_type = _post_type_from_state(data)
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    topic = lines[0] if lines else raw
    video_script = "\n".join(lines[1:]) if post_type is ChannelPostType.VIDEO and len(lines) > 1 else None
    rubric = data.get("rubric") if post_type is ChannelPostType.VIDEO else None

    await _run_channel_post(
        message,
        bot,
        state,
        topic,
        post_type=post_type,
        video_script=video_script,
        rubric=rubric,
    )


@router.callback_query(F.data == CB_POST_PUBLISH)
async def on_post_publish(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    post_text = (data.get("channel_post_text") or "").strip()
    if not post_text:
        await callback.answer("Пост устарел. Сгенерируй заново.", show_alert=True)
        return

    await callback.answer()
    error = await _publish_channel_post(bot, callback.message.chat.id if callback.message else 0, post_text)
    if callback.message:
        if error:
            await callback.message.answer(f"❌ {error}")
        else:
            await callback.message.answer(
                "✅ Пост опубликован в канале.",
                reply_markup=main_menu_keyboard(),
            )


@router.callback_query(F.data == CB_POST_REGENERATE)
async def on_post_regenerate(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    topic = (data.get("channel_post_topic") or "").strip()
    if not topic:
        await callback.answer("Данные поста устарели.", show_alert=True)
        return

    post_type = _post_type_from_state(data)
    video_script = (data.get("channel_post_script") or "").strip() or None
    rubric = data.get("rubric") if post_type is ChannelPostType.VIDEO else None
    await callback.answer()
    if callback.message:
        await _run_channel_post(
            callback.message,
            bot,
            state,
            topic,
            post_type=post_type,
            video_script=video_script,
            rubric=rubric,
        )


@router.callback_query(F.data == CB_POST_EDIT)
async def on_post_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    if not (data.get("channel_post_text") or "").strip():
        await callback.answer("Пост устарел. Сгенерируй заново.", show_alert=True)
        return

    await callback.answer()
    await state.set_state(PanelStates.waiting_channel_post_edit)
    if callback.message:
        await callback.message.answer(CHANNEL_POST_EDIT_PROMPT, reply_markup=nav_keyboard())


@router.callback_query(F.data == CB_POST_FROM_VIDEO)
async def on_post_from_video(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    session = _session_or_error(data)
    if session is None:
        await callback.answer("Данные ролика устарели.", show_alert=True)
        return

    script, idea, _, _, rubric = session
    topic = idea.strip() or script.splitlines()[0].strip()
    await callback.answer()
    if callback.message:
        await state.update_data(channel_post_type=ChannelPostType.VIDEO.value)
        await _run_channel_post(
            callback.message,
            bot,
            state,
            topic,
            post_type=ChannelPostType.VIDEO,
            video_script=script,
            rubric=rubric.value,
        )


@router.message(PanelStates.waiting_channel_post_edit, F.text)
async def on_channel_post_edited(message: Message, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    post_text = (message.text or "").strip()
    if not post_text:
        await message.answer("Текст поста не может быть пустым.", reply_markup=nav_keyboard())
        return

    post_text = prepare_channel_post_html(post_text, TELEGRAM_CHANNEL_HANDLE)
    data = await state.get_data()
    result = ChannelPostResult(
        text=post_text,
        post_type=data.get("channel_post_type", ChannelPostType.TOPIC.value),
        topic=data.get("channel_post_topic", ""),
        research_brief=data.get("channel_post_brief", ""),
        research_sources=tuple(data.get("channel_post_sources") or ()),
        video_script=data.get("channel_post_script", ""),
        video_kind=data.get("channel_post_video_kind", ""),
    )
    has_video = bool(data.get("script"))
    await _send_channel_post_preview(
        bot, message.chat.id, result, has_video_session=has_video
    )
    await state.update_data(**_save_channel_post(result))
    await state.set_state(PanelStates.main_menu)
    await message.answer("Выбери действие:", reply_markup=main_menu_keyboard())


@router.message(PanelStates.main_menu, F.text == BTN_VOICE_SCRIPT)
async def on_voice_script_start(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    await state.set_state(PanelStates.waiting_voiceover_script)
    await message.answer(VOICE_SCRIPT_PROMPT, reply_markup=nav_keyboard())


@router.message(PanelStates.main_menu, F.text == BTN_GENERATE_VIDEO)
async def on_generate_video_button(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    await _start_rubric_selection(message, state, flow_mode=FLOW_GENERATE)


@router.message(PanelStates.waiting_rubric, F.text)
async def on_rubric_selected(message: Message, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    rubric = rubric_from_button(message.text or "")
    if rubric is None:
        await message.answer("Выбери формат кнопкой ниже.", reply_markup=rubric_keyboard())
        return

    data = await state.get_data()
    flow_mode = data.get("flow_mode", FLOW_GENERATE)
    await state.update_data(rubric=rubric.value)

    if flow_mode == FLOW_BRAINSTORM:
        await state.set_state(PanelStates.brainstorm_chat)
        await state.update_data(brainstorm_history=[])
        await message.answer(
            BRAINSTORM_INTRO_BY_RUBRIC[rubric.value],
            reply_markup=nav_keyboard(),
        )
        return

    await state.set_state(PanelStates.waiting_video_topic)
    await message.answer(TOPIC_PROMPTS[rubric], reply_markup=nav_keyboard())


@router.message(PanelStates.waiting_video_topic, F.text)
async def on_video_topic_received(message: Message, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    idea = (message.text or "").strip()
    if not idea:
        await message.answer(
            "Тема не может быть пустой. Отправь текст идеи или промпта.",
            reply_markup=nav_keyboard(),
        )
        return

    data = await state.get_data()
    rubric = _rubric_from_state(data)

    await _run_generation(message, bot, state, idea, rubric=rubric)


@router.callback_query(F.data == CB_EDIT_SCRIPT)
async def on_edit_script_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    if _session_or_error(data) is None:
        await callback.answer("Данные ролика устарели. Сгенерируй видео заново.", show_alert=True)
        return

    await callback.answer()
    await state.set_state(PanelStates.waiting_manual_script)

    if callback.message:
        await callback.message.answer(EDIT_SCRIPT_PROMPT, reply_markup=nav_keyboard())


@router.message(PanelStates.waiting_manual_script, F.text)
async def on_manual_script_received(message: Message, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    script = (message.text or "").strip()
    if not script:
        await message.answer(
            "Сценарий не может быть пустым. Отправь полный текст для озвучки.",
            reply_markup=nav_keyboard(),
        )
        return

    await _run_script_correction(message, bot, state, script)


@router.message(PanelStates.waiting_voiceover_script, F.text)
async def on_voiceover_script_received(message: Message, bot: Bot, state: FSMContext) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        await _deny_access(message)
        return

    if await _go_main_menu_if_requested(message, state):
        return

    script = (message.text or "").strip()
    if not script:
        await message.answer(
            "Сценарий не может быть пустым. Отправь текст для озвучки.",
            reply_markup=nav_keyboard(),
        )
        return

    data = await state.get_data()
    rubric = _rubric_from_state(data) if data.get("rubric") else None
    await _run_voice_script(message, bot, state, script, rubric=rubric)


@router.callback_query(F.data == CB_MAIN_MENU)
async def on_main_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_allowed_user(callback.from_user.id if callback.from_user else None):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await callback.answer()
    if callback.message:
        await _show_main_menu(callback.message, state)


@router.message(PanelStates.brainstorm_chat)
async def on_brainstorm_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer(
        "Напиши текстом, о чём хочешь снять ролик — или нажми кнопки под моим ответом.",
        reply_markup=nav_keyboard(),
    )


@router.message(PanelStates.main_menu)
async def on_main_menu_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer(
        "Выбери действие на клавиатуре.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(PanelStates.waiting_rubric)
async def on_waiting_rubric_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer("Выбери формат ролика кнопкой ниже.", reply_markup=rubric_keyboard())


@router.message(PanelStates.waiting_video_topic)
async def on_waiting_topic_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer(
        "📝 Отправь текстовую тему или промпт для видео.",
        reply_markup=nav_keyboard(),
    )


@router.message(PanelStates.waiting_manual_script)
async def on_waiting_manual_script_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer(
        "✏️ Отправь полный исправленный сценарий текстом.",
        reply_markup=nav_keyboard(),
    )


@router.message(PanelStates.waiting_channel_post_type)
async def on_waiting_channel_post_type_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer(
        "Выбери тип поста кнопкой ниже.",
        reply_markup=channel_post_type_keyboard(),
    )


@router.message(PanelStates.waiting_channel_post_topic)
async def on_waiting_channel_post_topic_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer("📝 Отправь тему поста текстом.", reply_markup=nav_keyboard())


@router.message(PanelStates.waiting_channel_post_edit)
async def on_waiting_channel_post_edit_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer("✏️ Отправь полный текст поста.", reply_markup=nav_keyboard())


@router.message(PanelStates.waiting_voiceover_script)
async def on_waiting_voiceover_fallback(message: Message) -> None:
    if not _is_allowed_user(message.from_user.id if message.from_user else None):
        return

    await message.answer(
        "🎙 Отправь текст сценария для озвучки.",
        reply_markup=nav_keyboard(),
    )
