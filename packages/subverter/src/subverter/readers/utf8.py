"""Texts read where their file is not UTF-8: each character joined across the texts it spans.

whisper-cli writes each token's bytes as they are (``whisper_token_to_str``): a character
whisper's vocabulary lacks spans tokens -- 1,476 of its 50,257 are not UTF-8 alone -- and,
with ``-ml``, which splits a segment between tokens (``whisper_wrap_segment``), segments: its
JSON's texts and its SubRip, WebVTT, LRC and CSV cues. So each character is joined across the
texts it spans and given to the one it starts in; what is still not UTF-8 is refused where it
is: ``not UTF-8: NAME (WHERE)`` -- a text file's by its line (``by_line``).

A NUL in a text is read as U+FFFD, as the W3C's WebVTT parser reads one, and noted
(``nul_notes``): kept, it would end libass's script and ffmpeg's SubRip reading there, every
later cue lost (measured, libass 0.17.1 and ffmpeg 8.1.2).
"""

import codecs
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final, Literal, NamedTuple

from subverter._errors import refuse

__all__ = [
    "UTF16_BOMS",
    "Errors",
    "Joined",
    "Nuls",
    "Source",
    "by_line",
    "file_text",
    "joined",
    "nul_notes",
]

UTF16_BOMS: Final = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)  # a UTF-16 file's, each order

# how a file's strings give back their bytes: as UTF-8, or each surrogate U+DC80-DCFF its byte
type Errors = Literal["strict", "surrogateescape"]


@dataclass(frozen=True, slots=True)
class Source:
    """The file read: its name, for messages; how its strings give back their bytes."""

    name: str
    errors: Errors


class Nuls(NamedTuple):
    """The NULs read as U+FFFD: how many; where the first was."""

    total: int
    first: str | None


class Joined(NamedTuple):
    """The texts, each character whole, each NUL U+FFFD; their NULs."""

    texts: list[str]
    nuls: Nuls


def joined(texts: Sequence[str], source: Source, where: Callable[[int], str]) -> Joined:
    """``texts`` as UTF-8, each character joined across the texts it spans, in the one it starts.

    Refused at ``where``: a byte no character takes, a character the texts end inside, a lone
    surrogate (a JSON escape) -- but in a file not UTF-8, an escaped U+DC80-DCFF reads as the
    byte ``surrogateescape`` keeps so: the two are one string.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    found: list[str] = []
    total, first = 0, None  # the NULs
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
        if n := whole.count("\0"):  # a character alone, never a byte of a multibyte one
            total, first = total + n, first or where(k)
            whole = whole.replace("\0", "\ufffd")
        if started is not None and whole:  # its first character, the one started before
            found[started] += whole[0]
            whole, started = whole[1:], None
        found.append(whole)
        if started is None and decoder.getstate()[0]:
            started = k
    if started is not None:
        refuse(f"not UTF-8: {source.name} ({where(started)})")
    return Joined(found, Nuls(total, first))


def by_line(texts: Sequence[tuple[int, str]], name: str) -> Joined:
    """``joined`` on a text file's texts, each with its line (from 1): refused by ``line N``.

    The file read as ``file_text`` reads it: each byte no character takes a surrogate.
    """
    source = Source(name, "surrogateescape")
    return joined([text for _, text in texts], source, lambda k: f"line {texts[k][0]}")


def file_text(data: bytes) -> str:
    """A text file's bytes as UTF-8, a BOM off; each byte no character takes kept as a surrogate.

    Its reader joins a character split across its texts (``joined``), as whisper-cli's ``-ml``
    writes one, and refuses what still is not UTF-8 by its line (``by_line``).
    """
    return data.decode("utf-8", "surrogateescape").removeprefix("\ufeff")


def nul_notes(*nuls: Nuls) -> tuple[str, ...]:
    """A reading's NULs (``Joined.nuls``, in order), read as U+FFFD: counted, the first named."""
    total = sum(n.total for n in nuls)
    first = next((n.first for n in nuls if n.first is not None), None)
    if not total:
        return ()
    return (f"{total} NULs read as U+FFFD, as the W3C reads them: the first in {first}",)
