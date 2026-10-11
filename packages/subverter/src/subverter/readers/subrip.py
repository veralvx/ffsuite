"""SubRip and WebVTT: cues; WhisperX's highlighted cues, read back into words."""

import re
from fractions import Fraction
from typing import Final, NamedTuple

from subverter.markup import untagged
from subverter.readers.fields import DECIMAL, NUMBER, exact, is_decimal, ms
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue, Reading, Timing

__all__ = ["read"]

_PARTS: Final = 3  # a time's most: hours, minutes, seconds
_MS_DIGITS: Final = 3  # a fraction of seconds, as SubRip and WebVTT write one: milliseconds
_ARROW: Final = re.compile(r"[ \t]*-->[ \t]*")  # a cue's times, either side
_END: Final = re.compile(rf"{NUMBER}(?::{NUMBER}){{0,{_PARTS - 1}}}")  # what follows, ignored
_BLANK_LINE: Final = re.compile(r"[ \t]*")  # a cue's end
_UNDERLINE: Final = re.compile(r"<u>([^<]*)</u>")  # WhisperX --highlight_words: the word


def read(lines: list[str], name: str, *, webvtt: bool) -> Reading:
    """The cues, or WhisperX's sentences and words (``_is_highlighted``); notes (``_rows``)."""
    cues, notes = _rows(lines, name, webvtt=webvtt)
    source = ".vtt" if webvtt else ".srt"
    references = webvtt  # SubRip has none: ffmpeg's subrip decodes none
    if not _is_highlighted(cues):
        return Reading(
            source, has_words=False, cues=tuple(cues), notes=notes, has_references=references
        )
    sentences, words = _highlighted(cues)
    return Reading(
        f"WhisperX --highlight_words {source}",
        has_words=True,
        cues=tuple(sentences),
        words=tuple(words),
        notes=notes,
        has_references=references,
    )


class _Timing(NamedTuple):
    """A timing line's start and end, each None past a double's range (``_ms``).

    ``odd``: its times whose seconds' fraction is not of three digits -- each as written, read.
    """

    start: int | None
    end: int | None
    odd: tuple[tuple[str, int | None], ...]


def _timing(line: str) -> _Timing | None:
    """A timing line's times, or None: no timing line.

    A timing line: an arrow, wholly a time before it (``_ms``), and a time first after it --
    what follows, WebVTT's settings or SubRip's coordinates, ignored, a blank between or not
    (as ffmpeg reads them, and the W3C's "remainder").
    """
    if "-->" not in line:
        return None
    left, right = _ARROW.split(line, maxsplit=1)
    start = left.replace(",", ".").split(":")
    end = _END.match(right.replace(",", "."))  # "," to ".": the same length, so ``right``'s spans
    if end is None or len(start) > _PARTS or not all(map(is_decimal, start)):
        return None
    sides = [(left.strip(), start), (right[: end.end()], end[0].split(":"))]
    times = [(written, *_ms(parts)) for written, parts in sides]
    odd = tuple((written, value) for written, value, is_odd in times if is_odd)
    return _Timing(times[0][1], times[1][1], odd)


def _ms(parts: list[str]) -> tuple[int | None, bool]:
    """subs_srt_vtt's ms(), each part read exactly, the seconds by ``_seconds``; their oddness.

    h:m:s, m:s, or m alone -- awk read a bare number as minutes. None if a part is past a
    double's range.
    """
    *larger, last = parts if len(parts) > 1 else [*parts, "0"]  # minutes alone
    seconds, is_odd = _seconds(last)
    values = [v for v in [*map(exact, larger), seconds] if v is not None]
    if len(values) < len(larger) + 1:
        return None, is_odd
    h, m, s = [Fraction(0)] * (_PARTS - len(values)) + values
    return ms(h * 3600 + m * 60 + s, 1000), is_odd


def _seconds(text: str) -> tuple[Fraction | None, bool]:
    """The seconds' value; whether their fraction is odd: written, not of three digits.

    An odd fraction is a count of milliseconds, as ffmpeg's srt and webvtt demuxers and VLC's
    subtitle module read it (``01,5`` 1.005 s, ``01,5000`` 6 s): three digits read alike either
    way. With an exponent, a decimal.
    """
    found = DECIMAL.fullmatch(text)  # always: ``_timing`` read every part a decimal
    sign, whole, fraction, only, exponent = found.groups() if found else (None,) * 5
    digits = fraction or only
    if exponent is not None or not digits or len(digits) == _MS_DIGITS:
        return exact(text), False
    integral, count = exact(whole or "0"), exact(digits)
    if integral is None or count is None:
        return None, True
    value = integral + count / 1000
    return (-value if sign == "-" else value), True


def _rows(lines: list[str], name: str, *, webvtt: bool) -> tuple[list[Cue], tuple[str, ...]]:
    """Cues, their text kept with its tags (a WhisperX <u> marks a word); notes (``_notes``).

    A cue opens at its timing line (``_timing``) and closes at a blank line, or at the next cue
    (bash's intext and its set st, which always changed together). Its text lines joined by a
    space, each character joined across the lines it spans (``utf8.by_line``: what is still not
    UTF-8, refused by its line).

    Any other line holding ``-->`` is the cue's text in SubRip, as ffmpeg reads it; in WebVTT it
    ends the cue, and the lines after it up to a blank line or a timing line are no cue's (W3C
    WebVTT, "collect a WebVTT block": its timings do not parse, the block is dropped) -- a
    timing line with an odd time too ("collect a WebVTT timestamp": not three digits, an error).
    """
    times: list[tuple[int | None, int | None]] = []
    texts: list[tuple[int, int]] = []  # each text line: its cue, its index among the lines
    odd: list[tuple[int, _Timing]] = []  # each timing line with an odd time: its line, its times
    is_open = False
    for i, line in enumerate(lines):
        timing = _timing(line)
        if timing is not None and timing.odd:
            odd.append((i + 1, timing))
            if webvtt:
                timing = None  # no timing line: its block dropped
        if timing is not None:
            times.append((timing.start, timing.end))
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
    cues = [Cue(*t, " ".join(p)) for t, p in zip(times, parts, strict=True)]
    return cues, _notes(odd, webvtt=webvtt)


def _notes(odd: list[tuple[int, _Timing]], *, webvtt: bool) -> tuple[str, ...]:
    """Odd times: WebVTT's cues dropped, SubRip's times read as ms -- counted, the first named."""
    if not odd:
        return ()
    line, timing = odd[0]
    written, value = timing.odd[0]
    if webvtt:
        why = "a time with a fraction not of three digits (W3C WebVTT)"
        return (f"{len(odd)} cues dropped: {why}, the first {written} on line {line}",)
    count = sum(len(t.odd) for _, t in odd)
    how = "read as milliseconds as ffmpeg and VLC read them"
    taken = "no time (past a double's range)" if value is None else f"{_in_seconds(value)} s"
    first = f"the first, {written} on line {line}, as {taken}"
    return (f"{count} times had a fraction not of three digits, {how}: {first}",)


def _in_seconds(value: int) -> str:
    """``value`` ms as seconds, its trailing zeros off: 1005 is ``1.005``, 6000 ``6``."""
    sign, size = "-" if value < 0 else "", abs(value)
    return f"{sign}{size // 1000}.{size % 1000:03d}".rstrip("0").rstrip(".")


def _is_highlighted(cues: list[Cue]) -> bool:
    """WhisperX --highlight_words, by structure: <u> somewhere, most neighbours one text."""
    plains = [untagged(c.text) for c in cues]
    underlined = any("<u>" in c.text for c in cues)
    same = sum(1 for i in range(1, len(plains)) if plains[i] == plains[i - 1])
    return underlined and len(cues) > 1 and same / (len(cues) - 1) >= 0.5  # noqa: PLR2004 -- most


def _highlighted(cues: list[Cue]) -> tuple[list[Cue], list[Timing]]:
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
