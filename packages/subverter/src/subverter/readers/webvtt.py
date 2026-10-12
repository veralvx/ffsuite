"""WebVTT's grammar, as the W3C reads it (``cues.Dialect``).

A timing line wholly "collect WebVTT cue timings and settings" -- else none, and a line holding
``-->`` ends the cue, its block dropped, noted (Chromium 141 alike; ffmpeg's demuxer and VLC 3
read some such lines, ffmpeg losing every cue after one it cannot).
"""

import re
from fractions import Fraction
from typing import Final

from subverter.readers.cues import Dialect, Found, Timed
from subverter.readers.fields import exact, ms

__all__ = ["DIALECT"]

# "collect a WebVTT timestamp": hours of any ASCII digits and a colon, or none; minutes and
# seconds of two, each to 59 (``_LAST``); a fraction of three. A first field over 59, or not
# of two digits, is hours, their seconds needed -- so ``75:00.000`` is none
_TIMESTAMP: Final = r"(?:([0-9]+):)?([0-9]{2}):([0-9]{2})\.([0-9]{3})(?![0-9])"
_BLANKS: Final = "[ \t\f]*"  # "skip whitespace": a line's ASCII whitespace
# a start, the arrow, an end; what remains, the cue's settings, ignored
_TIMINGS: Final = re.compile(f"{_BLANKS}{_TIMESTAMP}{_BLANKS}-->{_BLANKS}{_TIMESTAMP}")
_LAST: Final = 59  # a minute's and a second's largest


def _timing(line: str) -> Timed | None:
    """A timing line's times, as the W3C collects them; or None: no timing line."""
    found = _TIMINGS.match(line)
    if found is None:
        return None
    fields = found.groups()
    start, end = fields[:4], fields[4:]
    if any(int(side[1]) > _LAST or int(side[2]) > _LAST for side in (start, end)):
        return None  # past 59: an error
    return Timed(_ms(*start), _ms(*end))


def _ms(hours: str | None, minutes: str, seconds: str, fraction: str) -> int | None:
    """A timestamp's whole ms; None past a double's range (hours of any digits, ``exact``)."""
    hour = exact(hours or "0")
    if hour is None:
        return None
    return ms(hour * 3600 + int(minutes) * 60 + int(seconds) + Fraction(int(fraction), 1000), 1000)


def _notes(found: Found) -> tuple[str, ...]:
    """The blocks dropped: counted, the first named by its line."""
    if not found.dropped:
        return ()
    line, text = found.dropped[0]
    why = "a line holding --> that is no WebVTT timing line (W3C)"
    return (f"{len(found.dropped)} cues dropped: {why}, the first {text} on line {line}",)


# its texts hold HTML character references (the W3C's cue text tokenizer), and no ASS escape
# (ffmpeg's webvtt decoder escapes a backslash)
DIALECT: Final = Dialect(
    ".vtt",
    _timing,
    arrow_ends=True,
    index=None,
    notes=_notes,
    has_references=True,
    has_ass_escapes=False,
)
