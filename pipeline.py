import asyncio
import logging
import shutil
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

from config import GEMINI_STEP_DELAY_SEC, OUTPUT_DIR, RESEARCH_ENABLED
from models import ChannelPostResult, PipelineResult
from services.audio_generator import AudioGenerator, AudioGeneratorError
from services.channel_post_generator import ChannelPostGenerator, ChannelPostGeneratorError
from services.channel_post_types import ChannelPostType
from services.gemini_registry import GeminiPurpose, uses_same_api_key
from services.script_rubrics import ScriptRubric
from services.text_generator import TextGenerator, TextGeneratorError
from services.topic_researcher import TopicResearcher, TopicResearcherError
from services.video_renderer import VideoRenderer, VideoRendererError

logger = logging.getLogger(__name__)

StageCallback = Callable[[str], Awaitable[None] | None]


class PipelineError(Exception):
    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        super().__init__(message)


class VideoPipeline:
    def __init__(self) -> None:
        self._text_generator = TextGenerator()
        self._audio_generator = AudioGenerator()
        self._video_renderer = VideoRenderer()
        self._topic_researcher = TopicResearcher() if RESEARCH_ENABLED else None
        self._channel_post_generator = ChannelPostGenerator()

    async def _notify(self, on_stage: StageCallback | None, text: str) -> None:
        if on_stage is None:
            return
        result = on_stage(text)
        if result is not None:
            await result

    @staticmethod
    def cleanup_output_dir() -> None:
        if not OUTPUT_DIR.exists():
            return

        for path in OUTPUT_DIR.iterdir():
            if path.name == ".gitkeep":
                continue
            try:
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            except OSError:
                logger.warning("Не удалось удалить временный файл: %s", path)

    @staticmethod
    def cleanup_delivery(video_path: str | Path) -> None:
        path = Path(video_path)
        if not path.exists():
            parent = path.parent
            if parent.name.startswith("shorts_") and parent.exists():
                shutil.rmtree(parent, ignore_errors=True)
            return

        parent = path.parent
        try:
            if parent.name.startswith("shorts_") and parent.exists():
                shutil.rmtree(parent, ignore_errors=True)
            else:
                path.unlink()
        except OSError:
            logger.warning("Не удалось удалить файлы доставки: %s", path)

    @staticmethod
    def _save_delivery_assets(video_path: Path, audio_path: Path) -> tuple[Path, Path]:
        if not video_path.exists() or video_path.stat().st_size == 0:
            raise FileNotFoundError(f"Готовое видео не найдено: {video_path}")
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")

        delivery_dir = Path(tempfile.mkdtemp(prefix="shorts_"))
        video_dest = delivery_dir / "result.mp4"
        audio_dest = delivery_dir / "audio.mp3"

        shutil.move(str(video_path), str(video_dest))
        shutil.copy2(str(audio_path), str(audio_dest))
        return video_dest, audio_dest

    async def _render_and_deliver(
        self,
        audio_file: Path,
        script: str,
        *,
        idea: str,
        segments: list | None = None,
        research_sources: tuple[str, ...] = (),
        research_brief: str = "",
        rubric: str = "story",
    ) -> PipelineResult:
        job_id = uuid.uuid4().hex[:8]

        try:
            video_path = await self._video_renderer.render(audio_file, job_id)
        except VideoRendererError as exc:
            raise PipelineError("Рендеринг видео", str(exc)) from exc

        try:
            video_dest, audio_dest = self._save_delivery_assets(video_path, audio_file)
        except FileNotFoundError as exc:
            raise PipelineError("Рендеринг видео", str(exc)) from exc

        return PipelineResult(
            script=script,
            video_path=str(video_dest),
            audio_path=str(audio_dest),
            idea=idea,
            segments=segments or [],
            research_sources=research_sources,
            research_brief=research_brief,
            rubric=rubric,
        )

    async def _research_topic(
        self,
        idea: str,
        *,
        rubric: ScriptRubric | None = None,
    ) -> tuple[str | None, tuple[str, ...]]:
        if not RESEARCH_ENABLED or self._topic_researcher is None:
            return None, ()

        from services.script_rubrics import ScriptRubric as SR

        try:
            if rubric is SR.NEWS:
                research = await self._topic_researcher.research_news(idea)
            else:
                research = await self._topic_researcher.research(idea)
        except TopicResearcherError as exc:
            logger.warning("Поиск фактов не удался, продолжаю без него: %s", exc)
            return None, ()

        return research.brief, research.sources

    async def run(
        self,
        idea: str,
        on_stage: StageCallback | None = None,
        *,
        rubric: ScriptRubric | None = None,
    ) -> PipelineResult:
        from services.script_rubrics import ScriptRubric as SR

        rubric = rubric or SR.STORY
        job_id = uuid.uuid4().hex[:8]
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audio_path = OUTPUT_DIR / f"{job_id}_audio.mp3"

        try:
            research_brief: str | None = None
            research_sources: tuple[str, ...] = ()
            if RESEARCH_ENABLED:
                await self._notify(on_stage, "🔍 Ищу факты (Flash + Google Search)...")
                research_brief, research_sources = await self._research_topic(idea, rubric=rubric)
                if (
                    uses_same_api_key(GeminiPurpose.RESEARCH, GeminiPurpose.SCRIPT)
                    and GEMINI_STEP_DELAY_SEC > 0
                ):
                    await self._notify(
                        on_stage,
                        f"⏳ Пауза {int(GEMINI_STEP_DELAY_SEC)} сек (лимит RPM)...",
                    )
                    await asyncio.sleep(GEMINI_STEP_DELAY_SEC)

            await self._notify(on_stage, f"✍️ Пишу сценарий ({rubric.value}, Pro)...")

            try:
                script_result = await self._text_generator.generate_script(
                    idea,
                    rubric=rubric,
                    research_brief=research_brief,
                )
            except TextGeneratorError as exc:
                raise PipelineError("Генерация сценария", str(exc)) from exc

            script = script_result.script

            await self._notify(on_stage, "🎙 Озвучиваю текст...")

            try:
                audio_result = await self._audio_generator.generate(
                    script, audio_path, rubric=rubric
                )
            except AudioGeneratorError as exc:
                raise PipelineError("Озвучка", str(exc)) from exc

            await self._notify(on_stage, "🎬 Собираю заготовку (синий фон + озвучка)...")

            return await self._render_and_deliver(
                Path(audio_result.audio_path),
                script,
                idea=idea,
                segments=audio_result.segments,
                research_sources=research_sources,
                research_brief=research_brief or "",
                rubric=rubric.value,
            )
        finally:
            self.cleanup_output_dir()

    async def revise(
        self,
        script: str,
        feedback: str,
        on_stage: StageCallback | None = None,
        *,
        idea: str = "",
        rubric: ScriptRubric | None = None,
        research_brief: str = "",
        research_sources: tuple[str, ...] = (),
    ) -> PipelineResult:
        from services.script_rubrics import ScriptRubric as SR

        rubric = rubric or SR.STORY
        feedback = feedback.strip()
        if not feedback:
            raise PipelineError("Правки", "Опиши, что нужно изменить в тексте")

        job_id = uuid.uuid4().hex[:8]
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        new_audio_path = OUTPUT_DIR / f"{job_id}_audio.mp3"

        try:
            await self._notify(on_stage, "✍️ Переписываю сценарий по твоим правкам...")

            try:
                new_script = await self._text_generator.revise_script(
                    script,
                    feedback,
                    rubric=rubric,
                    research_brief=research_brief or None,
                )
            except TextGeneratorError as exc:
                raise PipelineError("Генерация сценария", str(exc)) from exc

            await self._notify(on_stage, "🎙 Переозвучиваю текст...")

            try:
                audio_result = await self._audio_generator.generate(
                    new_script, new_audio_path, rubric=rubric
                )
            except AudioGeneratorError as exc:
                raise PipelineError("Озвучка", str(exc)) from exc

            await self._notify(on_stage, "🎬 Собираю обновлённую заготовку...")

            return await self._render_and_deliver(
                Path(audio_result.audio_path),
                new_script,
                idea=idea,
                segments=audio_result.segments,
                research_sources=research_sources,
                research_brief=research_brief,
                rubric=rubric.value,
            )
        finally:
            self.cleanup_output_dir()

    async def render_from_script(
        self,
        script: str,
        on_stage: StageCallback | None = None,
        *,
        idea: str = "",
        rubric: ScriptRubric | None = None,
        research_brief: str = "",
        research_sources: tuple[str, ...] = (),
    ) -> PipelineResult:
        from services.script_rubrics import ScriptRubric as SR

        rubric = rubric or SR.STORY
        script = script.strip()
        if not script:
            raise PipelineError("Сценарий", "Текст сценария не может быть пустым")

        job_id = uuid.uuid4().hex[:8]
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audio_path = OUTPUT_DIR / f"{job_id}_audio.mp3"

        try:
            await self._notify(on_stage, "🎙 Озвучиваю обновлённый сценарий...")

            try:
                audio_result = await self._audio_generator.generate(
                    script, audio_path, rubric=rubric
                )
            except AudioGeneratorError as exc:
                raise PipelineError("Озвучка", str(exc)) from exc

            await self._notify(on_stage, "🎬 Собираю обновлённую заготовку...")

            return await self._render_and_deliver(
                Path(audio_result.audio_path),
                script,
                idea=idea,
                segments=audio_result.segments,
                research_sources=research_sources,
                research_brief=research_brief,
                rubric=rubric.value,
            )
        finally:
            self.cleanup_output_dir()

    async def voice_script(
        self,
        script: str,
        on_stage: StageCallback | None = None,
        *,
        rubric: ScriptRubric | None = None,
    ) -> str:
        from services.script_rubrics import ScriptRubric as SR

        rubric = rubric or SR.TIPS
        script = script.strip()
        if not script:
            raise PipelineError("Сценарий", "Текст сценария не может быть пустым")

        job_id = uuid.uuid4().hex[:8]
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        audio_path = OUTPUT_DIR / f"{job_id}_audio.mp3"

        try:
            await self._notify(on_stage, "🎙 Озвучиваю сценарий...")

            try:
                audio_result = await self._audio_generator.generate(
                    script, audio_path, rubric=rubric
                )
            except AudioGeneratorError as exc:
                raise PipelineError("Озвучка", str(exc)) from exc

            delivery_dir = Path(tempfile.mkdtemp(prefix="shorts_voice_"))
            audio_dest = delivery_dir / "voiceover.mp3"
            shutil.copy2(str(audio_result.audio_path), str(audio_dest))
            return str(audio_dest)
        finally:
            self.cleanup_output_dir()

    async def _research_brainstorm(
        self,
        query: str,
        on_stage: StageCallback | None = None,
    ) -> str | None:
        if not RESEARCH_ENABLED or self._topic_researcher is None:
            return None

        await self._notify(on_stage, "🔍 Ищу информацию в интернете...")
        try:
            research = await self._topic_researcher.research_brainstorm(query)
        except TopicResearcherError as exc:
            logger.warning("Поиск для brainstorm не удался, продолжаю без него: %s", exc)
            return None

        if (
            uses_same_api_key(GeminiPurpose.RESEARCH, GeminiPurpose.BRAINSTORM)
            and GEMINI_STEP_DELAY_SEC > 0
        ):
            await self._notify(
                on_stage,
                f"⏳ Пауза {int(GEMINI_STEP_DELAY_SEC)} сек (лимит RPM)...",
            )
            await asyncio.sleep(GEMINI_STEP_DELAY_SEC)

        return research.brief

    async def brainstorm_reply(
        self,
        user_message: str,
        history: list[dict[str, str]],
        *,
        rubric: ScriptRubric,
        on_stage: StageCallback | None = None,
    ) -> str:
        from services.content_rubrics import format_brainstorm_research_query

        query = format_brainstorm_research_query(user_message, history)
        research_brief = await self._research_brainstorm(query, on_stage)
        await self._notify(on_stage, "💭 Думаю...")
        try:
            return await self._text_generator.brainstorm_reply(
                user_message,
                history,
                rubric=rubric,
                research_brief=research_brief,
            )
        except TextGeneratorError as exc:
            raise PipelineError("Обсуждение темы", str(exc)) from exc

    async def summarize_brainstorm(
        self,
        history: list[dict[str, str]],
        *,
        rubric: ScriptRubric,
        on_stage: StageCallback | None = None,
    ) -> str:
        from services.content_rubrics import format_brainstorm_history

        query = format_brainstorm_history(history)
        research_brief = await self._research_brainstorm(query, on_stage)
        await self._notify(on_stage, "📝 Формулирую промпт...")
        try:
            return await self._text_generator.summarize_brainstorm(
                history,
                rubric=rubric,
                research_brief=research_brief,
            )
        except TextGeneratorError as exc:
            raise PipelineError("Обсуждение темы", str(exc)) from exc

    async def generate_channel_post(
        self,
        topic: str,
        *,
        post_type: ChannelPostType,
        video_script: str | None = None,
        rubric: str | None = None,
        on_stage: StageCallback | None = None,
    ) -> ChannelPostResult:
        topic = topic.strip()
        if not topic:
            raise PipelineError("Пост", "Тема не может быть пустой")

        await self._notify(on_stage, "🔍 Ищу информацию для поста...")

        try:
            brief, sources = await self._channel_post_generator.research(
                topic,
                post_type=post_type,
                video_script=video_script,
                rubric=rubric,
            )
            await self._notify(on_stage, "✍️ Пишу пост...")
            post_text, video_kind = await self._channel_post_generator.compose(
                topic,
                post_type=post_type,
                research_brief=brief,
                video_script=video_script,
                rubric=rubric,
            )
        except ChannelPostGeneratorError as exc:
            raise PipelineError("Пост", str(exc)) from exc

        return ChannelPostResult(
            text=post_text,
            post_type=post_type.value,
            topic=topic,
            research_brief=brief,
            research_sources=sources,
            video_script=(video_script or "").strip(),
            video_kind=video_kind.value if video_kind else "",
        )
