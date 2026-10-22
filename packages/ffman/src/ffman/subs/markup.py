"""A transcript's markup: what its tags, override blocks and escapes leave of its text."""

import re
from enum import Enum, auto
from typing import Final

from subverter.markup import decoded, drawn, unstamped, untagged
from subverter.transcript import Reading

from ffman.subs.breaks import joined

# each format's blanks made spaces, its CRs line breaks (a SubRip's lines split at them already)
_PLAIN: Final = str.maketrans({"\t": " ", "\r": "\n"})  # an LRC's too: lines sharing a stamp
_SUBRIP: Final = str.maketrans({"\t": " "})  # a tab, libass's space
_VTT: Final = str.maketrans({"\t": " ", "\f": " ", "\r": "\n"})  # written or decoded
# a line break, the blanks around it, the lines after: from a run's first blank (linear, not each)
_LINE: Final = re.compile(r"(?<! ) *\n[ \n]*")
_BLANKS: Final = re.compile(" +")  # a tab a space already
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
    r"""``text`` as its format's readers show it, on one line: blanks squeezed, trimmed.

    A line break, the blanks around it, is a space, or nothing where ``breaks.joined`` says so:
    between two CJK characters, as a writer wraps a script without spaces.

    ``PLAIN``, CSV's, TSV's and JSON's: as their writers write it -- whisper-cli, OpenAI whisper,
    WhisperX and ffmpeg's whisper filter mark no text up -- a tab a space, a CR a line break.
    ``WEBVTT``: no override, no escape -- a ``{\...}`` and a typed ``\n`` or ``\t`` text, as every
    reader shows them -- a tag no ``>`` closes run to the text's end (``untagged``), and each run
    between tags decoded, a decoded ``<`` or ``{`` text, a CR, written or decoded, a line break.
    ``SUBRIP``: the text as ffmpeg and libass read it (``drawn``) -- its tags as ffmpeg's decoder
    reads them, a ``<br>`` a line break; every block off, ``{text}`` too, as ffmpeg and mpv hide
    it; ``\N`` a line break, ffman wrapping; ``\n`` a space, ``\h`` a no-break space;
    ``\t`` text, as libass draws it. ``LRC``: plain but for its word stamps, off (``unstamped``).
    """
    match markup:
        case Markup.WEBVTT:
            runs = untagged(text, into=_TAG_MARK, webvtt=True).split(_TAG_MARK)
            text = "".join(decoded(run) for run in runs).translate(_VTT)
        case Markup.SUBRIP:
            text = drawn(text).text.translate(_SUBRIP)
        case Markup.LRC:  # a line break: lines sharing a stamp, one cue (``readers.lrc``)
            text = unstamped(text).translate(_PLAIN)
        case _:  # Markup.PLAIN: a case of its own left a branch no member takes
            text = text.translate(_PLAIN)
    text = _LINE.sub(lambda m: "" if joined(m.string, m.start(), m.end()) else " ", text)
    return _BLANKS.sub(" ", text).removeprefix(" ").removesuffix(" ")


def hidden(text: str) -> list[str]:
    r"""A SubRip text's blocks libass hides that hold text (``drawn``), each as libass reads it.

    A block's text is what comes before its first tag (``{note\i1}``: ``note``); a block of
    tags alone (``{\an8}``) or an empty one holds none.
    """
    return [f"{{{b}}}" for b in drawn(text).blocks if b.split("\\", 1)[0].strip()]
