r"""A transcript as SRT, for a soft subtitle track (the bash ffman's write_srt).

Cues past the media's end are dropped and one running past it is cut there: a
cue past the end would stretch the file. The end is the media's duration in whole
milliseconds, floored -- so no cue outlasts it (bash truncated a float: 1.005 s,
1004 ms).

ffmpeg converts the SRT into the track (``attach.py``): its subrip decoder reads it into ASS,
and the track's encoder -- SubRip again in Matroska, mov_text in MP4, WebVTT in WebM -- writes
that text raw but for its ``\N``, ``\n`` and ``{\...}`` (``ass_split.c``). So each text is
written for its codec (``_WRITTEN``), the track holding it exactly. A word joiner (U+2060: zero
width, skipped by libass) breaks what a reader would read: after a backslash (libass's ``\N``
``\n`` ``\h`` ``\{`` ``\}``, the encoders' ``\N`` ``\n``), after a ``{`` (the decoder drops
``{\...}`` and ``{y:...}``; the encoders read an unclosed ``{\`` to the text's end -- SubRip's
and WebVTT's, its style on into the next cue), after a ``<`` (the decoder's tags,
``htmlsubtitles.c``); and first in a text holding ``-->``, which the demuxer might read as a
timing line.
"""

import math
from collections.abc import Callable
from fractions import Fraction
from typing import Final

from subverter.transcript import Chunk

_WJ: Final = "\u2060"  # a word joiner
_JOINED: Final = {"\\": "\\" + _WJ, "{": "{" + _WJ, "<": "<" + _WJ}
# MP4's mov_text, stored as written (no escape in it); SubRip's text past its last "}"
_JOINS: Final = str.maketrans(_JOINED)
# Matroska's SubRip, read again by ffmpeg and libass: a "{" with a "}" after it a block to
# libass, so its \{ (``unescaped``); VLC shows that backslash
_BRACED: Final = str.maketrans({**_JOINED, "{": "\\{" + _WJ})
# WebM's WebVTT: the W3C's references for & < > (ffmpeg's webvtt encoder escapes nothing)
_WEBVTT: Final = str.maketrans({**_JOINED, "&": "&amp;", "<": "&lt;", ">": "&gt;"})


def _subrip(text: str) -> str:
    cut = text.rfind("}") + 1  # each "{" before it has a "}" after it
    return text[:cut].translate(_BRACED) + text[cut:].translate(_JOINS)


_WRITTEN: Final[dict[str, Callable[[str], str]]] = {
    "srt": _subrip,
    "mov_text": lambda text: text.translate(_JOINS),
    "webvtt": lambda text: text.translate(_WEBVTT),
}


def srt(chunks: tuple[Chunk, ...], until: Fraction | None, *, codec: str) -> str:
    """The chunks as SRT for a ``codec`` track, none past ``until`` (the duration, s, if known)."""
    clip = math.floor(until * 1000) if until is not None else 0
    written = _WRITTEN[codec]
    cues: list[str] = []
    for chunk in chunks:
        if clip > 0 and chunk.start >= clip:
            continue
        end = clip if clip > 0 and chunk.end > clip else chunk.end
        text = written(chunk.text)
        text = _WJ + text if "-->" in text else text
        cues.append(f"{len(cues) + 1}\n{_time(chunk.start)} --> {_time(end)}\n{text}\n\n")
    return "".join(cues)


def _time(ms: int) -> str:
    hours, minutes, seconds = ms // 3600000, ms % 3600000 // 60000, ms % 60000 // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms % 1000:03d}"
