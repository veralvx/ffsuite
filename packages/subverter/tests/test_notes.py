"""notes: what a note quotes of a text -- a cue at Netflix's most whole, a longer text cut."""

from typing import Final

import pytest
import subverter
from subverter import Cue


@pytest.mark.parametrize(
    ("text", "quoted"),
    [
        ("", ""),
        ("a" * 85, "a" * 85),  # two lines of 42 characters and the space joining them: whole
        ("a" * 86, "a" * 85 + "... (1 more characters)"),
        ("é" * 400_000, "é" * 85 + "... (399915 more characters)"),  # characters, not bytes
    ],
    ids=["empty", "85", "86", "400000"],
)
def test_an_excerpt_is_a_cue_at_netflixs_most_the_rest_counted(text: str, quoted: str) -> None:
    assert subverter.excerpt(text) == quoted


_LONG: Final = "x" * 100  # past a cue at its most
_SHOWN: Final = "x" * 85 + "... (15 more characters)"
_T1: Final = "00:00:01,000 --> 00:00:02,000"


@pytest.mark.parametrize(
    ("fmt", "data", "shown"),
    [
        pytest.param(  # SubRip: text after an empty line, read on
            "srt", f"1\n{_T1}\na\n\n{_LONG}\n", f"the first, {_SHOWN} on line 5", id="continued"
        ),
        pytest.param(  # SubRip: text after a line of spaces, read on
            "srt", f"1\n{_T1}\na\n  \n{_LONG}\n", f"the first, {_SHOWN} on line 5", id="spaced"
        ),
        pytest.param(  # SubRip: a number alone before a timing line, the next cue's index
            "srt",
            f"1\n{_T1}\na\n{'1' * 100}\n{_T1}\nb\n",
            f"the first, {'1' * 85}... (15 more characters) on line 4",
            id="index",
        ),
        pytest.param(  # SubRip: a fraction not of three digits
            "srt",
            f"1\n{'0' * 100}0:00:01,5 --> 00:00:02,000\na\n",
            f"the first, {'0' * 85}... (24 more characters) on line 2, as 1.005 s",
            id="fraction",
        ),
        pytest.param(  # WebVTT: a line holding --> that is no timing line, its block dropped
            "vtt",
            f"WEBVTT\n\n00:01.000 --> 00:02.000\na\n\n{_LONG} --> y\nb\n",
            f"the first {'x' * 85}... (21 more characters) on line 6",
            id="dropped",
        ),
        pytest.param(  # WebVTT: text in no cue
            "vtt",
            f"WEBVTT\n\n00:01.000 --> 00:02.000\na\n\n{_LONG}\n",
            f"the first {_SHOWN} on line 6",
            id="stray",
        ),
    ],
)
def test_a_readers_note_quotes_an_excerpt(fmt: str, data: str, shown: str) -> None:
    (note,) = subverter.read(fmt, data.encode(), f"a.{fmt}").notes
    assert shown in note


def test_a_short_text_is_quoted_whole() -> None:
    reading = subverter.read("srt", f"1\n{_T1}\na\n\nshort\n".encode(), "a.srt")
    assert reading.cues == (Cue(1000, 2000, "a short"),)
    assert reading.notes[0].endswith("the first, short on line 5")
