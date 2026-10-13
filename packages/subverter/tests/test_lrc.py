"""LRC (``readers/lrc.py``) against its rules, as recorded (docs/decisions.md's rows, the reader's
docstrings): its lines, stamps, offset and texts.

Every expectation is worked by hand from a rule, not taken from a run: what the reader yields
before ffman's normalising (sorted, each line ending where the next starts; no trim, no clamp).
"""

import re
from typing import Final

import pytest
import subverter
from subverter import Cue


def test_lrc_lines_sorted_each_ending_at_the_next_the_last_3_s_later() -> None:
    huge = "9" * 400
    data = f"[00:03.50]b\n[00:01.00]a\nnot a line\n[{huge}:00.00]too far\n[00:05]c\n"
    assert subverter.read("lrc", data.encode(), "a.lrc").cues == (
        Cue(1000, 3500, "a"),
        Cue(3500, 5000, "b"),
        Cue(5000, 8000, "c"),
    )


@pytest.mark.parametrize(
    ("data", "cues", "notes"),
    [
        pytest.param(  # the convention's: global, in ms, + sooner -- a tag after a line too
            "[00:01.00]one\n[offset:+500]\n[00:02.00]two\n",
            (Cue(500, 1500, "one"), Cue(1500, 4500, "two")),
            ("LRC offset on line 2 applied: every line 500 ms sooner",),
            id="sooner",
        ),
        pytest.param(
            "[offset:-250]\n[00:01.00]a\n",
            (Cue(1250, 4250, "a"),),
            ("LRC offset on line 1 applied: every line 250 ms later",),
            id="later",
        ),
        pytest.param(  # the last whole one; each other one noted ("9"*400: no number, exact's)
            f"[offset:+100]\n[offset:abc]\n[offset: -200 ]\n[offset:1.5]\n[offset:{'9' * 400}]\n[00:01.00]a\n",
            (Cue(1200, 4200, "a"),),
            (
                "LRC offset on line 2 ignored: not a whole number of milliseconds",
                "LRC offset on line 4 ignored: not a whole number of milliseconds",
                "LRC offset on line 5 ignored: not a whole number of milliseconds",
                "LRC offset on line 3 applied: every line 200 ms later",
            ),
            id="the last whole one",
        ),
        pytest.param(  # ffmpeg's tag (measured): first on its line, the rest of it ignored
            "[offset:+500] by ear\n[00:01.00]a\n",
            (Cue(500, 3500, "a"),),
            ("LRC offset on line 1 applied: every line 500 ms sooner",),
            id="the rest of its line",
        ),
        pytest.param(  # no offset tag: lower case, first on its line (ffmpeg's); no tag at all
            # without its colon (Navidrome joins it, as text, to a timed line before it): a line dropped
            "[OFFSET:+500]\n [offset:+500]\n[offset+500]\n[00:01.00]a\n",
            (Cue(1000, 4000, "a"),),
            (
                "1 LRC lines dropped, opened by no stamp ffman reads nor a tag: the first, [offset+500] on line 3",
            ),
            id="no offset tag",
        ),
        pytest.param("[offset:+0]\n[00:01.00]a\n", (Cue(1000, 4000, "a"),), (), id="zero"),
    ],
)
def test_an_lrc_offset_moves_every_time(
    data: str, cues: tuple[Cue, ...], notes: tuple[str, ...]
) -> None:
    reading = subverter.read("lrc", data.encode(), "a.lrc")
    assert (reading.cues, reading.notes) == (cues, notes)


_BLANKED: Final = "had blanks before their stamp, read as Navidrome and Jellyfin read them"
_SIGNED: Final = "had a stamp with a minus, a time before 0, read as ffmpeg writes and reads it"
_DROPPED: Final = "dropped, opened by no stamp ffman reads nor a tag"


@pytest.mark.parametrize(
    ("data", "cues", "notes"),
    [
        pytest.param(  # Navidrome trims a line, Jellyfin finds a stamp anywhere (ffmpeg's sscanf
            # is given the blanks read_ts skipped: no stamp)
            " [00:02.00]two\n\t[00:03.00] \t[00:04.00]three\n",
            (Cue(2000, 3000, "two"), Cue(3000, 4000, "three"), Cue(4000, 7000, "three")),
            (f"2 LRC lines {_BLANKED} (ffmpeg drops them): the first, [00:02.00]two on line 1",),
            id="blanks before",
        ),
        pytest.param(  # ffmpeg's lrcenc writes a time before 0 so, its lrcdec reads it (measured)
            "[00:02.00][-00:01.50]a\n[offset:-500]\n[-1:00.00]b\n",
            (Cue(-59500, -1000, "b"), Cue(-1000, 2500, "a"), Cue(2500, 5500, "a")),
            (
                "LRC offset on line 2 applied: every line 500 ms later",
                f"2 LRC lines {_SIGNED} (Navidrome and Jellyfin read none): the first, "
                + "[00:02.00][-00:01.50]a on line 1",
            ),
            id="a minus",
        ),
        pytest.param(  # a minus of no time is 0: no time before it (ffmpeg's lrcenc writes none)
            "[-00:00.00]zero\n", (Cue(0, 3000, "zero"),), (), id="a minus of 0"
        ),
        pytest.param(  # no stamp ffman reads: hours (Navidrome's), a plus, a comma, a colon
            # before the fraction, text before the stamp (Jellyfin's) or none (Navidrome joins it
            # to the line before), a time past a double's range, a blank not ffmpeg's (a space or a
            # tab) before the stamp; the line named without its trailing blanks
            "[00:01.00]a\n[1:02:03.00]hours \t\n[+00:05.00]plus\n[00:06,00]comma\n"
            + f"[00:07:50]colon\nno stamp\nx [00:08.00]after text\n[{'9' * 306}:00.00]far\n"
            + "\u00a0[00:09.00]no-break space\n",
            (Cue(1000, 4000, "a"),),
            (f"8 LRC lines {_DROPPED}: the first, [1:02:03.00]hours on line 2",),
            id="dropped",
        ),
        pytest.param(  # a tag (a letter or Wikipedia's # first, then a colon), or no text
            "[ti:t]\n[Ar:a]\n[#:comment]\n [la:en] x\n\n \t\n[00:01.00]a\n",
            (Cue(1000, 4000, "a"),),
            (),
            id="tags and empty lines",
        ),
    ],
)
def test_an_lrc_line_read_past_its_form_or_dropped_is_noted(
    data: str, cues: tuple[Cue, ...], notes: tuple[str, ...]
) -> None:
    reading = subverter.read("lrc", data.encode(), "a.lrc")
    assert (reading.cues, reading.notes) == (cues, notes)


@pytest.mark.parametrize(
    ("data", "cues"),
    [
        pytest.param(  # Wikipedia's repeated line: a line a stamp, sorted among the others
            "[00:05.00][00:09.00]chorus\n[00:07.00]two\n",
            (Cue(5000, 7000, "chorus"), Cue(7000, 9000, "two"), Cue(9000, 12000, "chorus")),
            id="repeated",
        ),
        pytest.param(  # blanks between stamps, as Navidrome reads them (ffmpeg drops the second)
            "[00:01.00] \t[00:03.00]  x\n",
            (Cue(1000, 3000, "  x"), Cue(3000, 6000, "  x")),
            id="blanks between",
        ),
        pytest.param(  # a stamp past a double's range in ms: no line of its own, the rest kept
            f"[00:01.00][{'9' * 306}:00.00][00:02.00]a\n",
            (Cue(1000, 2000, "a"), Cue(2000, 5000, "a")),
            id="one past a double",
        ),
        pytest.param(  # a stamp after the text: text
            "[00:01.00]text [00:08.00]later\n",
            (Cue(1000, 4000, "text [00:08.00]later"),),
            id="after the text",
        ),
    ],
)
def test_an_lrc_line_of_several_stamps_is_a_line_each(data: str, cues: tuple[Cue, ...]) -> None:
    assert subverter.read("lrc", data.encode(), "a.lrc").cues == cues


def test_an_lrc_line_of_several_stamps_is_joined_once() -> None:
    data = b"[00:01.00][00:03.00]caf\xc3\n[00:02.00]\xa9 ok\n"  # \xc3\xa9, an e acute, across the two lines
    assert subverter.read("lrc", data, "a.lrc").cues == (
        Cue(1000, 2000, "caf\u00e9"),
        Cue(2000, 3000, " ok"),
        Cue(3000, 6000, "caf\u00e9"),
    )


def test_an_lrc_time_past_a_double_in_ms_drops_its_line() -> None:
    minutes = "9" * 306  # a number (under 10**308), but in ms (times 60 000) past a double's range
    data = f"[00:01.00]kept\n[{minutes}:00.00]dropped\n".encode()
    assert subverter.read("lrc", data, "a.lrc").cues == (Cue(1000, 4000, "kept"),)


def test_an_lrcs_cr_cr_lf_is_one_line_end_as_subrips() -> None:
    # observable in a line's number alone: an LRC reads no blank line
    data = b"[ti:x]\r\r\n[offset:+500]\r\r\n[00:01.00]one\r\r\n"
    reading = subverter.read("lrc", data, "a.lrc")
    assert reading.notes == ("LRC offset on line 2 applied: every line 500 ms sooner",)


def test_lrc_lines_are_joined_as_written_then_sorted() -> None:
    data = b"[00:05.00] \xd1\n[00:01.00]\x91x\n"  # ё begun at 5 s, ended in the line at 1 s
    assert subverter.read("lrc", data, "a.lrc").cues == (
        Cue(1000, 5000, "x"),
        Cue(5000, 8000, " ё"),
    )


# --- encodings: UTF-8, or UTF-16 by its BOM, as Navidrome (``ioutils.UTF8Reader``) and Jellyfin
# (.NET's BOM detection) read it -- ffmpeg 8.1.2 detects no LRC there (``lrc_probe``, measured)

_SONG: Final = "[ti:x]\r\n[00:02.00]caf\u00e9 \U0001f600\r\n[00:01.00]one\r\n"


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_an_lrc_in_utf16_by_its_bom_reads_as_in_utf8(codec: str) -> None:
    data = ("\ufeff" + _SONG).encode(codec)
    assert subverter.read("lrc", data, "a.lrc") == subverter.read("lrc", _SONG.encode(), "a.lrc")


@pytest.mark.parametrize(
    ("data", "line"),
    [
        pytest.param(
            ("\ufeff" + _SONG.replace("one", "o\ud800ne")).encode("utf-16-le", "surrogatepass"),
            3,
            id="a lone surrogate",
        ),
        pytest.param(("\ufeff" + _SONG).encode("utf-16-le") + b"x", 4, id="an odd byte"),
        pytest.param(  # its lines SubRip's: CR CR LF one end
            "\ufeff[ti:x]\r\r\n\udc00".encode("utf-16-be", "surrogatepass"), 2, id="BE"
        ),
    ],
)
def test_an_lrcs_unit_not_utf16_is_refused_by_its_line(data: bytes, line: int) -> None:
    with pytest.raises(subverter.Error, match=re.escape(f"not UTF-16: a.lrc (line {line})")):
        _ = subverter.read("lrc", data, "a.lrc")
