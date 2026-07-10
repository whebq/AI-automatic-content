"""Подготовка сценария для стабильной озвучки ElevenLabs."""

from __future__ import annotations

import re

_BRAND_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bCursor\b", re.IGNORECASE), "Курсор"),
    (re.compile(r"\bSpaceX\b", re.IGNORECASE), "Спейс Икс"),
    (re.compile(r"\bxAI\b"), "икс эй ай"),
    (re.compile(r"\bColossus\b", re.IGNORECASE), "Колоссус"),
    (re.compile(r"\biOS\b"), "АйОС"),
    (re.compile(r"\bIPO\b"), "выход на биржу"),
    (re.compile(r"\bTelegram\b", re.IGNORECASE), "Телеграм"),
    (re.compile(r"\bOpenAI\b", re.IGNORECASE), "Опен Эй Ай"),
    (re.compile(r"\bAnthropic\b", re.IGNORECASE), "Антропик"),
    (re.compile(r"\bGitHub\b", re.IGNORECASE), "ГитХаб"),
    (re.compile(r"\bClaude\b", re.IGNORECASE), "Клод"),
    (re.compile(r"\bPlaywright\b", re.IGNORECASE), "Плейрайт"),
)


def brands_to_speech_ru(text: str) -> str:
    for pattern, replacement in _BRAND_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text
_BANG_QUESTION_RE = re.compile(r"!\?|\?!")
_MULTI_PUNCT_RE = re.compile(r"([.!?])\1+")
_DASH_BREAK_RE = re.compile(r"\s*—\s*")
_SPACE_RE = re.compile(r"\s+")

_ONES_M = (
    "",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
)
_ONES_F = (
    "",
    "одна",
    "две",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
)
_TEENS = (
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
)
_TENS = (
    "",
    "десять",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
)
_HUNDREDS = (
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
)

_AGE_RE = re.compile(
    r"(?<!\w)(?P<num>\d{1,3})\s*(?P<unit>лет|года|год)\b",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"(?<!\w)(?P<num>\d{1,3})\s*%")
_MONEY_SUFFIX_RE = re.compile(
    r"(?<!\w)(?P<num>\d+(?:[.,]\d+)?)\s*(?P<suffix>млн|млрд|тыс|миллион(?:а|ов)?|миллиард(?:а|ов)?|тысяч(?:и)?)\b",
    re.IGNORECASE,
)
_DOLLAR_RE = re.compile(
    r"\$\s*(?P<num>\d+(?:[.,]\d+)?)\s*(?P<suffix>млн|млрд|тыс|million|billion|k)?",
    re.IGNORECASE,
)
_DAYS_RE = re.compile(r"(?<!\w)(?P<num>\d{1,4})\s*(?P<unit>дн(?:ей|я|ь))\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<!\w)(?P<num>(?:19|20)\d{2})\s*(?:год[ау]?)?\b")
_PLAIN_NUM_RE = re.compile(r"(?<!\w)(?P<num>\d{1,4})(?!\w)")


def _parse_number(raw: str) -> int | None:
    cleaned = raw.replace(",", ".").strip()
    if not cleaned:
        return None
    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        if right.strip("0"):
            return None
        cleaned = left
    if not cleaned.isdigit():
        return None
    return int(cleaned)


def _int_to_words(n: int, *, feminine: bool = False) -> str:
    if n < 0 or n > 999_999:
        return str(n)
    if n == 0:
        return "ноль"

    parts: list[str] = []

    millions = n // 1_000_000
    if millions:
        parts.append(f"{_int_to_words(millions)} миллион" if millions == 1 else f"{_int_to_words(millions)} миллионов")
        n %= 1_000_000

    thousands = n // 1000
    if thousands:
        thousand_word = _triplet_to_words(thousands, feminine=True)
        if thousands == 1:
            parts.append("тысяча")
        elif thousands % 10 in (2, 3, 4) and thousands % 100 not in (12, 13, 14):
            parts.append(f"{thousand_word} тысячи")
        else:
            parts.append(f"{thousand_word} тысяч")
        n %= 1000

    if n:
        parts.append(_triplet_to_words(n, feminine=feminine))

    return " ".join(part for part in parts if part)


def _triplet_to_words(n: int, *, feminine: bool = False) -> str:
    if n <= 0 or n > 999:
        return str(n)

    parts: list[str] = []
    hundreds = n // 100
    if hundreds:
        parts.append(_HUNDREDS[hundreds])

    remainder = n % 100
    if 10 <= remainder < 20:
        parts.append(_TEENS[remainder - 10])
    else:
        tens = remainder // 10
        ones = remainder % 10
        if tens:
            parts.append(_TENS[tens])
        if ones:
            parts.append((_ONES_F if feminine else _ONES_M)[ones])

    return " ".join(parts)


def _age_phrase(n: int) -> str:
    words = _int_to_words(n)
    if n % 100 in (11, 12, 13, 14):
        return f"{words} лет"
    last = n % 10
    if last == 1:
        return f"{words} год"
    if last in (2, 3, 4):
        return f"{words} года"
    return f"{words} лет"


def _money_suffix_phrase(num: int, suffix: str, *, with_dollars: bool = False) -> str:
    suffix = suffix.lower()
    words = _int_to_words(num)
    mapping = {
        "млн": ("миллион", "миллиона", "миллионов"),
        "million": ("миллион", "миллиона", "миллионов"),
        "млрд": ("миллиард", "миллиарда", "миллиардов"),
        "billion": ("миллиард", "миллиарда", "миллиардов"),
        "тыс": ("тысяча", "тысячи", "тысяч"),
        "k": ("тысяча", "тысячи", "тысяч"),
    }
    if suffix in mapping:
        one, few, many = mapping[suffix]
        if num % 100 in (11, 12, 13, 14):
            unit = many
        elif num % 10 == 1:
            unit = one
        elif num % 10 in (2, 3, 4):
            unit = few
        else:
            unit = many
        phrase = f"{words} {unit}"
        return f"{phrase} долларов" if with_dollars else phrase

    if suffix in {"миллион", "миллиона", "миллионов", "миллиард", "миллиарда", "миллиардов", "тысяч", "тысячи"}:
        phrase = f"{words} {suffix}"
        return f"{phrase} долларов" if with_dollars else phrase

    return f"{words} {suffix}"


def numbers_to_speech_ru(text: str) -> str:
    """Цифры → слова для стабильной русской озвучки ElevenLabs."""

    def age_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        return _age_phrase(num) if num is not None else match.group(0)

    def percent_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        return f"{_int_to_words(num)} процентов" if num is not None else match.group(0)

    def money_suffix_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        if num is None:
            return match.group(0)
        return _money_suffix_phrase(num, match.group("suffix"), with_dollars=False)

    def dollar_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        if num is None:
            return match.group(0)
        suffix = (match.group("suffix") or "").strip()
        if suffix:
            return _money_suffix_phrase(num, suffix, with_dollars=True)
        return f"{_int_to_words(num)} долларов"

    def days_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        if num is None:
            return match.group(0)
        words = _int_to_words(num)
        if num % 100 in (11, 12, 13, 14):
            unit = "дней"
        elif num % 10 == 1:
            unit = "день"
        elif num % 10 in (2, 3, 4):
            unit = "дня"
        else:
            unit = "дней"
        return f"{words} {unit}"

    def year_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        return _int_to_words(num) if num is not None else match.group(0)

    def plain_sub(match: re.Match[str]) -> str:
        num = _parse_number(match.group("num"))
        return _int_to_words(num) if num is not None else match.group(0)

    text = _DOLLAR_RE.sub(dollar_sub, text)
    text = _MONEY_SUFFIX_RE.sub(money_suffix_sub, text)
    text = _AGE_RE.sub(age_sub, text)
    text = _PERCENT_RE.sub(percent_sub, text)
    text = _DAYS_RE.sub(days_sub, text)
    text = _YEAR_RE.sub(year_sub, text)
    text = _PLAIN_NUM_RE.sub(plain_sub, text)
    return text


def limit_exclamations(text: str, max_count: int = 2) -> str:
    count = 0
    chars: list[str] = []
    for char in text:
        if char == "!":
            if count < max_count:
                chars.append("!")
                count += 1
            else:
                chars.append(".")
        else:
            chars.append(char)
    return "".join(chars)


def prepare_script_for_tts(script: str, *, rubric: str | None = None) -> str:
    """Убирает конструкции, из-за которых TTS часто запинается."""
    text = script.strip()
    if not text:
        return text

    text = _BANG_QUESTION_RE.sub("?", text)
    text = text.replace("!?", "?").replace("?!", "?")
    text = _MULTI_PUNCT_RE.sub(r"\1", text)
    text = _DASH_BREAK_RE.sub(", ", text)
    text = text.replace("…", "...")
    text = _SPACE_RE.sub(" ", text)

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line:
            lines.append(line)

    if not lines:
        return text

    merged = "\n".join(lines)
    if rubric == "news":
        merged = limit_exclamations(merged, max_count=2)
    return merged


def script_lines_to_speech(script: str, *, rubric: str | None = None) -> str:
    """Склеивает фразы и готовит текст для TTS."""
    text = prepare_script_for_tts(script, rubric=rubric)
    parts = [part.strip() for part in text.splitlines() if part.strip()]
    if not parts:
        return numbers_to_speech_ru(text)

    sentences: list[str] = []
    for part in parts:
        if part[-1] not in ".!?…":
            part = f"{part}."
        sentences.append(part)

    merged = " ".join(sentences)
    merged = brands_to_speech_ru(merged)
    return numbers_to_speech_ru(merged)
