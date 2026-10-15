r"""ffmpeg's ``whisper`` filter's JSON (``format=json``): one object a line, its text as written.

The filter (FFmpeg 8, ``libavfilter/af_whisper.c``) writes each segment by one ``av_asprintf``,
``{"start":S,"end":E,"text":"T"}`` and an LF -- ``S`` and ``E`` integer ms (``PRId64``), its
window's start plus whisper's -- its text escaped not at all: a ``"``, a ``\`` or a line break in
it is its own. A JSON parser reads it wrong or not at all: Python's json refuses it ("Extra data",
or at a text's ``"`` "Expecting ',' delimiter"), jq stops at such a ``"``, and either, a line at a
time, makes ``C:\new`` a line break. A record opens a line with ``{"start":``; a line that does not
continues the one before, a line break in its text; blank lines after its ``"}`` are in no text. Its
lines end as csv's (``table.split_lines``): a file re-saved has CR LFs or CRs for the filter's LFs,
so a text's own CR, indistinguishable from them, is read as a line break too. A record not of the
writer's form -- a file cut mid-write -- is dropped, noted. UTF-8, or UTF-16 by its BOM, as the text
transcripts; each character joined across the texts it spans, as the filter's ``max_len`` splits a
segment between tokens (``table.timed``).
"""

import codecs
import re
from typing import Final

from subverter._errors import counted
from subverter.readers.table import split_lines, timed
from subverter.readers.utf8 import bom_text
from subverter.transcript import Reading

__all__ = ["read", "written"]

_SIGNATURE: Final = '{"start":'  # the filter's first bytes: no other whisper JSON opens so
# a record, whole: the writer's av_asprintf, the blank lines after it -- a text ends at its "}
_RECORD: Final = re.compile(r'\{"start":(-?[0-9]+),"end":(-?[0-9]+),"text":"(.*)"\}\n*', re.DOTALL)
_OPENINGS: Final = tuple(
    bom + _SIGNATURE.encode(codec)
    for bom, codec in (
        (b"", "utf-8"),
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    )
)


def written(data: bytes) -> bool:
    """Whether ``data`` opens as the filter writes: ``{"start":``, after a BOM or none."""
    return data.startswith(_OPENINGS)


def read(data: bytes, name: str) -> Reading:
    """The filter's JSON's cues, as written: a record a cue; its notes."""
    text = bom_text(data, name, lambda whole: len(split_lines(whole)))
    records: list[tuple[int, list[str]]] = []  # each record's first line (from 1), its lines
    for line, part in enumerate(split_lines(text), 1):
        if part.startswith(_SIGNATURE) or not records:  # read directly, its first line too
            records.append((line, [part]))
        else:
            records[-1][1].append(part)  # its lines joined once, below: linear
    found: list[tuple[int, str, str, str]] = []  # each record's first line, start, end, text
    dropped: list[tuple[int, str]] = []
    for line, parts in records:
        whole = "\n".join(parts)
        if match := _RECORD.fullmatch(whole):
            found.append((line, match[1], match[2], match[3]))
        else:
            dropped.append((line, whole.rstrip("\n")))  # named as written, but its blank lines
    cues, nuls = timed(found, name)
    what = "records not as ffmpeg's whisper filter writes one dropped"
    return Reading(
        "ffmpeg whisper filter JSON",
        has_words=False,
        cues=cues,
        notes=counted(dropped, what) + nuls,
    )
