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
from hypothesis import example, given, settings
from hypothesis import strategies as st
from subverter import Cue, Reading, Timing

# --- SubRip and WebVTT: a cue opens at its --> line, closes at its format's end line or the next cue


def test_srt_a_bom_and_crs_off_lines_joined_the_last_cue_closed_at_the_end() -> None:
    data = "\ufeff1\r\n00:00:01,000 --> 00:00:02,500\r\nHello\r\nthere\r\n\r\n2\r\n00:00:03,000 --> 00:00:04,000\r\nbye\r\n"
    assert subverter.read("srt", data.encode(), "a.srt") == Reading(
        ".srt",
        has_words=False,
        cues=(Cue(1000, 2500, "Hello\nthere"), Cue(3000, 4000, "bye")),
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
    assert subverter.read("srt", data.encode(), "a.srt").cues == (Cue(1000, 2000, f"a\n{line}"),)


@pytest.mark.parametrize("blank", [" ", "\t"])
def test_a_subrip_arrows_blanks_are_read_in_linear_time(blank: str) -> None:
    # a run of blanks, an arrow not right after it: ``[ \t]*-->`` scans the run again from each
    # blank (36 s here)
    line = f"{blank * 200_000}x --> y"
    data = f"1\n00:00:01,000 --> 00:00:02,000\na\n{line}\n"
    began = time.process_time()
    assert subverter.read("srt", data.encode(), "a.srt").cues == (Cue(1000, 2000, f"a\n{line}"),)
    assert time.process_time() - began < 1


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
        ("The sign said:\nNote: 1 --> 2\nand then", "The sign said:\nNote: 1 --> 2\nand then"),
        ("a --> b\nc", "a --> b\nc"),
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


@pytest.mark.parametrize(
    "line",
    [
        # bash's lenient forms, text now, as ffmpeg 8.1.2 reads them (measured), VLC 3 too (by
        # source): no hours; a bare number, once minutes; a decimal in a part; a blank before a
        # colon
        "00:01 --> 00:02",
        "5 --> 7",
        "2024 --> 2025: what changed",
        "1 --> 2 then 3",
        "1.5:00:00,000 --> 2:00:00,000",
        "00 :00:01,000 --> 00:00:02,000",
        # more after a time's numbers -- an exponent, a fraction's mark without its digits:
        # text as ffmpeg reads it, VLC 3 ignoring what follows (by source)
        "00:00:01.5e0 --> 00:00:02,000",
        "00:00:01, --> 00:00:02,000",
        "00:00:01,000 --> 00:00:02,",
    ],
)
def test_a_subrip_line_whose_times_are_not_hours_minutes_and_seconds_is_text(line: str) -> None:
    data = f"1\n00:00:00,000 --> 00:00:00,500\nfirst\n{line}\nsecond\n"
    assert subverter.read("srt", data.encode(), "a.srt").cues == (
        Cue(0, 500, f"first\n{line}\nsecond"),
    )


@pytest.mark.parametrize(
    ("line", "times"),
    [
        # sscanf's %d each part (ffmpeg's ``get_event_info``): blanks, then a sign, before its
        # digits; each part a whole number, added as written, a sign its own (measured)
        ("00: 00: 01,000 --> 00:00:02,000", (1000, 2000)),
        ("+00:00:01,000 --> 00:00:02,000", (1000, 2000)),
        (" 00:00:08.500 --> -00:00:09,000 X1:1", (8500, 9000)),  # a sign on zero hours lost
        ("-01:30:00,000 --> 02:00:00,000", (-1_800_000, 7_200_000)),
        ("00:00:-01,500 --> 00:00:02,000", (-500, 2000)),
        ("00:00:01, 500 --> 00:00:02,000", (1000 + 500, 2000)),
        ("00:75:00,000 --> 00:75:01,000", (4_500_000, 4_501_000)),  # past 59, read
    ],
)
def test_a_subrip_time_is_hours_minutes_and_seconds_each_whole(
    line: str, times: tuple[int, int]
) -> None:
    data = f"1\n{line}\nx\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert (reading.cues, reading.notes) == ((Cue(*times, "x"),), ())


_BARE: Final = (
    "{n} times had no fraction, read as VLC reads them (ffmpeg reads no such timing line, its"
    " cue lost): the first, {time} on line {line}"
)


@pytest.mark.parametrize(
    ("line", "times", "n", "time"),
    [
        ("00:00:01 --> 00:00:02,000", (1000, 2000), 1, "00:00:01"),
        ("00:00:01,000 --> 00:00:02 X1:5", (1000, 2000), 1, "00:00:02"),
        (" 00:00:01 -->00:00:02", (1000, 2000), 2, "00:00:01"),
    ],
)
def test_a_subrip_time_without_a_fraction_is_read_as_vlc_reads_it_noted(
    line: str, times: tuple[int, int], n: int, time: str
) -> None:
    # VLC 3 reads it (``subtitle_ParseSubRipTimingValue``, by source); ffmpeg 8.1.2's sscanf
    # needs a fraction: the line text, the cue lost (measured)
    data = f"1\n00:00:00,000 --> 00:00:00,500\nfirst\n\n2\n{line}\nx\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(0, 500, "first"), Cue(*times, "x"))
    assert reading.notes == (_BARE.format(n=n, time=time, line=6),)


# C's isspace but the line ends, which end a line first: what sscanf's %d and " " skip
_C_BLANKS: Final = " \t\v\f"


class _ScanfError(Exception):
    """sscanf stopped short of a timing line's eight numbers."""


def _scanf_number(line: str, at: int) -> tuple[int, int]:
    """sscanf's %d at ``at``: blanks skipped, a sign, then one digit or more; its value, its end."""
    while at < len(line) and line[at] in _C_BLANKS:
        at += 1
    start = at
    if at < len(line) and line[at] in "+-":
        at += 1
    digits = at
    while at < len(line) and line[at] in "0123456789":
        at += 1
    if at == digits:
        raise _ScanfError
    return int(line[start:at]), at


def _scanf_time(line: str, at: int) -> tuple[int, int]:
    """``%d:%d:%d%*1[,.]%d``, the fraction optional (VLC 3's): ms, as added; its end."""
    h, at = _scanf_number(line, at)
    for _ in range(2):
        if line[at : at + 1] != ":":
            raise _ScanfError
        value, at = _scanf_number(line, at + 1)
        h = h * 60 + value
    fraction = 0
    if line[at : at + 1] in (",", "."):  # a mark: its number needed
        fraction, at = _scanf_number(line, at + 1)
    return h * 1000 + fraction, at


def _ffmpeg_timing(line: str) -> tuple[int, int] | None:
    """ffmpeg 8.1's ``get_event_info`` (srtdec.c), transcribed: ``%d:%d:%d%*1[,.]%d --> %d:%d:
    %d%*1[,.]%d``, then anything; exact, as no C ``int`` -- and the fraction optional."""
    try:
        start, at = _scanf_time(line, 0)
        end, _ = _scanf_time(line, _scanf_arrow(line, at))
    except _ScanfError:
        return None
    return start, end


def _scanf_arrow(line: str, at: int) -> int:
    """`` --> ``'s first blank and its arrow: any blanks, none too, then ``-->``; past it."""
    while at < len(line) and line[at] in _C_BLANKS:
        at += 1
    if line[at : at + 3] != "-->":
        raise _ScanfError
    return at + 3


# a SubRip time, well and badly made: its numbers (blanks, a sign, digits -- or not), its
# colons, its fraction's mark, what follows it; each part mostly well made (nine in ten), as a
# timing line needs every one of them


def _mostly(well: tuple[str, ...], badly: tuple[str, ...]) -> st.SearchStrategy[str]:
    return st.sampled_from(well * (9 * len(badly) // len(well) + 1) + badly)


_NUMBERS: Final = _mostly(
    ("0", "00", "5", "59", "100", " 5", "\t0", "\f5", "+5", "-5"), ("", "x", "5.5", "1e1", "- 5")
)
_COLONS: Final = _mostly((":",), (" :", "."))
_MARKS: Final = _mostly(("", ",", ".", ", "), (",,", ",-"))
_TAILS: Final = _mostly(("",), (" ", "x", "e0", " X1:5", ",", ":5"))


@st.composite
def _srt_times(draw: st.DrawFn) -> str:
    h, m, s = draw(_NUMBERS), draw(_NUMBERS), draw(_NUMBERS)
    mark = draw(_MARKS)
    fraction = draw(_NUMBERS) if mark else ""
    return f"{h}{draw(_COLONS)}{m}{draw(_COLONS)}{s}{mark}{fraction}{draw(_TAILS)}"


@settings(max_examples=2000)  # cheap, and a timing line needs each of its parts well made
@example("00:00:01,000", " --> ", "00:00:02,x")  # a mark without its number
@example("00:00:01,-500", " --> ", "-01:00:02.5")  # signs, a short fraction
@given(
    _srt_times(),
    st.sampled_from(("-->", " --> ", "\t-->", "-- >", "->", " -->\v", " -->\u00a0")),
    _srt_times(),
)
def test_a_subrip_timing_line_is_read_as_ffmpegs_sscanf_reads_it(
    left: str, arrow: str, right: str
) -> None:
    line = left + arrow + right
    times = _ffmpeg_timing(line)
    reading = subverter.read("srt", f"1\n{line}\nx\n".encode(), "a.srt")
    assert reading.cues == ((Cue(*times, "x"),) if times else ())


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
        ("00:00:01, 5", 1005, "1.005 s"),  # a blank before its digits (sscanf's %d)
        ("00:00:-01,5", -995, "-0.995 s"),  # added, its sign the seconds' own (measured)
        pytest.param(f"00:00:01,{'9' * 400}", None, "no time (past a double's range)", id="huge"),
        pytest.param(f"00:00:01,{'1' * 20000}", None, "no time (past a double's range)", id="long"),
        # three digits, alike either way; no fraction to read so: no note
        ("00:00:01,500", 1500, None),
        ("00:00:01,050", 1050, None),
        ("00:00:01,-500", 500, None),  # signed: 1 - 0.500 s either way
    ],
)
def test_a_subrip_fraction_not_of_three_digits_is_a_count_of_ms_noted(
    written: str, start: int | None, said: str | None
) -> None:
    data = f"1\n{written} --> 00:00:09,000\nx\n"
    began = time.process_time()
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert time.process_time() - began < 1  # a long fraction read in bounded work
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
        ("3 apples", "first\n3 apples", None),
        ("2.", "first\n2.", None),
        ("+2", "first\n+2", None),
        ("-2", "first\n-2", None),
        ("\uff12", "first\n\uff12", None),  # a fullwidth 2: no ASCII digit
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
        ("first\n2", "first\n2"),  # no timing line after it: the file's end
        ("first\n2\na --> b", "first\n2\na --> b"),  # a line holding --> is no timing line
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
            "first\nstray",
            (_CONTINUED_NOTE.format(n=1, text="stray", line=5),),
        ),
        (
            "first\n\n\n\nstray one\nstray two\n\nstray three\n\n2",
            "first\nstray one\nstray two\nstray three",
            (_CONTINUED_NOTE.format(n=1, text="stray one", line=7),),
        ),
        ("first\n\n2024\n\n3", "first\n2024", (_CONTINUED_NOTE.format(n=1, text="2024", line=5),)),
        ("first\n\n2\n", "first", ()),  # the index, empty lines either side of it
        ("first\n2\n", "first", (_INDEX_NOTE.format(n=1, number="2", line=4),)),
        ("the year\n2024\n", "the year", (_INDEX_NOTE.format(n=1, number="2024", line=4),)),
        (  # ffmpeg: `first`, its decoder ending the text at the spaces (measured)
            "first\n   \nsecond line\n\n2",
            "first\nsecond line",
            (_SPACED_NOTE.format(n=1, text="second line", line=5),),
        ),
        (
            "first\n\n   \nafter spaces\n\n2",
            "first\nafter spaces",
            (_SPACED_NOTE.format(n=1, text="after spaces", line=6),),
        ),
        ("   \nfirst", "first", (_SPACED_NOTE.format(n=1, text="first", line=4),)),  # ffmpeg: ``
        (  # ffmpeg: `first\Nkept`; each kind noted
            "first\n\nkept\n   \nlost\n\n2",
            "first\nkept\nlost",
            (
                _CONTINUED_NOTE.format(n=1, text="kept", line=5),
                _SPACED_NOTE.format(n=1, text="lost", line=7),
            ),
        ),
        (  # after a line of spaces, an empty line noted no more: one note, the spaces'
            "first\n   \nlost\n\nmore\n\n2",
            "first\nlost\nmore",
            (_SPACED_NOTE.format(n=1, text="lost", line=5),),
        ),
        ("first\n   \n2", "first", ()),  # the index after spaces: a cue's end written loosely
        ("first\n2\n   ", "first\n2", ()),  # the spaces after `2`: its text, no index, as ffmpeg's
        (  # the same after spaces: `2` text, not an index -- ffmpeg: `first`
            "first\n   \n2\n   ",
            "first\n2",
            (_SPACED_NOTE.format(n=1, text="2", line=5),),
        ),
        (  # a timing line ffmpeg cannot read: its cue the one before's, as ffmpeg's (measured)
            "first\n\n2\n00:00:02,500 -> 00:00:02,800\ncut",
            "first\n2\n00:00:02,500 -> 00:00:02,800\ncut",
            (_CONTINUED_NOTE.format(n=1, text="2", line=5),),
        ),
        ("first\n\t\nsecond\n\n2", "first\n\t\nsecond", ()),
        ("first\n \t \nsecond\n\n2", "first\n \t \nsecond", ()),
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
        Cue(1000, 2000, "first\n2024"),
        Cue(3000, 4000, ""),
        Cue(5000, 6000, "third"),
    )
    assert reading.notes == ()


def test_a_subrip_files_last_cue_runs_to_its_end() -> None:
    # ffmpeg: `last\nSubtitles by X`, the credits after the last cue its text (measured)
    data = f"1\n{_T1}\nfirst\n\n2\n{_T2}\nlast\n\nSubtitles by X\n"
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(1000, 2000, "first"), Cue(3000, 4000, "last\nSubtitles by X"))
    assert reading.notes == (_CONTINUED_NOTE.format(n=1, text="Subtitles by X", line=9),)


@pytest.mark.parametrize(
    ("line", "first"),
    [
        ("", "first"),
        ("   ", "first\n   \nsecond"),
        ("\t", "first\n\t\nsecond"),
        (" \t ", "first\n \t \nsecond"),
    ],
)
def test_only_an_empty_line_ends_a_webvtt_cue(line: str, first: str) -> None:
    # "collect a WebVTT block" ends at an empty line alone: Chromium 141 reads `first\n   \nsecond`
    # (measured); after an empty line, no cue's
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
        (Cue(1000, 2000, "first\n2"), Cue(3000, 4000, "second")),
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
        # space, a tab or its line's end after it, STYLE and REGION ASCII whitespace alone
        ("NOTE a comment\n\nNOTE\nlines\n\nSTYLE\n::cue {}\n\nREGION \t\nid:r\n", 1, ()),
        ("STYLE\f\n::cue {}\n\nREGION\f \nid:r\n", 1, ()),  # a form feed: ASCII whitespace
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
    return k, (None if cue is None else Cue(cue.start, cue.end, "\n".join(text)))


def _w3c_cues(text: str) -> tuple[Cue, ...] | None:
    """W3C WebVTT's "WebVTT parser algorithm": its cues; None, unread."""
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
            cues.append(Cue(*times, "\n".join(lines)))
        h1, m1, s1, f1, h2, m2, s2, f2 = map(int, found.groups())
        times = ((h1 * 60 + m1) * 60 + s1) * 1000 + f1, ((h2 * 60 + m2) * 60 + s2) * 1000 + f2
        held, lines = None, []
    if times is not None:  # the last: a number held back is its text
        cues.append(Cue(*times, "\n".join([*lines, *([held] if held else [])])))
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


# --- OpenAI whisper's and WhisperX's --highlight_words: by structure, a run of one text a sentence, each <u> a word


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
        "OpenAI whisper or WhisperX --highlight_words .srt",
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


# OpenAI whisper's own WriteSRT (openai-whisper v20250625, utils.py, run on a result of two segments
# and their words, highlight_words=True): a cue a word, and one for each gap between words
_OPENAI_HIGHLIGHTED: Final = (
    "1\n00:00:00,000 --> 00:00:00,400\n<u>Hello</u> big world.\n\n"
    "2\n00:00:00,400 --> 00:00:00,500\nHello big world.\n\n"
    "3\n00:00:00,500 --> 00:00:00,800\nHello <u>big</u> world.\n\n"
    "4\n00:00:00,800 --> 00:00:01,500\nHello big <u>world.</u>\n\n"
    "5\n00:00:02,000 --> 00:00:02,400\n<u>Bye</u> now.\n\n"
    "6\n00:00:02,400 --> 00:00:02,500\nBye now.\n\n"
    "7\n00:00:02,500 --> 00:00:03,000\nBye <u>now.</u>\n\n"
)


def test_openai_whispers_highlighted_cues_read_into_sentences_and_words() -> None:
    assert subverter.read("srt", _OPENAI_HIGHLIGHTED.encode(), "a.srt") == Reading(
        "OpenAI whisper or WhisperX --highlight_words .srt",
        has_words=True,
        cues=(Cue(0, 1500, "Hello big world.", "0"), Cue(2000, 3000, "Bye now.", "1")),
        words=(
            Timing("0", 0, 400, "Hello"),
            Timing("0", 500, 800, "big"),
            Timing("0", 800, 1500, "world."),
            Timing("1", 2000, 2400, "Bye"),
            Timing("1", 2500, 3000, "now."),
        ),
        has_ass_escapes=True,
    )


# Each the writer's own (`utils.py` loaded by path, run on a result given here): OpenAI whisper
# v20250625's, WhisperX's at the tag named. 今 abuts 日 (no cue between), a gap before は (its cue)
_TODAY: Final = (
    "1\n00:00:01,000 --> 00:00:01,200\n<u>今</u> 日 は\n\n"
    "2\n00:00:01,200 --> 00:00:01,380\n今 <u>日</u> は\n\n"
    "3\n00:00:01,380 --> 00:00:01,400\n今日は\n\n"
    "4\n00:00:01,400 --> 00:00:01,600\n今 日 <u>は</u>\n\n"
)
_TODAY_WORDS: Final = (
    Timing("0", 1000, 1200, "今"),
    Timing("0", 1200, 1380, "日"),
    Timing("0", 1400, 1600, "は"),
)


@pytest.mark.parametrize(
    ("data", "sentence"),
    [
        (_TODAY, "今日は"),
        (
            re.sub(r"^(?=[今<])", "[SPEAKER_00]: ", _TODAY, flags=re.MULTILINE),
            "[SPEAKER_00]: 今日は",
        ),
        (  # --max_line_width 2 --max_line_count 2: its line break between words, joined by nothing
            _TODAY.replace(" は", " \nは")
            .replace("今日は", "今日\nは")
            .replace(" <u>は</u>", " \n<u>は</u>"),
            "今日は",
        ),
    ],
    ids=["3.8.6", "3.8.6 diarized", "3.8.6 wrapped"],
)
def test_whisperxs_highlighted_cues_in_ja_or_zh_read_as_its_json(data: str, sentence: str) -> None:
    # its `ja` and `zh` cue of a gap between words joins them by nothing, its highlighted ones by
    # spaces (`LANGUAGES_WITHOUT_SPACES`, from 3.2.0): the spaces its own, the sentence its JSON's
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert (reading.has_words, reading.cues, reading.words) == (
        True,
        (Cue(1000, 1600, sentence, "0", sentence.removesuffix("今日は")),),  # its speaker its lead
        _TODAY_WORDS,
    )


def test_whisperxs_highlighted_webvtt_in_ja_reads_as_its_json() -> None:
    data = "WEBVTT\n\n" + re.sub(r"^\d+\n", "", _TODAY, flags=re.MULTILINE).replace(
        "00:00:", "00:"
    ).replace(",", ".")
    reading = subverter.read("vtt", data.encode(), "a.vtt")
    assert (reading.cues, reading.words) == ((Cue(1000, 1600, "今日は", "0"),), _TODAY_WORDS)


def test_a_sentence_without_a_gap_is_unspaced_by_its_files_others() -> None:
    # 天 abuts 気: no cue joins them by nothing, but 今日は's does, in the same file
    data = _TODAY + "5\n00:00:02,000 --> 00:00:02,200\n<u>天</u> 気\n\n"
    data += "6\n00:00:02,200 --> 00:00:02,400\n天 <u>気</u>\n\n"
    assert subverter.read("srt", data.encode(), "a.srt").cues == (
        Cue(1000, 1600, "今日は", "0"),
        Cue(2000, 2400, "天気", "1"),
    )


@pytest.mark.parametrize(
    "data",
    [
        # WhisperX 3.8.6, `ja`, no gap: nothing joined by nothing
        "1\n00:00:01,000 --> 00:00:01,200\n<u>今</u> 日\n\n2\n00:00:01,200 --> 00:00:01,400\n今 <u>日</u>\n\n",
        # OpenAI whisper, `ja`, its words' own space: alike
        "1\n00:00:01,000 --> 00:00:01,200\n<u>山田</u> 太郎\n\n2\n00:00:01,200 --> 00:00:01,400\n山田 <u>太郎</u>\n\n",
    ],
    ids=["WhisperX, no gap", "OpenAI whisper, a space"],
)
def test_without_a_gaps_cue_a_highlighted_sentences_spaces_are_as_written(data: str) -> None:
    (cue,) = subverter.read("srt", data.encode(), "a.srt").cues
    assert " " in cue.text


def test_a_speakers_form_underlined_is_a_word_no_lead() -> None:
    # OpenAI whisper's sentence opening `[Music]: `: its first word, not a speaker -- before, the
    # lead too, drawn twice in chunk-word
    data = "".join(
        f"{n}\n00:00:0{n},000 --> 00:00:0{n},500\n{text}\n\n"
        for n, text in enumerate(
            [
                "<u>[Music]:</u> hello there",
                "[Music]: <u>hello</u> there",
                "[Music]: hello <u>there</u>",
            ],
            1,
        )
    )
    reading = subverter.read("srt", data.encode(), "a.srt")
    assert reading.cues == (Cue(1000, 3500, "[Music]: hello there", "0"),)
    assert [w.text for w in reading.words] == ["[Music]:", "hello", "there"]


@pytest.mark.parametrize(
    "second",
    ["[SPEAKER_01]: ", ""],
    ids=["another speaker", "no speaker"],
)
def test_one_text_of_two_speakers_is_two_sentences(second: str) -> None:
    # WhisperX 3.7.6, diarized: the second segment's gap cue first -- its speaker its own, or none
    # (`diarize.py` gives a segment no speaker when it meets no turn)
    data = (
        "1\n00:00:00,500 --> 00:00:00,700\n[SPEAKER_00]: <u>Yes,</u> sure.\n\n"
        "2\n00:00:00,700 --> 00:00:01,000\n[SPEAKER_00]: Yes, <u>sure.</u>\n\n"
        f"3\n00:00:01,200 --> 00:00:01,500\n{second}Yes, sure.\n\n"
        f"4\n00:00:01,500 --> 00:00:01,700\n{second}<u>Yes,</u> sure.\n\n"
        f"5\n00:00:01,700 --> 00:00:02,000\n{second}Yes, <u>sure.</u>\n\n"
    )
    assert subverter.read("srt", data.encode(), "a.srt").cues == (
        Cue(500, 1000, "[SPEAKER_00]: Yes, sure.", "0", "[SPEAKER_00]: "),
        Cue(1200, 2000, f"{second}Yes, sure.", "1", second),
    )


def test_whisperx_v31s_gap_cue_without_its_speaker_leaves_its_file_cues() -> None:
    # the tags v3.1.0 and v3.1.1 (git alone: PyPI's 3.1.x, a third party's, write as 3.2.0) write a
    # gap's cue without its speaker: a segment of no speaker alike (3.7.6's above), so cues
    texts = (
        "[SPEAKER_00]: <u>Hello</u> world.",
        "Hello world.",
        "[SPEAKER_00]: Hello <u>world.</u>",
    )
    data = _srt(
        [
            ("00:00:00,500", "00:00:00,900", texts[0]),
            ("00:00:00,900", "00:00:01,000", texts[1]),
            ("00:00:01,000", "00:00:01,500", texts[2]),
        ]
    )
    reading = subverter.read("srt", data, "a.srt")
    assert (reading.has_words, tuple(c.text for c in reading.cues)) == (False, texts)


# OpenAI whisper --max_words_per_line 1; WhisperX 3.8.6 --max_line_width 1 --max_line_count 1 alike
_A_WORD_A_CUE: Final = (
    "1\n00:00:00,500 --> 00:00:00,900\n<u>Hello</u>\n\n"
    "2\n00:00:01,000 --> 00:00:01,300\n<u>big</u>\n\n"
    "3\n00:00:01,300 --> 00:00:01,900\n<u>world.</u>\n\n"
)


@pytest.mark.parametrize(
    "speaker", ["", "[SPEAKER_00]: "], ids=["OpenAI whisper", "WhisperX, diarized"]
)
def test_a_cue_a_word_underlined_is_a_sentence_of_that_word(speaker: str) -> None:
    data = re.sub(r"^(?=<u>)", speaker, _A_WORD_A_CUE, flags=re.MULTILINE)
    reading = subverter.read("srt", data.encode(), "a.srt")
    times = ((500, 900), (1000, 1300), (1300, 1900))
    words = ("Hello", "big", "world.")
    assert (reading.has_words, reading.cues, reading.words) == (
        True,
        tuple(
            Cue(a, z, speaker + t, str(i), speaker)
            for i, ((a, z), t) in enumerate(zip(times, words, strict=True))
        ),
        tuple(
            Timing(str(i), a, z, t) for i, ((a, z), t) in enumerate(zip(times, words, strict=True))
        ),
    )


def test_a_cue_a_word_holds_one_with_a_space() -> None:
    # OpenAI whisper merges a prepended `-` into the next word (timing.py, merge_punctuations)
    data = (
        "1\n00:00:00,500 --> 00:00:00,900\n<u>Well</u>\n\n"
        "2\n00:00:01,000 --> 00:00:01,300\n<u>- I</u>\n\n"
        "3\n00:00:01,300 --> 00:00:01,900\n<u>think.</u>\n\n"
    )
    reading = subverter.read("srt", data.encode(), "a.srt")
    spans = ((500, 900, "Well"), (1000, 1300, "- I"), (1300, 1900, "think."))
    assert (reading.cues, reading.words) == (
        tuple(Cue(a, z, w, str(i)) for i, (a, z, w) in enumerate(spans)),
        tuple(Timing(str(i), a, z, w) for i, (a, z, w) in enumerate(spans)),
    )


def test_a_cue_a_word_with_an_untimed_one_is_cues() -> None:
    # WhisperX 3.8.2 (3.7.8 alike): a word it could not align, `2024`, a cue of no underline at its
    # segment's times, over its neighbours' -- no word to read; the file read as written
    texts = ("<u>In</u>", "2024", "<u>we</u>", "<u>won.</u>")
    data = _srt(
        [
            ("00:00:00,500", "00:00:00,700", texts[0]),
            ("00:00:00,500", "00:00:01,900", texts[1]),
            ("00:00:01,200", "00:00:01,400", texts[2]),
            ("00:00:01,400", "00:00:01,900", texts[3]),
        ]
    )
    reading = subverter.read("srt", data, "a.srt")
    assert (reading.has_words, tuple(c.text for c in reading.cues)) == (False, texts)


@pytest.mark.parametrize(
    "texts",
    [
        ("<u>one</u>", "two three"),  # a cue not underlined
        ("<u>one</u> two", "<u>three</u> four"),  # each opening underlined, not wholly
        ("<u>one</u>",),  # one cue: no structure
    ],
    ids=["one not underlined", "underlined first", "one cue"],
)
def test_underlined_cues_but_not_a_word_each_are_cues(texts: tuple[str, ...]) -> None:
    data = _srt([(f"00:00:0{i},000", f"00:00:0{i},500", t) for i, t in enumerate(texts)])
    reading = subverter.read("srt", data, "a.srt")
    assert (reading.has_words, [c.text for c in reading.cues]) == (False, list(texts))


def test_a_highlighted_sentence_keeps_its_markup_but_its_underline() -> None:
    # its text as written, for its reader to read as any cue's -- before, every tag off as SubRip
    # and WebVTT read none: `x < 5 and y > 3` lost `< 5 and y >`
    data = _srt(
        [
            ("00:00:00,000", "00:00:00,500", "<u>if</u> x < 5 and <i>y</i> > 3"),
            ("00:00:00,500", "00:00:01,000", "if <u>x</u> < 5 and <i>y</i> > 3"),
        ]
    )
    reading = subverter.read("srt", data, "a.srt")
    assert reading.cues == (Cue(0, 1000, "if x < 5 and <i>y</i> > 3", "0"),)
    untimed = (Timing("0", None, None, w) for w in ("<", "5", "and", "<i>y</i>", ">", "3"))
    assert reading.words == (Timing("0", 0, 500, "if"), Timing("0", 500, 1000, "x"), *untimed)


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


# WhisperX 3.8.2's WriteSRT (`utils.py`, run): a word it left untimed (`{"word": "101"}`) has no
# highlighted cue, only its place in the others' text
_UNTIMED: Final = (
    "1\n00:00:02,500 --> 00:00:02,800\n<u>Room</u> 101 is open.\n\n"
    "2\n00:00:02,800 --> 00:00:03,100\nRoom 101 is open.\n\n"
    "3\n00:00:03,100 --> 00:00:03,200\nRoom 101 <u>is</u> open.\n\n"
    "4\n00:00:03,200 --> 00:00:03,250\nRoom 101 is open.\n\n"
    "5\n00:00:03,250 --> 00:00:03,800\nRoom 101 is <u>open.</u>\n\n"
)


@pytest.mark.parametrize(
    ("data", "words"),
    [
        (_UNTIMED.encode(), ["Room", None, "is", "open."]),
        (  # --max_line_width 8 --max_line_count 2: its line break before a word
            _UNTIMED.replace("101 is", "101 \nis").replace("101 <u>is", "101 \n<u>is").encode(),
            ["Room", None, "is", "open."],
        ),
        (  # diarized, its first word untimed: after its speaker
            _srt(
                [
                    ("00:00:01,000", "00:00:01,300", "[SPEAKER_00]: Hi <u>there</u> you."),
                    ("00:00:01,300", "00:00:01,400", "[SPEAKER_00]: Hi there you."),
                    ("00:00:01,400", "00:00:01,900", "[SPEAKER_00]: Hi there <u>you.</u>"),
                ]
            ),
            [None, "there", "you."],
        ),
        (  # `ja`, a full-width digit untimed: its highlighted cues' spaces its own, between words
            _srt(
                [
                    ("00:00:01,000", "00:00:01,200", "<u>部</u> 屋 \uff11 号"),
                    ("00:00:01,200", "00:00:01,400", "部 <u>屋</u> \uff11 号"),
                    ("00:00:01,400", "00:00:01,800", "部屋\uff11号"),
                    ("00:00:01,800", "00:00:02,000", "部 屋 \uff11 <u>号</u>"),
                ]
            ),
            ["部", "屋", None, "号"],
        ),
        (  # --max_line_width 8 --max_line_count 2: an untimed word right after its line break
            _srt(
                [
                    ("00:00:01,000", "00:00:01,300", "<u>Call</u> now \n911 ok"),
                    ("00:00:01,300", "00:00:01,600", "Call <u>now</u> \n911 ok"),
                    ("00:00:01,600", "00:00:02,000", "Call now \n911 ok"),
                    ("00:00:02,000", "00:00:02,400", "Call now \n911 <u>ok</u>"),
                ]
            ),
            ["Call", "now", None, "ok"],
        ),
    ],
    ids=["en", "wrapped", "diarized, first", "ja", "after a break"],
)
def test_a_highlighted_sentences_word_not_underlined_is_an_untimed_word(
    data: bytes, words: list[str | None]
) -> None:
    """Its text where no cue underlines it: a word of no time, placed as its JSON's (ffman)."""
    reading = subverter.read("srt", data, "a.srt")
    (sentence,) = reading.cues
    found = [w.text if w.start is not None else None for w in reading.words]
    assert found == words
    # its words, together, its text past its speaker, without its spaces and line breaks
    spoken = "".join(sentence.text.removeprefix(sentence.lead).split())
    assert "".join(w.text for w in reading.words) == spoken
    untimed = [w for w in reading.words if w.start is None]
    assert [(w.segment, w.end) for w in untimed] == [("0", None)]
    assert untimed[0].text in sentence.text


# WhisperX v3.1.1's WriteSRT (`utils.py`, run), diarized: its gap cue without the speaker splits a
# sentence into parts of one text, each underlining its own words
_SPLIT: Final = [
    ("00:00:00,500", "00:00:00,800", "[SPEAKER_00]: <u>One</u> two three four."),
    ("00:00:00,800", "00:00:01,000", "[SPEAKER_00]: One <u>two</u> three four."),
    ("00:00:01,000", "00:00:01,300", "[SPEAKER_00]: One two <u>three</u> four."),
    ("00:00:01,300", "00:00:01,700", "[SPEAKER_00]: One two three <u>four.</u>"),
    ("00:00:02,000", "00:00:02,300", "[SPEAKER_00]: <u>Five</u> {} seven."),
    ("00:00:02,300", "00:00:02,700", "Five {} seven."),
    ("00:00:02,700", "00:00:03,000", "[SPEAKER_00]: Five {} <u>seven.</u>"),
]


@pytest.mark.parametrize(
    ("between", "words"),
    [
        ("<u>six</u>", ["Five", "six", "seven."]),  # its own cue, `six` timed
        ("66", ["Five", None, "seven."]),  # untimed: once, in the part before it
    ],
    ids=["timed", "untimed"],
)
def test_a_sentence_split_into_parts_of_one_text_holds_each_word_once(
    between: str, words: list[str | None]
) -> None:
    """A word another part underlines is that part's; an untimed one the part it follows."""
    cues = [
        (a, z, t.format(between.removeprefix("<u>").removesuffix("</u>"))) for a, z, t in _SPLIT
    ]
    if between.startswith("<u>"):  # `six`'s cue: it underlined, the parts as the writer splits them
        cues.insert(5, ("00:00:02,300", "00:00:02,500", "[SPEAKER_00]: Five <u>six</u> seven."))
        cues[6] = ("00:00:02,500", "00:00:02,700", cues[6][2])
    reading = subverter.read("srt", _srt(cues), "a.srt")
    found = [(w.segment, w.text if w.start is not None else None) for w in reading.words[4:]]
    assert [w for _, w in found] == words
    assert [s for s, w in found if w is None] == ["1"] * words.count(None)


def test_an_untimed_word_after_a_later_parts_word_is_that_parts() -> None:
    # WhisperX v3.1.1's WriteSRT (run): `88` untimed, after the second part's `seven`
    cues = [
        *_SPLIT[:4],
        ("00:00:02,000", "00:00:02,300", "[SPEAKER_00]: <u>Five</u> seven 88"),
        ("00:00:02,300", "00:00:02,700", "Five seven 88"),
        ("00:00:02,700", "00:00:03,000", "[SPEAKER_00]: Five <u>seven</u> 88"),
    ]
    found = subverter.read("srt", _srt(cues), "a.srt").words[4:]
    assert [(w.segment, w.text, w.start) for w in found] == [
        ("1", "Five", 2000),
        ("3", "seven", 2700),
        ("3", "88", None),
    ]


def test_sentences_of_two_texts_are_never_one_sentences_words() -> None:
    # `there` underlined past `Go`, but in another text: each sentence's untimed words its own
    data = _srt(
        [
            ("00:00:00,000", "00:00:00,500", "<u>Go</u> 7"),
            ("00:00:00,500", "00:00:01,000", "Go 7"),
            ("00:00:01,000", "00:00:01,500", "Hi <u>there</u>"),
            ("00:00:01,500", "00:00:02,000", "Hi there"),
        ]
    )
    found = subverter.read("srt", data, "a.srt").words
    assert [(w.segment, w.text, w.start) for w in found] == [
        ("0", "Go", 0),
        ("0", "7", None),
        ("1", "Hi", None),
        ("1", "there", 1000),
    ]


# a sentence of eight words, each its own cue: the file read as highlighted, whatever follows
_EIGHT: Final = [
    (
        f"00:00:00,{k}00",
        f"00:00:00,{k + 1}00",
        " ".join(f"<u>{w}</u>" if j == k else w for j, w in enumerate("abcdefgh")),
    )
    for k in range(8)
]


@pytest.mark.parametrize(
    ("cues", "words"),
    [
        (  # WhisperX 3.8.2 (run): two speakers, one text, each word untimed in the other's
            [
                ("00:00:01,000", "00:00:01,300", "[SPEAKER_00]: <u>Room</u> 101"),
                ("00:00:02,300", "00:00:02,600", "[SPEAKER_01]: Room <u>101</u>"),
            ],
            [("1", "Room", 1000), ("1", "101", None), ("2", "Room", None), ("2", "101", 2300)],
        ),
        (  # WhisperX v3.1.1 (run): two speakers, one text, its gap cue without a speaker between
            [
                ("00:00:01,000", "00:00:01,300", "[SPEAKER_00]: <u>Room</u> 101"),
                ("00:00:02,000", "00:00:02,300", "Room 101"),
                ("00:00:02,300", "00:00:02,600", "[SPEAKER_01]: Room <u>101</u>"),
            ],
            [("1", "Room", 1000), ("1", "101", None), ("3", "Room", None), ("3", "101", 2300)],
        ),
        (  # WhisperX 3.8.2 (run): another speaker's of one text, no word timed, between
            [
                ("00:00:01,000", "00:00:01,300", "[SPEAKER_00]: <u>Room</u> 101"),
                ("00:00:01,600", "00:00:01,900", "[SPEAKER_01]: Room 101"),
                ("00:00:02,300", "00:00:02,600", "[SPEAKER_00]: Room <u>101</u>"),
            ],
            [("1", "Room", 1000), ("1", "101", None), ("3", "Room", None), ("3", "101", 2300)],
        ),
        (  # WhisperX 3.8.2 (run): a sentence of no word timed between two of one text
            [
                ("00:00:01,000", "00:00:01,300", "<u>Room</u> 101"),
                ("00:00:01,500", "00:00:01,800", "Hmm"),
                ("00:00:02,300", "00:00:02,600", "Room <u>101</u>"),
            ],
            [("1", "Room", 1000), ("1", "101", None), ("3", "Room", None), ("3", "101", 2300)],
        ),
        (  # WhisperX v3.1.1 (run): one text twice, its gap cues, `Hi` untimed in each
            [
                ("00:00:00,800", "00:00:01,000", "Hi you"),
                ("00:00:01,000", "00:00:01,400", "[SPEAKER_00]: Hi <u>you</u>"),
                ("00:00:01,800", "00:00:02,000", "Hi you"),
                ("00:00:02,000", "00:00:02,400", "[SPEAKER_00]: Hi <u>you</u>"),
            ],
            [("2", "Hi", None), ("2", "you", 1000), ("4", "Hi", None), ("4", "you", 2000)],
        ),
        (  # WhisperX v3.1.1 (run): its second underlined within the first's, `A` and `c` untimed
            [
                ("00:00:01,000", "00:00:01,200", "[SPEAKER_00]: <u>A</u> b c"),
                ("00:00:01,200", "00:00:01,400", "[SPEAKER_00]: A <u>b</u> c"),
                ("00:00:01,400", "00:00:01,600", "[SPEAKER_00]: A b <u>c</u>"),
                ("00:00:01,800", "00:00:02,000", "A b c"),
                ("00:00:02,000", "00:00:02,200", "[SPEAKER_00]: A <u>b</u> c"),
            ],
            [
                ("1", "A", 1000),
                ("1", "b", 1200),
                ("1", "c", 1400),
                ("3", "A", None),
                ("3", "b", 2000),
                ("3", "c", None),
            ],
        ),
        (  # WhisperX v3.1.1 (run): a sentence no word aligned, then one split: each part's own gaps
            [
                ("00:00:01,000", "00:00:01,500", "[SPEAKER_00]: Hmm"),
                ("00:00:02,000", "00:00:02,300", "[SPEAKER_00]: <u>Five</u> six seven."),
                ("00:00:02,300", "00:00:02,500", "[SPEAKER_00]: Five <u>six</u> seven."),
                ("00:00:02,500", "00:00:02,700", "Five six seven."),
                ("00:00:02,700", "00:00:03,000", "[SPEAKER_00]: Five six <u>seven.</u>"),
            ],
            [("2", "Five", 2000), ("2", "six", 2300), ("4", "seven.", 2700)],
        ),
        (  # WhisperX v3.1.1 (run): a split sentence's first word untimed, the first part's
            [
                ("00:00:01,800", "00:00:02,000", "55 Five six seven."),
                ("00:00:02,000", "00:00:02,300", "[SPEAKER_00]: 55 <u>Five</u> six seven."),
                ("00:00:02,300", "00:00:02,500", "[SPEAKER_00]: 55 Five <u>six</u> seven."),
                ("00:00:02,500", "00:00:02,700", "55 Five six seven."),
                ("00:00:02,700", "00:00:03,000", "[SPEAKER_00]: 55 Five six <u>seven.</u>"),
            ],
            [
                ("2", "55", None),
                ("2", "Five", 2000),
                ("2", "six", 2300),
                ("4", "seven.", 2700),
            ],
        ),
    ],
    ids=[
        "two speakers",
        "two speakers, v3.1.1",
        "another speaker's between",
        "a sentence between",
        "a repeat on its last",
        "a repeat within",
        "after one unaligned",
        "first",
    ],
)
def test_only_a_split_sentences_parts_share_their_words(
    cues: list[tuple[str, str, str]], words: list[tuple[str, str, int | None]]
) -> None:
    """One speaker, one text, only its gap cues between, its underline moving on: one sentence."""
    found = subverter.read("srt", _srt([*_EIGHT, *cues]), "a.srt").words[8:]
    assert [(w.segment, w.text, w.start) for w in found] == words


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
