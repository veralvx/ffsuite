"""A transcript's markup: what its tags, override blocks and escapes leave of its text."""

import re
from typing import Final

from subverter.markup import decoded, unescaped, untagged

_OVERRIDE: Final = re.compile(r"\{\\[^}]*\}")  # {\an8}: ASS's, off in LRC, CSV, TSV, JSON (bash's)
# LRC's, CSV's, TSV's and JSON's tab or line break, typed (\t, \n) or not (bash's)
_BREAK: Final = re.compile(r"\\[tn]|[\t\n\r]")
_SUBRIP_BREAK: Final = re.compile(r"[\t\n\r]")  # a tab or a line break, as libass reads them
_VTT_BREAK: Final = re.compile(r"[\t\n\f\r]")  # a .vtt's tab, break or FF, written or decoded
_BLANKS: Final = re.compile(r"[ \t]+")
_TAG_MARK: Final = "\uffff"  # where a tag was: a noncharacter (a transcript's own, dropped)


def clean(text: str, *, references: bool, escapes: bool) -> str:
    r"""Bash's CLEAN_AWK: tags and overrides off, breaks to spaces, blanks squeezed, trimmed.

    Overrides first: one opening with an escape (``{\t(...)}``) is dropped whole, as ffmpeg's
    subrip decoder and VLC drop it -- bash broke it first, showing it. ``references``
    (WebVTT's): no override, no escape -- a ``{\...}`` and a typed ``\n`` or ``\t`` text, as
    every reader shows them -- a tag no ``>`` closes run to the text's end (``untagged``), and
    each run between tags decoded, a decoded ``<`` or ``{`` text, a break, written or decoded, a
    space. ``escapes`` (SubRip's, never with references): the text as ffmpeg and libass read it
    (``unescaped``) -- its tags as ffmpeg's decoder reads them, a ``<br>`` a line break; every
    block off, ``{text}`` too, as ffmpeg and mpv hide it; ``\N`` a line break, so a space,
    ffman wrapping; ``\n`` a space, ``\h`` a no-break space; ``\t`` text, as libass draws it.
    """
    if references:
        runs = untagged(text, into=_TAG_MARK, webvtt=True).split(_TAG_MARK)
        text = _VTT_BREAK.sub(" ", "".join(decoded(run) for run in runs))
    elif escapes:
        text = _SUBRIP_BREAK.sub(" ", unescaped(text).text)
    else:
        text = _BREAK.sub(" ", _overrides_off(untagged(text)))
    return _BLANKS.sub(" ", text).removeprefix(" ").removesuffix(" ")


def _overrides_off(text: str) -> str:
    r"""``text`` without its ``{\...}`` overrides (``_OVERRIDE``), none sought past its last ``}``.

    Past it none closes: sought from each ``{\`` there, the steps are the square of their count.
    """
    end = text.rfind("}") + 1
    return _OVERRIDE.sub("", text[:end]) + text[end:]


def hidden(text: str) -> list[str]:
    r"""A SubRip text's blocks libass hides that hold text (``unescaped``), each as libass reads it.

    A block's text is what comes before its first tag (``{note\i1}``: ``note``); a block of
    tags alone (``{\an8}``) or an empty one holds none.
    """
    return [f"{{{b}}}" for b in unescaped(text).blocks if b.split("\\", 1)[0].strip()]
