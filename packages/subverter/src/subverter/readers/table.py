"""CSV and TSV, as whisper-cli and WhisperX write them: start, end, text (ms), columns by header.

A header is a first record naming start and end, in any order (bash: one starting with
start); without one, the columns are start, end, text. A record short of a column reads it
empty, as awk's ``$n`` past the last field: its text "", its time none.
"""

import csv
import io

from subverter.readers.fields import time_ms
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue

__all__ = ["rows"]


def rows(kind: str, text: str, name: str) -> list[Cue]:
    """whisper-cli .csv (RFC 4180 quoting) or WhisperX .tsv (tabs, none); a time read, or none.

    Each character joined across the texts it spans (``utf8.by_line``: what is still not
    UTF-8, refused by the line its record starts on).
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
    for n, fields in enumerate(records):
        line, before = before + 1, records.line_num
        names = [f.lower() for f in fields] if n == 0 else []
        if "start" in names and "end" in names:  # a header: its columns, any order (the last named)
            for i, column in enumerate(names, 1):
                si = i if column == "start" else si
                ei = i if column == "end" else ei
                ti = i if column == "text" else ti
            continue
        if fields:  # a blank line is no record
            found.append((line, _field(fields, si), _field(fields, ei), _field(fields, ti)))
    whole = by_line([(first, cell) for first, *_, cell in found], name)
    return [
        Cue(time_ms(a, 1), time_ms(z, 1), t) for (_, a, z, _), t in zip(found, whole, strict=True)
    ]


def _field(fields: list[str], column: int) -> str:
    """The record's ``column`` (from 1); one past its last field empty."""
    return fields[column - 1] if column <= len(fields) else ""
