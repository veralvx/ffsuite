"""WebVTT, as the W3C reads it: its line ends, its signature, its cues (``cues``, its ``Dialect``).

A file not opening with its signature is refused, as the W3C's parser processes none (Chromium
141 alike; VLC 3 refuses each unless forced; ffmpeg's demuxer reads one whose first block opens
``WEBVTT``, ``NOTE``, ``STYLE`` or ``REGION``, or is a cue -- any other, no cue). A timing line
is wholly "collect WebVTT cue timings and settings" -- else none, and a line holding ``-->``
ends the cue, its block dropped, noted (Chromium alike; ffmpeg's demuxer and VLC 3 read some
such lines, ffmpeg losing every cue after one it cannot). A cue ends at an empty line ("collect a
WebVTT block"): a block of text after it, holding no ``-->``, is no cue's -- dropped (Chromium
and VLC 3 alike; ffmpeg's demuxer loses every cue after it), noted past the first cue.
"""

import re
from fractions import Fraction
from typing import Final

from subverter._errors import refuse
from subverter.notes import excerpt
from subverter.readers.cues import Dialect, Found, Timed
from subverter.readers.cues import read as read_cues
from subverter.readers.fields import exact, ms
from subverter.transcript import Reading

__all__ = ["read", "split_lines"]

_LINE_END: Final = re.compile(r"\r\n|\r|\n")
_SIGNATURE: Final = "WEBVTT"
_AFTER: Final = ("", " ", "\t")  # what may follow it on its line
_ENDS: Final = re.compile("")  # "collect a WebVTT block": a cue's end, an empty line alone

# "collect a WebVTT timestamp": hours of any ASCII digits and a colon, or none; minutes and
# seconds of two, each to 59 (``_LAST``); a fraction of three. A first field over 59, or not
# of two digits, is hours, their seconds needed -- so ``75:00.000`` is none
_TIMESTAMP: Final = r"(?:([0-9]+):)?([0-9]{2}):([0-9]{2})\.([0-9]{3})(?![0-9])"
_BLANKS: Final = "[ \t\f]*"  # "skip whitespace": a line's ASCII whitespace
# a start, the arrow, an end; what remains, the cue's settings, ignored
_TIMINGS: Final = re.compile(f"{_BLANKS}{_TIMESTAMP}{_BLANKS}-->{_BLANKS}{_TIMESTAMP}")
_LAST: Final = 59  # a minute's and a second's largest
# the syntax's blocks of no text: a comment (``NOTE``, then a space, a tab or its line's end), a
# style sheet or a region (its keyword, then spaces or tabs alone)
_NO_TEXT: Final = re.compile(r"NOTE(?:[ \t].*)?|(?:STYLE|REGION)[ \t]*")


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
    """The blocks dropped: a cue's for its timing line; text no cue holds."""
    return _dropped_notes(found.dropped) + _stray_notes(found.strays)


def _dropped_notes(dropped: list[tuple[int, str]]) -> tuple[str, ...]:
    """The cues dropped for their timing line: counted, the first named by its line."""
    if not dropped:
        return ()
    line, text = dropped[0]
    why = "a line holding --> that is no WebVTT timing line (W3C)"
    return (f"{len(dropped)} cues dropped: {why}, the first {excerpt(text)} on line {line}",)


def _stray_notes(strays: list[tuple[int, str]]) -> tuple[str, ...]:
    """The text no cue holds, but the syntax's blocks of none: counted, the first named."""
    texts = [(line, text.strip()) for line, text in strays if not _NO_TEXT.fullmatch(text)]
    if not texts:
        return ()
    line, text = texts[0]
    why = "after an empty line, in no cue (W3C)"
    return (f"{len(texts)} text blocks dropped: {why}, the first {excerpt(text)} on line {line}",)


def split_lines(text: str) -> list[str]:
    """The text's lines, as the W3C ends them: at each CRLF, CR or LF -- CR CR LF two ends."""
    return _LINE_END.split(text)


def read(lines: list[str], name: str) -> Reading:
    """A WebVTT file's cues (``cues.read``); refused unless it opens with its signature.

    "WebVTT parser algorithm": ``WEBVTT`` first -- a BOM before it decoded away, a second one
    not -- then nothing on its line, or a space or a tab before anything; else the file is
    not processed. Its line is then skipped whole, an arrow on it no timing line.
    """
    first = lines[0] if lines else ""
    rest = first.removeprefix(_SIGNATURE)
    if rest == first or rest[:1] not in _AFTER:
        refuse(f"not a WebVTT file: {name} (its first line is not WEBVTT)")
    return read_cues(["", *lines[1:]], name, _DIALECT)  # blank: the lines keep their numbers


# its texts hold HTML character references (the W3C's cue text tokenizer), and no ASS escape
# (ffmpeg's webvtt decoder escapes a backslash)
_DIALECT: Final = Dialect(
    ".vtt",
    _timing,
    ends=_ENDS,
    blank=_ENDS,  # an empty line: it ends the cue first
    arrow_ends=True,
    index=None,
    notes=_notes,
    has_references=True,
    has_ass_escapes=False,
)
