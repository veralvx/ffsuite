"""LRC: a line's times, its text; the ``[offset:]`` tag moving every time.

Its encodings and line ends, no standard's, SubRip's (``subrip.file_lines``): UTF-8, or UTF-16 by
its BOM, as Navidrome and Jellyfin read it (ffmpeg's lrcdec reads none); a CR or an LF ending a
line (ffmpeg's ends one at an LF alone, dropping each CR -- a CR-only file one line).
"""

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Final

from subverter._errors import shown
from subverter.markup import LRC_TIME
from subverter.readers.fields import exact, ms
from subverter.readers.subrip import file_lines
from subverter.readers.utf8 import Nuls, by_line, nul_notes
from subverter.transcript import Cue, Reading

__all__ = ["read"]

_BLANKS: Final = " \t"  # ffmpeg's lrcdec's (find_header, read_ts, count_ts)
_TIME: Final = rf"\[(-?){LRC_TIME}\]"  # [mm:ss.xx]; a minus before 0, ffmpeg's lrcenc's
_STAMP: Final = re.compile(_TIME)
# a line's stamps, blanks between them (as Navidrome reads them), then its text
_STAMPS: Final = re.compile(rf"{_TIME}(?:[{_BLANKS}]*{_TIME})*")
# a tag: a letter first (ffmpeg's lrcdec lower case, Navidrome's either) or a # (Wikipedia's
# comment), then a colon
_TAG: Final = re.compile(r"\[[A-Za-z#][^\]:]*:")
# ffmpeg's lrcdec (measured): first on its line, lower case, its value up to the first "]"
_OFFSET: Final = re.compile(r"\[offset:([^\]]*)\]")
_WHOLE: Final = re.compile(r"[ \t]*[-+]?[0-9]+[ \t]*")
# the notes' (``_line_notes``)
_BLANKED: Final = (
    "had blanks before their stamp, read as Navidrome and Jellyfin read them (ffmpeg drops them)"
)
_SIGNED: Final = (
    "had a stamp with a minus, a time before 0, read as ffmpeg writes and reads it "
    "(Navidrome and Jellyfin read none)"
)
_DROPPED: Final = "dropped, opened by no stamp ffman reads nor a tag"


@dataclass
class _Lines:
    """The lines ``_rows`` read past the convention's form, or dropped: each (line, text)."""

    blanked: list[tuple[int, str]] = field(default_factory=list)  # blanks before the stamp
    signed: list[tuple[int, str]] = field(default_factory=list)  # a stamp's time before 0
    dropped: list[tuple[int, str]] = field(default_factory=list)  # no stamp read, no tag


def read(data: bytes, name: str) -> Reading:
    """The cues, every time moved by the offset (``_offset``), and its notes."""
    lines = file_lines(data, name)
    offset, notes = _offset(lines)
    cues, nuls, odd = _rows(lines, name, offset)
    return Reading(
        ".lrc",
        has_words=False,
        cues=tuple(cues),
        notes=notes + _line_notes(odd) + nul_notes(nuls),
        has_word_stamps=True,
    )


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


def _rows(lines: list[str], name: str, offset: int) -> tuple[list[Cue], Nuls, _Lines]:
    """Starts only, ``offset`` ms sooner: each line ends where the next starts (the last 3 s on).

    A line's stamps open it, after any blanks (Navidrome trims a line, Jellyfin finds a stamp
    anywhere; ffmpeg 8.1.2 drops the line, its ``sscanf`` given the blanks ``read_ts`` skipped).
    A line of several stamps is a line each (Wikipedia's repeated line; ffmpeg's lrcdec). Each
    character joined across the lines it spans, in the file's order, then sorted
    (``utf8.by_line``: what is still not UTF-8, refused by its line); their NULs. A line of no
    text or a tag is no lyric; any other line no stamp opens is dropped (``_Lines``).
    """
    # each timed line: its starts, its line (from 1), its text
    stamped: list[tuple[list[int], int, str]] = []
    odd = _Lines()
    for i, line in enumerate(lines, 1):
        body = line.lstrip(_BLANKS)
        run = _STAMPS.match(body)
        stamps = _STAMP.finditer(run[0]) if run else ()
        # each stamp read: its time, its start (``offset`` ms sooner); none past a double's range
        kept = [
            (t, s)
            for m in stamps
            if (t := _time(m)) is not None and (s := ms(t - offset, 1)) is not None
        ]
        if run and kept:  # kept is empty without a run: run narrows the type alone
            stamped.append(([s for _, s in kept], i, body[run.end() :]))
            if len(body) < len(line):
                odd.blanked.append((i, body))
            if any(t < 0 for t, _ in kept):
                odd.signed.append((i, body))
        elif body and not _TAG.match(body):
            odd.dropped.append((i, body))
    whole = by_line([(i, text) for _, i, text in stamped], name)
    timed = [(s, t) for (starts, _, _), t in zip(stamped, whole.texts, strict=True) for s in starts]
    timed.sort(key=lambda t: t[0])  # stable, as sort -s
    ends = [t[0] for t in timed[1:]] + ([timed[-1][0] + 3000] if timed else [])
    return [Cue(s, e, t) for (s, t), e in zip(timed, ends, strict=True)], whole.nuls, odd


def _time(stamp: re.Match[str]) -> Fraction | None:
    """A stamp's time in ms, exactly, negative by its minus; None past ``exact``'s bound."""
    minutes, seconds = exact(stamp[2]), exact(stamp[3])
    if minutes is None or seconds is None:
        return None
    time = (minutes * 60 + seconds) * 1000
    return -time if stamp[1] else time


def _line_notes(odd: _Lines) -> tuple[str, ...]:
    """The lines read past the convention's form, and those dropped: each kind counted, the first.

    Blanks before a stamp, as Navidrome and Jellyfin read them; a minus, as ffmpeg's lrcenc
    writes a time before 0 and its lrcdec reads it (measured, 8.1.2). Dropped: a line no stamp
    ffman reads opens -- hours (Navidrome's), a plus, a comma or a colon before the fraction,
    text before a stamp (Jellyfin's) or none (Navidrome joins it to the line before).
    """
    kinds = ((odd.blanked, _BLANKED), (odd.signed, _SIGNED), (odd.dropped, _DROPPED))
    return tuple(_counted(found, how) for found, how in kinds if found)


def _counted(found: list[tuple[int, str]], how: str) -> str:
    """A kind's note: its lines counted, the first named, by its line."""
    line, text = found[0]
    return f"{len(found)} LRC lines {how}: the first, {shown(text.rstrip())} on line {line}"
