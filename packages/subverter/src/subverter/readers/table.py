"""CSV and TSV, as the whisper tools write them: start, end, text (ms), columns by header.

A header is a first record naming start and end, in any order (bash: one starting with
start); without one, the columns are start, end, text. A blank line is no record, so a header
after one is the first (pandas' ``skip_blank_lines``). A record short of a column reads it
empty, as awk's ``$n`` past the last field: its text "", its time none. In a TSV whose text is
its last column, a line of no tab after a record ending at its text is that record's text, a
line break in it, noted: OpenAI whisper's and WhisperX's ``WriteTSV`` write each record a line
of its columns, its text stripped, its tabs made spaces, its line breaks kept (``utils.py``),
and quote nothing.

UTF-8, or UTF-16 by its BOM (``bom_text``), as a SubRip and an LRC are read: no whisper tool
writes UTF-16, but a spreadsheet may (Excel's "Unicode Text": UTF-16 LE, a BOM first); a unit
not UTF-16 refused by its line, counted as csv splits them.
"""

import csv
import io
import re
from collections.abc import Sequence
from typing import Final

from subverter._errors import counted, refuse
from subverter.readers.fields import time_ms
from subverter.readers.utf8 import bom_text, by_line, nul_notes
from subverter.transcript import Cue, Reading

__all__ = ["read", "split_lines", "timed"]

_LINE_END: Final = re.compile(r"\r\n|\r|\n")  # csv's: each one a line's end


def read(kind: str, data: bytes, name: str) -> Reading:
    """A ``csv`` or ``tsv`` file's cues (``_rows``); a field past csv's limit refused by name."""
    text = bom_text(data, name, lambda whole: len(split_lines(whole)))
    try:
        cues, notes = _rows(kind, text, name)
    except csv.Error as error:  # a field past csv's limit (128 KiB): no subtitle's text
        refuse(f"unreadable .{kind}: {name}: {error}")
    return Reading(f".{kind}", has_words=False, cues=cues, notes=notes)


def split_lines(text: str) -> list[str]:
    """``text``'s lines, as csv ends them: at each CRLF, CR or LF."""
    return _LINE_END.split(text)


def timed(
    rows: Sequence[tuple[int, str, str, str]],
    name: str,
    speakers: Sequence[str] = (),
) -> tuple[tuple[Cue, ...], tuple[str, ...]]:
    """Rows of a line (from 1), a start and an end in ms, a text: their cues, their NULs' notes.

    Each character joined across the texts it spans (``utf8.by_line``: what is still not UTF-8,
    refused by its row's line); a time read, or none (``fields.time_ms``). Each of ``speakers``,
    whisper-cli's ``-di`` column, before its text as its SubRip writes it, ``(speaker 0)``
    (``cli.cpp``): its ``lead``, each read alone; none for an empty one, or a text of none (a cue
    dropped).
    """
    whole = by_line([(line, text) for line, *_, text in rows], name)
    said = speakers or [""] * len(rows)
    names = by_line(
        [
            (line, s if t.strip() else "")
            for (line, *_), s, t in zip(rows, said, whole.texts, strict=True)
        ],
        name,
        alone=True,
    )
    leads = [f"(speaker {n})" if n else "" for n in names.texts]
    cues = tuple(
        Cue(time_ms(a, 1), time_ms(z, 1), lead + t, "", lead)
        for (_, a, z, _), t, lead in zip(rows, whole.texts, leads, strict=True)
    )
    return cues, nul_notes(whole.nuls, names.nuls)


def _rows(kind: str, text: str, name: str) -> tuple[tuple[Cue, ...], tuple[str, ...]]:
    """whisper-cli's .csv (RFC 4180 quoting), OpenAI whisper's and WhisperX's .tsv (no quoting).

    Its cues and their NULs' notes (``timed``), its lines read into a record before noted
    (``_joined_notes``).
    """
    source = io.StringIO(text, newline="")
    records = (
        csv.reader(source, delimiter="\t", quoting=csv.QUOTE_NONE)
        if kind == "tsv"
        else csv.reader(source)
    )
    si, ei, ti, width = 1, 2, 3, 3
    pi = 0  # whisper-cli's -di speaker column, if the header names one: no TSV writer's
    # each record's first line, start, end, its text's lines, its speaker
    found: list[tuple[int, str, str, list[str], str]] = []
    joined: list[tuple[int, str]] = []  # each line of no tab read into the TSV record before
    at_text = False  # the last record ended at its text, the last column: as WriteTSV writes one
    before = 0  # the lines read before a record
    header_due = True  # the first record may be the header
    for fields in records:
        line, before = before + 1, records.line_num
        if not fields:  # a blank line is no record
            continue
        names = [f.lower() for f in fields] if header_due else []
        header_due = False
        if "start" in names and "end" in names:  # a header: its columns, any order (the last named)
            for i, column in enumerate(names, 1):
                si = i if column == "start" else si
                ei = i if column == "end" else ei
                ti = i if column == "text" else ti
                pi = i if column == "speaker" and kind == "csv" else pi
            width = len(names)
            continue
        if kind == "tsv" and len(fields) == 1 and at_text:  # its text, broken
            found[-1][3].append(fields[0])  # its lines joined once, at the end: linear
            joined.append((line, fields[0]))
            continue
        speaker = _field(fields, pi) if pi else ""
        found.append((line, _field(fields, si), _field(fields, ei), [_field(fields, ti)], speaker))
        at_text = len(fields) == ti == width
    rows = [(at, a, z, "\n".join(parts)) for at, a, z, parts, _ in found]
    cues, nuls = timed(rows, name, [s for *_, s in found])
    return cues, _joined_notes(joined) + nuls


def _joined_notes(joined: list[tuple[int, str]]) -> tuple[str, ...]:
    """The TSV lines read into the record before (``_rows``): counted, the first named."""
    how = "read as the text of the record before, a line break in it"
    return counted(joined, f"TSV lines of no tab {how} (OpenAI whisper's and WhisperX's TSV)")


def _field(fields: list[str], column: int) -> str:
    """The record's ``column`` (from 1); one past its last field empty."""
    return fields[column - 1] if column <= len(fields) else ""
