"""SubRip's and WebVTT's cues: one reading of their cue blocks, each format's grammar its own.

``Dialect``: a format's grammar (``subrip``, ``webvtt``). WhisperX's highlighted cues, in
either, read back into words.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import groupby
from typing import Final, NamedTuple

from subverter.markup import untagged
from subverter.readers.utf8 import Nuls, by_line, nul_notes
from subverter.transcript import Cue, Reading, Timing

__all__ = ["Dialect", "Found", "Timed", "read"]

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
    cue's index, no blank line before it, its number. ``dropped``: a line holding ``-->`` that
    is no timing line, its block dropped. ``continued``: a cue's first text after an empty line,
    no line of spaces before it. ``spaced``: a cue's first text after a line of spaces.
    ``strays``: a run of lines no cue holds, opening after an empty line past the first line
    holding ``-->`` -- not a line alone before one (the next cue's identifier, as the W3C reads
    it), nor blanks alone -- its first line of text, as written.
    """

    odd: list[tuple[int, Timed]] = field(default_factory=list)
    indexes: list[tuple[int, str]] = field(default_factory=list)
    dropped: list[tuple[int, str]] = field(default_factory=list)
    continued: list[tuple[int, str]] = field(default_factory=list)
    spaced: list[tuple[int, str]] = field(default_factory=list)
    strays: list[tuple[int, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Dialect:
    """A cue format's grammar, as ``read`` takes it.

    ``timing``: a line's timings, or None -- no timing line. ``ends``: a line ending the cue,
    the lines after it up to a timing line no cue's; None, none. ``blank``: a line skipped, the
    cue going on. ``arrow_ends``: a line holding ``-->`` that is none ends the cue alike; else
    it is text. ``index``: a cue's last line taken for the next cue's index, only empty lines
    between it and a timing line. ``notes``: what ``Found`` is noted as. ``has_references``,
    ``has_ass_escapes``: what its texts hold (``Reading``).
    """

    source: str
    timing: Callable[[str], Timed | None]
    ends: re.Pattern[str] | None
    blank: re.Pattern[str]
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

    A cue opens at its timing line and closes at its dialect's end line, or at the next cue; its
    lines joined (``_joined``: what is still not UTF-8, refused by its line).
    """
    times: list[tuple[int | None, int | None]] = []
    texts: list[tuple[int, int]] = []  # each text line: its cue, its index among the lines
    found, index, ends = Found(), dialect.index, dialect.ends
    is_open, blanks = False, _Blanks()  # the open cue's blank lines
    skipped: list[int] = []  # the lines no cue holds
    arrow = len(lines)  # the first line holding -->, a timing line or dropped; none yet
    for i, line in enumerate(lines):
        timing = dialect.timing(line)
        if timing is not None:
            arrow = min(arrow, i)
            if timing.odd:
                found.odd.append((i + 1, timing))
            if (
                index
                and is_open
                and (last := _index(index, lines, texts, len(times) - 1, i)) is not None
            ):
                _note_index(dialect, lines, last, found)
            times.append((timing.start, timing.end))
            is_open, blanks = True, _Blanks()
        elif ends and ends.fullmatch(line):
            is_open = False
        elif dialect.blank.fullmatch(line):
            blanks.met(line)  # skipped: the cue goes on
        elif dialect.arrow_ends and "-->" in line:
            arrow = min(arrow, i)
            found.dropped.append((i + 1, line.strip()))
            is_open = False
        elif is_open:
            blanks.note(found, i + 1, line)
            texts.append((len(times) - 1, i))
        else:
            skipped.append(i)
    found.strays = _strays(lines, skipped, arrow)
    cues, nuls = _joined(lines, name, times, texts)
    return cues, dialect.notes(found) + nul_notes(nuls)


@dataclass(slots=True)
class _Blanks:
    """The blank lines an open cue met, a line of spaces among them or not; its text after them."""

    met_blank: bool = False
    met_spaces: bool = False
    noted_empty: bool = False  # its first text after an empty line, no line of spaces before it
    noted_spaces: bool = False  # its first text after a line of spaces

    def met(self, line: str) -> None:
        """A blank line, empty or of spaces."""
        self.met_blank, self.met_spaces = True, self.met_spaces or bool(line)

    def note(self, found: Found, at: int, line: str) -> None:
        """A text line (line ``at``, from 1): the cue's first after its kind of blank, noted."""
        if self.met_spaces and not self.noted_spaces:
            found.spaced.append((at, line.strip()))
            self.noted_spaces = True
        elif self.met_blank and not self.met_spaces and not self.noted_empty:
            found.continued.append((at, line.strip()))
            self.noted_empty = True


def _strays(lines: list[str], skipped: list[int], arrow: int) -> list[tuple[int, str]]:
    """``Found.strays``: the runs of ``skipped`` lines past line ``arrow`` (from 0)."""
    strays: list[tuple[int, str]] = []
    for _, group in groupby(enumerate(skipped), lambda pair: pair[1] - pair[0]):
        run = [i for _, i in group]
        first, last = run[0], run[-1]
        if first < arrow or lines[first - 1]:
            continue  # before any cue, or no empty line before it: a dropped block's
        if len(run) == 1 and last + 1 < len(lines) and "-->" in lines[last + 1]:
            continue  # an identifier
        text = next((i for i in run if lines[i].strip()), None)
        if text is not None:
            strays.append((text + 1, lines[text]))
    return strays


def _index(
    index: re.Pattern[str], lines: list[str], texts: list[tuple[int, int]], cue: int, timing: int
) -> int | None:
    """The cue's last line, taken off its texts, when the next cue's index; its line, or None.

    A number alone, only empty lines between it and the timing line (``timing``, from 0) -- a
    line of spaces there keeps it text, as ffmpeg's demuxer reads it.
    """
    if not texts or texts[-1][0] != cue:
        return None
    last = texts[-1][1]
    if not index.fullmatch(lines[last]) or any(lines[last + 1 : timing]):
        return None
    _ = texts.pop()
    return last


def _note_index(dialect: Dialect, lines: list[str], last: int, found: Found) -> None:
    """An index taken (``_index``): noted when no blank line stands before it.

    When one does, it is no text after that blank: its ``Found.continued`` or ``spaced`` undone.
    """
    if not dialect.blank.fullmatch(lines[last - 1]):
        found.indexes.append((last + 1, lines[last].strip()))
    for after in (found.continued, found.spaced):
        if after and after[-1][0] == last + 1:
            _ = after.pop()


def _joined(
    lines: list[str],
    name: str,
    times: list[tuple[int | None, int | None]],
    texts: list[tuple[int, int]],
) -> tuple[list[Cue], Nuls]:
    """Each cue, its text lines joined by a space; their NULs (``utf8.by_line``)."""
    whole = by_line([(i + 1, lines[i]) for _, i in texts], name)
    parts: list[list[str]] = [[] for _ in times]
    for (cue, _), text in zip(texts, whole.texts, strict=True):
        if text:  # a line of a character's last bytes alone: given to the line it starts in
            parts[cue].append(text)
    return [Cue(*t, " ".join(p)) for t, p in zip(times, parts, strict=True)], whole.nuls


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
