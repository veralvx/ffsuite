"""The readers: a transcript's format to what it holds -- cues, word timings, notes, refusals."""

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
            return subrip.read(data, name)
        case "vtt":
            return webvtt.read(data, name)
        case "lrc":
            return lrc.read(data, name)
        case "csv" | "tsv":
            return table.read(fmt, data, name)
        case _:
            return whisper.read(data, name)
