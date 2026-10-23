"""SubRip's and WebVTT's cues: one reading of their cue blocks, each format's grammar its own.

``Dialect``: a format's grammar (``subrip``, ``webvtt``). OpenAI whisper's and WhisperX's
highlighted cues, in either, read back into words: one name for both, WhisperX's writer OpenAI's
copied -- its ``ja`` and ``zh`` spaces and its speakers its own.
"""

import re
from bisect import bisect_right
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import groupby, pairwise
from typing import Final, NamedTuple

from subverter.readers.utf8 import Nuls, by_line, nul_notes
from subverter.transcript import Cue, Reading, Timing

__all__ = ["Dialect", "Found", "Odd", "Timed", "read"]

_UNDERLINE: Final = re.compile(r"<u>([^<]*)</u>")  # --highlight_words: the word
_UNDERLINES: Final = re.compile(r"</?u>")  # its tags (``_plain``)
_SPEAKER: Final = re.compile(r"\[[^\]\n]*\]: ")  # WhisperX's diarized cue opens f"[{speaker}]: "
_LIT_WORD: Final = re.compile(r"<u>[^<]+</u>")  # a cue wholly underlined: a word, its writer's
_RUN: Final = re.compile(r"\S+")  # a highlighted cue's word, between its spaces (``_words``)


class Odd(NamedTuple):
    """A time written oddly but read: how (its dialect's word), as written, as read."""

    kind: str
    written: str
    value: int | None


class Timed(NamedTuple):
    """A timing line's start and end, each None past a double's range (``fields.ms``).

    ``odd``: its times written oddly but read (SubRip's: a short fraction, or none at all).
    """

    start: int | None
    end: int | None
    odd: tuple[Odd, ...] = ()


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
    """The cues, or highlighted sentences and words (``_is_highlighted``); notes (``_rows``)."""
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
    sentences, words = _highlighted(cues, unspaced=_is_unspaced(cues))
    return Reading(
        f"OpenAI whisper or WhisperX --highlight_words {dialect.source}",
        has_words=True,
        cues=tuple(sentences),
        words=tuple(words),
        notes=notes,
        has_references=references,
        has_ass_escapes=escapes,
    )


def _rows(lines: list[str], name: str, dialect: Dialect) -> tuple[list[Cue], tuple[str, ...]]:
    """Cues, their text kept with its tags (a highlighting <u> marks a word); notes (``dialect``).

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
    """Each cue, its text lines joined by a line break; their NULs (``utf8.by_line``)."""
    whole = by_line([(i + 1, lines[i]) for _, i in texts], name)
    parts: list[list[str]] = [[] for _ in times]
    for (cue, _), text in zip(texts, whole.texts, strict=True):
        if text:  # a line of a character's last bytes alone: given to the line it starts in
            parts[cue].append(text)
    return [Cue(*t, "\n".join(p)) for t, p in zip(times, parts, strict=True)], whole.nuls


def _plain(text: str) -> str:
    """A highlighted cue's text without its underline: its sentence's, as written."""
    return _UNDERLINES.sub("", text)


def _spoken(text: str) -> int:
    """Where a cue's text starts after WhisperX's speaker, if it opens with one."""
    speaker = _SPEAKER.match(text)
    return speaker.end() if speaker else 0


def _unspeakered(text: str) -> str:
    """A cue's text after WhisperX's speaker."""
    return text[_spoken(text) :]


def _key(text: str) -> str:
    """A cue's sentence as its neighbours compare: no underline, no space or break past a speaker.

    WhisperX joins a ``ja`` or ``zh`` cue of a gap between words by nothing, a highlighted one by
    spaces (``utils.py`` from 3.2.0; PyPI's 3.1.x, a third party's, alike).
    """
    return _sentence(text, unspaced=True)


def _is_highlighted(cues: list[Cue]) -> bool:
    """--highlight_words, by structure: <u> somewhere, most neighbours one text -- or a cue a word.

    A cue a word, each wholly underlined: OpenAI whisper's ``--max_words_per_line 1`` (no gap's
    cue; ``merge_punctuations``' ``- I`` one word), WhisperX's from 3.7.7 (its cue times its
    words'). A cue of no underline among them -- a word WhisperX left untimed, at its segment's
    times -- leaves the file cues.
    """
    if len(cues) <= 1 or not any("<u>" in c.text for c in cues):
        return False
    if all(_LIT_WORD.fullmatch(_unspeakered(c.text)) for c in cues):
        return True
    keys = [_key(c.text) for c in cues]
    same = sum(1 for a, b in pairwise(keys) if a == b)
    return same / (len(cues) - 1) >= 0.5  # noqa: PLR2004 -- most


def _is_unspaced(cues: list[Cue]) -> bool:
    """Whether a gap's cue joins its words by nothing where a highlighted neighbour has spaces.

    WhisperX's ``ja`` and ``zh``: its spaces are its own, none in a word (``alignment.py``: a word
    a character, a space none). Without such a cue, nothing tells them from a text's own: OpenAI
    whisper's ``ja`` joins its words by nothing, a space one of them holds kept.
    """
    texts = [_plain(c.text) for c in cues]
    return any(a != b and _key(a) == _key(b) for a, b in pairwise(texts))


def _highlighted(cues: list[Cue], *, unspaced: bool) -> tuple[list[Cue], list[Timing]]:
    """One sentence a run of one text (new when the underline moves back); each <u> a word.

    A sentence's text is its first cue's without the underline -- ``unspaced``, without WhisperX's
    spaces too, as its gap cues join its words (``_is_unspaced``); its lead, its speaker. A word no
    cue underlines -- one WhisperX left untimed -- is a word of no time (``_words``).
    """
    sentences: list[Cue] = []
    parts: list[_Part] = []
    gaps: list[str] = []  # the sentences of no underline since the last part: their keys
    current, text, lead, cs, ce, last, sid = "", "", "", None, None, -1, -1
    lit: list[tuple[int, Timing]] = []  # the sentence's words, each at its underline's offset
    shown = ""  # a highlighted cue's text without its underline: its words, each where it stands

    def close() -> None:
        nonlocal gaps
        sentences.append(Cue(cs, ce, text, str(sid), lead))
        if not lit:
            gaps.append(_key(text))
            return
        skip = _spoken(shown) if lead else 0
        parts.append(_Part([(at - skip, w) for at, w in lit], shown[skip:], lead, tuple(gaps)))
        gaps = []

    for cue in cues:
        key = _key(cue.text)
        underline = _UNDERLINE.search(cue.text)
        offset = len(_plain(cue.text[: underline.start()])) if underline else -1
        if key != current or (underline and offset <= last):
            if current:
                close()
            sid, current, cs, last, lit, shown = sid + 1, key, cue.start, -1, [], ""
            text = _sentence(cue.text, unspaced=unspaced)
            lead = text[: _spoken(text)]
        ce = cue.end
        if underline:
            lit.append((offset, Timing(str(sid), cue.start, cue.end, underline[1])))
            shown, last = shown or _plain(cue.text), offset
            if offset < len(lead):  # a word, not a speaker: OpenAI whisper's `[Music]:` underlined
                lead = ""
    if current:
        close()
    return sentences, _words(parts)


class _Part(NamedTuple):
    """A highlighted sentence's words, read past its lead (``_words``).

    ``lit``, its underlined words, each at its offset; ``shown``, a highlighted cue's text without
    its underline -- its words where they stand; ``gaps``, the keys of the sentences of no
    underline between it and the part before.
    """

    lit: list[tuple[int, Timing]]
    shown: str
    lead: str
    gaps: tuple[str, ...]

    def continues(self, before: "_Part") -> bool:
        """Whether it is ``before``'s sentence, split by WhisperX v3.1.x's gap cue.

        One speaker and one text; between them, cues of that text alone, no speaker (``utils.py``
        writes a gap's cue without it); its underline past ``before``'s.
        """
        key = _key(self.shown)
        return (
            (self.lead, self.shown) == (before.lead, before.shown)
            and all(g == key for g in self.gaps)
            and self.lit[0][0] > before.lit[-1][0]
        )


def _words(parts: list[_Part]) -> list[Timing]:
    """The sentences' words: the underlined, and each run of a text that none holds, untimed.

    Parts of one sentence, split (``_Part.continues``), are one sentence's words. Within them, a run
    of ``shown`` between its spaces no underlined word holds is a word of no time, the part's it
    follows (the first's, before any): WhisperX joins a highlighted cue's words by spaces (a line
    break before one it wraps at), and a word it left untimed (no ``start``: ``alignment.py``) is in
    each cue's text but underlined in none. OpenAI whisper times every word, a space in one (``-
    I``) its own.
    """
    words: list[Timing] = []
    group: list[_Part] = []
    for part in [*parts, None]:
        if part and group and part.continues(group[-1]):
            group.append(part)
            continue
        held = [(at, at + len(w.text)) for p in group for at, w in p.lit]
        firsts = [p.lit[0][0] for p in group]
        found: list[list[tuple[int, Timing]]] = [list(p.lit) for p in group]
        for m in _RUN.finditer(group[0].shown if group else ""):
            if not any(a < m.end() and m.start() < z for a, z in held):
                k = max(bisect_right(firsts, m.start()) - 1, 0)
                found[k].append((m.start(), Timing(group[k].lit[0][1].segment, None, None, m[0])))
        words += [w for f in found for _, w in sorted(f, key=lambda r: r[0])]
        group = [part] if part else []
    return words


def _sentence(text: str, *, unspaced: bool) -> str:
    """A highlighted cue's sentence: its text without the underline (``unspaced``: its spaces too).

    WhisperX's spaces and line breaks are between its words alone, which its ``ja`` and ``zh`` join
    by nothing; its speaker's ``[X]: `` kept.
    """
    plain = _plain(text)
    if not unspaced:
        return plain
    at = _spoken(plain)
    return plain[:at] + plain[at:].replace(" ", "").replace("\n", "")
