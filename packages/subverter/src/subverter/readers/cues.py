"""SubRip's and WebVTT's cues: one reading of their cue blocks, each format's grammar its own.

``Dialect``: a format's grammar (``subrip``, ``webvtt``). WhisperX's highlighted cues, in
either, read back into words.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, NamedTuple

from subverter.markup import untagged
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue, Reading, Timing

__all__ = ["Dialect", "Found", "Timed", "read"]

_BLANK_LINE: Final = re.compile(r"[ \t]*")  # a cue's end
_UNDERLINE: Final = re.compile(r"<u>([^<]*)</u>")  # WhisperX --highlight_words: the word


class Timed(NamedTuple):
    """A timing line's start and end, each None past a double's range (``fields.ms``).

    ``odd``: its times written oddly but read -- each as written, read (SubRip's short fraction).
    """

    start: int | None
    end: int | None
    odd: tuple[tuple[str, int | None], ...] = ()


@dataclass(slots=True)
class Found:
    """What a reading met that its dialect may note, each by its line (from 1).

    ``odd``: a timing line with an odd time. ``indexes``: a cue's line taken for the next
    cue's index, its number. ``dropped``: a line holding ``-->`` that is no timing line, its
    block dropped.
    """

    odd: list[tuple[int, Timed]] = field(default_factory=list)
    indexes: list[tuple[int, str]] = field(default_factory=list)
    dropped: list[tuple[int, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Dialect:
    """A cue format's grammar, as ``read`` takes it.

    ``timing``: a line's timings, or None -- no timing line. ``arrow_ends``: a line holding
    ``-->`` that is none ends the cue, the lines after it up to a blank line or a timing line no
    cue's; else it is text. ``index``: a cue's line taken for the next cue's index, its blank
    line missing, when right before a timing line. ``notes``: what ``Found`` is noted as.
    ``has_references``, ``has_ass_escapes``: what its texts hold (``Reading``).
    """

    source: str
    timing: Callable[[str], Timed | None]
    arrow_ends: bool
    index: re.Pattern[str] | None
    notes: Callable[[Found], tuple[str, ...]]
    has_references: bool
    has_ass_escapes: bool


def read(lines: list[str], name: str, dialect: Dialect) -> Reading:
    """The cues, or WhisperX's sentences and words (``_is_highlighted``); notes (``_rows``)."""
    cues, notes = _rows(lines, name, dialect)
    references, escapes = dialect.has_references, dialect.has_ass_escapes
    if not _is_highlighted(cues):
        return Reading(
            dialect.source,
            has_words=False,
            cues=tuple(cues),
            notes=notes,
            has_references=references,
            has_ass_escapes=escapes,
        )
    sentences, words = _highlighted(cues)
    return Reading(
        f"WhisperX --highlight_words {dialect.source}",
        has_words=True,
        cues=tuple(sentences),
        words=tuple(words),
        notes=notes,
        has_references=references,
        has_ass_escapes=escapes,
    )


def _rows(lines: list[str], name: str, dialect: Dialect) -> tuple[list[Cue], tuple[str, ...]]:
    """Cues, their text kept with its tags (a WhisperX <u> marks a word); notes (``dialect``).

    A cue opens at its timing line and closes at a blank line, or at the next cue (bash's
    intext and its set st, which always changed together). Its text lines joined by a space,
    each character joined across the lines it spans (``utf8.by_line``: what is still not UTF-8,
    refused by its line).
    """
    times: list[tuple[int | None, int | None]] = []
    texts: list[tuple[int, int]] = []  # each text line: its cue, its index among the lines
    found, index = Found(), dialect.index
    is_open = False
    for i, line in enumerate(lines):
        timing = dialect.timing(line)
        if timing is not None:
            if timing.odd:
                found.odd.append((i + 1, timing))
            if index and texts and texts[-1][1] == i - 1 and index.fullmatch(lines[i - 1]):
                _ = texts.pop()  # the line before (line i, from 1): the next cue's index
                found.indexes.append((i, lines[i - 1].strip()))
            times.append((timing.start, timing.end))
            is_open = True
        elif _BLANK_LINE.fullmatch(line):
            is_open = False
        elif dialect.arrow_ends and "-->" in line:
            found.dropped.append((i + 1, line.strip()))
            is_open = False
        elif is_open:
            texts.append((len(times) - 1, i))
    whole = by_line([(i + 1, lines[i]) for _, i in texts], name)
    parts: list[list[str]] = [[] for _ in times]
    for (cue, _), text in zip(texts, whole, strict=True):
        if text:  # a line of a character's last bytes alone: given to the line it starts in
            parts[cue].append(text)
    cues = [Cue(*t, " ".join(p)) for t, p in zip(times, parts, strict=True)]
    return cues, dialect.notes(found)


def _is_highlighted(cues: list[Cue]) -> bool:
    """WhisperX --highlight_words, by structure: <u> somewhere, most neighbours one text."""
    plains = [untagged(c.text) for c in cues]
    underlined = any("<u>" in c.text for c in cues)
    same = sum(1 for i in range(1, len(plains)) if plains[i] == plains[i - 1])
    return underlined and len(cues) > 1 and same / (len(cues) - 1) >= 0.5  # noqa: PLR2004 -- most


def _highlighted(cues: list[Cue]) -> tuple[list[Cue], list[Timing]]:
    """One sentence a run of one text (new when the underline moves back); each <u> a word."""
    sentences: list[Cue] = []
    words: list[Timing] = []
    current, cs, ce, last, sid = "", None, None, -1, -1
    for cue in cues:
        plain = untagged(cue.text)
        underline = _UNDERLINE.search(cue.text)
        offset = len(untagged(cue.text[: underline.start()])) if underline else -1
        if plain != current or (underline and offset <= last):
            if current:
                sentences.append(Cue(cs, ce, current, str(sid)))
            sid, current, cs, last = sid + 1, plain, cue.start, -1
        ce = cue.end
        if underline:
            words.append(Timing(str(sid), cue.start, cue.end, underline[1]))
            last = offset
    if current:
        sentences.append(Cue(cs, ce, current, str(sid)))
    return sentences, words
