"""SubRip's grammar, as ffmpeg's srt demuxer reads it (``cues.Dialect``).

Its line ends (``split_lines``); its timing line, a seconds fraction not of three digits a
count of ms; an empty line or a line of spaces skipped, the cue going on (``_BLANK``); a number
alone, only empty lines between it and a timing line, the next cue's index; a line holding
``-->`` that is no timing line, text.
"""

import re
from fractions import Fraction
from typing import Final

from subverter.notes import excerpt
from subverter.readers.cues import Dialect, Found, Timed
from subverter.readers.cues import read as read_cues
from subverter.readers.fields import DECIMAL, NUMBER, exact, is_decimal, ms
from subverter.transcript import Reading

__all__ = ["read", "split_lines"]

_PARTS: Final = 3  # a time's most: hours, minutes, seconds
_MS_DIGITS: Final = 3  # a fraction of seconds, as SubRip writes one: milliseconds
_END: Final = re.compile(rf"{NUMBER}(?::{NUMBER}){{0,{_PARTS - 1}}}")  # what follows, ignored
# a cue's last line, a number alone, only empty lines between it and a timing line: the next
# cue's index, as ffmpeg's srt demuxer reads it (which, after a cue's text, drops any line
# starting with a number there)
_INDEX: Final = re.compile(r"[ \t]*[0-9]+[ \t]*")
# an empty line, ffmpeg's demuxer skips (srtdec.c): the cue goes on; a line of spaces alone too,
# as MPC-HC (STS.cpp) and Subtitle Edit (SubRip.cs) read it -- ffmpeg's decoder ends the text
# there (htmlsubtitles.c, a line end at a line's start), its demuxer keeping what follows
_BLANK: Final = re.compile(" *")
_SSCANF_BLANKS: Final = " \t\v\f"  # C's isspace, no line end: sscanf's round " --> " (srtdec.c)


def _timing(line: str) -> Timed | None:
    """A timing line's times, or None: no timing line -- the line is text, as ffmpeg reads it.

    A timing line: an arrow, wholly a time before it (``_ms``), and a time first after it --
    what follows, SubRip's coordinates, ignored, a blank between or not (as ffmpeg reads them).
    """
    if "-->" not in line:
        return None
    # at its first arrow, the blanks after it off (``is_decimal`` takes those before) -- not by
    # ``[ \t]*-->``, which scans a run of blanks again from each of them
    left, _, right = line.partition("-->")
    right = right.lstrip(_SSCANF_BLANKS)
    start = left.replace(",", ".").split(":")
    end = _END.match(right.replace(",", "."))  # "," to ".": the same length, so ``right``'s spans
    if end is None or len(start) > _PARTS or not all(map(is_decimal, start)):
        return None
    sides = [(left.strip(), start), (right[: end.end()], end[0].split(":"))]
    times = [(written, *_ms(parts)) for written, parts in sides]
    odd = tuple((written, value) for written, value, is_odd in times if is_odd)
    return Timed(times[0][1], times[1][1], odd)


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

    An odd fraction is a count of milliseconds, as ffmpeg's srt demuxer and VLC's subtitle
    module read it (``01,5`` 1.005 s, ``01,5000`` 6 s): three digits read alike either way.
    With an exponent, a decimal.
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


def _notes(found: Found) -> tuple[str, ...]:
    """Odd times read as ms, indexes taken from cues' texts, texts kept after a blank line."""
    return (
        _fraction_notes(found.odd)
        + _index_notes(found.indexes)
        + _continued_notes(found.continued)
        + _spaced_notes(found.spaced)
    )


def _fraction_notes(odd: list[tuple[int, Timed]]) -> tuple[str, ...]:
    """Odd times, read as ms: counted, the first named, with what it was read as."""
    if not odd:
        return ()
    line, timing = odd[0]
    written, value = timing.odd[0]
    count = sum(len(t.odd) for _, t in odd)
    how = "read as milliseconds as ffmpeg and VLC read them"
    taken = "no time (past a double's range)" if value is None else f"{_in_seconds(value)} s"
    first = f"the first, {excerpt(written)} on line {line}, as {taken}"
    return (f"{count} times had a fraction not of three digits, {how}: {first}",)


def _index_notes(indexes: list[tuple[int, str]]) -> tuple[str, ...]:
    """The indexes taken from cues' texts: counted, the first named."""
    if not indexes:
        return ()
    line, number = indexes[0]
    how = "read as the next cue's index, as ffmpeg reads them"
    first = f"the first, {excerpt(number)} on line {line}"
    return (f"{len(indexes)} lines of a number alone before a timing line {how}: {first}",)


def _continued_notes(continued: list[tuple[int, str]]) -> tuple[str, ...]:
    """The cues read on past an empty line (VLC and Kodi end them there): counted, the first."""
    if not continued:
        return ()
    line, text = continued[0]
    how = "read as theirs, as ffmpeg reads them"
    first = f"the first, {excerpt(text)} on line {line}"
    return (f"{len(continued)} cues held text after an empty line, {how}: {first}",)


def _spaced_notes(spaced: list[tuple[int, str]]) -> tuple[str, ...]:
    """The cues read on past a line of spaces (ffmpeg's decoder ends them): counted, the first."""
    if not spaced:
        return ()
    line, text = spaced[0]
    how = "read as theirs, as MPC-HC and Subtitle Edit read them (ffmpeg's decoder drops it)"
    first = f"the first, {excerpt(text)} on line {line}"
    return (f"{len(spaced)} cues held text after a line of spaces, {how}: {first}",)


def _in_seconds(value: int) -> str:
    """``value`` ms as seconds, its trailing zeros off: 1005 is ``1.005``, 6000 ``6``."""
    sign, size = "-" if value < 0 else "", abs(value)
    return f"{sign}{size // 1000}.{size % 1000:03d}".rstrip("0").rstrip(".")


def split_lines(text: str) -> list[str]:
    r"""The text's lines, at ``\r*\n|\r``: a CR or an LF ends one, the CRs before an LF part of it.

    Each line holding text ffmpeg's (``ff_subtitles_read_line``, which takes CR CR LF as one end
    too): a CRLF file written again in text mode reads as written (VLC 3 alike). Its empty lines
    differ: ffmpeg skips the CRs and an LF after any end, so reads none; here each is kept for
    the notes (an LF then a CR two ends), a cue reading on past it as ffmpeg's does (``_BLANK``).
    In linear time, as that pattern is not: at the LFs, each part's CRs before one off, then at
    the CRs left.
    """
    *ended, last = text.split("\n")
    return [line for part in ended for line in part.rstrip("\r").split("\r")] + last.split("\r")


def read(lines: list[str], name: str) -> Reading:
    """A SubRip file's cues (``cues.read``): no signature to it."""
    return read_cues(lines, name, _DIALECT)


# its texts hold ASS's escapes, as ffmpeg's subrip decoder passes them to libass, and no HTML
# reference (it decodes none)
_DIALECT: Final = Dialect(
    ".srt",
    _timing,
    ends=None,
    blank=_BLANK,
    arrow_ends=False,
    index=_INDEX,
    notes=_notes,
    has_references=False,
    has_ass_escapes=True,
)
