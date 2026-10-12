"""SubRip's grammar, as ffmpeg's srt demuxer reads it (``cues.Dialect``).

Its timing line, a seconds fraction not of three digits a count of ms; a number alone right
before a timing line the next cue's index; a line holding ``-->`` that is no timing line, text.
"""

import re
from fractions import Fraction
from typing import Final

from subverter.readers.cues import Dialect, Found, Timed
from subverter.readers.fields import DECIMAL, NUMBER, exact, is_decimal, ms

__all__ = ["DIALECT"]

_PARTS: Final = 3  # a time's most: hours, minutes, seconds
_MS_DIGITS: Final = 3  # a fraction of seconds, as SubRip writes one: milliseconds
_ARROW: Final = re.compile(r"[ \t]*-->[ \t]*")  # a cue's times, either side
_END: Final = re.compile(rf"{NUMBER}(?::{NUMBER}){{0,{_PARTS - 1}}}")  # what follows, ignored
# a cue's line of a number alone right before a timing line: the next cue's index, its blank
# line missing, as ffmpeg's srt demuxer reads it (which, after a cue's text, drops any line
# starting with a number there)
_INDEX: Final = re.compile(r"[ \t]*[0-9]+[ \t]*")


def _timing(line: str) -> Timed | None:
    """A timing line's times, or None: no timing line -- the line is text, as ffmpeg reads it.

    A timing line: an arrow, wholly a time before it (``_ms``), and a time first after it --
    what follows, SubRip's coordinates, ignored, a blank between or not (as ffmpeg reads them).
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
    """Odd times read as ms, and indexes taken from cues' texts: each counted, the first named."""
    return _fraction_notes(found.odd) + _index_notes(found.indexes)


def _fraction_notes(odd: list[tuple[int, Timed]]) -> tuple[str, ...]:
    """Odd times, read as ms: counted, the first named, with what it was read as."""
    if not odd:
        return ()
    line, timing = odd[0]
    written, value = timing.odd[0]
    count = sum(len(t.odd) for _, t in odd)
    how = "read as milliseconds as ffmpeg and VLC read them"
    taken = "no time (past a double's range)" if value is None else f"{_in_seconds(value)} s"
    first = f"the first, {written} on line {line}, as {taken}"
    return (f"{count} times had a fraction not of three digits, {how}: {first}",)


def _index_notes(indexes: list[tuple[int, str]]) -> tuple[str, ...]:
    """The indexes taken from cues' texts: counted, the first named."""
    if not indexes:
        return ()
    line, number = indexes[0]
    how = "read as the next cue's index, as ffmpeg reads them"
    first = f"the first, {number} on line {line}"
    return (f"{len(indexes)} lines of a number alone before a timing line {how}: {first}",)


def _in_seconds(value: int) -> str:
    """``value`` ms as seconds, its trailing zeros off: 1005 is ``1.005``, 6000 ``6``."""
    sign, size = "-" if value < 0 else "", abs(value)
    return f"{sign}{size // 1000}.{size % 1000:03d}".rstrip("0").rstrip(".")


# its texts hold ASS's escapes, as ffmpeg's subrip decoder passes them to libass, and no HTML
# reference (it decodes none)
DIALECT: Final = Dialect(
    ".srt",
    _timing,
    arrow_ends=False,
    index=_INDEX,
    notes=_notes,
    has_references=False,
    has_ass_escapes=True,
)
