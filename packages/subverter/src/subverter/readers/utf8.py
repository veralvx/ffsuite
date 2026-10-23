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
    "bom_text",
    "by_line",
    "file_text",
    "joined",
    "nul_notes",
    "utf16",
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
    """The NULs read as U+FFFD: how many; where the first was, and its place in the file."""

    total: int
    first: str | None
    at: tuple[int, ...] = ()  # ordered as the file: the first of several readings' (`nul_notes`)


class Joined(NamedTuple):
    """The texts, each character whole, each NUL U+FFFD; their NULs."""

    texts: list[str]
    nuls: Nuls


def joined(
    texts: Sequence[str],
    source: Source,
    where: Callable[[int], str],
    place: Callable[[int], tuple[int, ...]] = lambda k: (k,),
) -> Joined:
    """``texts`` as UTF-8, each character joined across the texts it spans, in the one it starts.

    Its first NUL ``where`` and at ``place`` in the file. Refused at ``where``: a byte no character
    takes, a character the texts end inside, a lone
    surrogate (a JSON escape) -- but in a file not UTF-8, an escaped U+DC80-DCFF reads as the
    byte ``surrogateescape`` keeps so: the two are one string.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    found: list[str] = []
    total, first, at = 0, None, ()  # the NULs
    started: int | None = None  # the text an unfinished character starts in
    for k, text in enumerate(texts):
        pending = len(decoder.getstate()[0])  # the unfinished character's bytes, in ``started``
        try:
            whole = decoder.decode(text.encode("utf-8", source.errors))
        except UnicodeEncodeError:  # a lone surrogate
            refuse(f"not UTF-8: {source.name} ({where(k)})")
        except UnicodeDecodeError as e:  # a byte no character takes: in ``started``'s, or here
            bad = k if started is None or e.start >= pending else started
            refuse(f"not UTF-8: {source.name} ({where(bad)})")
        if n := whole.count("\0"):  # a character alone, never a byte of a multibyte one
            if first is None:
                first, at = where(k), place(k)
            total += n
            whole = whole.replace("\0", "\ufffd")
        if started is not None and whole:  # its first character, the one started before
            found[started] += whole[0]
            whole, started = whole[1:], None
        found.append(whole)
        if started is None and decoder.getstate()[0]:
            started = k
    if started is not None:
        refuse(f"not UTF-8: {source.name} ({where(started)})")
    return Joined(found, Nuls(total, first, at))


def apart(
    texts: Sequence[str],
    source: Source,
    where: Callable[[int], str],
    place: Callable[[int], tuple[int, ...]],
) -> Joined:
    """``joined`` on each text alone: no character joined across them (a speaker's)."""

    def one(k: int, text: str) -> Joined:
        return joined([text], source, lambda _: where(k), lambda _: place(k))

    each = [one(k, t) for k, t in enumerate(texts)]
    found = [j.nuls for j in each if j.nuls.first is not None]
    first = min(found, key=lambda n: n.at, default=Nuls(0, None))
    return Joined(
        [j.texts[0] for j in each], Nuls(sum(n.total for n in found), first.first, first.at)
    )


def by_line(texts: Sequence[tuple[int, str]], name: str, *, alone: bool = False) -> Joined:
    """``joined`` on a text file's texts, each with its line (from 1): refused by ``line N``.

    The file read as ``file_text`` reads it: each byte no character takes a surrogate. Its first
    NUL placed at its line; ``alone``: each text read alone (``apart``).
    """
    source = Source(name, "surrogateescape")
    read = apart if alone else joined
    return read(
        [text for _, text in texts],
        source,
        lambda k: f"line {texts[k][0]}",
        lambda k: (texts[k][0],),
    )


def file_text(data: bytes) -> str:
    """A text file's bytes as UTF-8, a BOM off; each byte no character takes kept as a surrogate.

    Its reader joins a character split across its texts (``joined``), as whisper-cli's ``-ml``
    writes one, and refuses what still is not UTF-8 by its line (``by_line``).
    """
    return data.decode("utf-8", "surrogateescape").removeprefix("\ufeff")


def utf16(data: bytes, name: str, lines: Callable[[str], int]) -> str | None:
    """A file's text by its UTF-16 BOM, either order, as ffmpeg's reader recodes it; else None.

    ffmpeg's ``ff_text_init_avio``, its SubRip's and ASS's alike; an LRC's as Navidrome and Jellyfin
    read it (ffmpeg's LRC reader reads bytes); a CSV's and a TSV's as a spreadsheet may write one
    (ffmpeg reads neither). A unit not UTF-16 -- a lone surrogate, an odd last byte -- refused by
    its line: ``lines``, how many its format's reader counts in a text. ffmpeg's reader takes the
    one for a NUL (``ff_text_r8``), what follows its format reader's, and the other for a character.
    """
    if not data.startswith(UTF16_BOMS):
        return None
    try:
        return data.decode("utf-16")  # its BOM read, then off
    except UnicodeDecodeError as error:  # at a unit's start: what is before it is whole
        whole = data[: error.start].decode("utf-16")
        refuse(f"not UTF-16: {name} (line {lines(whole)})")


def bom_text(data: bytes, name: str, lines: Callable[[str], int]) -> str:
    """A text file's text: UTF-16 by its BOM (``utf16``, ``lines`` counting), else UTF-8."""
    text = utf16(data, name, lines)
    return file_text(data) if text is None else text


def nul_notes(*nuls: Nuls) -> tuple[str, ...]:
    """A reading's NULs (``Joined.nuls``), read as U+FFFD: counted, the first in the file named.

    The first by place (``Nuls.at``); of places alike, or none, the first given.
    """
    total = sum(n.total for n in nuls)
    if not total:
        return ()
    first = min((n for n in nuls if n.first is not None), key=lambda n: n.at).first  # the file's
    return (f"{total} NULs read as U+FFFD, as the W3C reads them: the first in {first}",)
