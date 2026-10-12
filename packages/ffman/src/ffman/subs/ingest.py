"""Transcripts in, chunks and words out: the bash ffman's ingest_subs, stage by stage.

The format's reader (``readers``) gives cues; the normalisers (``normalize``)
make them chunks and, where the source times words, words. ASS and SSA pass
through: burned and attached as they are, from ffman's copy, each NUL in it
U+FFFD (``passed``).
"""

import codecs
import re
from typing import Final, NamedTuple

from subverter import readers
from subverter.readers.utf8 import Nuls, nul_notes
from subverter.transcript import Transcript

from ffman.errors import refuse
from ffman.media.paths import ext_of
from ffman.subs import markup, normalize

# the formats ffman reads none of: burned and attached as they are, from its copy (``passed``)
PASSED_THROUGH: Final = ("ass", "ssa")
_UTF16: Final = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)
_LINE_END: Final = re.compile(rb"\r\n|\r|\n")  # an editor's: the note's line


class Passed(NamedTuple):
    """An ASS's or SSA's bytes as ffmpeg is given them; their notes."""

    data: bytes
    notes: tuple[str, ...]


def passed(data: bytes) -> Passed:
    """``data``, each NUL U+FFFD, as in the transcripts ffman reads (``utf8.nul_notes``): noted.

    Kept, a NUL ends libass's script -- burned, every later event lost -- and ffmpeg's ASS
    reader cuts its line there, the rest a header line (measured, libass 0.17.1 and ffmpeg
    8.1.2). A UTF-16 file (its BOM) is left as it is: its NULs are its characters' bytes.
    """
    first = data.find(b"\0")
    if first < 0 or data.startswith(_UTF16):
        return Passed(data, ())
    nuls = Nuls(data.count(b"\0"), f"line {len(_LINE_END.findall(data, 0, first)) + 1}")
    return Passed(data.replace(b"\0", "\ufffd".encode()), nul_notes(nuls))


def ingest(name: str, data: bytes) -> Transcript:
    """A transcript from its bytes, as bash's ingest_subs read it: its refusals, its notes."""
    fmt = ext_of(name)
    if fmt in PASSED_THROUGH:
        notes = passed(data).notes
        return Transcript(fmt, f".{fmt}", has_words=False, chunks=(), words=(), notes=notes)
    found = readers.read(fmt, data, name)
    references, escapes = found.has_references, found.has_ass_escapes
    chunks = normalize.cues(found.cues, references=references, escapes=escapes)
    if not chunks:
        refuse(f"no timed text found in: {name}")
    notes = list(found.notes)
    if escapes and (runs := [run for cue in found.cues for run in markup.hidden(cue.text)]):
        how = "ASS's override blocks, as ffmpeg and mpv hide them"
        notes.append(f"{len(runs)} braced runs hidden, {how}: the first, {runs[0]}")
    if not found.has_words:
        return Transcript(fmt, found.source, found.has_words, chunks, (), tuple(notes))
    placed_words, placed, untimed = normalize.words(
        chunks, found.words, references=references, escapes=escapes
    )
    if placed:
        why = "(untimed, tied, out of order or outside their sentence)"
        notes.append(
            f"{placed} words had no usable time of their own {why}: placed between their neighbours"
        )
    if untimed:
        notes.append(f"{untimed} sentences had no word timings: shown without word highlighting")
    return Transcript(fmt, found.source, found.has_words, chunks, placed_words, tuple(notes))
