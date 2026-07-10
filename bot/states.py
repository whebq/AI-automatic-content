from aiogram.fsm.state import State, StatesGroup


class PanelStates(StatesGroup):
    main_menu = State()
    waiting_rubric = State()
    waiting_video_topic = State()
    waiting_manual_script = State()
    waiting_voiceover_script = State()
    waiting_channel_post_type = State()
    waiting_channel_post_topic = State()
    waiting_channel_post_edit = State()
    brainstorm_chat = State()
