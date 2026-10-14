"""LRC: a line's times, its text; the ``[offset:]`` tag moving every time.

Its encodings and line ends, no standard's, SubRip's (``subrip.file_lines``): UTF-8, or UTF-16 by
its BOM, as Navidrome and Jellyfin read it (ffmpeg's lrcdec reads none); a CR or an LF ending a
line (ffmpeg's ends one at an LF alone, dropping each CR -- a CR-only file one line).
"""

import re
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import groupby
from typing import Final, NamedTuple

from subverter._errors import counted, shown
from subverter.markup import LRC_TIME, unstamped
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
_BLANK_RUN: Final = re.compile(rf"[{_BLANKS}]+")  # squeezed to a space, as ffman shows a text
# a tag: a letter first (ffmpeg's lrcdec lower case, Navidrome's either) or a # (Wikipedia's
# comment), then a colon
_TAG: Final = re.compile(r"\[[A-Za-z#][^\]:]*:")
# ffmpeg's lrcdec (measured): first on its line, lower case, its value up to the first "]"
_OFFSET: Final = re.compile(r"\[offset:([^\]]*)\]")
_WHOLE: Final = re.compile(r"[ \t]*[-+]?[0-9]+[ \t]*")
_FFMPEG_SECONDS: Final = 60  # ffmpeg's lrcdec, read_ts: seconds past it drop the line
# Navidrome's seconds of one or two digits, LrcParser's two: past 60 of more, no reader's
_SECONDS_DIGITS: Final = 2
# an offset ignored: why, in its notes' order (``_offset``)
_NOT_FIRST: Final = "not first on its line, as ffmpeg's tag (Navidrome applies it)"
_NOT_WHOLE: Final = "not a whole number of milliseconds"
_PAST_RANGE: Final = "past a double's range"
_SUPERSEDED: Final = "another after it"
# the notes' (``_line_notes``)
_BLANKED: Final = (
    "had blanks before their stamp, read as Navidrome and Jellyfin read them (ffmpeg drops them)"
)
_SIGNED: Final = (
    "had a stamp with a minus, a time before 0, read as ffmpeg writes and reads it "
    "(Navidrome and Jellyfin read none)"
)
_LATE: Final = (
    "had a stamp of seconds past 60, read as Navidrome and Jellyfin read them (ffmpeg drops them)"
)
_SHARED: Final = (
    "shared a stamp with a line before, joined to it, as Navidrome and Jellyfin show both "
    "(ffmpeg shows the last alone)"
)
_DROPPED: Final = "dropped, opened by no stamp ffman reads nor a tag"


# a stamp's line: its start, its line (from 1), as written from its stamps, its text, the text
# as shown (``_cues``'s key)
type _Timed = tuple[int, int, str, str, str]


@dataclass
class _Lines:
    """The lines ``_rows`` read past the convention's form, or dropped: each (line, text)."""

    blanked: list[tuple[int, str]] = field(default_factory=list)  # blanks before the stamp
    signed: list[tuple[int, str]] = field(default_factory=list)  # a stamp's time before 0
    late: list[tuple[int, str]] = field(default_factory=list)  # a stamp's seconds past 60
    shared: list[tuple[int, str]] = field(default_factory=list)  # joined to a line before
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
    """The last ``[offset:]`` of whole ms, 0 if none; its note, one a reason others are ignored.

    The convention's (Wikipedia, "LRC (file format)"; OpenSubsonic's structured lyrics): one
    offset for every time, wherever it stands, ``+`` sooner. ffmpeg 8.1.2 moves only the lines
    after it, by microseconds; pylrc the other way; bash read none. Ignored: one after blanks
    (ffmpeg's tag is first on its line), one not whole, one past a double's range (no time
    left), one another follows.
    """
    offset, at = 0, 0
    ignored: dict[str, list[int]] = {
        why: [] for why in (_NOT_FIRST, _NOT_WHOLE, _PAST_RANGE, _SUPERSEDED)
    }
    for i, line in enumerate(lines, 1):
        body = line.lstrip(_BLANKS)
        tag = _OFFSET.match(body)
        if tag is None:
            continue
        value = exact(tag[1]) if _WHOLE.fullmatch(tag[1]) else None  # past a double: no number
        if len(body) < len(line):
            ignored[_NOT_FIRST].append(i)
        elif value is None:
            ignored[_NOT_WHOLE].append(i)
        elif ms(value, 1) is None:
            ignored[_PAST_RANGE].append(i)
        else:
            if at:
                ignored[_SUPERSEDED].append(at)
            offset, at = int(value), i
    notes: list[str] = []
    if offset:
        way = "sooner" if offset > 0 else "later"
        size = shown(str(abs(offset)))
        notes.append(f"LRC offset on line {at} applied: every line {size} ms {way}")
    notes += [
        f"{len(found)} LRC offsets ignored, {why}: the first on line {found[0]}"
        for why, found in ignored.items()
        if found
    ]
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
    # each timed line: its starts, its line (from 1), as written from its stamps, its text
    stamped: list[tuple[list[int], int, str, str]] = []
    odd = _Lines()
    for i, line in enumerate(lines, 1):
        body = line.lstrip(_BLANKS)
        run = _STAMPS.match(body)
        stamps = _STAMP.finditer(run[0]) if run else ()
        # each stamp read (``_read``), its start (``offset`` ms sooner): none past a double's range
        kept = [
            (r, s)
            for m in stamps
            if (r := _read(m)) is not None and (s := ms(r.time - offset, 1)) is not None
        ]
        if run and kept:  # kept is empty without a run: run narrows the type alone
            stamped.append(([s for _, s in kept], i, body, body[run.end() :]))
            if len(body) < len(line):
                odd.blanked.append((i, body))
            if any(r.time < 0 for r, _ in kept):
                odd.signed.append((i, body))
            if any(r.seconds > _FFMPEG_SECONDS for r, _ in kept):
                odd.late.append((i, body))
        elif body and not _TAG.match(body):
            odd.dropped.append((i, body))
    whole = by_line([(i, text) for _, i, _, text in stamped], name)
    timed: list[_Timed] = []
    for (starts, i, body, _), text in zip(stamped, whole.texts, strict=True):
        shown_as = _BLANK_RUN.sub(" ", unstamped(text)).strip(" ")  # once a line, not a stamp
        timed += [(s, i, body, text, shown_as) for s in starts]
    timed.sort(key=lambda t: t[0])  # stable, as sort -s: the file's order within a start
    cues = _cues(timed, odd)
    odd.shared = sorted(set(odd.shared))  # a line once, by the file's order
    return cues, whole.nuls, odd


def _cues(timed: list[_Timed], odd: _Lines) -> list[Cue]:
    """A cue a start, each ending where the next starts (the last 3 s on), from ``timed``.

    The lines of one start are one cue, their texts joined by a line break -- ffmpeg's lrcenc
    writes a cue's lines each with its stamp, Navidrome and Jellyfin show each (ffmpeg's lrcdec
    each but the last for no time) -- each line joined to one before noted (``odd.shared``). A
    line of no text but blanks and word stamps joins nothing, nor one of a text its start shows
    already (a stamp repeated, a line twice): shown once, as ffmpeg shows it, the earlier of no
    length.
    """
    starts: list[int] = []
    texts: list[str] = []
    for start, run in groupby(timed, key=lambda t: t[0]):
        said: dict[str, tuple[int, str, str]] = {}  # each text shown: its first line
        for _, i, body, text, shown_as in run:
            if shown_as and shown_as not in said:
                said[shown_as] = (i, body, text)
        joined = list(said.values())
        odd.shared += [(i, body) for i, body, _ in joined[1:]]
        starts.append(start)
        texts.append("\n".join(text for _, _, text in joined))
    ends = [*starts[1:], starts[-1] + 3000] if starts else []
    return [Cue(s, e, t) for s, e, t in zip(starts, ends, texts, strict=True)]


class _Stamp(NamedTuple):
    """A stamp read: its time in ms, exactly, negative by its minus; its seconds."""

    time: Fraction
    seconds: Fraction


def _read(stamp: re.Match[str]) -> _Stamp | None:
    """``stamp`` read; None past ``exact``'s bound, or of seconds no reader reads.

    Past 60 (ffmpeg's) of more than two digits (Navidrome's and LrcParser's): ``[00:099.00]``.
    """
    minutes, seconds = exact(stamp[2]), exact(stamp[3])
    if minutes is None or seconds is None:
        return None
    if seconds > _FFMPEG_SECONDS and len(stamp[3].partition(".")[0]) > _SECONDS_DIGITS:
        return None
    time = (minutes * 60 + seconds) * 1000
    return _Stamp(-time if stamp[1] else time, seconds)


def _line_notes(odd: _Lines) -> tuple[str, ...]:
    """The lines read past the convention's form, and those dropped: each kind counted, the first.

    Blanks before a stamp, as Navidrome and Jellyfin read them; a minus, as ffmpeg's lrcenc
    writes a time before 0 and its lrcdec reads it (measured, 8.1.2); seconds past 60, as
    Navidrome and Jellyfin read them; a line joined to one before (``_cues``). Dropped: a line
    no stamp ffman reads opens -- hours (Navidrome's), a plus, a comma or a colon before the
    fraction, seconds past 60 of more than two digits (``_read``), text before a stamp
    (Jellyfin's) or none (Navidrome joins it to the line before).
    """
    kinds = (
        (odd.blanked, _BLANKED),
        (odd.signed, _SIGNED),
        (odd.late, _LATE),
        (odd.shared, _SHARED),
        (odd.dropped, _DROPPED),
    )
    return tuple(note for found, how in kinds for note in _counted(found, how))


def _counted(found: list[tuple[int, str]], how: str) -> tuple[str, ...]:
    """A kind's note (``counted``), the first named without its trailing blanks."""
    return counted([(at, text.rstrip()) for at, text in found], f"LRC lines {how}")
