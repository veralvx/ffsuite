"""Each reader against its rules, as recorded (docs/decisions.md's rows, the readers' docstrings):
the dispatcher, the line ends of every format and the other formats here; SubRip's and WebVTT's
cues in ``test_cues.py``, LRC's lines in ``test_lrc.py``.

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
        # Chromium 141: `fi\ufffdrst\nline2` (measured), its lines joined here by a space
        (
            "vtt",
            b"WEBVTT\n\n00:01.000 --> 00:02.000\nfi\x00rst\nline2\n",
            ["fi\ufffdrst line2"],
            "line 4",
        ),
        ("lrc", b"[00:01.00]fi\x00rst\n[00:03.00]second\n", ["fi\ufffdrst", "second"], "line 1"),
        ("csv", b"start,end,text\n1000,2000,fi\x00rst\n", ["fi\ufffdrst"], "line 2"),
        ("tsv", b"start\tend\ttext\n1000\t2000\tfi\x00rst\n", ["fi\ufffdrst"], "line 2"),
        (
            "json",
            _cli([{"offsets": {"from": 0, "to": 1500}, "text": " fi\u0000rst"}]),
            [" fi\ufffdrst"],
            ".transcription[0].text",
        ),
        (
            "json",
            _cli([{"offsets": {"from": 0, "to": 1500}, "text": " a"}]).replace(
                b" a", b" fi\x00rst"
            ),
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


def test_a_nul_in_a_word_reads_as_u_fffd_noted_by_its_path() -> None:
    whisperx = {"segments": [{"start": 1, "end": 2, "text": "ab", "words": [{"word": "a\u0000b"}]}]}
    reading = subverter.read("json", json.dumps(whisperx).encode(), "a.json")
    assert [w.text for w in reading.words] == ["a\ufffdb"]
    assert reading.notes == (_NUL_NOTE.format(n=1, where=".segments[0].words[0].word"),)
    tokens = [_token(" a\u0000b", 0, 500)]
    cli = _cli([{"offsets": {"from": 0, "to": 500}, "text": " ab", "tokens": tokens}])
    reading = subverter.read("json", cli, "a.json")
    assert [w.text for w in reading.words] == [" a\ufffdb"]
    where = ".transcription[0].tokens[0].text"
    assert reading.notes == (_NUL_NOTE.format(n=1, where=where),)


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
