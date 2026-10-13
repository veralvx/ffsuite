"""A transcript's markup: its tags, which a reader reads its words without; references; escapes."""

import html
import re
from typing import Final, NamedTuple

__all__ = ["Unescaped", "decoded", "unclosed", "unescaped", "untagged"]

_TAG: Final = re.compile(r"<[^>]*>")  # <u>, <i>, <font ...>: SubRip's and WebVTT's
_VTT_TAG: Final = re.compile(r"<[^>]*>?")  # WebVTT's: one no > closes, to the text's end (W3C)
_DECIMAL: Final = re.compile(r"&#([0-9]+);?")  # a decimal reference
_DIGITS_MAX: Final = 7  # a decimal reference's: 10**7 is past U+10FFFF
# ffmpeg 8.1's subrip decoder, at a "{" (htmlsubtitles.c, handle_open_brace): MicroDVD's style,
# {y:i}, dropped; and ASS's tags, but while one {\anN} alone has been met (scanbraces, exactly)
_STYLE: Final = re.compile(r"[CcFfoPSsYy]:")
_ALIGNMENT: Final = re.compile(r"\{\\an[0-9]\}")
# libass 0.17.1's reading of an event's text, left to right: a "{" with a "}" after it opens a
# block, to the first "}" (ass_render.c); \N \h \{ \} its escapes (ass_get_next_char) -- not
# \n, a space but under WrapStyle 2; else a character. Past the last "}" no block opens: there,
# the escapes alone, so no "{" is scanned to the end
_BLOCK_OR_ESCAPE: Final = re.compile(r"\{([^}]*)\}|\\([Nh{}])")
_ESCAPE: Final = re.compile(r"\\([Nh{}])")
_ESCAPES: Final = {"N": "\n", "h": "\u00a0", "{": "{", "}": "}"}


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


class Unescaped(NamedTuple):
    """A SubRip text as ffmpeg and libass draw it; the override blocks libass hides, unbraced."""

    text: str
    blocks: tuple[str, ...]


def unescaped(text: str) -> Unescaped:
    r"""A SubRip text as mpv and an ffmpeg burn draw it: its override blocks off, its escapes read.

    ffmpeg's subrip decoder passes the text to ASS (``_passed``), and libass reads it: a
    block, ``{...}``, hidden -- ASS's tags, or its comment form, ``{text}``; ``\N`` a line
    break, ``\h`` U+00A0, ``\{`` and ``\}`` braces, a backslash before one a character of its
    own (``_BLOCK_OR_ESCAPE``). VLC's subsdec reads ``\N`` and ``\h`` alike, but shows ``\{``
    and a ``{text}``.
    """
    blocks: list[str] = []

    def read(found: re.Match[str]) -> str:
        block, escape = found.group(1, 2)
        if block is not None:
            blocks.append(block)
            return ""
        return _ESCAPES[escape]

    text = _passed(text)
    cut = text.rfind("}") + 1
    tail = _ESCAPE.sub(lambda found: _ESCAPES[found[1]], text[cut:])
    return Unescaped(_BLOCK_OR_ESCAPE.sub(read, text[:cut]) + tail, tuple(blocks))


def _passed(text: str) -> str:
    r"""What ffmpeg's subrip decoder passes to libass: ASS's tags and MicroDVD's style off.

    At each ``{`` (``_STYLE``, ``_ALIGNMENT``), to the first ``}`` after it, a backslash before
    the ``{`` or not: libass never reads that ``\{``. A ``{`` with no ``}`` after it drops
    nothing, nor does any after it. Each ``{`` read once: bounded.
    """
    kept: list[str] = []
    k = alignments = 0
    last = text.rfind("}")
    start = text.find("{")
    while 0 <= start < last:
        alignments += _ALIGNMENT.match(text, start) is not None
        tags = alignments != 1 and text.startswith("\\", start + 1)
        if tags or _STYLE.match(text, start + 1):
            kept.append(text[k:start])
            k = text.find("}", start + 2) + 1  # one there: neither "\\" nor ":" is a "}"
            start = text.find("{", k)
        else:
            start = text.find("{", start + 1)
    return "".join(kept) + text[k:]


def untagged(text: str, *, into: str = "", webvtt: bool = False) -> str:
    """``text`` without its tags: each ``into``.

    ``webvtt``: its tags as the W3C's cue text tokenizer reads them -- one no ``>`` closes runs
    to the text's end (``unclosed``), as Chromium 141 and ffmpeg 8.1.2 show it; else that
    ``<`` is text, as ffmpeg's subrip decoder shows it.
    """
    return (_VTT_TAG if webvtt else _TAG).sub(into, text)


def unclosed(text: str) -> str:
    """A WebVTT text's tag no ``>`` closes, to the text's end (``untagged``); else empty.

    It opens at the first ``<`` after the last ``>``.
    """
    start = text.find("<", text.rfind(">") + 1)
    return text[start:] if start >= 0 else ""
