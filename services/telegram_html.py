"""Подготовка HTML для Telegram parse_mode=HTML."""

from __future__ import annotations

import re

_TELEGRAM_ALLOWED_TAGS = frozenset({
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "code",
    "pre",
    "a",
    "blockquote",
    "tg-spoiler",
})

_BLOCK_BREAK_RE = re.compile(
    r"</?(?:p|div|section|article|header|footer|h[1-6])[^>]*>",
    re.IGNORECASE,
)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LI_OPEN_RE = re.compile(r"<li[^>]*>", re.IGNORECASE)
_LIST_RE = re.compile(r"</?(?:ul|ol)[^>]*>", re.IGNORECASE)
_STRIP_WRAPPER_RE = re.compile(r"</?(?:span|font|mark)[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{4,}")


def sanitize_telegram_html(text: str) -> str:
    """Убирает теги, которые Telegram не понимает (<p>, <div>…), сохраняя разрешённые."""
    text = text.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    text = _BR_RE.sub("\n", text)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = _LI_OPEN_RE.sub("• ", text)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = _LIST_RE.sub("\n", text)
    text = _STRIP_WRAPPER_RE.sub("", text)

    def _keep_allowed_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        name_match = re.match(r"</?(\w+)", tag, re.IGNORECASE)
        if name_match and name_match.group(1).lower() in _TELEGRAM_ALLOWED_TAGS:
            return tag
        return ""

    text = _TAG_RE.sub(_keep_allowed_tag, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_channel_signature(text: str, handle: str) -> str:
    """Приводит подпись канала к точному handle из конфига."""
    handle = handle.strip()
    if not handle:
        return text

    text = _HANDLE_RE.sub(handle, text)
    lines = text.rstrip().splitlines()
    while lines and _HANDLE_RE.fullmatch(lines[-1].strip()):
        lines.pop()
    body = "\n".join(lines).rstrip()
    return f"{body}\n\n{handle}"


def prepare_channel_post_html(text: str, handle: str) -> str:
    return normalize_channel_signature(sanitize_telegram_html(text), handle)
