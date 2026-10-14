"""A transcript's markup: what its tags, override blocks and escapes leave of its text."""

import re
from enum import Enum, auto
from typing import Final

from subverter.markup import decoded, drawn, unstamped, untagged
from subverter.transcript import Reading

_BREAK: Final = re.compile(r"[\t\n\r]")  # a plain text's tab or line break; an LRC's lines joined
_SUBRIP_BREAK: Final = re.compile(r"[\t\n]")  # a tab, libass's space; a break (\N, <br>)
_VTT_BREAK: Final = re.compile(r"[\t\n\f\r]")  # a .vtt's tab, break or FF, written or decoded
_BLANKS: Final = re.compile(r"[ \t]+")
_TAG_MARK: Final = "\uffff"  # where a tag was: a noncharacter (a transcript's own, dropped)


class Markup(Enum):
    """How a format's texts mark up -- its reading's flags, one value (``of``) -- for ``clean``."""

    PLAIN = auto()  # CSV's, TSV's, JSON's: no flag
    WEBVTT = auto()  # ``Reading.has_references``
    SUBRIP = auto()  # ``Reading.has_ass_escapes``
    LRC = auto()  # ``Reading.has_word_stamps``

    @classmethod
    def of(cls, found: Reading) -> "Markup":
        """The markup of ``found``'s texts, by its flags (one at most set)."""
        if found.has_references:
            return cls.WEBVTT
        if found.has_ass_escapes:
            return cls.SUBRIP
        return cls.LRC if found.has_word_stamps else cls.PLAIN


def clean(text: str, markup: Markup) -> str:
    r"""``text`` as its format's readers show it, breaks spaces, blanks squeezed, trimmed.

    ``PLAIN``, CSV's, TSV's and JSON's: as their writers write it -- whisper-cli, OpenAI whisper and
    WhisperX mark no text up -- a tab or line break a space. ``WEBVTT``: no override, no escape --
    a ``{\...}`` and a typed ``\n`` or ``\t`` text, as every reader shows them -- a tag no ``>``
    closes run to the text's end (``untagged``), and each run between tags decoded, a decoded ``<``
    or ``{`` text, a break, written or decoded, a space. ``SUBRIP``: the text as ffmpeg and libass
    read it (``drawn``) -- its tags as ffmpeg's decoder reads them, a ``<br>`` a line break; every
    block off, ``{text}`` too, as ffmpeg and mpv hide it; ``\N`` a line break, so a space, ffman
    wrapping; ``\n`` a space, ``\h`` a no-break space; ``\t`` text, as libass draws it. ``LRC``:
    plain but for its word stamps, off (``unstamped``).
    """
    match markup:
        case Markup.WEBVTT:
            runs = untagged(text, into=_TAG_MARK, webvtt=True).split(_TAG_MARK)
            text = _VTT_BREAK.sub(" ", "".join(decoded(run) for run in runs))
        case Markup.SUBRIP:
            text = _SUBRIP_BREAK.sub(" ", drawn(text).text)
        case Markup.LRC:  # a line break: lines sharing a stamp, one cue (``readers.lrc``)
            text = _BREAK.sub(" ", unstamped(text))
        case _:  # Markup.PLAIN: a case of its own left a branch no member takes
            text = _BREAK.sub(" ", text)
    return _BLANKS.sub(" ", text).removeprefix(" ").removesuffix(" ")


def hidden(text: str) -> list[str]:
    r"""A SubRip text's blocks libass hides that hold text (``drawn``), each as libass reads it.

    A block's text is what comes before its first tag (``{note\i1}``: ``note``); a block of
    tags alone (``{\an8}``) or an empty one holds none.
    """
    return [f"{{{b}}}" for b in drawn(text).blocks if b.split("\\", 1)[0].strip()]
