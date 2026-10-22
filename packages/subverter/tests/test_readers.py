"""Each reader against its rules, as recorded (docs/decisions.md's rows, the readers' docstrings):
the dispatcher, and what the formats share -- line ends, text not UTF-8, a NUL, their texts'
flags; SubRip's and WebVTT's cues in ``test_cues.py``, LRC's lines in ``test_lrc.py``, CSV's and
TSV's in ``test_table.py``, whisper JSON's in ``test_whisper.py``.

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
from subverter import Cue
from subverter.readers import subrip, webvtt

# --- the dispatcher: a .txt and an unknown format refused, in the words ffman's tests record


@pytest.mark.parametrize(
    ("fmt", "message"),
    [
        (
            "txt",
            "a .txt transcript has no timestamps; use whisper-cli -osrt, -ovtt, -olrc, -ocsv, -oj or -ojf, or OpenAI whisper's or WhisperX's srt, vtt, tsv or json",
        ),
        ("xyz", "unsupported subtitle format '.xyz' (srt, vtt, lrc, csv, tsv, json)"),
    ],
)
def test_a_format_without_a_reader_is_refused(fmt: str, message: str) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}$"):
        _ = subverter.read(fmt, b"x", f"a.{fmt}")


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
_BOTH: Final = (Cue(1000, 2000, "first\nline2"), Cue(3000, 4000, "second"))
_NO_TEXT: Final = (Cue(1000, 2000, ""), Cue(3000, 4000, ""))


@pytest.mark.parametrize(
    ("fmt", "text", "cues"),
    [
        # Chromium 141, each: a lone CR a line end, in a line too; CR CR LF and LF CR two ends,
        # so a blank line after each timing line -- its cue of no text
        ("vtt", _VTT.replace("\n", "\r"), _BOTH),
        ("vtt", _VTT.replace("\n", "\r", 3), _BOTH),
        ("vtt", _VTT.replace("first", "fi\rrst"), (Cue(1000, 2000, "fi\nrst\nline2"), _BOTH[1])),
        ("vtt", _VTT.replace("line2\n\n", "line2\r\r"), _BOTH),
        ("vtt", _VTT.replace("\n", "\r\r\n"), _NO_TEXT),
        ("vtt", _VTT.replace("\n", "\n\r"), _NO_TEXT),
        # ffmpeg 8.1.2, each: a lone CR a line end, in a line too; CR CR LF one; LF CR two, each
        # cue's empty lines skipped (its texts after them noted)
        ("srt", _SRT.replace("\n", "\r"), _BOTH),
        ("srt", _SRT.replace("\n", "\r", 3), _BOTH),
        ("srt", _SRT.replace("first", "fi\rrst"), (Cue(1000, 2000, "fi\nrst\nline2"), _BOTH[1])),
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


def test_a_cues_lines_are_joined_each_its_characters_whole() -> None:
    # é begun in a line, ended in the next: its lines joined by a line break, as any cue's
    data = b"1\n00:00:01,000 --> 00:00:02,000\ncaf\xc3\n\xa9 ok\n"
    assert subverter.read("srt", data, "a.srt").cues == (Cue(1000, 2000, "café\n ok"),)


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


# --- a NUL in a text, any format: U+FFFD, as the W3C's WebVTT parser reads one, noted -- kept, it
# would end libass's script and ffmpeg's SubRip reading there, every later cue lost (measured)
_NUL_NOTE: Final = "{n} NULs read as U+FFFD, as the W3C reads them: the first in {where}"
_SRT_NUL: Final = (
    b"1\n00:00:01,000 --> 00:00:02,000\nfi\x00rst\n\n2\n00:00:03,000 --> 00:00:04,000\nsecond\n"
)


@pytest.mark.parametrize(
    ("fmt", "data", "texts", "where"),
    [
        ("srt", _SRT_NUL, ["fi\ufffdrst", "second"], "line 3"),
        # Chromium 141: `fi\ufffdrst\nline2` (measured)
        (
            "vtt",
            b"WEBVTT\n\n00:01.000 --> 00:02.000\nfi\x00rst\nline2\n",
            ["fi\ufffdrst\nline2"],
            "line 4",
        ),
        ("lrc", b"[00:01.00]fi\x00rst\n[00:03.00]second\n", ["fi\ufffdrst", "second"], "line 1"),
        ("csv", b"start,end,text\n1000,2000,fi\x00rst\n", ["fi\ufffdrst"], "line 2"),
        ("tsv", b"start\tend\ttext\n1000\t2000\tfi\x00rst\n", ["fi\ufffdrst"], "line 2"),
        (
            "json",
            json.dumps(
                {"transcription": [{"offsets": {"from": 0, "to": 1500}, "text": " fi\u0000rst"}]}
            ).encode(),
            [" fi\ufffdrst"],
            ".transcription[0].text",
        ),
        (
            "json",
            json.dumps({"transcription": [{"offsets": {"from": 0, "to": 1500}, "text": " a"}]})
            .encode()
            .replace(b" a", b" fi\x00rst"),
            [" fi\ufffdrst"],
            ".transcription[0].text",
        ),
    ],
    ids=["srt", "vtt", "lrc", "csv", "tsv", "whisper-cli, escaped", "whisper-cli, raw"],
)
def test_a_nul_reads_as_u_fffd_noted(fmt: str, data: bytes, texts: list[str], where: str) -> None:
    reading = subverter.read(fmt, data, f"a.{fmt}")
    assert [c.text for c in reading.cues] == texts
    assert reading.notes == (_NUL_NOTE.format(n=1, where=where),)


def test_nuls_counted_the_first_named() -> None:
    data = _SRT_NUL.replace(b"second", b"se\x00co\x00nd")
    reading = subverter.read("srt", data, "a.srt")
    assert [c.text for c in reading.cues] == ["fi\ufffdrst", "se\ufffdco\ufffdnd"]
    assert reading.notes == (_NUL_NOTE.format(n=3, where="line 3"),)


def test_a_nul_is_noted_where_it_is() -> None:
    data = _SRT_NUL.replace(b"fi\x00rst", b"first").replace(b"second", b"sec\x00ond")
    reading = subverter.read("srt", data, "a.srt")
    assert reading.notes == (_NUL_NOTE.format(n=1, where="line 7"),)
    both = {
        "segments": [{"start": 1, "end": 2, "text": "a\u0000b", "words": [{"word": "a\u0000b"}]}]
    }
    reading = subverter.read("json", json.dumps(both).encode(), "a.json")
    assert reading.notes == (_NUL_NOTE.format(n=2, where=".segments[0].text"),)


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


@pytest.mark.parametrize("fmt", ["srt", "vtt", "lrc", "csv", "tsv", "json"])
def test_only_an_lrcs_texts_hold_word_stamps(fmt: str) -> None:
    # Enhanced LRC's <mm:ss.xx>, a word's start, kept for its consumer (``unstamped``)
    data = {
        "srt": "1\n00:00:01,000 --> 00:00:02,000\n<00:01.50>two\n",
        "vtt": "WEBVTT\n\n00:01.000 --> 00:02.000\n<00:01.50>two\n",
        "lrc": "[00:01.00]<00:01.50>two\n",
        "csv": "start,end,text\n1000,2000,<00:01.50>two\n",
        "tsv": "start\tend\ttext\n1000\t2000\t<00:01.50>two\n",
        "json": json.dumps({"segments": [{"start": 1, "end": 2, "text": "<00:01.50>two"}]}),
    }[fmt]
    reading = subverter.read(fmt, data.encode(), f"a.{fmt}")
    assert (reading.has_word_stamps, reading.cues[0].text) == (fmt == "lrc", "<00:01.50>two")
