"""Простой рендер: синий фон референса + озвучка (монтаж — в CapCut)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import numpy as np
from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, ImageClip, VideoClip, afx, vfx
from PIL import Image, ImageEnhance

from config import (
    BACKGROUND_BRIGHTNESS,
    BACKGROUND_MODE,
    BACKGROUND_RGB,
    BACKGROUND_TEXTURE,
    OUTPUT_DIR,
    RENDER_FPS,
    RENDER_PRESET,
    RENDER_THREADS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)

logger = logging.getLogger(__name__)


class VideoRendererError(Exception):
    pass


def _brighten_frame(frame: np.ndarray) -> np.ndarray:
    image = ImageEnhance.Brightness(Image.fromarray(frame)).enhance(BACKGROUND_BRIGHTNESS)
    return np.asarray(image)


def _load_background(duration: float) -> VideoClip:
    if BACKGROUND_MODE == "texture" and BACKGROUND_TEXTURE.is_file():
        clip = ImageClip(str(BACKGROUND_TEXTURE))
        clip = clip.with_effects([vfx.Resize(new_size=(TARGET_WIDTH, TARGET_HEIGHT))])
        if abs(BACKGROUND_BRIGHTNESS - 1.0) > 0.01:
            clip = clip.image_transform(_brighten_frame)
        return clip.with_duration(duration)

    return ColorClip(
        size=(TARGET_WIDTH, TARGET_HEIGHT),
        color=BACKGROUND_RGB,
    ).with_duration(duration)


def _render_video_sync(audio_path: Path, output_path: Path) -> Path:
    audio_clip = None
    composed = None

    try:
        audio_clip = AudioFileClip(str(audio_path))
        duration = float(audio_clip.duration or 0)
        if duration <= 0:
            raise VideoRendererError("Аудиофайл пустой или повреждён")

        background = _load_background(duration)
        composed = CompositeVideoClip([background], size=(TARGET_WIDTH, TARGET_HEIGHT))
        composed = composed.with_duration(duration)
        composed = composed.with_audio(audio_clip)
        composed = composed.with_effects([afx.AudioNormalize()])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        composed.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=RENDER_FPS,
            preset=RENDER_PRESET,
            threads=RENDER_THREADS,
            logger=None,
        )

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise VideoRendererError(f"MoviePy не создал видеофайл: {output_path}")

        return output_path
    finally:
        for clip in (composed, audio_clip):
            if clip is not None:
                clip.close()


class VideoRenderer:
    async def render(self, audio_path: Path, job_id: str) -> Path:
        output_path = OUTPUT_DIR / f"{job_id}_result.mp4"
        try:
            return await asyncio.to_thread(_render_video_sync, audio_path, output_path)
        except VideoRendererError:
            raise
        except Exception as exc:
            logger.exception("MoviePy render error")
            raise VideoRendererError(f"Ошибка рендеринга видео: {exc}") from exc
