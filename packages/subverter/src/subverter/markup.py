"""A transcript's markup: its tags, which a reader reads its words without; references; escapes."""

import html
import re
from typing import Final

__all__ = ["decoded", "unescaped", "untagged"]

_TAG: Final = re.compile(r"<[^>]*>")  # <u>, <i>, <font ...>: SubRip's and WebVTT's
_DECIMAL: Final = re.compile(r"&#([0-9]+);?")  # a decimal reference
_DIGITS_MAX: Final = 7  # a decimal reference's: 10**7 is past U+10FFFF
# libass's escapes but \n (ass_get_next_char): no escape's output holds a backslash, so each
# is read alone, in any order
_ESCAPES: Final = (("\\N", "\n"), ("\\h", "\u00a0"), ("\\{", "{"), ("\\}", "}"))


def decoded(text: str) -> str:
    """A WebVTT text run's HTML character references decoded: ``html.unescape``, bounded.

    A run between tags (WebVTT's tokenizer decodes none across one). ``html.unescape``
    follows HTML's table and numeric rules but drops C0 controls (tab, LF, FF and CR aside),
    DEL and noncharacters, which HTML keeps. A decimal one of more than 7 significant
    digits (past U+10FFFF) is U+FFFD unread: Python's int refuses past 4300 digits.
    """
    return html.unescape(_DECIMAL.sub(_bounded, text))


def _bounded(match: re.Match[str]) -> str:
    digits = match[1].lstrip("0") or "0"
    return "\ufffd" if len(digits) > _DIGITS_MAX else f"&#{digits};"


def unescaped(text: str) -> str:
    r"""A SubRip text's ASS escapes as libass draws them: a break, a no-break space, braces.

    ``\N`` a line break, ``\h`` U+00A0, ``\{`` and ``\}`` braces. ffmpeg's subrip decoder
    passes the text to ASS as written, so libass reads them (``ass_get_next_char``, 0.17.1) --
    mpv and an ffmpeg burn; VLC's subsdec reads ``\N`` and ``\h`` alike, and shows ``\{`` as
    written. A backslash before one is a character of its own, as libass reads it; ``\n``,
    libass's break only under ``WrapStyle: 2``, is left as written.
    """
    for escape, character in _ESCAPES:
        text = text.replace(escape, character)
    return text


def untagged(text: str, *, into: str = "") -> str:
    """``text`` without its tags: each ``into``."""
    return _TAG.sub(into, text)
