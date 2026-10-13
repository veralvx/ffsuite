"""SubRip's grammar, as ffmpeg's srt demuxer reads it (``cues.Dialect``).

Its encoding, UTF-8 or UTF-16 by its BOM (``file_lines``); its line ends (``split_lines``); its
timing line, each time hours:minutes:seconds of whole numbers, a fraction a count of ms
(``_TIME``); an empty line or a line of spaces skipped, the cue going on (``_BLANK``); a number
alone, only empty lines between it and a timing line, the next cue's index; a line holding
``-->`` that is no timing line, text.
"""

import re
from typing import Final

from subverter._errors import shown
from subverter.readers.cues import Dialect, Found, Odd, Timed
from subverter.readers.cues import read as read_cues
from subverter.readers.fields import exact, ms
from subverter.readers.utf8 import file_text, utf16
from subverter.transcript import Reading

__all__ = ["file_lines", "read", "split_lines"]

# a cue's last line, a number alone, only empty lines between it and a timing line: the next
# cue's index, as ffmpeg's srt demuxer reads it (which, after a cue's text, drops any line led
# by a number there, a negative one aside: strtol's)
_INDEX: Final = re.compile(r"[ \t]*[0-9]+[ \t]*")
# an empty line, ffmpeg's demuxer skips (srtdec.c): the cue goes on; a line of spaces alone too,
# as MPC-HC (STS.cpp) and Subtitle Edit (SubRip.cs) read it -- ffmpeg's decoder ends the text
# there (htmlsubtitles.c, a line end at a line's start), its demuxer keeping what follows
_BLANK: Final = re.compile(" *")
_SSCANF_BLANKS: Final = " \t\v\f"  # C's isspace, no line end: sscanf's (srtdec.c)
_MS_DIGITS: Final = 3  # a fraction of seconds, as SubRip writes one: milliseconds
_SHORT: Final = "short"  # an odd time (``Odd.kind``): its fraction not of three digits
_BARE: Final = "bare"  # no fraction: VLC 3's, not ffmpeg's
# sscanf's %d, ffmpeg's ``get_event_info`` reads each of a time's numbers by: blanks, a sign,
# ASCII digits -- each run whole (possessive: ``(?![,.])`` splits no digits, a failed match
# gives back no blanks one by one)
_NUMBER: Final = rf"[{_SSCANF_BLANKS}]*+[-+]?[0-9]++"
# hours:minutes:seconds, then a fraction's mark and its number -- or no mark: the fraction
# optional, as VLC 3 reads it (ffmpeg's needs one); a mark without its number, no time
_TIME: Final = re.compile(rf"({_NUMBER}):({_NUMBER}):({_NUMBER})(?:[,.]({_NUMBER})|(?![,.]))")


def _timing(line: str) -> Timed | None:
    """A timing line's times, or None: no timing line -- the line is text, as ffmpeg reads it.

    ffmpeg's sscanf (``get_event_info``), the fraction optional (``_TIME``): at its first arrow,
    wholly a time before it, blanks round it, and a time first after it -- what follows,
    SubRip's coordinates, ignored, a blank between or not.
    """
    left, arrow, right = line.partition("-->")
    if not arrow:
        return None
    start = _TIME.fullmatch(left.rstrip(_SSCANF_BLANKS))  # its numbers take the blanks before
    end = _TIME.match(right)
    if start is None or end is None:
        return None
    times = [(found[0].lstrip(_SSCANF_BLANKS), *_ms(found)) for found in (start, end)]
    odd = tuple(Odd(kind, written, value) for written, value, kind in times if kind)
    return Timed(times[0][1], times[1][1], odd)


def _ms(time: re.Match[str]) -> tuple[int | None, str | None]:
    """A time's ms, as ffmpeg reads it: each number added, its own sign (``-00`` none); how odd.

    Its fraction a count of ms, as ffmpeg's srt demuxer and VLC's subtitle module read it
    (``01,5`` 1.005 s, ``01,5000`` 6 s): ``_SHORT`` if not of three digits -- three read alike
    either way; none, ``_BARE``. Each number read exactly (``exact``): None if one is past a
    double's range.
    """
    hours, minutes, seconds, fraction = time.groups()
    numbers = (hours, minutes, seconds, fraction or "0")
    values = [value for value in map(exact, numbers) if value is not None]
    digits = (fraction or "").lstrip(_SSCANF_BLANKS).lstrip("-+")
    kind = _BARE if fraction is None else _SHORT if len(digits) != _MS_DIGITS else None
    if len(values) < len(numbers):
        return None, kind
    h, m, s, count = values
    return ms(((h * 60 + m) * 60 + s) * 1000 + count, 1), kind


def _notes(found: Found) -> tuple[str, ...]:
    """Odd times, indexes taken from cues' texts, texts kept after a blank line."""
    return (
        _fraction_notes(found.odd)
        + _bare_notes(found.odd)
        + _index_notes(found.indexes)
        + _continued_notes(found.continued)
        + _spaced_notes(found.spaced)
    )


def _fraction_notes(odd: list[tuple[int, Timed]]) -> tuple[str, ...]:
    """Short fractions, read as ms: counted, the first named, with what it was read as."""
    times = _odd(odd, _SHORT)
    if not times:
        return ()
    line, first = times[0]
    how = "read as milliseconds as ffmpeg and VLC read them"
    value = first.value
    taken = "no time (past a double's range)" if value is None else f"{_in_seconds(value)} s"
    named = f"the first, {shown(first.written)} on line {line}, as {taken}"
    return (f"{len(times)} times had a fraction not of three digits, {how}: {named}",)


def _bare_notes(odd: list[tuple[int, Timed]]) -> tuple[str, ...]:
    """Times without a fraction, read as VLC reads them: counted, the first named."""
    times = _odd(odd, _BARE)
    if not times:
        return ()
    line, first = times[0]
    how = "read as VLC reads them (ffmpeg reads no such timing line, its cue lost)"
    named = f"the first, {shown(first.written)} on line {line}"
    return (f"{len(times)} times had no fraction, {how}: {named}",)


def _odd(odd: list[tuple[int, Timed]], kind: str) -> list[tuple[int, Odd]]:
    """The odd times of one kind, each with its line."""
    return [(line, time) for line, timing in odd for time in timing.odd if time.kind == kind]


def _index_notes(indexes: list[tuple[int, str]]) -> tuple[str, ...]:
    """The indexes taken from cues' texts: counted, the first named."""
    if not indexes:
        return ()
    line, number = indexes[0]
    how = "read as the next cue's index, as ffmpeg reads them"
    first = f"the first, {shown(number)} on line {line}"
    return (f"{len(indexes)} lines of a number alone before a timing line {how}: {first}",)


def _continued_notes(continued: list[tuple[int, str]]) -> tuple[str, ...]:
    """The cues read on past an empty line (VLC and Kodi end them there): counted, the first."""
    if not continued:
        return ()
    line, text = continued[0]
    how = "read as theirs, as ffmpeg reads them"
    first = f"the first, {shown(text)} on line {line}"
    return (f"{len(continued)} cues held text after an empty line, {how}: {first}",)


def _spaced_notes(spaced: list[tuple[int, str]]) -> tuple[str, ...]:
    """The cues read on past a line of spaces (ffmpeg's decoder ends them): counted, the first."""
    if not spaced:
        return ()
    line, text = spaced[0]
    how = "read as theirs, as MPC-HC and Subtitle Edit read them (ffmpeg's decoder drops it)"
    first = f"the first, {shown(text)} on line {line}"
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


def read(data: bytes, name: str) -> Reading:
    """A SubRip file's cues (``cues.read``), its lines ``split_lines``'s: no signature to it."""
    return read_cues(file_lines(data, name), name, _DIALECT)


def file_lines(data: bytes, name: str) -> list[str]:
    """A SubRip's or an LRC's lines (``split_lines``): UTF-16 by its BOM (``utf16``), else UTF-8.

    A refusal's line counted as they are split here. ffmpeg's SubRip reader recodes UTF-16 (VLC
    3 alike), stopping at a lone surrogate's NUL, every later cue lost; its LRC one reads none.
    """
    text = utf16(data, name, lambda whole: len(split_lines(whole)))
    return split_lines(file_text(data) if text is None else text)


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
