"""The readers: a transcript's format to what it holds -- cues, word timings, notes, refusals."""

import csv
from typing import Final

from subverter._errors import refuse
from subverter.readers import lrc, subrip, table, whisper
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
        case "srt" | "vtt":
            cues = subrip.rows(_lines(data), name, webvtt=fmt == "vtt")
            references = fmt == "vtt"  # SubRip has none: ffmpeg's subrip decodes none
            if not subrip.is_highlighted(cues):
                return Reading(
                    f".{fmt}", has_words=False, cues=tuple(cues), has_references=references
                )
            sentences, words = subrip.highlighted(cues)
            source = f"WhisperX --highlight_words .{fmt}"
            return Reading(
                source,
                has_words=True,
                cues=tuple(sentences),
                words=tuple(words),
                has_references=references,
            )
        case "lrc":
            return Reading(".lrc", has_words=False, cues=tuple(lrc.rows(_lines(data), name)))
        case "csv" | "tsv":
            try:
                cues = table.rows(fmt, _text(data), name)
            except csv.Error as error:  # a field past csv's limit (128 KiB): no subtitle's text
                refuse(f"unreadable .{fmt}: {name}: {error}")
            return Reading(f".{fmt}", has_words=False, cues=tuple(cues))
        case _:
            return whisper.read(data, name)


def _text(data: bytes) -> str:
    """The bytes as UTF-8, a BOM off; each byte no character takes kept as a surrogate.

    The readers join a character split across their texts (``utf8.joined``), as whisper-cli's
    ``-ml`` writes one, and refuse what still is not UTF-8 by its line.
    """
    return data.decode("utf-8", "surrogateescape").removeprefix("\ufeff")


def _lines(data: bytes) -> list[str]:
    """The text's lines, a trailing CR off each (awk sees no record after the last newline)."""
    lines = [line.removesuffix("\r") for line in _text(data).split("\n")]
    if lines and lines[-1] == "":
        _ = lines.pop()
    return lines
