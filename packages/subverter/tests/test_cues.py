"""SubRip and WebVTT, the cue formats (``readers/cues.py``, ``subrip.py``, ``webvtt.py``), against
their rules, as recorded (docs/decisions.md's rows, the readers' docstrings) -- each rule's two
readings side by side.

Every expectation is worked by hand from a rule, not taken from a run: what a reader yields
before ffman's normalising (no trim, no sort, no clamp, no cue dropped).
"""

import re
import time
from typing import Final

import pytest
import subverter
from hypothesis import given, settings
from hypothesis import strategies as st
from subverter import Cue, Reading, Timing

# --- SubRip and WebVTT: a cue opens at its --> line, closes at its format's end line or the next cue


def test_srt_a_bom_and_crs_off_lines_joined_the_last_cue_closed_at_the_end() -> None:
    data = "\ufeff1\r\n00:00:01,000 --> 00:00:02,500\r\nHello\r\nthere\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nbye\r\n"
    assert subverter.read("srt", data.encode(), "a.srt") == Reading(
        ".srt",
        has_words=False,
        cues=(Cue(1000, 2500, "Hello there"), Cue(3000, 4000, "bye")),
        has_ass_escapes=True,
    )


def test_vtt_minutes_alone_settings_ignored_tags_kept_the_next_cue_closing_one() -> None:
    data = "WEBVTT\n\n00:01.000 --> 00:02.000 align:start position:10%\n<i>hi</i>\n01:00:00.000 --> 01:00:01.500\nnext\n"
    assert subverter.read("vtt", data.encode(), "a.vtt").cues == (
        Cue(1000, 2000, "<i>hi</i>"),
        Cue(3_600_000, 3_601_500, "next"),
    )


def test_a_subrip_part_past_a_double_is_no_time() -> None:
    huge = "9" * 400  # its first digit past 10**308: no number, so no time
    data = f"1\n00:00:01,000 --> {huge}:00:02,000\nx\n"
    assert subverter.read("srt", data.encode(), "a.srt").cues == (Cue(1000, None, "x"),)


# a WebVTT file's signature (W3C WebVTT, "WebVTT parser algorithm"): "WEBVTT" first -- one BOM
# before it, decoded away -- then a space, a tab or the line's end; else the file is not
# processed, as Chromium 141 reads none of its cues (VLC 3 refuses each unless forced; ffmpeg
# reads one whose first block opens WEBVTT, NOTE, STYLE or REGION, or is a cue -- any other, none)
_UNSIGNED: Final = "not a WebVTT file: a.vtt (its first line is not WEBVTT)"


@pytest.mark.parametrize(
    ("head", "kept"),
    [
        ("WEBVTT\n\n", True),
        ("WEBVTT\n", True),
        ("WEBVTT - a title\n\n", True),
        ("WEBVTT\ta title\n\n", True),
        ("WEBVTT FILE\n\n", True),
        ("\ufeffWEBVTT\n\n", True),
        ("WEBVTT\r\n\r\n", True),
        ("", False),
        ("WEBVTTX\n\n", False),
        ("WEBVTT-title\n\n", False),
        ("WEBVTT:\n\n", False),
        ("webvtt\n\n", False),
        ("Webvtt\n\n", False),
        (" WEBVTT\n\n", False),
        ("\nWEBVTT\n\n", False),
        ("WEBVTT\xa0x\n\n", False),
        ("WEBVTT\x0cx\n\n", False),
        ("\ufeff\ufeffWEBVTT\n\n", False),
        ("NOTE x\n\nWEBVTT\n\n", False),
    ],
)
def test_a_webvtt_file_opens_with_its_signature_else_it_is_refused(head: str, kept: bool) -> None:
    data = f"{head}00:01.000 --> 00:02.000\nfirst\n".encode()
    if kept:
        assert subverter.read("vtt", data, "a.vtt").cues == (Cue(1000, 2000, "first"),)
    else:
        with pytest.raises(subverter.Error, match=re.escape(_UNSIGNED)):
            _ = subverter.read("vtt", data, "a.vtt")


@pytest.mark.parametrize(
    "data",
    [
        b"",  # shorter than its signature
        b"\xef\xbb\xbf",  # a BOM alone
    ],
)
def test_an_empty_webvtt_file_is_refused(data: bytes) -> None:
    with pytest.raises(subverter.Error, match=re.escape(_UNSIGNED)):
        _ = subverter.read("vtt", data, "a.vtt")


@pytest.mark.parametrize("data", [b"WEBVTT", b"WEBVTT\n", b"WEBVTT\r"])
def test_a_signed_webvtt_file_of_no_cue_is_read_as_none(data: bytes) -> None:
    assert subverter.read("vtt", data, "a.vtt").cues == ()


# --- encodings: SubRip's UTF-8, or UTF-16 by its BOM, as ffmpeg 8.1.2's reader recodes it
# (``ff_text_init_avio``; VLC 3 alike); WebVTT's UTF-8 alone (W3C: "UTF-8 decode")

_CAFE: Final = "1\r\n00:00:01,000 --> 00:00:02,000\r\ncafé 😀\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nnext\r\n"


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_a_subrip_file_in_utf16_by_its_bom_reads_as_in_utf8(codec: str) -> None:
    bom = b"\xff\xfe" if codec.endswith("le") else b"\xfe\xff"
    data = bom + _CAFE.encode(codec)
    assert subverter.read("srt", data, "a.srt") == subverter.read("srt", _CAFE.encode(), "a.srt")


# a lone surrogate (ffmpeg's reader stops there, the cue lost), a unit's lone byte at the end
# (ffmpeg reads it as a character): refused by its line, as an ASS's (ffman's "ASS UTF-16")
_LONE: Final = _CAFE.replace("next", "ne\ud800xt").encode("utf-16-le", "surrogatepass")


@pytest.mark.parametrize(
    ("data", "line"),
    [
        pytest.param(b"\xff\xfe" + _LONE, 7, id="a lone surrogate"),
        pytest.param(b"\xff\xfe" + _CAFE.encode("utf-16-le") + b"x", 8, id="an odd byte"),
        pytest.param(  # its lines SubRip's: CR CR LF one end
            b"\xfe\xff" + "1\r\r\nx\udc00".encode("utf-16-be", "surrogatepass"), 2, id="BE"
        ),
    ],
)
def test_a_subrip_files_unit_not_utf16_is_refused_by_its_line(data: bytes, line: int) -> None:
    with pytest.raises(subverter.Error, match=re.escape(f"not UTF-16: a.srt (line {line})")):
        _ = subverter.read("srt", data, "a.srt")


def test_a_nul_in_a_utf16_subrip_reads_as_u_fffd_noted() -> None:
    data = b"\xff\xfe" + "1\n00:00:01,000 --> 00:00:02,000\na\0b\n".encode("utf-16-le")
    reading = subverter.read("srt", data, "a.srt")
    assert (reading.cues, reading.notes) == (
        (Cue(1000, 2000, "a\ufffdb"),),
        ("1 NULs read as U+FFFD, as the W3C reads them: the first in line 3",),
    )


@pytest.mark.parametrize("bom", [b"\xff\xfe", b"\xfe\xff"], ids=["LE", "BE"])
def test_a_webvtt_file_in_utf16_is_refused_so_named(bom: bytes) -> None:
    codec = "utf-16-le" if bom == b"\xff\xfe" else "utf-16-be"
    data = bom + "WEBVTT\n\n00:01.000 --> 00:02.000\nx\n".encode(codec)
    with pytest.raises(
        subverter.Error, match=r"^not a WebVTT file: a\.vtt \(UTF-16: WebVTT is UTF-8\)$"
    ):
        _ = subverter.read("vtt", data, "a.vtt")


def test_a_no_break_space_after_a_subrip_arrow_is_no_blank() -> None:
    # ffmpeg 8.1.2 (measured): the line is text, as any character but C's blanks
    line = "00:00:03,000 -->\u00a000:00:04,000"
    data = f"1\n00:00:01,000 --> 00:00:02,000\na\n{line}\n"
    assert subverter.read("srt", data.encode(), "a.srt").cues == (Cue(1000, 2000, f"a {line}"),)


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_a_subrip_arrows_blanks_are_read_in_linear_time(blank: str) -> None:
    # a run of blanks, an arrow not right after it: ``[ \t]*-->`` scans the run again from each
    # blank (36 s here)
    line = f"{blank * 200_000}x --> y"
    data = f"1\n00:00:01,000 --> 00:00:02,000\na\n{line}\n"
    began = time.monotonic()
    assert subverter.read("srt", data.encode(), "a.srt").cues == (Cue(1000, 2000, f"a {line}"),)
    assert time.monotonic() - began < 1


@pytest.mark.parametrize(
    "line",
    [
        "00:00:03,000\t-->\t00:00:04,000",  # tabs round the arrow
        "00:00:03,000 --> 00:00:04,000 --> 00:00:05,000",  # its first arrow
        "00:00:03,000\f-->\v00:00:04,000",  # C's other blanks, sscanf's (before: text)
    ],
)
def test_a_subrip_timing_lines_arrow_is_its_first_blanks_round_it(line: str) -> None:
    # as ffmpeg 8.1.2 reads them (measured)
    data = f"1\n00:00:01,000 --> 00:00:02,000\na\n\n2\n{line}\nb\n"
    cues = (Cue(1000, 2000, "a"), Cue(3000, 4000, "b"))
    assert subverter.read("srt", data.encode(), "a.srt").cues == cues


@pytest.mark.parametrize(
    "head",
    ["WEBVTT a --> b\n", "WEBVTT 00:00.000 --> 00:00.500\nheader?\n"],
)
def test_a_webvtt_signature_line_is_skipped_whole(head: str) -> None:
    # Chromium 141 reads the one cue: an arrow on the signature's line no timing line, no drop
    data = f"{head}\n00:01.000 --> 00:02.000\nfirst\n"
    reading = subverter.read("vtt", data.encode(), "a.vtt")
    assert (reading.cues, reading.notes) == ((Cue(1000, 2000, "first"),), ())


def test_a_webvtt_hour_past_a_double_is_no_time() -> None:
    huge = "9" * 400  # the W3C reads hours of any digits; past 10**308, no time
    data = f"WEBVTT\n\n00:01.000 --> {huge}:00:02.000\nx\n"
    assert subverter.read("vtt", data.encode(), "a.vtt").cues == (Cue(1000, None, "x"),)


@pytest.mark.parametrize(
    ("text", "read"),
    [
        # a side that is no time: the line is text -- awk read "Note: 1" as 1 s, "xx" as 0
        ("The sign said:\nNote: 1 --> 2\nand then", "The sign said: Note: 1 --> 2 and then"),
        ("a --> b\nc", "a --> b c"),
        ("xx:00:01,000 --> 00:00:02,000", "xx:00:01,000 --> 00:00:02,000"),
        ("00:00:01,000 -->", "00:00:01,000 -->"),
        ("1:2:3:4 --> 5", "1:2:3:4 --> 5"),
    ],
)
def test_a_subrip_line_whose_arrow_has_no_time_each_side_is_text(text: str, read: str) -> None:
    data = f"1\n00:00:01,000 --> 00:00:04,000\n{text}\n\n2\n00:00:05,000 --> 00:00:06,000\nnext\n"
    assert subverter.read("srt", data.encode(), "a.srt").cues == (
        Cue(1000, 4000, read),
        Cue(5000, 6000, "next"),
    )


def test_bash_lenient_timing_lines_are_still_timing_lines() -> None:
    # minutes and seconds alone; a bare number, minutes; either fraction mark; a sign on zero
    # hours (lost, as ffmpeg loses it); spaces; SubRip's coordinates after
    data = "1\n00:01 --> 00:02\na\n\n2\n5 --> 7\nb\n\n3\n 00:00:08.500 --> -00:00:09,000 X1:1\nc\n"
    assert subverter.read("srt", data.encode(), "a.srt").cues == (
        Cue(1000, 2000, "a"),
        Cue(300_000, 420_000, "b"),
        Cue(8500, 9000, "c"),
    )


@pytest.mark.parametrize(
    ("fmt", "data"),
    [
        ("srt", "1\n00:00:01,000 --> 00:00:02,000X1:5\nglued\n"),  # ffmpeg 8.1 reads it a cue
        ("vtt", "WEBVTT\n\n00:01.000 --> 00:02.000align:left\nglued\n"),  # W3C's "remainder"
    ],
)
def test_an_end_glued_to_what_follows_it_ends_where_its_time_does(fmt: str, data: str) -> None:
    assert subverter.read(fmt, data.encode(), f"a.{fmt}").cues == (Cue(1000, 2000, "glued"),)


def test_a_webvtt_line_whose_arrow_has_no_time_each_side_ends_the_cue_its_block_dropped() -> None:
    # W3C WebVTT, "collect a WebVTT block": a line holding "-->" ends the cue's text; its block
    # is a cue only if its timings parse -- else dropped, up to the blank line (Chromium alike)
    data = (
        "WEBVTT\n\n00:01.000 --> 00:04.000\nx\nleft --> right\ny\n\n"
        "00:05.000 --> 00:06.000\nnext\n\n00:07.000 --> 00:08.000\nNOTE a --> b\n"
    )
    assert subverter.read("vtt", data.encode(), "a.vtt").cues == (
        Cue(1000, 4000, "x"),
        Cue(5000, 6000, "next"),
        Cue(7000, 8000, ""),
    )


def test_a_file_without_a_final_newline_loses_no_line() -> None:
    data = b"1\n00:00:01,000 --> 00:00:02,000\nlast"  # no newline after the last line
    assert subverter.read("srt", data, "a.srt").cues == (Cue(1000, 2000, "last"),)


# --- a seconds fraction not of three digits: SubRip's a count of ms, WebVTT's no time

# each case's first odd time on line 2, its timing line
_ODD_SUBRIP: Final = (
    "{n} times had a fraction not of three digits, read as milliseconds as ffmpeg and VLC read"
    " them: the first, {time} on line 2, as {said}"
)

# the huge and long times past 60 characters: quoted by their first 57, then the cut's mark
_CUT: Final = {
    f"00:00:01,{'9' * 400}": f"00:00:01,{'9' * 48}...",
    f"00:00:01,{'1' * 20000}": f"00:00:01,{'1' * 48}...",
}


@pytest.mark.parametrize(
    ("written", "start", "said"),
    [  # ffmpeg 8.1.2's srt demuxer and VLC 3's subtitle module: its digits a count of ms
        ("00:00:01,5", 1005, "1.005 s"),
        ("00:00:01,25", 1025, "1.025 s"),
        ("00:00:01,5000", 6000, "6 s"),
        ("00:00:01.0500", 1500, "1.5 s"),
        ("00:01,5", 1005, "1.005 s"),  # minutes and seconds
        ("00:00:.5", 5, "0.005 s"),  # a fraction alone
        ("00:00:-01,5", -1005, "-1.005 s"),  # its sign the seconds'
        pytest.param(f"00:00:01,{'9' * 400}", None, "no time (past a double's range)", id="huge"),
        pytest.param(f"00:00:01,{'1' * 20000}", None, "no time (past a double's range)", id="long"),
        # three digits, alike either way; no fraction to read so: no note
        ("00:00:01,500", 1500, None),
        ("00:00:01,050", 1050, None),
        ("00:00:01,", 1000, None),
        ("00:00:01.5e0", 1500, None),  # an exponent: a decimal
        ("00:00.5:01,000", 31000, None),  # a fraction of minutes: a decimal
        ("1.5", 90000, None),  # minutes alone
    ],
)
def test_a_subrip_fraction_not_of_three_digits_is_a_count_of_ms_noted(
    written: str, start: int | None, said: str | None
) -> None:
    data = f"1\n{written} --> 00:00:09,000\nx\n"
    began = time.monotonic()
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert time.monotonic() - began < 1  # a long fraction read in bounded work
    quoted = _CUT.get(written, written)
    notes = () if said is None else (_ODD_SUBRIP.format(n=1, time=quoted, said=said),)
    assert (reading.cues, reading.notes) == ((Cue(start, 9000, "x"),), notes)


def test_subrip_odd_fractions_counted_the_first_named() -> None:
    data = "1\n00:00:01,5 --> 00:00:02,25\na\n\n2\n00:00:03,5000 --> 00:00:09.5\nb\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(1005, 2025, "a"), Cue(8000, 9005, "b"))
    assert reading.notes == (_ODD_SUBRIP.format(n=4, time="00:00:01,5", said="1.005 s"),)


_DROPPED: Final = (
    "{n} cues dropped: a line holding --> that is no WebVTT timing line (W3C), the first {line} "
    "on line {at}"
)


def test_a_webvtt_fraction_not_of_three_digits_drops_its_cue_noted() -> None:
    # W3C WebVTT, "collect a WebVTT timestamp": not exactly three digits, an error -- the
    # timings do not parse, the block dropped (Chromium 141 alike); ffmpeg reads them as ms
    data = (
        "WEBVTT\n\n00:00.000 --> 00:01.000\nok\n00:01.000 --> 00:02.5 align:start\na\n\n"
        "00:03.000 --> 00:04.5000\nb\nmore\n\n00:05.000 --> 00:06.000\nc\n"
    )
    reading = subverter.read("vtt", data.encode(), "a.vtt")
    assert reading.cues == (Cue(0, 1000, "ok"), Cue(5000, 6000, "c"))
    assert reading.notes == (_DROPPED.format(n=2, line="00:01.000 --> 00:02.5 align:start", at=5),)


# each timing line as Chromium 141 reads it (W3C WebVTT, "collect WebVTT cue timings and
# settings"): its cue's start and end, or none -- the block dropped. Lenient: ffmpeg 8.1.2's
# webvtt demuxer reads it (VLC 3 too, but a sign and 100:00.000); at the other forms ffmpeg
# loses the rest of the file. VLC also needs a space each side of the arrow
_TIMINGS: Final = {
    "00:01.000 --> 00:02.000": (1000, 2000),
    "0:00:01.000 --> 0:00:02.000": (1000, 2000),  # hours of any digits
    "100:00:00.000 --> 100:00:01.000": (360_000_000, 360_001_000),
    "00:01.000-->00:02.000": (1000, 2000),  # whitespace optional
    " 00:01.000\t-->\t00:02.000": (1000, 2000),
    "\f00:01.000\f-->\f00:02.000": (1000, 2000),  # a form feed: ASCII whitespace
    "01:02:03.004 --> 01:02:03.005": (3_723_004, 3_723_005),
    "59:59.998 --> 59:59.999": (3_599_998, 3_599_999),
    "00:01.000 --> 00:02.000garbage": (1000, 2000),  # the remainder: settings, ignored
    "00:01.000 --> 00:02.000.500": (1000, 2000),
    "5 --> 7": None,  # bash's minutes
    "1.5 --> 2.5": None,
    "-00:01.000 --> 00:02.000": None,  # lenient: a sign
    "+00:01.000 --> 00:02.000": None,  # lenient
    "0:01.000 --> 0:02.000": None,  # lenient: one digit, hours needing their seconds
    "00:1.000 --> 00:2.000": None,  # lenient
    "00:75.000 --> 00:76.000": None,  # lenient: past 59
    "00:60:00.000 --> 00:60:01.000": None,  # lenient
    "75:00.000 --> 75:01.000": None,  # lenient as minutes: hours, needing their seconds
    "100:00.000 --> 100:01.000": None,  # lenient
    "00:01 --> 00:02": None,  # no fraction
    "00:01. --> 00:02.": None,
    "00:01.5 --> 00:02.5": None,  # lenient: a short fraction (as ms)
    "00:01.0000 --> 00:02.0000": None,  # lenient: three digits read, the rest ignored
    "00:01.0e1 --> 00:02.000": None,  # lenient: the exponent ignored (bash's: 10 s)
    "00:01,000 --> 00:02,000": None,
    "\u0660\u0660:\u0660\u0661.\u0660\u0660\u0660 --> 00:02.000": None,  # ASCII digits alone
    "\uff10\uff10:\uff10\uff11.\uff10\uff10\uff10 --> 00:02.000": None,
    "00:0_1.000 --> 00:02.000": None,
    "00:01 .000 --> 00:02.000": None,
}


@pytest.mark.parametrize(("line", "times"), list(_TIMINGS.items()))
def test_a_webvtt_timing_line_is_the_w3cs_else_its_block_dropped_noted(
    line: str, times: tuple[int, int] | None
) -> None:
    data = f"WEBVTT\n\n{line}\nfirst\n\n00:05.000 --> 00:06.000\nsecond\n"
    reading = subverter.read("vtt", data.encode(), "a.vtt")
    kept = (Cue(*times, "first"),) if times else ()
    assert reading.cues == (*kept, Cue(5000, 6000, "second"))
    dropped = () if times else (_DROPPED.format(n=1, line=line.strip(), at=3),)
    assert reading.notes == dropped


class _TimestampError(Exception):
    """W3C WebVTT's "return an error"."""


def _digits(line: str, at: int, width: int = 0) -> tuple[int, int]:
    """ASCII digits from ``at``, at least one -- exactly ``width``, if given: value, end."""
    end = at
    while end < len(line) and line[end] in "0123456789":
        end += 1
    if end == at or (width and end - at != width):
        raise _TimestampError
    return int(line[at:end]), end


def _mark(line: str, at: int, mark: str) -> int:
    """Past ``mark`` at ``at``, or an error."""
    if line[at : at + len(mark)] != mark:
        raise _TimestampError
    return at + len(mark)


def _blanks(line: str, at: int) -> int:
    """W3C's "skip whitespace", in a line."""
    while at < len(line) and line[at] in " \t\f":
        at += 1
    return at


def _timestamp(line: str, at: int) -> tuple[int, int]:
    """W3C WebVTT's "collect a WebVTT timestamp", step by step: the time in ms, where it ends."""
    value1, end = _digits(line, at)
    hours = end - at != 2 or value1 > 59
    value2, end = _digits(line, _mark(line, end, ":"), 2)
    if hours or line[end : end + 1] == ":":
        value3, end = _digits(line, _mark(line, end, ":"), 2)
    else:
        value1, value2, value3 = 0, value1, value2
    fraction, end = _digits(line, _mark(line, end, "."), 3)
    if value2 > 59 or value3 > 59:
        raise _TimestampError
    return ((value1 * 60 + value2) * 60 + value3) * 1000 + fraction, end


def _w3c_timings(line: str) -> tuple[int, int] | None:
    """W3C WebVTT's "collect WebVTT cue timings and settings", step by step: start and end."""
    try:
        start, at = _timestamp(line, _blanks(line, 0))
        end, _ = _timestamp(line, _blanks(line, _mark(line, _blanks(line, at), "-->")))
    except _TimestampError:
        return None
    return start, end


# what a timing line is made of, well and badly: digits of every length, its marks, blanks
_TIMING_PARTS: Final = (
    "0",
    "5",
    "00",
    "59",
    "60",
    "100",
    ":",
    ".",
    "000",
    "-",
    "+",
    ",",
    "e1",
    " ",
)


@given(
    st.lists(st.sampled_from(_TIMING_PARTS), max_size=8).map("".join),
    st.sampled_from(("-->", " --> ", "\t-->", "-- >")),
    st.lists(st.sampled_from((*_TIMING_PARTS, "\f", "x")), max_size=8).map("".join),
)
def test_a_webvtt_timing_line_is_read_as_the_w3c_reads_it(
    left: str, arrow: str, right: str
) -> None:
    line = left + arrow + right
    reading = subverter.read("vtt", f"WEBVTT\n\n{line}\nx\n".encode(), "a.vtt")
    times = _w3c_timings(line)
    assert reading.cues == ((Cue(*times, "x"),) if times else ())
    assert len(reading.notes) == (0 if times or "-->" not in line else 1)


# --- SubRip: a number alone right before a timing line, in a cue, is the next cue's index

_T1: Final = "00:00:01,000 --> 00:00:02,000"
_T2: Final = "00:00:03,000 --> 00:00:04,000"
_INDEX_NOTE: Final = (
    "{n} lines of a number alone before a timing line read as the next cue's index, as ffmpeg"
    " reads them: the first, {number} on line {line}"
)


@pytest.mark.parametrize(
    ("line", "first", "number"),
    [  # ffmpeg 8.1.2's srt demuxer drops each of the first three (measured)
        ("2", "first", "2"),
        (" 02 ", "first", "02"),
        ("\t7", "first", "7"),
        # no number alone: text -- ffmpeg drops the first three too (a number first), not -2
        ("3 apples", "first 3 apples", None),
        ("2.", "first 2.", None),
        ("+2", "first +2", None),
        ("-2", "first -2", None),
        ("\uff12", "first \uff12", None),  # a fullwidth 2: no ASCII digit
    ],
)
def test_a_number_alone_before_a_subrip_timing_line_is_the_next_index_noted(
    line: str, first: str, number: str | None
) -> None:
    data = f"1\n{_T1}\nfirst\n{line}\n{_T2}\nsecond\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(1000, 2000, first), Cue(3000, 4000, "second"))
    notes = () if number is None else (_INDEX_NOTE.format(n=1, number=number, line=4),)
    assert reading.notes == notes


def test_subrip_indexes_without_a_blank_line_counted_a_cue_of_one_index_line_empty() -> None:
    # a cue whose only line is a number: emptied, as ffmpeg's (its packet dropped, measured)
    t3 = "00:00:05,000 --> 00:00:06,000"
    data = f"1\n{_T1}\n2\n{_T2}\nsecond\n3\n{t3}\nthird\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (
        Cue(1000, 2000, ""),
        Cue(3000, 4000, "second"),
        Cue(5000, 6000, "third"),
    )
    assert reading.notes == (_INDEX_NOTE.format(n=2, number="2", line=3),)


@pytest.mark.parametrize(
    ("text", "first"),
    [
        ("first\n2", "first 2"),  # no timing line after it: the file's end
        ("first\n2\na --> b", "first 2 a --> b"),  # a line holding --> is no timing line
    ],
)
def test_a_number_not_right_before_a_subrip_timing_line_is_text(text: str, first: str) -> None:
    data = f"1\n{_T1}\n{text}\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert (reading.cues[0], reading.notes) == (Cue(1000, 2000, first), ())


# SubRip, as ffmpeg 8.1.2 reads it (measured, its ASS): its demuxer skips an empty line, so a
# cue's text runs on to the next timing line, its last line the next cue's index if a number
# alone, only empty lines after it; a tab, text. Its decoder ends the text at a line of spaces
# (htmlsubtitles.c), MPC-HC and Subtitle Edit reading on: read on here, as past an empty line
_CONTINUED_NOTE: Final = (
    "{n} cues held text after an empty line, read as theirs, as ffmpeg reads them: the first,"
    " {text} on line {line}"
)
_SPACED_NOTE: Final = (
    "{n} cues held text after a line of spaces, read as theirs, as MPC-HC and Subtitle Edit"
    " read them (ffmpeg's decoder drops it): the first, {text} on line {line}"
)


@pytest.mark.parametrize(
    ("text", "first", "notes"),
    [
        (
            "first\n\nstray\n\n2",
            "first stray",
            (_CONTINUED_NOTE.format(n=1, text="stray", line=5),),
        ),
        (
            "first\n\n\n\nstray one\nstray two\n\nstray three\n\n2",
            "first stray one stray two stray three",
            (_CONTINUED_NOTE.format(n=1, text="stray one", line=7),),
        ),
        ("first\n\n2024\n\n3", "first 2024", (_CONTINUED_NOTE.format(n=1, text="2024", line=5),)),
        ("first\n\n2\n", "first", ()),  # the index, empty lines either side of it
        ("first\n2\n", "first", (_INDEX_NOTE.format(n=1, number="2", line=4),)),
        ("the year\n2024\n", "the year", (_INDEX_NOTE.format(n=1, number="2024", line=4),)),
        (  # ffmpeg: `first`, its decoder ending the text at the spaces (measured)
            "first\n   \nsecond line\n\n2",
            "first second line",
            (_SPACED_NOTE.format(n=1, text="second line", line=5),),
        ),
        (
            "first\n\n   \nafter spaces\n\n2",
            "first after spaces",
            (_SPACED_NOTE.format(n=1, text="after spaces", line=6),),
        ),
        ("   \nfirst", "first", (_SPACED_NOTE.format(n=1, text="first", line=4),)),  # ffmpeg: ``
        (  # ffmpeg: `first\Nkept`; each kind noted
            "first\n\nkept\n   \nlost\n\n2",
            "first kept lost",
            (
                _CONTINUED_NOTE.format(n=1, text="kept", line=5),
                _SPACED_NOTE.format(n=1, text="lost", line=7),
            ),
        ),
        (  # after a line of spaces, an empty line noted no more: one note, the spaces'
            "first\n   \nlost\n\nmore\n\n2",
            "first lost more",
            (_SPACED_NOTE.format(n=1, text="lost", line=5),),
        ),
        ("first\n   \n2", "first", ()),  # the index after spaces: a cue's end written loosely
        ("first\n2\n   ", "first 2", ()),  # the spaces after `2`: its text, no index, as ffmpeg's
        (  # the same after spaces: `2` text, not an index -- ffmpeg: `first`
            "first\n   \n2\n   ",
            "first 2",
            (_SPACED_NOTE.format(n=1, text="2", line=5),),
        ),
        (  # a timing line ffmpeg cannot read: its cue the one before's, as ffmpeg's (measured)
            "first\n\n2\n00:00:02,500 -> 00:00:02,800\ncut",
            "first 2 00:00:02,500 -> 00:00:02,800 cut",
            (_CONTINUED_NOTE.format(n=1, text="2", line=5),),
        ),
        ("first\n\t\nsecond\n\n2", "first \t second", ()),
        ("first\n \t \nsecond\n\n2", "first  \t  second", ()),
    ],
)
def test_a_subrip_cue_runs_on_past_a_blank_line(
    text: str, first: str, notes: tuple[str, ...]
) -> None:
    data = f"1\n{_T1}\n{text}\n{_T2}\nsecond\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(1000, 2000, first), Cue(3000, 4000, "second"))
    assert reading.notes == notes


def test_a_subrip_cue_of_no_text_takes_no_index_from_the_cue_before() -> None:
    # ffmpeg: `first\N2024`, the empty cue dropped, `third` (measured): `2024` its cue's text,
    # that cue ended by the spaces
    t3 = "00:00:05,000 --> 00:00:06,000"
    data = f"1\n{_T1}\nfirst\n2024\n   \n2\n{_T2}\n{t3}\nthird\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (
        Cue(1000, 2000, "first 2024"),
        Cue(3000, 4000, ""),
        Cue(5000, 6000, "third"),
    )
    assert reading.notes == ()


def test_a_subrip_files_last_cue_runs_to_its_end() -> None:
    # ffmpeg: `last\nSubtitles by X`, the credits after the last cue its text (measured)
    data = f"1\n{_T1}\nfirst\n\n2\n{_T2}\nlast\n\nSubtitles by X\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(1000, 2000, "first"), Cue(3000, 4000, "last Subtitles by X"))
    assert reading.notes == (_CONTINUED_NOTE.format(n=1, text="Subtitles by X", line=9),)


@pytest.mark.parametrize(
    ("line", "first"),
    [
        ("", "first"),
        ("   ", "first     second"),
        ("\t", "first \t second"),
        (" \t ", "first  \t  second"),
    ],
)
def test_only_an_empty_line_ends_a_webvtt_cue(line: str, first: str) -> None:
    # "collect a WebVTT block" ends at an empty line alone: Chromium 141 reads `first\n   \nsecond`
    # (measured), its lines joined here by a space; after an empty line, no cue's
    data = f"WEBVTT\n\n00:01.000 --> 00:02.000\nfirst\n{line}\nsecond\n\n00:03.000 --> 00:04.000\nnext\n"
    assert subverter.read("vtt", data.encode(), "a.vtt").cues == (
        Cue(1000, 2000, first),
        Cue(3000, 4000, "next"),
    )


def test_a_webvtt_line_before_a_timing_line_is_text() -> None:
    # W3C WebVTT, "collect a WebVTT block": the lines before a later --> line stay the cue's
    # text (Chromium 141: "first\n2", measured)
    data = "WEBVTT\n\n00:01.000 --> 00:02.000\nfirst\n2\n00:03.000 --> 00:04.000\nsecond\n"
    reading = subverter.read("vtt", data.encode(), "a.vtt")
    assert (reading.cues, reading.notes) == (
        (Cue(1000, 2000, "first 2"), Cue(3000, 4000, "second")),
        (),
    )


_STRAY: Final = (
    "{n} text blocks dropped: after an empty line, in no cue (W3C), the first {text} on line {at}"
)
_HEAD: Final = "WEBVTT\n\n00:01.000 --> 00:02.000\nfirst\n\n"  # a cue, ended at line 5


@pytest.mark.parametrize(
    ("after", "cues", "notes"),
    [
        # "collect a WebVTT block": a block holding no --> line is no cue -- dropped (Chromium 141,
        # measured), counted, the first named
        ("second\n\n00:03.000 --> 00:04.000\nnext\n", 2, ((1, "second", 6),)),
        ("second\nmore\n\nthird\n", 1, ((2, "second", 6),)),
        ("credits\n", 1, ((1, "credits", 6),)),
        ("   \n  second\n", 1, ((1, "second", 7),)),  # named by its first text
        # a line alone before a line holding -->: the next cue's identifier (line count 2)
        ("id\n00:03.000 --> 00:04.000\nnext\n", 2, ()),
        ("id\nnot a time --> x\nlost\n", 1, ()),  # the cue dropped, noted alone (_DROPPED)
        # two before it: no identifier (line count 3), dropped; the cue read
        ("a\nb\n00:03.000 --> 00:04.000\nnext\n", 2, ((1, "a", 6),)),
        # a comment, a style sheet, a region: no text (the syntax's blocks); a NOTE needs a
        # space, a tab or its line's end after it, STYLE and REGION spaces or tabs alone
        ("NOTE a comment\n\nNOTE\nlines\n\nSTYLE\n::cue {}\n\nREGION \t\nid:r\n", 1, ()),
        ("NOTES\n\nSTYLE x\n", 1, ((2, "NOTES", 6),)),
        ("   \n\t\n", 1, ()),  # blanks alone: nothing lost
    ],
)
def test_webvtt_text_in_no_cue_is_dropped_noted(
    after: str, cues: int, notes: tuple[tuple[int, str, int], ...]
) -> None:
    reading = subverter.read("vtt", (_HEAD + after).encode(), "a.vtt")
    dropped = (_DROPPED.format(n=1, line="not a time --> x", at=7),) if "lost" in after else ()
    stray = tuple(_STRAY.format(n=n, text=text, at=at) for n, text, at in notes)
    assert (len(reading.cues), reading.notes) == (cues, dropped + stray)


def test_webvtt_text_after_a_dropped_first_cue_is_noted() -> None:
    # the first block holding --> is past the header and any title, its cue dropped or not
    data = "WEBVTT\n\n00:01,000 --> 00:02,000\nx\n\nstray\n\n00:03.000 --> 00:04.000\nnext\n"
    reading = subverter.read("vtt", data.encode(), "a.vtt")
    assert (reading.cues, reading.notes) == (
        (Cue(3000, 4000, "next"),),
        (
            _DROPPED.format(n=1, line="00:01,000 --> 00:02,000", at=3),
            _STRAY.format(n=1, text="stray", at=6),
        ),
    )


@pytest.mark.parametrize(
    ("data", "notes"),
    [
        ("WEBVTT\nKind: captions\nLanguage: en\n\n00:01.000 --> 00:02.000\nx\n", ()),  # its header
        ("WEBVTT\n\nA title\n\nmore\n\n00:01.000 --> 00:02.000\nx\n", ()),  # before any cue
        (  # `two` the dropped block's, noted with it
            "WEBVTT\n\n00:01.000 --> 00:02.000\none\nNote: 1 --> 2\ntwo\n",
            (_DROPPED.format(n=1, line="Note: 1 --> 2", at=5),),
        ),
    ],
)
def test_webvtt_text_before_any_cue_or_after_an_arrow_is_not_stray(
    data: str, notes: tuple[str, ...]
) -> None:
    assert subverter.read("vtt", data.encode(), "a.vtt").notes == notes


# --- whole files: WebVTT's as the W3C's parser reads them; SubRip's as ffmpeg's demuxer, but
# for subverter's recorded readings -- each transcribed, its cues compared on generated files


def _w3c_block(lines: list[str], k: int, *, header: bool) -> tuple[int, Cue | None]:
    """W3C WebVTT's "collect a WebVTT block" from line ``k``: the line after it, its cue or None.

    ``previous position`` is a line's start: after the last line taken, or after the timing line.
    """
    count, seen_arrow, previous, cue = 0, False, k, None
    text: list[str] = []
    while k < len(lines):
        line = lines[k]
        count, k = count + 1, k + 1
        if "-->" in line:
            if header or not (count == 1 or (count == 2 and not seen_arrow)):
                k = previous
                break
            seen_arrow, previous = True, k
            times = _w3c_timings(line)
            cue = None if times is None else Cue(*times, "")
            text = [] if times else text
        elif not line:
            break
        else:
            text.append(line)
            previous = k
    return k, (None if cue is None else Cue(cue.start, cue.end, " ".join(text)))


def _w3c_cues(text: str) -> tuple[Cue, ...] | None:
    """W3C WebVTT's "WebVTT parser algorithm": its cues, lines joined by a space; None, unread."""
    whole = text.replace("\r\n", "\n").replace("\r", "\n")
    if whole[:6] != "WEBVTT" or whole[6:7] not in ("", " ", "\t", "\n"):
        return None
    lines = whole.split("\n")
    lines = lines[:-1] if lines[-1] == "" else lines  # its last LF ends the input
    k, cues = 1, list[Cue]()
    if k < len(lines) and lines[k]:  # "Header"
        k, _ = _w3c_block(lines, k, header=True)
    while k < len(lines):  # "Block loop", after each block its LFs
        if not lines[k]:
            k += 1
            continue
        k, cue = _w3c_block(lines, k, header=False)
        cues += [cue] if cue else []
    return tuple(cues)


# what a WebVTT file is made of: timing lines good and bad, its blocks' words, blanks
_VTT_LINES: Final = (
    "",
    "00:01.000 --> 00:02.000",
    "00:00:03.000-->00:00:04.000 align:start",
    "\t00:05.000\t-->\t00:06.000",
    "00:01,000 --> 00:02,000",
    "00:01.5 --> 00:02.000",
    "60:00.000 --> 61:00.000",
    "a --> b",
    "NOTE x",
    "STYLE",
    "REGION",
    "WEBVTT",
    "a",
    "b c",
    "2",
    " ",
    "\t",
)


@settings(max_examples=1000)  # cheap, and each rule's case needs its lines in a row
@given(
    st.sampled_from(("WEBVTT", "WEBVTT - title", "WEBVTT\tx", "WEBVTTx", "webvtt")),
    st.lists(st.tuples(st.sampled_from(_VTT_LINES), st.sampled_from(("\n", "\r\n", "\r")))),
)
def test_a_webvtt_files_cues_are_the_w3cs(head: str, lines: list[tuple[str, str]]) -> None:
    text = head + "\n" + "".join(line + end for line, end in lines)
    cues = _w3c_cues(text)
    if cues is None:
        with pytest.raises(subverter.Error, match="not a WebVTT file"):
            _ = subverter.read("vtt", text.encode(), "a.vtt")
    else:
        assert subverter.read("vtt", text.encode(), "a.vtt").cues == cues


_SRT_TIMING: Final = re.compile(r"(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})")
_NUMBER_ALONE: Final = re.compile(r"[ \t]*[0-9]+[ \t]*")  # Index lines: ASCII digits, blanks


def _ffmpeg_srt(text: str) -> tuple[Cue, ...]:
    """ffmpeg 8.1's srt demuxer, ``srt_read_header`` (srtdec.c), on lines ended by LFs, transcribed
    -- but for subverter's recorded readings: a line of spaces alone no text (Cue ends), a
    number alone the only index it holds back (Index lines), a cue of no text kept (ffman drops
    it). Its timing lines the canonical ones (``get_event_info``)."""
    cues: list[Cue] = []
    times: tuple[int, int] | None = None
    held: str | None = None  # ``line_cache``
    lines: list[str] = []
    for line in text.split("\n"):
        if not line:
            continue
        found = _SRT_TIMING.fullmatch(line)
        if found is None:
            if times is None:
                continue
            if held is not None:  # another line after it: the payload's
                lines.append(held)
                held = None
            if _NUMBER_ALONE.fullmatch(line):
                held = line
            elif line.strip(" "):
                lines.append(line)
            continue
        if times is not None:  # the line held back dropped: an index
            cues.append(Cue(*times, " ".join(lines)))
        h1, m1, s1, f1, h2, m2, s2, f2 = map(int, found.groups())
        times = ((h1 * 60 + m1) * 60 + s1) * 1000 + f1, ((h2 * 60 + m2) * 60 + s2) * 1000 + f2
        held, lines = None, []
    if times is not None:  # the last: a number held back is its text
        cues.append(Cue(*times, " ".join([*lines, *([held] if held else [])])))
    return tuple(cues)


# what a SubRip file is made of: indexes, timing lines, numbers, blanks, texts
_SRT_LINES: Final = (
    "",
    "1",
    "12",
    " 7 ",
    "\t3",
    "2024",
    "3 apples",
    "+2",
    "-1",
    "2.",
    " ",
    "   ",
    "\t",
    "a",
    "b c",
    "x --> y",
    "00:00:01,000 --> 00:00:02,000",
    "00:01:00,500 --> 00:01:02,250",
)


@settings(max_examples=1000)  # cheap, and each rule's case needs its lines in a row
@given(st.lists(st.sampled_from(_SRT_LINES)))
def test_a_subrip_files_cues_are_ffmpegs_but_for_the_recorded_readings(lines: list[str]) -> None:
    text = "\n".join(lines)
    assert subverter.read("srt", text.encode(), "a.srt").cues == _ffmpeg_srt(text)


# --- WhisperX --highlight_words: by structure, a run of one text a sentence, each <u> a word


def _srt(cues: list[tuple[str, str, str]]) -> bytes:
    return "".join(f"{n}\n{a} --> {z}\n{t}\n\n" for n, (a, z, t) in enumerate(cues, 1)).encode()


def test_highlighted_cues_become_sentences_and_words() -> None:
    data = _srt(
        [
            ("00:00:00,000", "00:00:00,500", "<u>Hello</u> world"),
            ("00:00:00,500", "00:00:01,000", "Hello <u>world</u>"),
            ("00:00:01,000", "00:00:01,500", "<u>Bye</u> now"),
            ("00:00:01,500", "00:00:02,000", "Bye <u>now</u>"),
        ]
    )
    assert subverter.read("srt", data, "a.srt") == Reading(
        "WhisperX --highlight_words .srt",
        has_words=True,
        cues=(Cue(0, 1000, "Hello world", "0"), Cue(1000, 2000, "Bye now", "1")),
        words=(
            Timing("0", 0, 500, "Hello"),
            Timing("0", 500, 1000, "world"),
            Timing("1", 1000, 1500, "Bye"),
            Timing("1", 1500, 2000, "now"),
        ),
        has_ass_escapes=True,
    )


def test_an_underline_moving_back_starts_a_sentence_of_the_same_text() -> None:
    data = _srt(
        [
            ("00:00:00,000", "00:00:00,500", "<u>la</u> la"),
            ("00:00:00,500", "00:00:01,000", "la <u>la</u>"),
            ("00:00:01,000", "00:00:01,500", "<u>la</u> la"),
        ]
    )
    assert subverter.read("srt", data, "a.srt").cues == (
        Cue(0, 1000, "la la", "0"),
        Cue(1000, 1500, "la la", "1"),
    )


def test_an_underline_alone_is_no_highlighting() -> None:
    # <u> in a cue, but no two neighbours share a text: cues, as written
    data = _srt(
        [
            ("00:00:00,000", "00:00:01,000", "<u>one</u>"),
            ("00:00:01,000", "00:00:02,000", "two"),
        ]
    )
    reading = subverter.read("srt", data, "a.srt")
    assert (reading.has_words, reading.cues) == (
        False,
        (Cue(0, 1000, "<u>one</u>"), Cue(1000, 2000, "two")),
    )


def test_highlighted_a_cue_without_underline_adds_no_word_an_empty_run_no_sentence() -> None:
    data = _srt(
        [
            ("00:00:00,000", "00:00:00,500", "<u>a</u> b"),
            ("00:00:00,500", "00:00:01,000", "a <u>b</u>"),
            ("00:00:01,000", "00:00:01,500", "a b"),  # the same text, no underline: no word
            ("00:00:01,500", "00:00:02,000", ""),  # a run of no text: no sentence
            ("00:00:02,000", "00:00:02,500", ""),
        ]
    )
    reading = subverter.read("srt", data, "a.srt")
    assert reading.cues == (Cue(0, 1500, "a b", "0"),)
    assert reading.words == (Timing("0", 0, 500, "a"), Timing("0", 500, 1000, "b"))


def test_a_highlighted_reading_keeps_its_cues_notes() -> None:
    data = _srt(
        [
            ("00:00:00,5", "00:00:01,000", "<u>a</u> b"),
            ("00:00:01,000", "00:00:02,000", "a <u>b</u>"),
        ]
    )
    reading = subverter.read("srt", data, "a.srt")
    assert (reading.has_words, reading.notes) == (
        True,
        (_ODD_SUBRIP.format(n=1, time="00:00:00,5", said="0.005 s"),),
    )
