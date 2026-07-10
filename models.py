from dataclasses import dataclass, field


@dataclass(frozen=True)
class WordTiming:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SubtitleSegment:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class ScriptMeta:
    script: str
    pause_after_seconds: tuple[float, ...] = ()
    emphasis_phrases: tuple[str, ...] = ()


@dataclass(frozen=True)
class AudioResult:
    audio_path: str
    words: list[WordTiming]
    segments: list[SubtitleSegment]
    provider: str = "edge-tts"


@dataclass(frozen=True)
class ChannelPostResult:
    text: str
    post_type: str
    topic: str
    research_brief: str = ""
    research_sources: tuple[str, ...] = ()
    video_script: str = ""
    video_kind: str = ""


@dataclass(frozen=True)
class PipelineResult:
    script: str
    video_path: str
    audio_path: str
    idea: str = ""
    segments: list[SubtitleSegment] = field(default_factory=list)
    research_sources: tuple[str, ...] = ()
    research_brief: str = ""
    rubric: str = "story"
