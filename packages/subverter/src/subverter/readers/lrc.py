"""LRC: a line's time, its text; the ``[offset:]`` tag moving every time."""

import re
from typing import Final

from subverter.readers.fields import exact, ms
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue, Reading

__all__ = ["read"]

_STAMP: Final = re.compile(r"\[([0-9]+):([0-9]+(?:[.][0-9]+)?)\](.*)")  # [mm:ss.xx]text
# ffmpeg's lrcdec (measured): first on its line, lower case, its value up to the first "]"
_OFFSET: Final = re.compile(r"\[offset:([^\]]*)\]")
_WHOLE: Final = re.compile(r"[ \t]*[-+]?[0-9]+[ \t]*")


def read(lines: list[str], name: str) -> Reading:
    """The cues, every time moved by the offset (``_offset``), and its notes."""
    offset, notes = _offset(lines)
    return Reading(".lrc", has_words=False, cues=tuple(_rows(lines, name, offset)), notes=notes)


def _offset(lines: list[str]) -> tuple[int, tuple[str, ...]]:
    """The last ``[offset:]`` of whole ms, 0 if none; a note for it and for each one not whole.

    The convention's (Wikipedia, "LRC (file format)"; OpenSubsonic's structured lyrics): one
    offset for every time, wherever it stands, ``+`` sooner. ffmpeg 8.1.2 moves only the lines
    after it, by microseconds; pylrc the other way; bash read none.
    """
    offset, at = 0, 0
    notes: list[str] = []
    for i, line in enumerate(lines, 1):
        tag = _OFFSET.match(line)
        if tag is None:
            continue
        value = exact(tag[1]) if _WHOLE.fullmatch(tag[1]) else None  # past a double: no number
        if value is None:
            notes.append(f"LRC offset on line {i} ignored: not a whole number of milliseconds")
        else:
            offset, at = int(value), i
    if offset:
        way = "sooner" if offset > 0 else "later"
        notes.append(f"LRC offset on line {at} applied: every line {abs(offset)} ms {way}")
    return offset, tuple(notes)


def _rows(lines: list[str], name: str, offset: int) -> list[Cue]:
    """Starts only, ``offset`` ms sooner: each line ends where the next starts (the last 3 s on).

    Each character joined across the lines it spans, in the file's order, then sorted
    (``utf8.by_line``: what is still not UTF-8, refused by its line).
    """
    stamped: list[tuple[int, int, str]] = []  # each timed line: its start, its index, its text
    for i, line in enumerate(lines):
        m = _STAMP.fullmatch(line)
        if m is None:
            continue
        minutes, seconds = exact(m[1]), exact(m[2])
        if minutes is None or seconds is None:  # past a double's range: no time, no line
            continue
        start = ms((minutes * 60 + seconds) * 1000 - offset, 1)
        if start is not None:
            stamped.append((start, i, m[3]))
    whole = by_line([(i + 1, text) for _, i, text in stamped], name)
    timed = list(zip((s for s, _, _ in stamped), whole, strict=True))
    timed.sort(key=lambda t: t[0])  # stable, as sort -s
    ends = [t[0] for t in timed[1:]] + ([timed[-1][0] + 3000] if timed else [])
    return [Cue(s, e, t) for (s, t), e in zip(timed, ends, strict=True)]
