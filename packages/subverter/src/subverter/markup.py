"""A transcript's markup -- tags, references, escapes, word stamps -- its words read without."""

import html
import re
from typing import Final, NamedTuple

__all__ = ["LRC_TIME", "Drawn", "decoded", "drawn", "unclosed", "unstamped", "untagged"]

_TAG: Final = re.compile(r"<[^>]*>")  # <u>, <i>, <font ...>: SubRip's and WebVTT's, closed
_DECIMAL: Final = re.compile(r"&#([0-9]+);?")  # a decimal reference
_DIGITS_MAX: Final = 7  # a decimal reference's: 10**7 is past U+10FFFF
# ffmpeg 8.1's subrip decoder (htmlsubtitles.c, ff_htmlmarkup_to_ass), left to right: at a "{"
# (handle_open_brace), MicroDVD's style, {y:i}, dropped; and ASS's tags, but while one {\anN}
# alone has been met (scanbraces, exactly). At a "<" a tag follows (``_tag``): a "/" or not,
# then to the first ">", 127 characters at most, no "<" among them (scantag) -- any other "<",
# a character
_TAG_OPENER: Final = r"<(?=(/?)([^<>]{0,127})>)"
_OPENER: Final = re.compile(rf"\{{|{_TAG_OPENER}")
_TAG_OPENERS: Final = re.compile(_TAG_OPENER)  # past the last "}", no "{" drops anything
_STYLE: Final = re.compile(r"[CcFfoPSsYy]:")
_ALIGNMENT: Final = re.compile(r"\{\\an[0-9]\}")
_LIKELY: Final = re.compile(r"[0-9A-Za-z_/]*")  # "likely a tag": each character of its name
_KNOWN: Final = frozenset(("font", "b", "i", "s", "u"))  # its tags: ASS's style, no text
_BREAKS: Final = frozenset(("br", "br/"))  # a line break: \N
# libass 0.17.1's reading of an event's text, left to right: a "{" with a "}" after it opens a
# block, to the first "}" (ass_render.c); \N \n \h \{ \} its escapes (ass_get_next_char) --
# \n a space, as ffmpeg's script sets no WrapStyle (a break under 2); else a character, a
# backslash too (\t). Past the last "}" no block opens: there, the escapes alone, so no "{" is
# scanned to the end
_BLOCK_OR_ESCAPE: Final = re.compile(r"\{([^}]*)\}|\\([Nnh{}])")
_ESCAPE: Final = re.compile(r"\\([Nnh{}])")
_ESCAPES: Final = {"N": "\n", "n": " ", "h": "\u00a0", "{": "{", "}": "}"}
# an LRC stamp's time, ``mm:ss.xx`` -- minutes, then seconds, a decimal -- its lines' in brackets
# (``readers.lrc``), Enhanced LRC's words' in angle brackets (``unstamped``)
LRC_TIME: Final = r"([0-9]+):([0-9]+(?:[.][0-9]+)?)"
_WORD_STAMP: Final = re.compile(rf"<{LRC_TIME}>")


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


class Drawn(NamedTuple):
    """A SubRip text as ffmpeg and libass draw it; the override blocks libass hides, unbraced."""

    text: str
    blocks: tuple[str, ...]


def drawn(text: str) -> Drawn:
    r"""A SubRip text as mpv and an ffmpeg burn draw it: its tags and blocks off, its escapes read.

    ffmpeg's subrip decoder passes the text to ASS (``_passed``): its tags and ASS's off, a
    ``<br>`` a line break. Then libass reads it: a block, ``{...}``, hidden -- ASS's tags, or
    its comment form, ``{text}``; ``\N`` a line break, ``\n`` a space, ``\h`` U+00A0, ``\{``
    and ``\}`` braces; any other backslash a character of its own (``_BLOCK_OR_ESCAPE``).
    VLC's subsdec reads ``\N``, ``\n`` and ``\h`` alike, but shows ``\{`` and a ``{text}``.
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
    return Drawn(_BLOCK_OR_ESCAPE.sub(read, text[:cut]) + tail, tuple(blocks))


def _passed(text: str) -> str:
    r"""What ffmpeg's subrip decoder passes to libass, read left to right, as it reads it.

    At a ``{`` (``_STYLE``, ``_ALIGNMENT``), to the first ``}`` after it, a backslash before the
    ``{`` or not: libass never reads that ``\{``. A ``{`` with no ``}`` after it drops nothing,
    nor does any after it. At a ``<`` a tag follows, its tag (``_tag``). Past the last ``}``
    no ``{`` is sought, past the last ``>`` no ``<``; each read once, a tag's scan bounded.
    """
    kept: list[str] = []
    k = alignments = 0
    braces = text.rfind("}")
    end = max(braces, text.rfind(">") + 1)
    found = _OPENER.search(text, 0, end)
    while found is not None:
        start = found.start()
        if found[0] == "<":
            written, after = _tag(text, found)
            kept += [text[k:start], written]
            k = after
        elif start < braces:
            alignments += _ALIGNMENT.match(text, start) is not None
            tags = alignments != 1 and text.startswith("\\", start + 1)
            if tags or _STYLE.match(text, start + 1):
                kept.append(text[k:start])
                k = text.find("}", start + 2) + 1  # one there: neither "\\" nor ":" is a "}"
        at = max(k, start + 1)
        found = (_OPENER if at < braces else _TAG_OPENERS).search(text, at, end)
    return "".join(kept) + text[k:]


def _tag(text: str, found: re.Match[str]) -> tuple[str, int]:
    r"""What ffmpeg's subrip decoder writes for a ``<`` a tag follows, and where it goes on.

    Its name, after spaces, to the first space. A name it knows (``_KNOWN``): dropped; ``br``
    or ``br/``: a line break, ``\N``; else one "likely a tag", dropped: no space before its
    name, its name of ``_LIKELY``'s characters alone, and no ``<`` before the ``<`` (the last of
    a run, guillemets) unless it closes, ``</`` (``<v Bob>``, ``x<3 and y>2``'s ``3``). Else
    the ``<`` is a character (``1 < 2 and 3 > 2``, ``<<quote>>``, ``<c.yellow>``).
    """
    at, closing, tag = found.start(), found[1], found[2]
    after = at + 1 + len(closing) + len(tag) + 1  # past its ">"
    name = tag.lstrip(" ").split(" ", 1)[0]
    lower = name.lower() if name.isascii() else ""
    alone = text[at - 1 : at] != "<" or closing != ""
    likely = alone and tag[:1] != " " and _LIKELY.fullmatch(name) is not None
    if lower in _BREAKS:
        return "\\N", after
    if lower in _KNOWN or likely:
        return "", after
    return "<", at + 1


def untagged(text: str, *, into: str = "", webvtt: bool = False) -> str:
    """``text`` without its tags: each ``into``.

    ``webvtt``: its tags as the W3C's cue text tokenizer reads them -- one no ``>`` closes runs
    to the text's end (``unclosed``), as Chromium 141 and ffmpeg 8.1.2 show it; else that
    ``<`` is text, as ffmpeg's subrip decoder shows it. Past the last ``>`` no tag is sought:
    ``_TAG`` would scan to the end from each ``<`` there, its steps the square of their count.
    """
    end = text.rfind(">") + 1
    rest = unclosed(text) if webvtt else ""
    return _TAG.sub(into, text[:end]) + text[end : len(text) - len(rest)] + (into if rest else "")


def unstamped(text: str) -> str:
    """An LRC text without its Enhanced LRC word stamps, ``<mm:ss.xx>``, each word's start.

    As Jellyfin 12.2 (LrcParser 2025.623.0) shows it, reading them as word times -- Navidrome
    0.64.2 alike, but for the text before a line's first, which it drops; ffmpeg 8.1.2 shows them
    as text. Their grammar the line stamps' (``LRC_TIME``). Every other character as written -- a
    tag, a brace, a backslash, a reference -- as ffmpeg's, Jellyfin's and, but for the HTML it
    takes off, Navidrome's.
    """
    return _WORD_STAMP.sub("", text)


def unclosed(text: str) -> str:
    """A WebVTT text's tag no ``>`` closes, to the text's end (``untagged``); else empty.

    It opens at the first ``<`` after the last ``>``.
    """
    start = text.find("<", text.rfind(">") + 1)
    return text[start:] if start >= 0 else ""
