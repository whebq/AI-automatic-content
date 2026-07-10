from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
TELEGRAM_CHANNEL_HANDLE = os.getenv("TELEGRAM_CHANNEL_HANDLE", "@your_channel").strip()
TELEGRAM_CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL_NAME", "AI Channel").strip()

# Gemini — отдельный ключ на задачу (каждый из своего Google Cloud проекта = своя квота).
# Если ключ задачи пуст — используется GEMINI_API_KEY.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_RESEARCH_API_KEY = os.getenv("GEMINI_RESEARCH_API_KEY", "").strip()
GEMINI_SCRIPT_API_KEY = os.getenv("GEMINI_SCRIPT_API_KEY", "").strip()
GEMINI_BRAINSTORM_API_KEY = os.getenv("GEMINI_BRAINSTORM_API_KEY", "").strip()
GEMINI_CHANNEL_POST_API_KEY = os.getenv("GEMINI_CHANNEL_POST_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.0-flash-lite,gemini-2.5-flash-lite",
    ).split(",")
    if model.strip()
]
GEMINI_SCRIPT_MODEL = os.getenv("GEMINI_SCRIPT_MODEL", "gemini-2.5-pro")
GEMINI_SCRIPT_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_SCRIPT_FALLBACK_MODELS",
        "gemini-2.5-flash,gemini-2.0-flash",
    ).split(",")
    if model.strip()
]
GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
GEMINI_MAX_RETRY_DELAY_SEC = float(os.getenv("GEMINI_MAX_RETRY_DELAY_SEC", "12"))
GEMINI_MAX_429_RETRIES = int(os.getenv("GEMINI_MAX_429_RETRIES", "1"))
RESEARCH_ENABLED = os.getenv("RESEARCH_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
GEMINI_RESEARCH_MODEL = os.getenv("GEMINI_RESEARCH_MODEL", "gemini-2.5-flash")
GEMINI_RESEARCH_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_RESEARCH_FALLBACK_MODELS",
        "gemini-2.5-flash-lite",
    ).split(",")
    if model.strip()
]
GEMINI_CHANNEL_POST_MODEL = os.getenv("GEMINI_CHANNEL_POST_MODEL", "gemini-2.5-flash")
GEMINI_CHANNEL_POST_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_CHANNEL_POST_FALLBACK_MODELS",
        "gemini-2.5-flash-lite,gemini-2.0-flash",
    ).split(",")
    if model.strip()
]
# Пауза между поиском и сценарием (сек), чтобы не упереться в RPM на одном ключе
GEMINI_STEP_DELAY_SEC = float(os.getenv("GEMINI_STEP_DELAY_SEC", "14"))

# TTS: edge | elevenlabs
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").lower()
TTS_VOICE = os.getenv("TTS_VOICE", "ru-RU-DmitryNeural")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVENLABS_STABILITY = float(os.getenv("ELEVENLABS_STABILITY", "0.52"))
ELEVENLABS_SIMILARITY_BOOST = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.78"))
ELEVENLABS_STYLE = float(os.getenv("ELEVENLABS_STYLE", "0.58"))
ELEVENLABS_SPEED = float(os.getenv("ELEVENLABS_SPEED", "1.08"))

# Assets
BACKGROUNDS_DIR = BASE_DIR / os.getenv("BACKGROUNDS_DIR", "assets/backgrounds")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "assets/output")
REFERENCES_DIR = BASE_DIR / "assets" / "references"

# Фон заготовки (как в референсе)
BACKGROUND_MODE = os.getenv("BACKGROUND_MODE", "texture").lower()
BACKGROUND_TEXTURE = BACKGROUNDS_DIR / os.getenv(
    "BACKGROUND_TEXTURE", "texture_navy.jpg"
)
_BACKGROUND_RGB_RAW = os.getenv("BACKGROUND_RGB", "22,32,62")
_rgb_parts = [
    max(0, min(255, int(part.strip())))
    for part in _BACKGROUND_RGB_RAW.split(",")
    if part.strip().isdigit()
][:3]
BACKGROUND_RGB: tuple[int, int, int] = (
    (_rgb_parts[0], _rgb_parts[1], _rgb_parts[2])
    if len(_rgb_parts) == 3
    else (22, 32, 62)
)
BACKGROUND_BRIGHTNESS = float(os.getenv("BACKGROUND_BRIGHTNESS", "1.12"))

# Длина сценария (~45 сек озвучки при скорости 1.08)
SCRIPT_MIN_WORDS = int(os.getenv("SCRIPT_MIN_WORDS", "78"))
SCRIPT_MAX_WORDS = int(os.getenv("SCRIPT_MAX_WORDS", "98"))
TARGET_VIDEO_DURATION_SEC = float(os.getenv("TARGET_VIDEO_DURATION_SEC", "48"))

# Canvas
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# TTS-тайминги (для внутренней обработки озвучки)
SUBTITLE_MAX_WORDS_ON_SCREEN = int(os.getenv("SUBTITLE_MAX_WORDS_ON_SCREEN", "5"))
SUBTITLE_PHRASE_TARGET_WORDS = int(os.getenv("SUBTITLE_PHRASE_TARGET_WORDS", "4"))

# Рендер
RENDER_FPS = int(os.getenv("RENDER_FPS", "30"))
RENDER_PRESET = os.getenv("RENDER_PRESET", "veryfast")
RENDER_THREADS = int(os.getenv("RENDER_THREADS", "4"))
