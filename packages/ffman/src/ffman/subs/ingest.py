"""Transcripts in, chunks and words out: the bash ffman's ingest_subs, stage by stage.

The format's reader (``readers``) gives cues; the normalisers (``normalize``)
make them chunks and, where the source times words, words. ASS and SSA pass
through: burned and attached as they are, from ffman's copy -- UTF-8, each NUL
in it U+FFFD (``passed``) -- if both ffmpeg's reader and libass take it (``_script``).
"""

import codecs
import re
from collections.abc import Sequence
from typing import Final, NamedTuple

from subverter import readers
from subverter.markup import unclosed
from subverter.readers.utf8 import Nuls, nul_notes, utf16
from subverter.transcript import Transcript

from ffman.errors import refuse, shown
from ffman.media.paths import ext_of
from ffman.subs import markup, normalize

# the formats ffman parses none of: burned and attached as they are, from its copy (``passed``)
PASSED_THROUGH: Final = ("ass", "ssa")
_LINE_END: Final = re.compile(rb"\r\n|\r|\n")  # an editor's: the line a note or refusal names
_SIGNATURE: Final = b"[Script Info]"  # ffmpeg's ``ass_probe``: its 13 bytes, after blank lines
# libass's ``process_text`` and ``process_line``: a line, its BOMs and then spaces skipped
_LIBASS_LINE: Final = re.compile(rb"(?:\xef\xbb\xbf)*[ \t]*([^\r\n]*)")
_INFO: Final = _SIGNATURE.lower()  # libass's sections, by any case (``ass_strncasecmp``)
_STYLES: Final = (b"[v4+ styles]", b"[v4 styles]")  # each a type
_SECTIONS: Final = (_INFO, *_STYLES, b"[events]", b"[fonts]")  # any other leaves the last one
_SCRIPT_TYPE: Final = re.compile(rb"ScriptType:.*4\.00\+?[ \t]*")  # ``parse_script_type``


class Passed(NamedTuple):
    """An ASS's or SSA's bytes as ffmpeg is given them; their notes."""

    data: bytes
    notes: tuple[str, ...]


def passed(data: bytes, name: str) -> Passed:
    """The copy of ``data`` ffmpeg is given: UTF-8 (``_utf8``), each NUL U+FFFD, noted.

    Kept, a NUL ends libass's script -- burned, every later event lost -- and ffmpeg's ASS
    reader cuts its line there, the rest a header line (measured, libass 0.17.1 and ffmpeg
    8.1.2): U+FFFD, as in the transcripts ffman reads (``utf8.nul_notes``). A UTF-16 file
    (its BOM) is recoded first, so its U+0000s are NULs then.
    """
    data = _utf8(data, name)
    first = data.find(b"\0")
    if first < 0:
        return Passed(data, ())
    nuls = Nuls(data.count(b"\0"), f"line {_line(data, first)}")
    return Passed(data.replace(b"\0", "\ufffd".encode()), nul_notes(nuls))


def _utf8(data: bytes, name: str) -> bytes:
    """``data`` as UTF-8: a UTF-16 file (its BOM) recoded, as ffmpeg's reader recodes it.

    Refused at the line where it is neither, as subverter refuses a transcript not UTF-8:
    ``not UTF-8: NAME (line N)``, or ``not UTF-16`` (``utf16``). ffmpeg's ``ass`` filter gives
    libass no codepage, which then reads a byte not UTF-8 as its Latin-1 character
    (``ass_utf8_get_char``: CP1252's quotes become controls) and a UTF-16 script up to its
    first NUL byte -- no track, the burn failed; ffmpeg's decoder drops an event not UTF-8
    from the attached track, and its reader takes a unit not UTF-16 for a NUL
    (``ff_text_r8``) -- each measured.
    """
    text = utf16(data, name, lambda whole: _line(read := whole.encode(), len(read)))
    if text is not None:
        return text.encode()
    try:
        _ = data.decode()
    except UnicodeDecodeError as e:  # its start a character's: what is before it is whole
        refuse(f"not UTF-8: {name} (line {_line(data, e.start)})")
    return data  # UTF-8 already: no second copy


def _line(data: bytes, at: int) -> int:
    """The line offset ``at`` is on, from 1, as an editor counts them."""
    return len(_LINE_END.findall(data, 0, at)) + 1


def _script(data: bytes, fmt: str, name: str) -> None:
    """Refused unless ``data`` is a script both ffmpeg's reader and libass take.

    ffmpeg's reader (``ass_probe``) wants ``[Script Info]`` first, after a UTF-8 BOM and blank
    lines -- else no reader, or the LRC one, taking a ``[`` first: an empty track, unnoted
    (measured); libass a type, a styles section or ``[Script Info]``'s ``ScriptType`` of
    ``4.00+`` or ``4.00`` -- else no track, the burn failed (measured).
    """
    kind = "an SSA" if fmt == "ssa" else "an ASS"
    if not data.removeprefix(codecs.BOM_UTF8).lstrip(b"\r\n").startswith(_SIGNATURE):
        refuse(f"not {kind} file: {name} (its first line is not [Script Info])")
    info = False
    for found in _LIBASS_LINE.finditer(data):
        line = found[1]
        section = line[: len(_INFO)].lower()  # as long as the longest section's name
        if section.startswith(_STYLES):
            return
        if section.startswith(_SECTIONS):
            info = section.startswith(_INFO)
        elif info and _SCRIPT_TYPE.fullmatch(line):
            return
    why = "no [V4+ Styles] or [V4 Styles] section, nor ScriptType v4.00+ or v4.00"
    refuse(f"not {kind} file: {name} ({why})")


def _first(texts: Sequence[str]) -> str:
    """A note's first text, quoted."""
    return f"the first, {shown(texts[0])}"


def ingest(name: str, data: bytes) -> Transcript:
    """A transcript from its bytes, as bash's ingest_subs read it: its refusals, its notes."""
    fmt = ext_of(name)
    if fmt in PASSED_THROUGH:
        copy, notes = passed(data, name)
        _script(copy, fmt, name)
        return Transcript(fmt, f".{fmt}", has_words=False, chunks=(), words=(), notes=notes)
    found = readers.read(fmt, data, name)
    references, escapes = found.has_references, found.has_ass_escapes
    chunks, reversed_, same_start = normalize.cues(
        found.cues, references=references, escapes=escapes
    )
    if not chunks:
        refuse(f"no timed text found in: {name}")
    notes = list(found.notes)
    if reversed_:
        notes.append(
            f"{len(reversed_)} cues dropped: ending before they begin, {_first(reversed_)}"
        )
    if same_start:
        how = "beginning with the next, one cue shown at a time"
        notes.append(f"{len(same_start)} cues dropped: {how}, {_first(same_start)}")
    if escapes and (runs := [run for cue in found.cues for run in markup.hidden(cue.text)]):
        how = "ASS's override blocks, as ffmpeg and mpv hide them"
        notes.append(f"{len(runs)} braced runs hidden, {how}: {_first(runs)}")
    if references and (cut := [rest for cue in found.cues if (rest := unclosed(cue.text))]):
        what = f"{len(cut)} texts cut at a < with no > after it, a tag to their end (W3C)"
        notes.append(f"{what}: the first, {shown(cut[0].rstrip())}")
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
