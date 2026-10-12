"""LRC: a line's times, its text; the ``[offset:]`` tag moving every time."""

import re
from typing import Final

from subverter.readers.fields import exact, ms
from subverter.readers.subrip import split_lines
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue, Reading

# ``split_lines``, its line ends: no standard's, so SubRip's (ffmpeg's lrcdec ends a line at an
# LF alone, dropping each CR -- a CR-only file one line)
__all__ = ["read", "split_lines"]

_TIME: Final = r"\[([0-9]+):([0-9]+(?:[.][0-9]+)?)\]"  # [mm:ss.xx]
_STAMP: Final = re.compile(_TIME)
# a line's stamps, blanks between them (as Navidrome reads them), then its text
_STAMPS: Final = re.compile(rf"{_TIME}(?:[ \t]*{_TIME})*")
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

    A line of several stamps is a line each (Wikipedia's repeated line; ffmpeg's lrcdec). Each
    character joined across the lines it spans, in the file's order, then sorted
    (``utf8.by_line``: what is still not UTF-8, refused by its line).
    """
    # each timed line: its starts, its line (from 1), its text
    stamped: list[tuple[list[int], int, str]] = []
    for i, line in enumerate(lines, 1):
        run = _STAMPS.match(line)
        if run is None:
            continue
        starts = [s for m in _STAMP.finditer(run[0]) if (s := _start(m, offset)) is not None]
        if starts:
            stamped.append((starts, i, line[run.end() :]))
    whole = by_line([(i, text) for _, i, text in stamped], name)
    timed = [(s, text) for (starts, _, _), text in zip(stamped, whole, strict=True) for s in starts]
    timed.sort(key=lambda t: t[0])  # stable, as sort -s
    ends = [t[0] for t in timed[1:]] + ([timed[-1][0] + 3000] if timed else [])
    return [Cue(s, e, t) for (s, t), e in zip(timed, ends, strict=True)]


def _start(stamp: re.Match[str], offset: int) -> int | None:
    """A stamp's time in ms, ``offset`` ms sooner; None past a double's range (no line)."""
    minutes, seconds = exact(stamp[1]), exact(stamp[2])
    if minutes is None or seconds is None:
        return None
    return ms((minutes * 60 + seconds) * 1000 - offset, 1)
