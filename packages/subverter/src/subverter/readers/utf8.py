"""Texts read where their file is not UTF-8: each character joined across the texts it spans.

whisper-cli writes each token's bytes as they are (``whisper_token_to_str``): a character
whisper's vocabulary lacks spans tokens -- 1,476 of its 50,257 are not UTF-8 alone -- and,
with ``-ml``, which splits a segment between tokens (``whisper_wrap_segment``), segments: its
JSON's texts and its SubRip, WebVTT, LRC and CSV cues. So each character is joined across the
texts it spans and given to the one it starts in; what is still not UTF-8 is refused where it
is: ``not UTF-8: NAME (WHERE)`` -- a text file's by its line (``by_line``).
"""

import codecs
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from subverter._errors import refuse

__all__ = ["Errors", "Source", "by_line", "joined"]

# how a file's strings give back their bytes: as UTF-8, or each surrogate U+DC80-DCFF its byte
type Errors = Literal["strict", "surrogateescape"]


@dataclass(frozen=True, slots=True)
class Source:
    """The file read: its name, for messages; how its strings give back their bytes."""

    name: str
    errors: Errors


def joined(texts: Sequence[str], source: Source, where: Callable[[int], str]) -> list[str]:
    """``texts`` as UTF-8, each character joined across the texts it spans, in the one it starts.

    Refused at ``where``: a byte no character takes, a character the texts end inside, a lone
    surrogate (a JSON escape) -- but in a file not UTF-8, an escaped U+DC80-DCFF reads as the
    byte ``surrogateescape`` keeps so: the two are one string.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    found: list[str] = []
    started: int | None = None  # the text an unfinished character starts in
    for k, text in enumerate(texts):
        pending = len(decoder.getstate()[0])  # the unfinished character's bytes, in ``started``
        try:
            whole = decoder.decode(text.encode("utf-8", source.errors))
        except UnicodeEncodeError:  # a lone surrogate
            refuse(f"not UTF-8: {source.name} ({where(k)})")
        except UnicodeDecodeError as e:  # a byte no character takes: in ``started``'s, or here
            at = k if started is None or e.start >= pending else started
            refuse(f"not UTF-8: {source.name} ({where(at)})")
        if started is not None and whole:  # its first character, the one started before
            found[started] += whole[0]
            whole, started = whole[1:], None
        found.append(whole)
        if started is None and decoder.getstate()[0]:
            started = k
    if started is not None:
        refuse(f"not UTF-8: {source.name} ({where(started)})")
    return found


def by_line(texts: Sequence[tuple[int, str]], name: str) -> list[str]:
    """``joined`` on a text file's texts, each with its line (from 1): refused by ``line N``.

    The file read as ``readers._text`` reads it: each byte no character takes a surrogate.
    """
    source = Source(name, "surrogateescape")
    return joined([text for _, text in texts], source, lambda k: f"line {texts[k][0]}")
