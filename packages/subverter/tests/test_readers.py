"""Each reader against its rules, as recorded (docs/decisions.md's rows, the readers' docstrings).

Every expectation is worked by hand from a rule, not taken from a run: what a reader yields
before ffman's normalising (no trim, no sort but LRC's, no clamp, no cue dropped).
"""

import json
import re
import time
from typing import Final

import pytest
import subverter
from hypothesis import assume, given
from hypothesis import strategies as st
from subverter import Cue, Reading, Timing
from subverter.readers import subrip, webvtt

# --- the dispatcher: a .txt and an unknown format refused, in the words ffman's tests record


@pytest.mark.parametrize(
    ("fmt", "message"),
    [
        (
            "txt",
            "a .txt transcript has no timestamps; use whisper-cli -osrt, -ovtt, -olrc, -ocsv, -oj or -ojf, or WhisperX srt, vtt, tsv or json",
        ),
        ("xyz", "unsupported subtitle format '.xyz' (srt, vtt, lrc, csv, tsv, json)"),
    ],
)
def test_a_format_without_a_reader_is_refused(fmt: str, message: str) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}$"):
        _ = subverter.read(fmt, b"x", f"a.{fmt}")


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


# Line ends. WebVTT's the W3C's ("WebVTT parser algorithm": CRLF, CR and LF each one); SubRip's
# \r*\n|\r, its lines holding text ffmpeg's (ff_subtitles_read_line) -- a CRLF file written
# again in text mode, CR CR LF, read as written; VLC 3 alike; LRC's SubRip's
_PLAIN: Final = {
    "srt": "1\n00:00:01,000 --> 00:00:02,000\nfirst\nline2\n\n2\n00:00:03,000 --> 00:00:04,000\nsecond\n",
    "vtt": "WEBVTT\n\n00:01.000 --> 00:02.000\nfirst\nline2\n\n00:03.000 --> 00:04.000\nsecond\n",
    "lrc": "[00:01.00]first\n[00:03.00]second\n",
}
_SUBRIPS: Final = ("\n", "\r\n", "\r", "\r\r\n")  # CR CR LF one end
_ENDS: Final = {"srt": _SUBRIPS, "lrc": _SUBRIPS, "vtt": ("\n", "\r\n", "\r")}


@given(st.data())
@pytest.mark.parametrize("fmt", sorted(_PLAIN))
def test_any_mix_of_a_formats_line_ends_reads_as_lf(fmt: str, data: st.DataObject) -> None:
    lines = _PLAIN[fmt].split("\n")[:-1]
    kinds = st.sampled_from(_ENDS[fmt])
    ends = data.draw(st.lists(kinds, min_size=len(lines), max_size=len(lines)))
    # a lone CR before a blank line ended by an LF: one line end with it -- another file
    _ = assume(
        not any(
            a == "\r" and line == "" and b != "\r"
            for a, line, b in zip(ends, lines[1:], ends[1:], strict=False)
        )
    )
    text = "".join(line + end for line, end in zip(lines, ends, strict=True))
    plain = subverter.read(fmt, _PLAIN[fmt].encode(), f"a.{fmt}")
    assert subverter.read(fmt, text.encode(), f"a.{fmt}") == plain


_VTT: Final = _PLAIN["vtt"]
_SRT: Final = _PLAIN["srt"]
_BOTH: Final = (Cue(1000, 2000, "first line2"), Cue(3000, 4000, "second"))
_NO_TEXT: Final = (Cue(1000, 2000, ""), Cue(3000, 4000, ""))


@pytest.mark.parametrize(
    ("fmt", "text", "cues"),
    [
        # Chromium 141, each: a lone CR a line end, in a line too; CR CR LF and LF CR two ends,
        # so a blank line after each timing line -- its cue of no text
        ("vtt", _VTT.replace("\n", "\r"), _BOTH),
        ("vtt", _VTT.replace("\n", "\r", 3), _BOTH),
        ("vtt", _VTT.replace("first", "fi\rrst"), (Cue(1000, 2000, "fi rst line2"), _BOTH[1])),
        ("vtt", _VTT.replace("line2\n\n", "line2\r\r"), _BOTH),
        ("vtt", _VTT.replace("\n", "\r\r\n"), _NO_TEXT),
        ("vtt", _VTT.replace("\n", "\n\r"), _NO_TEXT),
        # ffmpeg 8.1.2, each: a lone CR a line end, in a line too; CR CR LF one; LF CR two, each
        # cue's empty lines skipped (its texts after them noted)
        ("srt", _SRT.replace("\n", "\r"), _BOTH),
        ("srt", _SRT.replace("\n", "\r", 3), _BOTH),
        ("srt", _SRT.replace("first", "fi\rrst"), (Cue(1000, 2000, "fi rst line2"), _BOTH[1])),
        ("srt", _SRT.replace("\n", "\r\r\n"), _BOTH),
        ("srt", _SRT.replace("line2\n\n", "line2\n\r\n"), _BOTH),
        ("srt", _SRT.replace("\n", "\n\r"), _BOTH),
        # ffmpeg's lrcdec ends a line at an LF alone and drops each CR: a CR-only file one line
        # (`first[00:03.00]second`), `fi\rrst` read `first` -- SubRip's line ends instead
        (
            "lrc",
            "[00:01.00]first\r[00:03.00]second\r",
            (Cue(1000, 3000, "first"), Cue(3000, 6000, "second")),
        ),
        (
            "lrc",
            "[00:01.00]first\r\r\n[00:03.00]second\r\r\n",
            (Cue(1000, 3000, "first"), Cue(3000, 6000, "second")),
        ),
        (
            "lrc",
            "[00:01.00]fi\rrst\n[00:03.00]second\n",
            (Cue(1000, 3000, "fi"), Cue(3000, 6000, "second")),
        ),
    ],
)
def test_each_formats_line_ends_are_read_as_measured(
    fmt: str, text: str, cues: tuple[Cue, ...]
) -> None:
    assert subverter.read(fmt, text.encode(), f"a.{fmt}").cues == cues


def test_an_lrcs_cr_cr_lf_is_one_line_end_as_subrips() -> None:
    # observable in a line's number alone: an LRC reads no blank line
    data = b"[ti:x]\r\r\n[offset:+500]\r\r\n[00:01.00]one\r\r\n"
    reading = subverter.read("lrc", data, "a.lrc")
    assert reading.notes == ("LRC offset on line 2 applied: every line 500 ms sooner",)


@given(st.lists(st.sampled_from(("\r", "\n", "a")), max_size=12).map("".join))
def test_subrips_split_is_its_pattern(text: str) -> None:
    assert subrip.split_lines(text) == re.split(r"\r*\n|\r", text)


def _ffmpeg_lines(text: str) -> list[str]:
    """ffmpeg 8.1's ff_subtitles_read_line, transcribed: to a CR or an LF, then CRs and an LF."""
    lines: list[str] = []
    i = 0
    while i < len(text):
        start = i
        while i < len(text) and text[i] not in "\r\n":
            i += 1
        lines.append(text[start:i])
        i += i < len(text)  # the CR or LF that ended it
        while text[i : i + 1] == "\r":
            i += 1
        i += text[i : i + 1] == "\n"
    return lines


@given(st.lists(st.sampled_from(("\r", "\n", "a")), max_size=12).map("".join))
def test_subrips_lines_holding_text_are_ffmpegs(text: str) -> None:
    # its empty lines differ: ffmpeg's reader yields none; here, each kept for the notes
    assert [s for s in subrip.split_lines(text) if s] == [s for s in _ffmpeg_lines(text) if s]


@given(st.lists(st.sampled_from(("\r", "\n", "a")), max_size=12).map("".join))
def test_webvtts_line_ends_are_the_w3cs(text: str) -> None:
    # "WebVTT parser algorithm": each CRLF an LF, then each CR an LF
    assert webvtt.split_lines(text) == text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


@pytest.mark.parametrize("fmt", ["srt", "vtt", "lrc"])
def test_a_run_of_crs_is_read_in_linear_time(fmt: str) -> None:
    # a run of CRs, no LF after it: ``\r*\n|\r`` scans the run again at each CR (18 s here)
    data = b"WEBVTT" * (fmt == "vtt") + b"\r" * 200_000
    began = time.monotonic()
    assert subverter.read(fmt, data, f"a.{fmt}").cues == ()
    assert time.monotonic() - began < 1


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
    notes = () if said is None else (_ODD_SUBRIP.format(n=1, time=written, said=said),)
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
# alone; its decoder ends the text at a line of spaces (htmlsubtitles.c); a tab, text
_CONTINUED_NOTE: Final = (
    "{n} cues held text after an empty line, read as theirs, as ffmpeg reads them: the first,"
    " {text} on line {line}"
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
        ("first\n   \nsecond line\n\n2", "first", ()),  # the text ended at the spaces
        ("first\n\n   \nafter spaces\n\n2", "first", ()),
        ("first\n2\n   ", "first 2", ()),  # the spaces after `2`: its text, no index
        (  # a timing line ffmpeg cannot read: its cue the one before's, as ffmpeg's (measured)
            "first\n\n2\n00:00:02,500 -> 00:00:02,800\ncut",
            "first 2 00:00:02,500 -> 00:00:02,800 cut",
            (_CONTINUED_NOTE.format(n=1, text="2", line=5),),
        ),
        ("first\n\t\nsecond\n\n2", "first \t second", ()),
        ("first\n \t \nsecond\n\n2", "first  \t  second", ()),
    ],
)
def test_a_subrip_cue_runs_on_past_an_empty_line_as_ffmpeg_reads_it(
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


# --- LRC: starts only, sorted; each line ends where the next starts, the last 3 s later


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
        pytest.param(  # no offset tag: lower case, first on its line (ffmpeg's)
            "[OFFSET:+500]\n [offset:+500]\n[offset+500]\n[00:01.00]a\n",
            (Cue(1000, 4000, "a"),),
            (),
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


# --- CSV and TSV: start, end, text in ms; a header names start and end, any order


@pytest.mark.parametrize(
    ("data", "cues"),
    [
        ('start,end,text\n0,1000,"a, b"\n', (Cue(0, 1000, "a, b"),)),  # RFC 4180 quoting
        ("speaker,end,start,text\nS1,2000,1000,hi\n", (Cue(1000, 2000, "hi"),)),  # by header
        ("500,900,x\n", (Cue(500, 900, "x"),)),  # no header: start, end, text
        ("start,end,text\nabc,900,y\n", (Cue(None, 900, "y"),)),  # no number: no time
        # a record short of a column: that field empty, as awk's $n past the last -- a text "", a
        # time none -- wherever the header puts it; a blank line no record
        ("start,end,text\n1,2\n", (Cue(1, 2, ""),)),
        ("text,start,end\nhello\n", (Cue(None, None, "hello"),)),
        ("text,end,start\nhi,2000\n", (Cue(None, 2000, "hi"),)),
        ("start,end,text\n\n0,1,x\n", (Cue(0, 1, "x"),)),
        # the header the first record, a blank line none (pandas' skip_blank_lines): a line of
        # spaces is one
        ("\n\r\ntext,start,end\nhello,0,1000\n", (Cue(0, 1000, "hello"),)),
        (
            " \nstart,end,text\n0,1,x\n",
            (Cue(None, None, ""), Cue(None, None, "text"), Cue(0, 1, "x")),
        ),
    ],
)
def test_a_csv_read_by_its_columns(data: str, cues: tuple[Cue, ...]) -> None:
    assert subverter.read("csv", data.encode(), "a.csv").cues == cues


def test_a_tsv_header_after_a_blank_line_is_its_header() -> None:
    data = "\ntext\tstart\tend\nhello\t0\t1000\n"
    assert subverter.read("tsv", data.encode(), "a.tsv").cues == (Cue(0, 1000, "hello"),)


def test_a_tsv_record_short_of_a_column_reads_it_empty() -> None:
    data = "text\tstart\tend\nhello\n0\n"  # its start and end, then its end, past the record
    assert subverter.read("tsv", data.encode(), "a.tsv").cues == (
        Cue(None, None, "hello"),
        Cue(None, None, "0"),
    )


def test_a_tsv_quotes_nothing() -> None:
    data = 'start\tend\ttext\n0\t1000\t"as written"\n'
    assert subverter.read("tsv", data.encode(), "a.tsv").cues == (Cue(0, 1000, '"as written"'),)


def test_a_field_past_csvs_limit_is_refused_by_name() -> None:
    data = "start,end,text\n0,1," + "x" * (128 * 1024 + 1) + "\n"
    with pytest.raises(
        subverter.Error, match=r"^unreadable \.csv: big\.csv: field larger than field limit"
    ):
        _ = subverter.read("csv", data.encode(), "big.csv")


# --- not UTF-8: whisper-cli -ml 1 splits a segment between tokens, so inside a character --
# " Это ёлка и 😀" by whisper's tokens, wrapped by its whisper_wrap_segment: each character
# joined across the texts it spans, in the one it starts; what is still not UTF-8 refused by line

# each cue's start and end (ms) and text, as whisper-cli's -ml 1 made them: ё and 😀 split
_SPLIT_CUES: Final = ((0, 100, b" \xd1"), (100, 200, b"\x91\xd0\xbb"), (200, 300, b" \xf0\x9f\x98"), (300, 400, b"\x80"))  # fmt: skip


def _srt_time(t: int, comma: str = ",") -> str:
    return f"00:00:{t // 1000:02d}{comma}{t % 1000:03d}"


def _whisper_cli_srt() -> bytes:
    cues = (
        b"%d\n%s --> %s\n%s\n\n" % (n, _srt_time(a).encode(), _srt_time(z).encode(), text)
        for n, (a, z, text) in enumerate(_SPLIT_CUES, 1)
    )
    return b"".join(cues)


def _whisper_cli_vtt() -> bytes:
    cues = (
        b"%s --> %s\n%s\n\n" % (_srt_time(a, ".").encode(), _srt_time(z, ".").encode(), text)
        for a, z, text in _SPLIT_CUES
    )
    return b"WEBVTT\n\n" + b"".join(cues)


def _whisper_cli_lrc() -> bytes:
    lines = (b"[00:00.%02d]%s\n" % (a // 10, text) for a, _, text in _SPLIT_CUES)
    return b"[by:whisper.cpp]\n" + b"".join(lines)


def _whisper_cli_csv() -> bytes:
    return b"start,end,text\n" + b"".join(b'%d,%d,"%s"\n' % cue for cue in _SPLIT_CUES)


@pytest.mark.parametrize(
    ("fmt", "data", "last"),
    [
        ("srt", _whisper_cli_srt(), 400),
        ("vtt", _whisper_cli_vtt(), 400),
        ("lrc", _whisper_cli_lrc(), 3300),  # starts only: the last 3 s later
        ("csv", _whisper_cli_csv(), 400),
    ],
    ids=["srt", "vtt", "lrc", "csv"],
)
def test_a_character_split_across_cues_is_the_one_where_it_starts(
    fmt: str, data: bytes, last: int
) -> None:
    assert subverter.read(fmt, data, f"a.{fmt}").cues == (
        Cue(0, 100, " ё"),
        Cue(100, 200, "л"),
        Cue(200, 300, " 😀"),
        Cue(300, last, ""),
    )


def test_lrc_lines_are_joined_as_written_then_sorted() -> None:
    data = b"[00:05.00] \xd1\n[00:01.00]\x91x\n"  # ё begun at 5 s, ended in the line at 1 s
    assert subverter.read("lrc", data, "a.lrc").cues == (
        Cue(1000, 5000, "x"),
        Cue(5000, 8000, " ё"),
    )


def test_a_cues_lines_are_joined_each_its_characters_whole() -> None:
    # é begun in a line, ended in the next: its lines joined by a space, as any cue's
    data = b"1\n00:00:01,000 --> 00:00:02,000\ncaf\xc3\n\xa9 ok\n"
    assert subverter.read("srt", data, "a.srt").cues == (Cue(1000, 2000, "café  ok"),)


@pytest.mark.parametrize(
    ("fmt", "data", "end"),
    [
        ("srt", b"1\xe9\n00:00:01,000 --> 00:00:02,000\nok\n", 2000),  # an index
        ("vtt", b"WEBVTT \xe9\n\n00:01.000 --> 00:02.000\nok\n", 2000),  # a header
        ("lrc", b"[ti:caf\xe9]\n[00:01.00]ok\n", 4000),  # a tag
    ],
)
def test_only_the_texts_read_must_be_utf8(fmt: str, data: bytes, end: int) -> None:
    assert subverter.read(fmt, data, f"a.{fmt}").cues == (Cue(1000, end, "ok"),)


@pytest.mark.parametrize(
    ("fmt", "data", "line"),
    [
        ("srt", b"1\n00:00:01,000 --> 00:00:02,000\ncaf\xe9\n", 3),
        ("srt", b"1\n00:00:01,000 --> 00:00:02,000\nok\ncaf\xe9\n", 4),
        ("srt", b"\xef\xbb\xbf1\r\n00:00:01,000 --> 00:00:02,000\r\ncaf\xe9\r\n", 3),
        ("srt", b"1\n00:00:01,000 --> 00:00:02,000\n \xd1\n", 3),
        ("srt", b"1\n00:00:01,000 --> 00:00:02,000\n\x91x\n", 3),
        (
            "srt",
            b"1\n00:00:01,000 --> 00:00:02,000\n \xd1\n\n2\n00:00:02,000 --> 00:00:03,000\nx\n",
            3,
        ),
        (
            "srt",
            b"1\n00:00:01,000 --> 00:00:02,000\n \xd1\n\n2\n00:00:02,000 --> 00:00:03,000\n\x91\xff\n",
            7,
        ),
        ("vtt", b"WEBVTT\n\n00:01.000 --> 00:02.000\ncaf\xe9\n", 4),
        ("lrc", b"[00:05.00]ok\n[00:01.00]caf\xe9\n", 2),
        ("csv", b'start,end,text\n0,1,"a\nb"\n1,2,"caf\xe9"\n', 4),
        ("tsv", b"start\tend\ttext\n0\t1\tcaf\xe9\n", 2),
    ],
    ids=[
        "a Latin-1 byte",
        "in a cue's second line",
        "a BOM and CRs",
        "a character never completed",
        "a character never begun",
        "a character broken by the next cue",
        "a byte past a character joined",
        "WebVTT",
        "LRC, as written, not as sorted",
        "CSV, a record's first line",
        "TSV",
    ],
)
def test_a_text_not_utf8_once_joined_is_refused_by_its_line(
    fmt: str, data: bytes, line: int
) -> None:
    message = f"not UTF-8: a.{fmt} (line {line})"
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}$"):
        _ = subverter.read(fmt, data, f"a.{fmt}")


# --- whisper JSON: refused unless whisper-cli's or WhisperX's

_NOT_A_TRANSCRIPT: Final = (
    "not a whisper-cli (.transcription) or WhisperX (.segments) JSON transcript"
)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"{", "not valid JSON"),
        # closed: an unclosed one is invalid JSON too, which a machine whose parser holds
        # 100000 levels reports first
        pytest.param(
            b"[" * 100_000 + b"]" * 100_000,
            "JSON nested too deeply to be a transcript",
            id="100000 deep",
        ),
        pytest.param(
            b"[" * 1001 + b"]" * 1001, "JSON nested too deeply to be a transcript", id="1001 deep"
        ),
        pytest.param(b"[" * 1000 + b"]" * 1000, _NOT_A_TRANSCRIPT, id="1000 deep"),
        (b"[]", _NOT_A_TRANSCRIPT),
        (b"5", _NOT_A_TRANSCRIPT),
        (b'{"transcription": [{"tokens": [{"text": 5}]}]}', "unreadable whisper-cli -ojf JSON"),
    ],
)
def test_a_json_not_a_transcript_is_refused(data: bytes, message: str) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}: a\\.json$"):
        _ = subverter.read("json", data, "a.json")


def test_json_past_the_parsers_stack_is_refused_as_too_deep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # the machine's limit, wherever it falls: a RecursionError from json.loads itself
    def out_of_stack(*_args: object, **_kwargs: object) -> object:
        raise RecursionError

    monkeypatch.setattr(json, "loads", out_of_stack)
    message = "JSON nested too deeply to be a transcript: a.json"
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}$"):
        _ = subverter.read("json", b"[]", "a.json")


# --- whisper-cli: offsets in ms; with -ojf, words from tokens, DTW times where they hold


def _cli(entries: list[object], language: str = "en") -> bytes:
    return json.dumps({"result": {"language": language}, "transcription": entries}).encode()


def test_whisper_cli_without_tokens_is_cues_alone_their_text_as_written() -> None:
    data = _cli([{"offsets": {"from": 0, "to": 1500}, "text": " Hi"}])
    assert subverter.read("json", data, "a.json") == Reading(
        "whisper-cli JSON", has_words=False, cues=(Cue(0, 1500, " Hi", "0"),)
    )


def _token(text: object, start: int, end: int, dtw: object = None) -> dict[str, object]:
    token: dict[str, object] = {"text": text, "offsets": {"from": start, "to": end}}
    if dtw is not None:
        token["t_dtw"] = dtw
    return token


def test_words_from_tokens_timed_by_dtw_where_inside_and_in_order() -> None:
    # " He" + "llo" one word (a leading space starts one); [_TT_] skipped; t_dtw in 10 ms units
    tokens = [_token(" He", 0, 200, 5), _token("llo", 200, 400, 15), _token(" world", 400, 900, 50)]
    tokens.append(_token("[_TT_150]", 900, 1000))
    data = _cli([{"offsets": {"from": 0, "to": 1000}, "text": " Hello world", "tokens": tokens}])
    reading = subverter.read("json", data, "a.json")
    assert (reading.source, reading.has_words, reading.notes) == ("whisper-cli -ojf JSON", True, ())
    # each word from its DTW time to the next's; the last to the sentence's end
    assert reading.words == (Timing("0", 50, 500, " Hello"), Timing("0", 500, 1000, " world"))


def test_dtw_out_of_order_falls_back_to_the_offsets_and_says_so() -> None:
    tokens = [_token(" one", 0, 400, 60), _token(" two", 400, 900, 20)]  # 600 ms, then 200: back
    data = _cli([{"offsets": {"from": 0, "to": 1000}, "text": " one two", "tokens": tokens}])
    reading = subverter.read("json", data, "a.json")
    assert reading.words == (Timing("0", 0, 400, " one"), Timing("0", 400, 900, " two"))
    assert reading.notes == (
        "DTW word times were outside their sentence or not in order in 1 of 1 sentences: used token offsets there",
    )


def test_a_language_without_spaces_makes_every_token_a_word() -> None:
    tokens = [_token("東", 0, 300), _token("京", 300, 600)]
    data = _cli(
        [{"offsets": {"from": 0, "to": 600}, "text": "東京", "tokens": tokens}], language="ja"
    )
    assert subverter.read("json", data, "a.json").words == (
        Timing("0", 0, 300, "東"),
        Timing("0", 300, 600, "京"),
    )


# whisper-cli writes each token's bytes (whisper_token_to_str) and escapes only `"` and `\`: a
# character its vocabulary lacks spans tokens, so the file is not UTF-8; a control character raw


def _with_bytes(value: object, texts: list[bytes]) -> bytes:
    """``value`` as JSON, each ``"@N@"`` string written as ``texts[N]``'s bytes: whisper-cli's way."""
    data = json.dumps(value).encode()
    for k, text in enumerate(texts):
        data = data.replace(f'"@{k}@"'.encode(), b'"' + text + b'"')
    return data


def _sentence(start: int, end: int, text: str, *tokens: dict[str, object]) -> dict[str, object]:
    return {"offsets": {"from": start, "to": end}, "text": text, "tokens": list(tokens)}


# " café", its é split over two tokens: C3, then A9
_SPLIT: Final = _with_bytes(
    {
        "transcription": [
            _sentence(0, 1000, "@0@", _token("@1@", 0, 500, 10), _token("@2@", 500, 1000, 60))
        ]
    },
    [" café".encode(), b" caf\xc3", b"\xa9"],
)


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"], ids=["", "a BOM"])
def test_a_character_split_across_tokens_is_joined_into_its_word(bom: bytes) -> None:
    reading = subverter.read("json", bom + _SPLIT, "a.json")
    assert reading.cues == (Cue(0, 1000, " café", "0"),)
    assert reading.words == (Timing("0", 100, 1000, " café"),)


def test_without_spaces_a_split_character_is_one_word_over_its_tokens() -> None:
    # 鬱 (E9 AC B1), not one of whisper's tokens: two of them -- one word, from the first's start
    tokens = (_token("@1@", 0, 300), _token("@2@", 300, 600), _token("は", 600, 900))
    sentence = _sentence(0, 900, "@0@", *tokens)
    data = _with_bytes(
        {"result": {"language": "ja"}, "transcription": [sentence]},
        ["鬱は".encode(), b"\xe9\xac", b"\xb1"],
    )
    assert subverter.read("json", data, "a.json").words == (
        Timing("0", 0, 600, "鬱"),
        Timing("0", 600, 900, "は"),
    )


def test_a_character_over_three_tokens_is_one() -> None:
    # 😀 (F0 9F 98 80) over " F0 9F", "98", "80": one word, the three tokens' span
    tokens = (_token("@0@", 0, 100), _token("@1@", 100, 200), _token("@2@", 200, 300))
    sentence = _sentence(0, 300, " 😀", *tokens)
    data = _with_bytes({"transcription": [sentence]}, [b" \xf0\x9f", b"\x98", b"\x80"])
    assert subverter.read("json", data, "a.json").words == (Timing("0", 0, 300, " 😀"),)


def test_a_character_split_across_sentences_is_the_one_where_it_starts() -> None:
    # -ml N splits a sentence between tokens: é's C3 ends one, its A9 starts the next
    first = _sentence(0, 500, "@0@", _token("@0@", 0, 500))
    second = _sentence(500, 1000, "@1@", _token("@2@", 500, 600), _token(" ok", 600, 1000))
    data = _with_bytes({"transcription": [first, second]}, [b" caf\xc3", b"\xa9 ok", b"\xa9"])
    reading = subverter.read("json", data, "a.json")
    assert reading.cues == (Cue(0, 500, " café", "0"), Cue(500, 1000, " ok", "1"))
    assert reading.words == (Timing("0", 0, 500, " café"), Timing("1", 600, 1000, " ok"))


@pytest.mark.parametrize(
    ("data", "where"),
    [
        (_with_bytes({"transcription": [{"text": "@0@"}]}, [b"caf\xe9"]), ".transcription[0].text"),
        (
            _with_bytes(
                {"transcription": [_sentence(0, 500, " ok", _token("@0@", 0, 500))]}, [b" \xc3"]
            ),
            ".transcription[0].tokens[0].text",
        ),
        (
            _with_bytes({"transcription": [{"text": "@0@"}, {"text": "@1@"}]}, [b"\xc3", b"x"]),
            ".transcription[0].text",
        ),
        (
            _with_bytes(
                {"transcription": [{"text": "@0@"}, {"text": "@1@"}]}, [b"\xc3", b"\xa9\xff"]
            ),
            ".transcription[1].text",
        ),
        (_with_bytes({"segments": [{"text": "@0@"}]}, [b"\xff"]), ".segments[0].text"),
        (
            b'{"segments": [{"text": "a", "words": [{"word": "\\ud800"}]}]}',
            ".segments[0].words[0].word",
        ),
    ],
    ids=[
        "a Latin-1 byte",
        "a character never completed",
        "a character broken by the next text",
        "a byte past a character joined",
        "WhisperX",
        "a lone surrogate",
    ],
)
def test_text_not_utf8_once_joined_is_refused_where_it_is(data: bytes, where: str) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(f'not UTF-8: a.json ({where})')}$"):
        _ = subverter.read("json", data, "a.json")


def test_in_a_file_not_utf8_an_escaped_byte_surrogate_is_its_byte() -> None:
    # surrogateescape's: the raw byte B1 and the escape \udcb1 are one string once read
    data = b'{"segments": [{"text": "\xe9\xac"}, {"text": "\\udcb1"}]}'
    assert [c.text for c in subverter.read("json", data, "a.json").cues] == ["鬱", ""]


def test_a_raw_control_character_reads_as_its_escaped_form() -> None:
    escaped = _cli([{"offsets": {"from": 0, "to": 1500}, "text": " a\tb\nc"}])
    raw = escaped.replace(b"\\t", b"\t").replace(b"\\n", b"\n")
    assert raw != escaped
    assert subverter.read("json", raw, "a.json") == subverter.read("json", escaped, "a.json")


# --- WhisperX: segments in seconds, their words their own; a value of the wrong kind is none


def test_whisperx_segments_and_words_in_seconds() -> None:
    words = [{"word": "Hi", "start": 0.5, "end": 0.8}, {"word": "there", "start": 0.9, "end": 1.25}]
    data = json.dumps(
        {"segments": [{"start": 0.5, "end": 1.25, "text": "Hi there", "words": words}]}
    )
    assert subverter.read("json", data.encode(), "a.json") == Reading(
        "WhisperX JSON",
        has_words=True,
        cues=(Cue(500, 1250, "Hi there", "0"),),
        words=(Timing("0", 500, 800, "Hi"), Timing("0", 900, 1250, "there")),
    )


def test_whisperx_values_as_typed() -> None:
    # a decimal string a number, rounded half up to the ms (1.0005 s: 1000.5 ms, 1001); true no
    # time; null text nothing; a number as text its JSON; a JSON number past a double no time
    segments = [
        {"start": "1.0005", "end": True, "text": None},
        {"start": 1e999, "end": 0, "text": 5},
    ]
    data = b'{"segments": ' + json.dumps(segments).replace("Infinity", "1e999").encode() + b"}"
    assert subverter.read("json", data, "a.json") == Reading(
        "WhisperX JSON", has_words=False, cues=(Cue(1001, None, "", "0"), Cue(None, 0, "5", "1"))
    )


@pytest.mark.parametrize(("seconds", "end"), [("1e305", 10**308), ("1e306", None)])
def test_a_time_past_a_doubles_range_is_none(seconds: str, end: int | None) -> None:
    # in ms: 10**308 is inside a double's range (its largest, ~1.8e308), 10**309 past it
    data = f'{{"segments": [{{"start": 0, "end": {seconds}, "text": "x"}}]}}'.encode()
    assert subverter.read("json", data, "a.json").cues == (Cue(0, end, "x", "0"),)


def test_a_token_or_word_not_an_object_is_no_value() -> None:
    tokens = [5, _token(" ok", 0, 500)]  # a malformed token: skipped
    cli = _cli([{"offsets": {"from": 0, "to": 500}, "text": " ok", "tokens": tokens}])
    assert subverter.read("json", cli, "a.json").words == (Timing("0", 0, 500, " ok"),)
    words = ["nope", {"word": "ok", "start": 0, "end": 0.5}]  # a malformed word: skipped
    wx = json.dumps({"segments": [{"start": 0, "end": 0.5, "text": "ok", "words": words}]}).encode()
    assert subverter.read("json", wx, "a.json").words == (Timing("0", 0, 500, "ok"),)


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("a.vtt", "WEBVTT\n\n00:01.000 --> 00:02.000\nA &amp; B\n"),
        (
            "h.vtt",
            "WEBVTT\n\n00:01.000 --> 00:02.000\n<u>A</u> &amp;\n\n00:02.000 --> 00:03.000\nA <u>&amp;</u>\n",
        ),
    ],
)
def test_a_vtts_texts_hold_references_kept_for_their_consumer_to_decode(
    name: str, data: str
) -> None:
    reading = subverter.read("vtt", data.encode(), name)
    assert reading.has_references
    assert "&amp;" in reading.cues[0].text  # as written: its runs between tags decoded after


@pytest.mark.parametrize("fmt", ["srt", "lrc", "csv", "tsv", "json"])
def test_no_other_format_holds_references(fmt: str) -> None:
    data = {
        "srt": "1\n00:00:01,000 --> 00:00:02,000\nA &amp; B\n",
        "lrc": "[00:01.00]A &amp; B\n",
        "csv": "start,end,text\n1000,2000,A &amp; B\n",
        "tsv": "start\tend\ttext\n1000\t2000\tA &amp; B\n",
        "json": json.dumps({"segments": [{"start": 1, "end": 2, "text": "A &amp; B"}]}),
    }[fmt]
    reading = subverter.read(fmt, data.encode(), f"a.{fmt}")
    assert not reading.has_references
    assert reading.cues[0].text == "A &amp; B"


@pytest.mark.parametrize(
    ("fmt", "escapes"),
    [
        ("srt", True),
        ("vtt", False),
        ("lrc", False),
        ("csv", False),
        ("tsv", False),
        ("json", False),
    ],
)
def test_only_a_subrips_texts_hold_ass_escapes(fmt: str, escapes: bool) -> None:
    # ffmpeg's subrip decoder passes its text to ASS as written; its webvtt and text decoders
    # escape a backslash (a word joiner after it), and the W3C's WebVTT has no escape
    data = {
        "srt": "1\n00:00:01,000 --> 00:00:02,000\none\\Ntwo\n",
        "vtt": "WEBVTT\n\n00:01.000 --> 00:02.000\none\\Ntwo\n",
        "lrc": "[00:01.00]one\\Ntwo\n",
        "csv": "start,end,text\n1000,2000,one\\Ntwo\n",
        "tsv": "start\tend\ttext\n1000\t2000\tone\\Ntwo\n",
        "json": json.dumps({"segments": [{"start": 1, "end": 2, "text": "one\\Ntwo"}]}),
    }[fmt]
    reading = subverter.read(fmt, data.encode(), f"a.{fmt}")
    assert (reading.has_ass_escapes, reading.cues[0].text) == (escapes, "one\\Ntwo")
