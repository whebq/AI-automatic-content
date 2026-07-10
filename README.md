# shorts-generator

Telegram-бот и Python-пайплайн для вертикальных Shorts (1080×1920): сценарий → озвучка → видео-заготовка (фон + голос). Субтитры и оверлеи монтируются вручную в CapCut.

## Стек

| Компонент | Технология |
|-----------|------------|
| Бот | aiogram 3 (FSM, polling) |
| Сценарий / research / посты | Google Gemini (`google-genai`) |
| TTS | Edge TTS или ElevenLabs |
| Рендер | MoviePy 2 + Pillow |
| Конфиг | `.env` → `config.py` |

Требования: Python 3.11+, FFmpeg в `PATH`.

## Архитектура

```
main.py                  # polling бота
bot/
  handlers.py            # FSM: генерация, brainstorm, озвучка, посты, правки
  keyboards.py
  states.py
pipeline.py              # VideoPipeline — оркестратор
services/
  text_generator.py      # сценарий / revise / brainstorm
  topic_researcher.py    # Gemini + Google Search grounding
  audio_generator.py     # TTS + сегменты субтитров
  tts_provider.py        # edge | elevenlabs
  video_renderer.py      # texture/RGB фон + mp3 → mp4
  script_rubrics.py      # промпты story / news / tips
  channel_post_*.py      # посты для Telegram-канала
  gemini_*.py            # ключи по задачам, retry, grounding
models.py                # dataclasses результатов
assets/
  backgrounds/           # texture_navy.jpg
  references/rubrics/    # style_block.txt по рубрикам
  overlays/              # локальные вставки для CapCut (не в git)
  output/                # временный вывод пайплайна
```

### Поток генерации видео

1. (опц.) `TopicResearcher` — факты через Gemini + Search (`story` / `news`)
2. `TextGenerator` — сценарий по рубрике (`GEMINI_SCRIPT_*`)
3. `AudioGenerator` — mp3 + word/phrase timings
4. `VideoRenderer` — 1080×1920, фон + аудио, без субтитров на кадре
5. Доставка в Telegram: `result.mp4` + `voiceover.mp3` + текст сценария

Доступ к боту: один `TELEGRAM_ALLOWED_USER_ID`.

## Рубрики

| Код | Назначение | Промпт |
|-----|------------|--------|
| `story` | Кейс человека: хук → схема → финал → CTA | `assets/references/rubrics/story/style_block.txt` |
| `news` | Событие «прямо сейчас», спокойный тон | `…/news/style_block.txt` + `golden_script_*.txt` |
| `tips` | Инструмент: боль → как пользоваться → результат (без биографий) | `…/tips/style_block.txt` |

Длина сценария по умолчанию: 78–98 слов (~45–48 сек озвучки).

## Команды бота

| Кнопка | Действие |
|--------|----------|
| 💡 Придумать тему | Brainstorm (Gemini) → промпт → генерация |
| 🚀 Сгенерировать видео | Рубрика → тема → полный пайплайн |
| 🎙 Озвучить сценарий | Готовый текст → только mp3 |
| 📝 Сделать пост | Пост на тему / пост к ролику → превью → publish в канал |
| ✏️ Откорректировать сценарий | Свой текст → переозвучка + новый mp4 |

## Установка

```bash
git clone <repo-url> shorts-generator
cd shorts-generator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполнить `.env` (см. ниже). Запуск:

```bash
python main.py
```

## Переменные окружения

### Telegram

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота |
| `TELEGRAM_ALLOWED_USER_ID` | Числовой user id (единственный оператор) |
| `TELEGRAM_CHANNEL_ID` | ID канала для publish постов (опц.) |
| `TELEGRAM_CHANNEL_HANDLE` | Подпись в конце поста, напр. `@your_channel` |
| `TELEGRAM_CHANNEL_NAME` | Имя канала в UI бота |

### Gemini

Отдельный ключ на задачу снижает риск 429 (лучше — разные GCP-проекты). Пустой ключ задачи → fallback на `GEMINI_API_KEY`.

| Переменная | Задача |
|------------|--------|
| `GEMINI_API_KEY` | Запасной |
| `GEMINI_RESEARCH_API_KEY` | Research / grounding |
| `GEMINI_SCRIPT_API_KEY` | Сценарий |
| `GEMINI_BRAINSTORM_API_KEY` | Brainstorm тем |
| `GEMINI_CHANNEL_POST_API_KEY` | Посты канала |

Модели: `GEMINI_SCRIPT_MODEL` (по умолчанию `gemini-2.5-pro`), `GEMINI_*_FALLBACK_MODELS`, `GEMINI_STEP_DELAY_SEC` — пауза между research и script при одном ключе.

`RESEARCH_ENABLED=true|false` — отключить поиск.

### TTS

| Переменная | Описание |
|------------|----------|
| `TTS_PROVIDER` | `edge` или `elevenlabs` |
| `TTS_VOICE` | Голос Edge, напр. `ru-RU-DmitryNeural` |
| `ELEVENLABS_API_KEY` | Ключ ElevenLabs |
| `ELEVENLABS_VOICE_ID` | ID голоса |
| `ELEVENLABS_MODEL` | По умолчанию `eleven_multilingual_v2` |
| `ELEVENLABS_STABILITY` / `SIMILARITY_BOOST` / `STYLE` / `SPEED` | Параметры голоса |

### Рендер / сценарий

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `BACKGROUND_MODE` | `texture` | `texture` или solid RGB |
| `BACKGROUND_TEXTURE` | `texture_navy.jpg` | Файл в `assets/backgrounds/` |
| `BACKGROUND_RGB` | `22,32,62` | Если mode ≠ texture |
| `SCRIPT_MIN_WORDS` / `SCRIPT_MAX_WORDS` | 78 / 98 | Длина сценария |
| `TARGET_VIDEO_DURATION_SEC` | 48 | Целевая длительность |
| `RENDER_PRESET` | `veryfast` | FFmpeg preset |
| `RENDER_THREADS` | 4 | Потоки кодирования |
| `OUTPUT_DIR` | `assets/output` | Временный вывод |

## Программный API пайплайна

```python
from pipeline import VideoPipeline
from services.script_rubrics import ScriptRubric

pipe = VideoPipeline()

# полный цикл
result = await pipe.run("тема", ScriptRubric.TIPS)

# правка сценария
result = await pipe.revise(script, "сделай короче хук")

# только озвучка + рендер
result = await pipe.render_from_script(script)

# только mp3
audio = await pipe.voice_script(script)

# пост для канала
post = await pipe.generate_channel_post(idea="...", post_type=...)
```

`PipelineResult`: пути к видео/аудио, текст сценария, сегменты субтитров (тайминги для CapCut).

## Assets

| Путь | В git | Назначение |
|------|-------|------------|
| `assets/backgrounds/texture_navy.jpg` | да | Фон заготовки |
| `assets/references/rubrics/*/style_block.txt` | да | Стиль рубрики в промпте |
| `assets/references/rubrics/rubric_analysis.json` | да | Разбор эталонных сценариев |
| `assets/overlays/**` | нет (только `.gitkeep`) | Локальные мемы/скрины для CapCut |
| `assets/output/**` | нет | Временные файлы пайплайна |

Свои референс-ролики кладите локально; `*.mp4` в `.gitignore`.

## Безопасность

- `.env` не коммитить (уже в `.gitignore`).
- Бот однопользовательский: чужие `user_id` получают отказ.
- Ключи API только через env, в коде секретов нет.

## Лицензия

Код — на ваше усмотрение (LICENSE не приложен). Не публикуйте чужие TikTok/YouTube-ролики и чужие логотипы в репозитории.
