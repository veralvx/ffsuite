"""The readers: a transcript's format to what it holds -- cues, word timings, notes, refusals."""

import csv
from typing import Final

from subverter._errors import refuse
from subverter.readers import lrc, subrip, table, webvtt, whisper
from subverter.transcript import Reading

__all__ = ["FORMATS", "read"]

FORMATS: Final = ("srt", "vtt", "lrc", "csv", "tsv", "json")  # the formats a reader reads


def read(fmt: str, data: bytes, name: str) -> Reading:
    """One format's reader, on the transcript's bytes (``name``: its name, in messages)."""
    if fmt == "txt":
        use = "use whisper-cli -osrt, -ovtt, -olrc, -ocsv, -oj or -ojf"
        refuse(f"a .txt transcript has no timestamps; {use}, or WhisperX srt, vtt, tsv or json")
    if fmt not in FORMATS:
        refuse(f"unsupported subtitle format '.{fmt}' ({', '.join(FORMATS)})")
    match fmt:
        case "srt":
            return subrip.read(subrip.split_lines(_text(data)), name)
        case "vtt":
            return webvtt.read(webvtt.split_lines(_text(data)), name)
        case "lrc":
            return lrc.read(lrc.split_lines(_text(data)), name)
        case "csv" | "tsv":
            try:
                rows, notes = table.rows(fmt, _text(data), name)
            except csv.Error as error:  # a field past csv's limit (128 KiB): no subtitle's text
                refuse(f"unreadable .{fmt}: {name}: {error}")
            return Reading(f".{fmt}", has_words=False, cues=tuple(rows), notes=notes)
        case _:
            return whisper.read(data, name)


def _text(data: bytes) -> str:
    """The bytes as UTF-8, a BOM off; each byte no character takes kept as a surrogate.

    The readers join a character split across their texts (``utf8.joined``), as whisper-cli's
    ``-ml`` writes one, and refuse what still is not UTF-8 by its line.
    """
    return data.decode("utf-8", "surrogateescape").removeprefix("\ufeff")
