"""A reader's note quotes a text as ffman's messages quote input (``_errors.shown``): on one line,
each character visible, 60 characters at most."""

from typing import Final

import pytest
import subverter
from subverter import Cue

_LONG: Final = "x" * 100  # past 60 characters
_LONG_QUOTED: Final = "x" * 57 + "..."  # its first 57, then the cut's mark
_T1: Final = "00:00:01,000 --> 00:00:02,000"


@pytest.mark.parametrize(
    ("fmt", "data", "quoted"),
    [
        pytest.param(  # SubRip: text after an empty line, read on
            "srt",
            f"1\n{_T1}\na\n\n{_LONG}\n",
            f"the first, {_LONG_QUOTED} on line 5",
            id="continued",
        ),
        pytest.param(  # SubRip: text after a line of spaces, read on
            "srt",
            f"1\n{_T1}\na\n  \n{_LONG}\n",
            f"the first, {_LONG_QUOTED} on line 5",
            id="spaced",
        ),
        pytest.param(  # SubRip: a number alone before a timing line, the next cue's index
            "srt",
            f"1\n{_T1}\na\n{'1' * 100}\n{_T1}\nb\n",
            f"the first, {'1' * 57}... on line 4",
            id="index",
        ),
        pytest.param(  # SubRip: a fraction not of three digits
            "srt",
            f"1\n{'0' * 100}0:00:01,5 --> 00:00:02,000\na\n",
            f"the first, {'0' * 57}... on line 2, as 1.005 s",
            id="fraction",
        ),
        pytest.param(  # WebVTT: a line holding --> that is no timing line, its block dropped
            "vtt",
            f"WEBVTT\n\n00:01.000 --> 00:02.000\na\n\n{_LONG} --> y\nb\n",
            f"the first {_LONG_QUOTED} on line 6",
            id="dropped",
        ),
        pytest.param(  # WebVTT: text in no cue
            "vtt",
            f"WEBVTT\n\n00:01.000 --> 00:02.000\na\n\n{_LONG}\n",
            f"the first {_LONG_QUOTED} on line 6",
            id="stray",
        ),
        pytest.param(  # LRC: a line no stamp opens, dropped
            "lrc",
            f"[00:01.00]a\n{_LONG}\n",
            f"the first, {_LONG_QUOTED} on line 2",
            id="lrc",
        ),
        pytest.param(  # TSV: a line of no tab, the text of the record before
            "tsv",
            f"start\tend\ttext\n0\t1\ta\n{_LONG}\n",
            f"the first, {_LONG_QUOTED} on line 3",
            id="tsv",
        ),
        pytest.param(  # each character visible: an ESC commands no terminal
            "vtt",
            "WEBVTT\n\n00:01.000 --> 00:02.000\na\n\n\x1b]0;t\x07\x1b[31m\N{NO-BREAK SPACE}red\n",
            "the first \\x1b]0;t\\x07\\x1b[31m\\xa0red on line 6",
            id="controls",
        ),
    ],
)
def test_a_readers_note_quotes_its_text_shown(fmt: str, data: str, quoted: str) -> None:
    (note,) = subverter.read(fmt, data.encode(), f"a.{fmt}").notes
    assert quoted in note


def test_a_short_text_is_quoted_whole() -> None:
    reading = subverter.read("srt", f"1\n{_T1}\na\n\nshort\n".encode(), "a.srt")
    assert reading.cues == (Cue(1000, 2000, "a short"),)
    assert reading.notes[0].endswith("the first, short on line 5")
