"""SubRip and WebVTT: cues; WhisperX's highlighted cues, read back into words."""

import re
from fractions import Fraction
from typing import Final

from subverter.markup import untagged
from subverter.readers.fields import NUMBER, exact, is_decimal, ms
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue, Timing

__all__ = ["highlighted", "is_highlighted", "rows"]

_PARTS: Final = 3  # a time's most: hours, minutes, seconds
_ARROW: Final = re.compile(r"[ \t]*-->[ \t]*")  # a cue's times, either side
_END: Final = re.compile(rf"{NUMBER}(?::{NUMBER}){{0,{_PARTS - 1}}}")  # what follows, ignored
_BLANK_LINE: Final = re.compile(r"[ \t]*")  # a cue's end
_UNDERLINE: Final = re.compile(r"<u>([^<]*)</u>")  # WhisperX --highlight_words: the word


def _timing(line: str) -> tuple[int | None, int | None] | None:
    """A timing line's start and end (each None past a double's range), or None: no timing line.

    A timing line: an arrow, wholly a time before it (``_ms``), and a time first after it --
    what follows, WebVTT's settings or SubRip's coordinates, ignored, a blank between or not
    (as ffmpeg reads them, and the W3C's "remainder").
    """
    if "-->" not in line:
        return None
    left, right = _ARROW.split(line, maxsplit=1)
    start = left.replace(",", ".").split(":")
    end = _END.match(right.replace(",", "."))
    if end is None or len(start) > _PARTS or not all(map(is_decimal, start)):
        return None
    return _ms(start), _ms(end[0].split(":"))


def _ms(parts: list[str]) -> int | None:
    """subs_srt_vtt's ms(), each part a decimal read exactly; None if one is past a double's range.

    h:m:s, m:s, or m alone -- awk read a bare number as minutes.
    """
    values = [v for v in map(exact, parts) if v is not None]
    if len(values) < len(parts):
        return None
    if len(values) == 1:  # minutes alone
        values.append(Fraction(0))
    h, m, s = [Fraction(0)] * (_PARTS - len(values)) + values
    return ms(h * 3600 + m * 60 + s, 1000)


def rows(lines: list[str], name: str, *, webvtt: bool) -> list[Cue]:
    """Cues, their text kept with its tags (a WhisperX <u> marks a word).

    A cue opens at its timing line (``_timing``) and closes at a blank line, or at the next cue
    (bash's intext and its set st, which always changed together). Its text lines joined by a
    space, each character joined across the lines it spans (``utf8.by_line``: what is still not
    UTF-8, refused by its line).

    Any other line holding ``-->`` is the cue's text in SubRip, as ffmpeg reads it; in WebVTT it
    ends the cue, and the lines after it up to a blank line or a timing line are no cue's (W3C
    WebVTT, "collect a WebVTT block": its timings do not parse, the block is dropped).
    """
    times: list[tuple[int | None, int | None]] = []
    texts: list[tuple[int, int]] = []  # each text line: its cue, its index among the lines
    is_open = False
    for i, line in enumerate(lines):
        timing = _timing(line)
        if timing is not None:
            times.append(timing)
            is_open = True
        elif _BLANK_LINE.fullmatch(line) or (webvtt and "-->" in line):
            is_open = False
        elif is_open:
            texts.append((len(times) - 1, i))
    whole = by_line([(i + 1, lines[i]) for _, i in texts], name)
    parts: list[list[str]] = [[] for _ in times]
    for (cue, _), text in zip(texts, whole, strict=True):
        if text:  # a line of a character's last bytes alone: given to the line it starts in
            parts[cue].append(text)
    return [Cue(*t, " ".join(p)) for t, p in zip(times, parts, strict=True)]


def is_highlighted(cues: list[Cue]) -> bool:
    """WhisperX --highlight_words, by structure: <u> somewhere, most neighbours one text."""
    plains = [untagged(c.text) for c in cues]
    underlined = any("<u>" in c.text for c in cues)
    same = sum(1 for i in range(1, len(plains)) if plains[i] == plains[i - 1])
    return underlined and len(cues) > 1 and same / (len(cues) - 1) >= 0.5  # noqa: PLR2004 -- most


def highlighted(cues: list[Cue]) -> tuple[list[Cue], list[Timing]]:
    """One sentence a run of one text (new when the underline moves back); each <u> a word."""
    sentences: list[Cue] = []
    words: list[Timing] = []
    current, cs, ce, last, sid = "", None, None, -1, -1
    for cue in cues:
        plain = untagged(cue.text)
        underline = _UNDERLINE.search(cue.text)
        offset = len(untagged(cue.text[: underline.start()])) if underline else -1
        if plain != current or (underline and offset <= last):
            if current:
                sentences.append(Cue(cs, ce, current, str(sid)))
            sid, current, cs, last = sid + 1, plain, cue.start, -1
        ce = cue.end
        if underline:
            words.append(Timing(str(sid), cue.start, cue.end, underline[1]))
            last = offset
    if current:
        sentences.append(Cue(cs, ce, current, str(sid)))
    return sentences, words
