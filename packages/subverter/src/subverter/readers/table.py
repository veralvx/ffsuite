"""CSV and TSV, as whisper-cli and WhisperX write them: start, end, text (ms), columns by header.

A header is a first record naming start and end, in any order (bash: one starting with
start); without one, the columns are start, end, text. A blank line is no record, so a header
after one is the first (pandas' ``skip_blank_lines``). A record short of a column reads it
empty, as awk's ``$n`` past the last field: its text "", its time none.

UTF-8, or UTF-16 by its BOM (``bom_text``), as a SubRip and an LRC are read: no whisper tool
writes UTF-16, but a spreadsheet may (Excel's "Unicode Text": UTF-16 LE, a BOM first); a unit
not UTF-16 refused by its line, counted as csv splits them.
"""

import csv
import io
import re
from typing import Final

from subverter._errors import refuse
from subverter.readers.fields import time_ms
from subverter.readers.utf8 import bom_text, by_line, nul_notes
from subverter.transcript import Cue, Reading

__all__ = ["read"]

_LINE_END: Final = re.compile(r"\r\n|\r|\n")  # csv's: each one a line's end


def read(kind: str, data: bytes, name: str) -> Reading:
    """A ``csv`` or ``tsv`` file's cues (``_rows``); a field past csv's limit refused by name."""
    text = bom_text(data, name, lambda whole: len(_LINE_END.split(whole)))
    try:
        cues, notes = _rows(kind, text, name)
    except csv.Error as error:  # a field past csv's limit (128 KiB): no subtitle's text
        refuse(f"unreadable .{kind}: {name}: {error}")
    return Reading(f".{kind}", has_words=False, cues=tuple(cues), notes=notes)


def _rows(kind: str, text: str, name: str) -> tuple[list[Cue], tuple[str, ...]]:
    """whisper-cli .csv (RFC 4180 quoting) or WhisperX .tsv (tabs, none); a time read, or none.

    Each character joined across the texts it spans (``utf8.by_line``: what is still not
    UTF-8, refused by the line its record starts on); its notes (``utf8.nul_notes``).
    """
    lines = io.StringIO(text, newline="")
    records = (
        csv.reader(lines, delimiter="\t", quoting=csv.QUOTE_NONE)
        if kind == "tsv"
        else csv.reader(lines)
    )
    si, ei, ti = 1, 2, 3
    found: list[tuple[int, str, str, str]] = []  # each record's first line, start, end, text
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
            continue
        found.append((line, _field(fields, si), _field(fields, ei), _field(fields, ti)))
    whole = by_line([(at, cell) for at, *_, cell in found], name)
    cues = [
        Cue(time_ms(a, 1), time_ms(z, 1), t)
        for (_, a, z, _), t in zip(found, whole.texts, strict=True)
    ]
    return cues, nul_notes(whole.nuls)


def _field(fields: list[str], column: int) -> str:
    """The record's ``column`` (from 1); one past its last field empty."""
    return fields[column - 1] if column <= len(fields) else ""
