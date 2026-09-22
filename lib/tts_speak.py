"""Make narration sound more natural when spoken by Kokoro TTS."""

from __future__ import annotations

import re

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
]


def _under_100(n: int) -> str:
    n = abs(int(n))
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    if ones == 0:
        return _TENS[tens]
    return f"{_TENS[tens]}-{_ONES[ones]}"


def _under_1000(n: int) -> str:
    n = abs(int(n))
    if n < 100:
        return _under_100(n)
    h, rest = divmod(n, 100)
    if rest == 0:
        return f"{_ONES[h]} hundred"
    return f"{_ONES[h]} hundred {_under_100(rest)}"


def year_to_words(year: int) -> str:
    """Speak years the way documentary narrators do."""
    y = int(year)
    if 2000 <= y <= 2009:
        return f"two thousand {_ONES[y - 2000]}" if y > 2000 else "two thousand"
    if 2010 <= y <= 2099:
        return f"twenty {_under_100(y - 2000)}"
    if 1900 <= y <= 1999:
        return f"nineteen {_under_100(y - 1900)}"
    if 1800 <= y <= 1899:
        return f"eighteen {_under_100(y - 1800)}"
    return _under_1000(y)


def percent_to_words(value: float, *, signed: bool = True) -> str:
    n = float(value)
    direction = ""
    if signed:
        if n < 0:
            direction = "down "
        elif n > 0:
            direction = "up "
    abs_n = abs(n)
    whole = int(round(abs_n))
    return f"{direction}{_under_1000(whole)} percent".strip()


def speakify_for_tts(text: str) -> str:
    """
    Rewrite narration for more human Kokoro delivery:
    - years → spoken words
    - percentages → spoken words
    - dollar amounts → spoken
    - light pauses before big numbers / reveals
    """
    if not text or not text.strip():
        return text

    out = str(text)

    # $1,234.56 or $12B style
    def _money(m: re.Match) -> str:
        num = m.group(1).replace(",", "")
        suffix = (m.group(2) or "").lower()
        try:
            val = float(num)
        except ValueError:
            return m.group(0)
        scale = ""
        if suffix == "k":
            scale = " thousand"
        elif suffix == "m":
            scale = " million"
        elif suffix in {"b", "bn"}:
            scale = " billion"
        elif suffix == "t":
            scale = " trillion"
        whole = int(round(val))
        return f"{_under_1000(whole) if whole < 1000 else _speak_large(whole)}{scale} dollars"

    def _speak_large(n: int) -> str:
        if n >= 1_000_000_000:
            b = n / 1_000_000_000
            return f"{_under_100(int(round(b)))} billion" if b < 100 else f"{int(round(b))} billion"
        if n >= 1_000_000:
            m = n / 1_000_000
            return f"{_under_100(int(round(m)))} million" if m < 100 else f"{int(round(m))} million"
        if n >= 1000:
            # e.g. 1247 → twelve hundred forty-seven (approx) or one thousand...
            thousands, rest = divmod(n, 1000)
            if rest == 0:
                return f"{_under_100(thousands)} thousand"
            return f"{_under_100(thousands)} thousand {_under_100(rest)}"
        return _under_1000(n)

    out = re.sub(
        r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([KkMmBbTt]|bn|BN)?\b",
        _money,
        out,
    )

    # Percents: +88.9%, -26%, 41 percent
    def _pct(m: re.Match) -> str:
        sign = m.group(1) or ""
        num = float(m.group(2))
        if sign == "-":
            num = -abs(num)
        elif sign == "+":
            num = abs(num)
        return percent_to_words(num, signed=True)

    out = re.sub(r"([+-])?\s*(\d+(?:\.\d+)?)\s*%", _pct, out)
    out = re.sub(
        r"([+-])?\s*(\d+(?:\.\d+)?)\s*percent\b",
        _pct,
        out,
        flags=re.I,
    )

    # Years 19xx / 20xx as standalone tokens
    def _year(m: re.Match) -> str:
        return year_to_words(int(m.group(1)))

    out = re.sub(r"\b((?:19|20)\d{2})\b", _year, out)

    # Pause before spoken number-heavy reveals if not already marked
    out = re.sub(
        r"(?<!\[pause\]\s)\b(up|down|nearly|almost|over|under)\s+(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|one|two|three)",
        r"[pause] \1 \2",
        out,
        flags=re.I,
    )

    # Soften stiff connectors into spoken rhythm
    replacements = [
        (r"\bHowever,\s*", "[pause] But "),
        (r"\bTherefore,\s*", "So "),
        (r"\bAdditionally,\s*", "And "),
        (r"\bFurthermore,\s*", "And "),
        (r"\bIn conclusion,\s*", "[pause] "),
        (r"\bIt is important to note that\s*", ""),
        (r"\bThis means that\s*", "That means "),
    ]
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.I)

    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"(\[pause\]\s*){2,}", "[pause] ", out, flags=re.I)
    return out.strip()


def humanize_spoken_short(text: str, rules: list | None = None) -> str:
    """Aggressive short-form pacing: pause on reveals, breath every 2–3 sentences."""
    from lib.script import apply_humanization

    # Prefer denser breaths for shorts
    short_rules = list(rules or []) + [
        "Add [pause] before major reveals",
        "Insert [breath] every 3 sentences",
    ]
    text = apply_humanization(text, short_rules)
    text = speakify_for_tts(text)

    # Pause before year-words if missing
    text = re.sub(
        r"(?<!\[pause\]\s)\b(twenty (?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty))\b",
        r"[pause] \1",
        text,
        flags=re.I,
        count=2,
    )
    return text
