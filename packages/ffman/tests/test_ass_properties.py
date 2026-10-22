import re
from itertools import groupby

from hypothesis import given, settings
from subverter.transcript import Transcript

from ffman.subs.ass import Style, script
from tests.support.subtitles import FRAMES, POS, STYLES, libass_reads, transcripts

EVENT = re.compile(
    r"Dialogue: ([01]),(\d+):(\d\d):(\d\d)\.(\d\d),(\d+):(\d\d):(\d\d)\.(\d\d),Default,,0,0,0,,(.*)"
)


def cs(h: str, m: str, s: str, c: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 100 + int(c)


@settings(max_examples=300, deadline=None)
@given(transcripts(), STYLES, FRAMES)
def test_what_holds_of_any_script(t: Transcript, style: Style, frame: tuple[int, int]) -> None:
    text, _ = script(t, *frame, style)
    # the transcript's span, in centiseconds; word mode holds a word up to 400 ms on
    lo, hi = t.chunks[0].start // 10 - 1, (t.chunks[-1].end + 409) // 10 + 1
    xs: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        m = EVENT.fullmatch(line)
        assert m, line
        start, end = cs(*m.group(2, 3, 4, 5)), cs(*m.group(6, 7, 8, 9))
        assert lo <= start < end <= hi, (start, end, lo, hi)
        # a layer of its own only to highlight a word
        assert m[1] == "0" or style.mode == "chunk-word"
        positions: list[tuple[str, str]] = POS.findall(m[10])
        assert positions or style.mode == "plain", m[10]  # placed: every event read, none skipped
        for x, y in positions:
            xs.add(x)
            assert -2000 < float(y) < 3000
    # every line centred: one x, half the canvas
    assert len(xs) <= 1


@settings(max_examples=300, deadline=None)
@given(transcripts(), STYLES, FRAMES)
def test_libass_draws_each_text_as_written(
    t: Transcript, style: Style, frame: tuple[int, int]
) -> None:
    """A brace or backslash in a text is drawn as itself, and makes no override block."""
    text, _ = script(t, *frame, style)
    events = [EVENT.fullmatch(line) for line in text.splitlines() if line.startswith("Dialogue:")]
    for m in events:
        assert m
        _, blocks = libass_reads(m[10])
        assert all(block.startswith("\\") for block in blocks), blocks  # ffman's own tags alone
    if style.mode != "plain":
        return  # the highlight's layers hide and show words: plain draws each chunk whole once
    texts = ["".join(c.text.split()) for c in t.chunks]
    shown: list[str] = []  # each chunk's lines, its events in a row: one time span
    for _, run in groupby((m for m in events if m), key=lambda m: m.group(2, 3, 4, 5, 6, 7, 8, 9)):
        shown.append("".join("".join(libass_reads(m[10])[0].split()) for m in run))
    assert shown == texts


_LIT = re.compile(r"\{\\alpha&H00&[^}]*\}(.*)\{\\r\\alpha&HFF&\}")  # layer 1's lit word


@settings(max_examples=300, deadline=None)
@given(transcripts(), STYLES, FRAMES)
def test_chunk_word_lights_its_timed_words_alone(
    t: Transcript, style: Style, frame: tuple[int, int]
) -> None:
    """Each word lit on layer 1 is one of its words -- never a lead's (a speaker's) unit."""
    if style.mode != "chunk-word":
        return
    words = {"".join(w.text.split()) for w in t.words}
    for line in script(t, *frame, style)[0].splitlines():
        m = EVENT.fullmatch(line)
        if m and m[1] == "1" and (lit := _LIT.search(m[10])):
            assert "".join(libass_reads(lit[1])[0].split()) in words, (lit[1], words)
