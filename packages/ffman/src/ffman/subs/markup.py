"""A transcript's markup: what its tags, override blocks and escapes leave of its text."""

import re
from typing import Final

from subverter.markup import decoded, unescaped, untagged

_OVERRIDE: Final = re.compile(r"\{\\[^}]*\}")  # {\an8}: ASS override blocks, as some SRTs carry
_BREAK: Final = re.compile(r"\\[tn]|[\t\n\r]")  # a tab or a line break, escaped (\t, \n) or not
_DECODED_BREAK: Final = re.compile(r"[\t\n\f\r]")  # decoded (&#10;, &#12;) or a .vtt's own FF
_BLANKS: Final = re.compile(r"[ \t]+")
_TAG_MARK: Final = "\uffff"  # where a tag was: a noncharacter (a transcript's own, dropped)
_MARKED_OVERRIDE: Final = re.compile(r"\{\uffff*\\[^}]*\}")  # _OVERRIDE, _TAG_MARKs in it


def clean(text: str, *, references: bool, escapes: bool) -> str:
    r"""Bash's CLEAN_AWK: tags and overrides off, breaks to spaces, blanks squeezed, trimmed.

    Overrides first: one opening with an escape (``{\t(...)}``) is dropped whole, as ffmpeg's
    subrip decoder and VLC drop it -- bash broke it first, showing it. ``references``
    (WebVTT's): each run between tags decoded, once the overrides are off -- a decoded ``<``
    or ``{`` text, a decoded break a space. ``escapes`` (SubRip's, never with references):
    the text as ffmpeg and libass read it (``unescaped``) -- every block off, ``{text}`` too, as
    ffmpeg and mpv hide it; ``\N`` a line break, so a space, ffman wrapping; ``\h`` a no-break
    space.
    """
    if references:
        text = _MARKED_OVERRIDE.sub("", untagged(text, into=_TAG_MARK))
    elif escapes:
        text = unescaped(untagged(text)).text
    else:
        text = _OVERRIDE.sub("", untagged(text))
    text = _BREAK.sub(" ", text)
    if references:
        runs = text.split(_TAG_MARK)
        text = _DECODED_BREAK.sub(" ", "".join(decoded(run) for run in runs))
    return _BLANKS.sub(" ", text).removeprefix(" ").removesuffix(" ")


def hidden(text: str) -> list[str]:
    r"""A SubRip text's blocks libass hides that hold text (``unescaped``), each as libass reads it.

    A block's text is what comes before its first tag (``{note\i1}``: ``note``); a block of
    tags alone (``{\an8}``) or an empty one holds none.
    """
    return [f"{{{b}}}" for b in unescaped(untagged(text)).blocks if b.split("\\", 1)[0].strip()]
