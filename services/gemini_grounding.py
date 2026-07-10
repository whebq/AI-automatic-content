"""Извлечение источников из ответов Gemini с Google Search."""

from __future__ import annotations

from google.genai import types


def extract_sources(response: types.GenerateContentResponse) -> tuple[str, ...]:
    sources: list[str] = []
    if not response.candidates:
        return ()

    metadata = response.candidates[0].grounding_metadata
    if not metadata or not metadata.grounding_chunks:
        return ()

    for chunk in metadata.grounding_chunks:
        if chunk.web and chunk.web.uri:
            sources.append(chunk.web.uri)
    return tuple(dict.fromkeys(sources))
