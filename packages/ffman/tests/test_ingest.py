import codecs
import json
import re
import time
from fractions import Fraction
from pathlib import Path
from typing import Final

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from subverter.transcript import Chunk, Word

from ffman.errors import REFUSALS, FfmanError
from ffman.subs.ass import Style, script
from ffman.subs.ingest import passed
from ffman.subs.markup import Markup, clean
from ffman.subs.srt import srt
from tests.support.ingesting import ingested
from tests.support.transcripts import HOSTILE, encoded

DROPPED: Final = (
    "{n} cues dropped: a line holding --> that is no WebVTT timing line (W3C), the first {line} "
    "on line {at}"
)
NUL_NOTE: Final = "{n} NULs read as U+FFFD, as the W3C reads them: the first in line {line}"
UNTIMED: Final = "{n} cues dropped: no time read for their start or end, the first, {text}"
REVERSED: Final = "{n} cues dropped: ending before they begin, the first, {text}"
SAME_START: Final = (
    "{n} cues dropped: beginning with the next, one cue shown at a time, the first, {text}"
)


def put(tmp_path: Path, name: str, text: str | bytes) -> str:
    path = tmp_path / name
    _ = path.write_bytes(encoded(text))
    return str(path)


def test_srt_crlf_bom_sorted_and_trimmed(tmp_path: Path) -> None:
    srt = "\ufeff1\r\n00:00:02,000 --> 00:00:04,000\r\n<i>Second</i>\r\n\r\n2\r\n00:00:01,000 --> 00:00:03,000\r\nFirst\r\n  line\r\n"
    t = ingested(put(tmp_path, "a.srt", srt))
    assert (t.fmt, t.source, t.has_words, t.words) == ("srt", ".srt", False, ())
    assert t.chunks == (
        Chunk(1000, 2000, "First line", ""),
        Chunk(2000, 4000, "Second", ""),
    )  # overlap ended by the next


def test_vtt_hours_settings_and_tags(tmp_path: Path) -> None:
    vtt = "WEBVTT\n\n1:00:01.500 --> 1:00:02.000 align:start\n{\\an8}Up \\N there\n"
    # ASS's {\an8} and \N: text in WebVTT, as Chromium, ffmpeg and VLC 3 show them (6.8.2)
    assert ingested(put(tmp_path, "a.vtt", vtt)).chunks == (
        Chunk(3601500, 3602000, r"{\an8}Up \N there", ""),
    )


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("C:\\new \\table", "C:\\new \\table"),  # before 6.8.2: `C: ew able`
        ("a\\nb\\tc", "a\\nb\\tc"),
        ("{\\i1}it{\\i0} x", "{\\i1}it{\\i0} x"),
        ("a\tb", "a b"),  # a tab: a blank, squeezed as any
    ],
)
def test_a_webvtt_texts_backslashes_and_braces_are_text(
    tmp_path: Path, text: str, shown: str
) -> None:
    # as Chromium 141 shows them (measured), ffmpeg's decoder (it escapes them for libass) and
    # VLC 3 (subsvtt.c) too
    t = ingested(put(tmp_path, "a.vtt", f"WEBVTT\n\n00:01.000 --> 00:02.000\n{text}\n"))
    assert [c.text for c in t.chunks] == [shown]


def test_a_webvtt_texts_backslashes_and_braces_are_burned_as_written(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "typed.vtt", HOSTILE["typed.vtt"]))
    drawn = "C:\\\u2060new \\\u2060table \\{\\\u2060an8\\}"  # libass's escapes (Text drawn)
    assert f",{drawn}\n" in script(t, 1920, 1080, Style())[0]


def test_highlighted_cues_become_sentences_and_words(tmp_path: Path) -> None:
    cues = "".join(
        f"{i}\n00:00:0{i},000 --> 00:00:0{i + 1},000\n{text}\n\n"
        for i, text in enumerate(["<u>Hi</u> you", "Hi <u>you</u>", "<u>Hi</u> you"], 1)
    )
    t = ingested(put(tmp_path, "h.srt", cues))
    assert (t.source, t.has_words) == ("OpenAI whisper or WhisperX --highlight_words .srt", True)
    assert [c.text for c in t.chunks] == [
        "Hi you",
        "Hi you",
    ]  # the underline moved back: a new sentence
    assert [(w.segment, w.text) for w in t.words] == [("0", "Hi"), ("0", "you"), ("1", "Hi")]


TRANSCRIPTS: Final = Path(__file__).parent / "fixtures" / "transcripts"


@pytest.mark.parametrize(
    ("highlighted", "written"),
    [("wx-ja-highlight.srt", "wx-ja.json"), ("openai-words.srt", "openai-words.json")],
    ids=["WhisperX, ja", "OpenAI whisper, a cue a word"],
)
def test_a_highlighted_transcript_holds_its_jsons_words(highlighted: str, written: str) -> None:
    # each written by its tool's own writers from one result (docs/upgrading.md, 12 and 26)
    got, want = (
        [(w.start, w.end, w.text) for w in ingested(TRANSCRIPTS / name).words]
        for name in (highlighted, written)
    )
    assert got == want


def test_whisperxs_ja_highlighted_cues_burn_unspaced_as_its_json() -> None:
    # its sentence its JSON's -- its end its last word's (utils.py, 3.7.7 on), the JSON's its
    # segment's -- so its chunk-word line abuts its characters as the JSON's (S163)
    srt, js = (ingested(TRANSCRIPTS / n) for n in ("wx-ja-highlight.srt", "wx-ja.json"))
    assert [c.text for c in srt.chunks] == [c.text for c in js.chunks] == ["今日は良い天気です"]
    ass = script(srt, 1920, 1080, Style("chunk-word", "plain"))[0]
    first = next(line for line in ass.splitlines() if line.startswith("Dialogue: 0"))
    assert re.sub(r".*\}", "", first) == "日は良い天気です"


def test_lrc_and_tables(tmp_path: Path) -> None:
    lrc = ingested(put(tmp_path, "a.lrc", "[00:02.50]Two\n[00:01]One\nno stamp\n"))
    assert lrc.chunks == (
        Chunk(1000, 2500, "One", ""),
        Chunk(2500, 5500, "Two", ""),
    )  # the last: 3 s
    csv = ingested(put(tmp_path, "a.csv", 'start,end,text\n1000,2000,"a, ""b"""\n'))
    assert csv.chunks == (Chunk(1000, 2000, 'a, "b"', ""),)
    # a header names start and end, in any order (stage B; bash: only one starting with start)
    other = ingested(put(tmp_path, "b.csv", 'text,end,start\n"a",2000,1000\n'))
    assert other.chunks == (Chunk(1000, 2000, "a", ""),)
    # without one, the columns are start, end, text
    plain = ingested(put(tmp_path, "d.csv", "500,2000,1000\n"))
    assert plain.chunks == (Chunk(500, 2000, "1000", ""),)
    # a time that is not a number is no time (stage B; bash's awk read "x" as 0 ms)
    with pytest.raises(REFUSALS, match="no timed text found"):
        _ = ingested(put(tmp_path, "c.csv", "start,end,text\nx,2000,a\n"))
    tsv = ingested(put(tmp_path, "a.tsv", "0\t900\tno header\n"))
    assert tsv.chunks == (Chunk(0, 900, "no header", ""),)


def test_whisper_cli_words(tmp_path: Path) -> None:
    def token(text: str, a: int, z: int, dtw: float | None = None) -> dict[str, object]:
        made: dict[str, object] = {"text": text, "offsets": {"from": a, "to": z}}
        if dtw is not None:
            made["t_dtw"] = dtw
        return made

    doc = {"transcription": [
        {"offsets": {"from": 0, "to": 1000}, "text": " Hi there", "tokens": [token("[_BEG_]", 0, 0), token(" Hi", 0, 400, 10), token(" the", 400, 700, 50), token("re", 700, 1000, 70)]},
        {"offsets": {"from": 1000, "to": 2000}, "text": " Late", "tokens": [token(" Late", 1100, 1900, 500)]},
    ]}  # fmt: skip
    t = ingested(put(tmp_path, "a.json", json.dumps(doc)))
    assert (t.source, t.has_words) == ("whisper-cli -ojf JSON", True)
    assert t.words == (
        Word("0", 100, 500, "Hi"),
        Word("0", 500, 1000, "there"),
        Word("1", 1100, 1900, "Late"),
    )  # DTW, then offsets
    assert t.notes == (
        "DTW word times were outside their sentence or not in order in 1 of 2 sentences: used token offsets there",
    )
    plain = ingested(
        put(
            tmp_path,
            "b.json",
            json.dumps({"transcription": [{"offsets": {"from": "5", "to": 900}, "text": 7}]}),
        )
    )
    assert (plain.source, plain.chunks) == ("whisper-cli JSON", (Chunk(5, 900, "7", "0"),))


def test_whisper_cli_token_bytes_are_joined_into_characters(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "bytes.json", HOSTILE["bytes.json"]))
    assert t.chunks == (Chunk(0, 1000, "鬱は", "0"), Chunk(1000, 2000, "心", "1"), Chunk(2000, 3000, "い", "2"))  # fmt: skip
    assert t.words == (
        Word("0", 50, 600, "鬱"),
        Word("0", 600, 1000, "は"),
        Word("1", 1050, 2000, "心"),
        Word("2", 2150, 3000, "い"),
    )  # each in the token and the sentence it starts; the tab trimmed as any space


def test_a_character_split_between_cues_is_joined_into_the_one_it_starts(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "split.srt", HOSTILE["split.srt"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (0, 50, "Это"),
        (50, 100, "ё"),
        (100, 200, "л"),
        (200, 250, "ка"),
        (250, 300, "и"),
        (300, 350, "😀"),
    ]  # the last cue's text, 😀's last byte alone, given to the one before: no text, no chunk


def test_a_transcript_not_utf8_is_refused_by_its_line(tmp_path: Path) -> None:
    path = put(tmp_path, "latin-1.srt", HOSTILE["latin-1.srt"])
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'not UTF-8: {path} (line 3)')}$"):
        _ = ingested(path)


def test_a_webvtt_without_its_signature_is_refused(tmp_path: Path) -> None:
    path = put(tmp_path, "unsigned.vtt", HOSTILE["unsigned.vtt"])
    why = f"not a WebVTT file: {path} (its first line is not WEBVTT)"
    with pytest.raises(REFUSALS, match=f"^{re.escape(why)}$"):
        _ = ingested(path)


def test_a_utf16_lrc_is_read_as_navidrome_and_jellyfin_read_it(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "utf-16.lrc", HOSTILE["utf-16.lrc"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [(0, 200, "café"), (200, 3200, "second")]
    assert t.notes == ()


def test_an_lrc_line_read_past_its_form_or_dropped_is_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "lines.lrc", HOSTILE["lines.lrc"]))
    # the line before 0 clamped, as any cue's; the empty last one ends `two`
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (0, 100, "before 0"),
        (100, 200, "blank"),
        (200, 400, "two"),
    ]
    assert t.notes == (
        "1 LRC lines had blanks before their stamp, read as Navidrome and Jellyfin read them (ffmpeg drops them): the first, [00:00.10]blank on line 2",
        "1 LRC lines had a stamp with a minus, a time before 0, read as ffmpeg writes and reads it (Navidrome and Jellyfin read none): the first, [-00:00.50]before 0 on line 3",
        "2 LRC lines dropped, opened by no stamp ffman reads nor a tag: the first, no stamp on line 5",
    )


@pytest.mark.parametrize("name", ["utf-16.csv", "utf-16.tsv"])
def test_a_utf16_table_is_read_as_a_subrip_is(tmp_path: Path, name: str) -> None:
    t = ingested(put(tmp_path, name, HOSTILE[name]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [(0, 200, "café"), (200, 400, "second")]
    assert t.notes == ()


def test_a_utf16_subrip_is_read_as_ffmpeg_recodes_it(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "utf-16.srt", HOSTILE["utf-16.srt"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [(0, 200, "café"), (200, 400, "second")]
    assert t.notes == ()


@pytest.mark.parametrize(
    ("name", "why"),
    [
        ("utf-16-bad.srt", "not UTF-16: {path} (line 3)"),
        ("utf-16-bad.lrc", "not UTF-16: {path} (line 2)"),
        ("utf-16-bad.tsv", "not UTF-16: {path} (line 3)"),
        ("utf-16.vtt", "not a WebVTT file: {path} (UTF-16: WebVTT is UTF-8)"),
    ],
)
def test_a_utf16_transcript_ffman_cannot_read_is_refused_so_named(
    tmp_path: Path, name: str, why: str
) -> None:
    path = put(tmp_path, name, HOSTILE[name])
    with pytest.raises(REFUSALS, match=f"^{re.escape(why.format(path=path))}$"):
        _ = ingested(path)


@pytest.mark.parametrize(
    ("name", "texts"),
    [
        ("cr.srt", ["first line", "second"]),
        ("crcrlf.srt", ["first line", "second"]),
        ("cr.vtt", ["first line", "second"]),
        ("cr.lrc", ["first", "second"]),
    ],
)
def test_a_transcripts_lines_may_end_in_a_cr(tmp_path: Path, name: str, texts: list[str]) -> None:
    t = ingested(put(tmp_path, name, HOSTILE[name]))
    assert [c.text for c in t.chunks] == texts


def test_a_webvtts_cr_cr_lf_is_two_line_ends(tmp_path: Path) -> None:
    path = put(tmp_path, "crcrlf.vtt", HOSTILE["crcrlf.vtt"])  # a cue of no text: none timed
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'no timed text found in: {path}')}$"):
        _ = ingested(path)


@pytest.mark.parametrize(
    ("name", "text", "notes"),
    [
        pytest.param(
            "x.lrc",
            HOSTILE["no-line.lrc"],
            (
                "1 LRC lines dropped, opened by no stamp ffman reads nor a tag: the first, [1:02:03.00]an hour in on line 2",
            ),
            id="the reader's",
        ),
        pytest.param(
            "x.vtt",
            "WEBVTT\n\n1 --> 2\nx\n",
            (DROPPED.format(n=1, line="1 --> 2", at=3),),
            id="the reader's, WebVTT",
        ),
        pytest.param(
            "x.srt",
            "1\n00:00:02,000 --> 00:00:01,000\nbackwards\n",
            (REVERSED.format(n=1, text="backwards"),),
            id="the normaliser's",
        ),
        pytest.param(
            "x.srt",
            "1\n00:00:01,000 --> 00:00:02,000\n{hidden}\n",
            (
                "1 braced runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {hidden}",
            ),
            id="the markup's",
        ),
        pytest.param(
            "x.csv",
            "start,end,text\nabc,1,lost\n",
            (UNTIMED.format(n=1, text="lost"),),
            id="the normaliser's, no time",
        ),
        pytest.param(
            "x.srt",
            (
                f"1\n{'9' * 400}:00:00,000 --> 00:00:01,000\nlost\n\n"
                "2\n00:00:02,000 --> 00:00:01,000\nbackwards\n\n3\n00:00:03,000 --> 00:00:04,000\n{hidden}\n"
            ),
            (
                UNTIMED.format(n=1, text="lost"),
                REVERSED.format(n=1, text="backwards"),
                "1 braced runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {hidden}",
            ),
            id="every one, in order",
        ),
    ],
)
def test_no_timed_text_is_refused_with_the_notes_that_say_why(
    tmp_path: Path, name: str, text: str, notes: tuple[str, ...]
) -> None:
    path = put(tmp_path, name, text)
    with pytest.raises(
        FfmanError, match=f"^{re.escape(f'no timed text found in: {path}')}$"
    ) as refused:
        _ = ingested(path)
    assert refused.value.notes == notes


def test_a_subrip_cue_reads_on_past_an_empty_line_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "continued.srt", HOSTILE["continued.srt"]))
    assert [c.text for c in t.chunks] == ["first kept", "last credits"]
    how = "read as theirs, as ffmpeg reads them"
    assert t.notes == (f"2 cues held text after an empty line, {how}: the first, kept on line 5",)


def test_a_subrip_cue_reads_on_past_a_line_of_spaces_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "spaced.srt", HOSTILE["spaced.srt"]))
    assert [c.text for c in t.chunks] == ["first lost", "last credits"]
    how = "read as theirs, as MPC-HC and Subtitle Edit read them (ffmpeg's decoder drops it)"
    assert t.notes == (
        f"2 cues held text after a line of spaces, {how}: the first, lost on line 5",
    )


def test_a_webvtt_line_of_spaces_is_its_cues_text(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "whitespace.vtt", HOSTILE["whitespace.vtt"]))
    assert [c.text for c in t.chunks] == ["first second"]


def test_a_webvtt_text_in_no_cue_is_dropped_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "stray.vtt", HOSTILE["stray.vtt"]))
    assert [c.text for c in t.chunks] == ["first", "second"]
    how = "after an empty line, in no cue (W3C)"
    assert t.notes == (f"2 text blocks dropped: {how}, the first lost on line 6",)


def test_a_nul_reads_as_u_fffd_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "nul.srt", HOSTILE["nul.srt"]))
    assert [c.text for c in t.chunks] == ["fi\ufffdrst", "second"]
    assert t.notes == (NUL_NOTE.format(n=1, line=3),)


def test_an_ass_nul_reads_as_u_fffd_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "nul.ass", HOSTILE["nul.ass"]))
    assert (t.fmt, t.chunks, t.notes) == ("ass", (), (NUL_NOTE.format(n=1, line=12),))


@pytest.mark.parametrize(
    ("data", "n", "line"),
    [
        (b"a\0b", 1, 1),
        (b"a\r\nb\rc\nd\r\re\0f", 1, 6),  # an editor's lines: CRLF one end, CR CR two
        (b"\0\nx\0\0", 3, 1),  # counted, the first named
    ],
)
def test_an_ass_nul_is_u_fffd_in_ffmans_copy(data: bytes, n: int, line: int) -> None:
    found, fffd = passed(data, "a.ass"), "\ufffd".encode()
    assert (b"\0" in found.data, found.data.count(fffd)) == (False, n)
    assert found.data.replace(fffd, b"\0") == data  # the rest as it was
    assert found.notes == (NUL_NOTE.format(n=n, line=line),)


def test_an_ass_without_a_nul_is_copied_as_it_is() -> None:
    assert passed(b"[Script Info]\n", "a.ass") == (b"[Script Info]\n", ())


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
def test_a_utf_16_ass_is_utf_8_in_ffmans_copy(codec: str) -> None:
    data = "\ufeff[Script Info]\ncafé\n".encode(codec)  # its BOM: ffmpeg's reader recodes it
    assert passed(data, "a.ass") == ("[Script Info]\ncafé\n".encode(), ())  # not noted


def test_a_utf_16_ass_nul_is_u_fffd_noted() -> None:
    data = "\ufeffa\r\nb\x00c\x00".encode("utf-16-le")  # a character, its bytes UTF-16's
    assert passed(data, "a.ass") == (
        "a\r\nb\ufffdc\ufffd".encode(),
        (NUL_NOTE.format(n=2, line=2),),
    )


@pytest.mark.parametrize(
    ("data", "line"),
    [
        ("\ufeffa\nfi\ud800rst".encode("utf-16-le", "surrogatepass"), 2),  # a lone surrogate
        ("\ufeffa\nfi\udc00rst".encode("utf-16-be", "surrogatepass"), 2),
        ("\ufeffa\r\nb\rfi\ud800".encode("utf-16-le", "surrogatepass"), 3),  # its pair cut off
        ("\ufeffa\nb".encode("utf-16-le") + b"x", 2),  # an odd byte last
    ],
)
def test_an_ass_not_utf_16_after_its_bom_is_refused_by_its_line(
    tmp_path: Path, data: bytes, line: int
) -> None:
    path = put(tmp_path, "a.ass", data)
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'not UTF-16: {path} (line {line})')}$"):
        _ = ingested(path)


@given(st.text(), st.sampled_from(["utf-16-le", "utf-16-be"]))
def test_a_utf_16_ass_is_passed_as_its_utf_8(text: str, codec: str) -> None:
    """Recoded first: its copy and notes its UTF-8's, a U+0000 and a BOM inside alike."""
    assert passed(("\ufeff" + text).encode(codec), "a.ass") == passed(text.encode(), "a.ass")


@given(
    st.sampled_from([b"", codecs.BOM_UTF8, codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE]), st.binary()
)
@example(b"", codecs.BOM_UTF16_LE)  # its BOM in ``rest``: UTF-16 all the same
@example(b"", codecs.BOM_UTF16_BE + b"[\0")
def test_any_ass_is_passed_or_refused_by_its_line(bom: bytes, rest: bytes) -> None:
    utf16 = (bom + rest).startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE))
    codec = "utf-16" if utf16 else "utf-8"
    try:
        _ = (bom + rest).decode(codec)
    except UnicodeDecodeError:
        refused = rf"^not {codec.upper()}: a\.ass \(line [1-9][0-9]*\)$"
        with pytest.raises(REFUSALS, match=refused):
            _ = passed(bom + rest, "a.ass")
    else:
        found = passed(bom + rest, "a.ass").data
        assert b"\0" not in found
        _ = found.decode()  # UTF-8 whole, or this raises


def test_an_ass_refused_as_no_script_after_its_nul_notes(tmp_path: Path) -> None:
    path = put(tmp_path, "a.ass", b"\0[Script Info]\nScriptType: v4.00+\n")
    why = "its first line is not [Script Info]"
    with pytest.raises(FfmanError, match=re.escape(f"not an ASS file: {path} ({why})")) as refused:
        _ = ingested(path)
    assert refused.value.notes == (
        "1 NULs read as U+FFFD, as the W3C reads them: the first in line 1",
    )


@pytest.mark.parametrize(
    ("data", "line"),
    [
        ("[Script Info]\nTitle: Café\n".encode("cp1252"), 2),  # a header's byte too
        ("a\r\nb\rcafé".encode("cp1252"), 3),
        (b"a\n\xc3", 2),  # a character cut off
        (b"a\n\xc3\xa9\x80", 2),  # a continuation alone, after a whole one
        (b"\xef\xbb\xbfa\n\xed\xa0\x80", 2),  # a surrogate, after a UTF-8 BOM
    ],
)
def test_an_ass_not_utf_8_is_refused_by_its_line(tmp_path: Path, data: bytes, line: int) -> None:
    path = put(tmp_path, "a.ass", data)
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'not UTF-8: {path} (line {line})')}$"):
        _ = ingested(path)


def test_an_ass_in_utf_8_is_copied_as_it_is() -> None:
    data = codecs.BOM_UTF8 + "[Script Info]\r\ncafé \u2019x\u2019\n".encode()  # its BOM kept
    assert passed(data, "a.ass") == (data, ())


def test_the_hostile_utf_16_ass_files(tmp_path: Path) -> None:
    assert ingested(put(tmp_path, "utf-16.ass", HOSTILE["utf-16.ass"])).notes == ()
    path = put(tmp_path, "utf-16-bad.ass", HOSTILE["utf-16-bad.ass"])
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'not UTF-16: {path} (line 12)')}$"):
        _ = ingested(path)


SIGNATURE: Final = "its first line is not [Script Info]"
TYPE: Final = "no [V4+ Styles] or [V4 Styles] section, nor ScriptType v4.00+ or v4.00"


@pytest.mark.parametrize(
    ("name", "text", "why"),
    [
        ("a.ass", "", SIGNATURE),
        ("a.ass", "hello\n", SIGNATURE),
        ("a.ass", "; by hand\n[Script Info]\nScriptType: v4.00+\n", SIGNATURE),
        ("a.ass", "  [Script Info]\nScriptType: v4.00+\n", SIGNATURE),  # ffmpeg's: no space
        ("a.ass", "[script info]\nScriptType: v4.00+\n", SIGNATURE),  # ffmpeg's: its case
        ("a.ass", "[Script Info\n[V4+ Styles]\n", SIGNATURE),  # its 13 bytes, `]` the last
        ("a.ass", "[V4+ Styles]\n[Script Info]\nScriptType: v4.00+\n", SIGNATURE),
        ("a.ssa", "hello\n", SIGNATURE),
        ("a.ass", "[Script Info]\nPlayResX: 384\n", TYPE),
        ("a.ass", "[Script Info]\nScriptType: v4.00++\n", TYPE),  # libass's: neither
        ("a.ass", "[Script Info]\nscripttype: v4.00+\n", TYPE),  # libass's: its case
        ("a.ass", "[Script Info]\n[Events]\nScriptType: v4.00+\n", TYPE),  # not Info's
    ],
)
def test_an_ass_that_is_no_script_is_refused(
    tmp_path: Path, name: str, text: str, why: str
) -> None:
    path = put(tmp_path, name, text)
    kind = "an SSA" if name.endswith(".ssa") else "an ASS"
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'not {kind} file: {path} ({why})')}$"):
        _ = ingested(path)


@pytest.mark.parametrize(
    "data",
    [
        "[Script Info]\nScriptType: v4.00+\n",
        "[Script Info]\r\nScriptType: 4.00\t \r\n",  # SSA's, VSFilter's form
        "\ufeff\r\n\n[Script Info]\n[V4+ Styles]\n",  # a BOM, blank lines first
        "[Script Info]\n  [v4 styles]\n",  # libass's: any case, spaces first
        "[Script Info]\n[Aegisub Project Garbage]\nScriptType: v4.00+\n",
        "[Script Info] x\n\t ScriptType: v4.00+\n",  # ffmpeg reads 13 bytes
        "[Script Info]\n\ufeffScriptType: v4.00+\n",  # libass's: a BOM first skipped
        "\ufeff[Script Info]\nScriptType: v4.00+\n".encode("utf-16-le"),  # recoded first
    ],
)
def test_an_ass_script_is_passed(tmp_path: Path, data: str | bytes) -> None:
    assert ingested(put(tmp_path, "a.ass", data)).notes == ()


def test_the_hostile_cp1252_ass_is_refused(tmp_path: Path) -> None:
    path = put(tmp_path, "cp1252.ass", HOSTILE["cp1252.ass"])
    with pytest.raises(REFUSALS, match=f"^{re.escape(f'not UTF-8: {path} (line 12)')}$"):
        _ = ingested(path)


def test_a_csv_header_after_a_blank_line_is_its_header(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "late-header.csv", HOSTILE["late-header.csv"]))
    assert t.chunks == (Chunk(0, 300, "hello", ""),)


def test_a_line_holding_an_arrow_is_subrips_text_and_ends_a_webvtt_cue(tmp_path: Path) -> None:
    srt = ingested(put(tmp_path, "arrows.srt", HOSTILE["arrows.srt"]))
    assert [(c.start, c.end, c.text) for c in srt.chunks] == [
        (0, 200, "The sign said: Note: 1 --> 2 y"),
        (200, 400, "a --> b c"),
    ]
    vtt = ingested(put(tmp_path, "arrows.vtt", HOSTILE["arrows.vtt"]))
    assert [(c.start, c.end, c.text) for c in vtt.chunks] == [(0, 200, "x"), (200, 400, "next")]
    assert vtt.notes == (DROPPED.format(n=1, line="Note: 1 --> 2", at=5),)


def test_an_lrc_offset_moves_every_time_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "offset.lrc", HOSTILE["offset.lrc"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [(100, 200, "one"), (200, 3200, "two")]
    assert t.notes == (
        "LRC offset on line 2 applied: every line 500 ms sooner",
        "1 LRC offsets ignored, not a whole number of milliseconds: the first on line 1",
    )


def test_a_fraction_not_of_three_digits_is_ms_in_subrip_no_time_in_webvtt(tmp_path: Path) -> None:
    srt = ingested(put(tmp_path, "fraction.srt", HOSTILE["fraction.srt"]))
    assert [(c.start, c.end, c.text) for c in srt.chunks] == [(5, 25, "five"), (250, 400, "next")]
    assert srt.notes == (
        "2 times had a fraction not of three digits, read as milliseconds as ffmpeg and VLC read them: the first, 00:00:00,5 on line 2, as 0.005 s",
    )
    vtt = ingested(put(tmp_path, "fraction.vtt", HOSTILE["fraction.vtt"]))
    assert [(c.start, c.end, c.text) for c in vtt.chunks] == [(0, 200, "ok")]
    assert vtt.notes == (DROPPED.format(n=1, line="00:00.2 --> 00:00.400", at=6),)


def test_a_webvtt_timing_line_is_the_w3cs_else_its_cue_dropped_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "timestamps.vtt", HOSTILE["timestamps.vtt"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [(0, 100, "kept"), (300, 400, "last")]
    assert t.notes == (DROPPED.format(n=3, line="5 --> 7", at=6),)


def test_a_number_alone_before_a_timing_line_is_the_next_cues_index(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "index.srt", HOSTILE["index.srt"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (0, 200, "first"),
        (200, 400, "2."),
        (400, 600, "third"),
    ]
    assert t.notes == (
        "2 lines of a number alone before a timing line read as the next cue's index, as ffmpeg reads them: the first, 2 on line 4",
    )


def test_an_lrcs_text_is_as_its_readers_show_it_but_its_word_stamps(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "markup.lrc", HOSTILE["markup.lrc"]))
    assert [c.text for c in t.chunks] == [
        "x<3 and y>2 <i>i</i>",
        "C:\\temp\\new {\\an8}up &amp;",
        "Enhanced word times",
    ]
    assert t.notes == ()


_TAGGED: Final = "x<3 and y>2 <i>i</i>"
_ESCAPED: Final = "C:\\new \\table {\\an8}up"


@pytest.mark.parametrize(
    ("name", "texts", "words"),
    [
        ("markup.csv", [_TAGGED, f"{_ESCAPED} &amp;", "tab here line"], []),
        ("markup.tsv", [_TAGGED, f"{_ESCAPED} &amp;"], []),  # a TSV holds no tab, no break
        (
            "markup.json",
            [_TAGGED, f"{_ESCAPED} tab line"],
            ["x<3", "and", "y>2", "<i>i</i>", "C:\\new", "\\table", "{\\an8}up tab line"],
        ),
    ],
    ids=["csv", "tsv", "json"],
)
def test_a_csv_tsv_or_json_text_is_as_its_writer_wrote_it(
    tmp_path: Path, name: str, texts: list[str], words: list[str]
) -> None:
    t = ingested(put(tmp_path, name, HOSTILE[name]))
    assert [c.text for c in t.chunks] == texts
    assert [w.text for w in t.words] == words
    assert t.notes == ()


def test_a_tsv_line_of_no_tab_is_the_text_of_the_record_before(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "newline.tsv", HOSTILE["newline.tsv"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (0, 200, "past an hour newline"),
        (200, 400, "next"),
    ]
    assert t.notes == (
        "1 TSV lines of no tab read as the text of the record before, a line break in it (OpenAI whisper's and WhisperX's TSV): the first, newline on line 3",
    )


def test_the_whisper_filters_json_is_read_its_texts_as_written(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "filter.json", HOSTILE["filter.json"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (0, 200, 'Hello "world" \\ C:\\new'),
        (200, 400, "tab here newline"),
    ]
    assert (t.source, t.has_words, t.notes) == ("ffmpeg whisper filter JSON", False, ())


def test_a_subrips_ass_escapes_read_as_libass_draws_them(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "escapes.srt", HOSTILE["escapes.srt"]))
    assert [c.text for c in t.chunks] == ["one two a\u00a0b"]  # the break ffman's to place
    assert t.notes == ()


def test_a_subrips_tags_and_escapes_read_as_ffmpeg_then_libass_draw_them(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "markup.srt", HOSTILE["markup.srt"]))
    assert [c.text for c in t.chunks] == [
        "1 < 2 and 3 > 2",  # no tag: a space after its <, no name ffmpeg knows
        "<<quote>> one two",  # guillemets; <br> a line break, so a space, ffman wrapping
        "C:\\temp ew <c.yellow>c",  # \t text, \n a space (libass's); a "." no tag's
    ]
    assert t.notes == ()


def test_braces_and_backslashes_are_drawn_as_written(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "braces.srt", HOSTILE["braces.srt"]))
    assert [c.text for c in t.chunks] == ["a{b} c\\x"]  # \{ \} its braces; {d} a block, hidden
    assert t.notes == (
        "1 braced runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {d}",
    )
    (event,) = [
        line for line in script(t, 1920, 1080, Style())[0].splitlines() if "Dialogue" in line
    ]
    assert event.endswith(",a\\{b\\} c\\\u2060x")


@pytest.mark.parametrize(
    ("text", "shown", "notes"),
    [
        pytest.param(  # libass's blocks: ASS's comment form hidden, noted; tags alone, not
            "a{note}b {\\an8}c {y:i}d {}e {note2\\i1}f {unclosed",
            "ab c d e f {unclosed",
            (
                "2 braced runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {note}",
            ),
            id="hidden",
        ),
        pytest.param("a{\\an8} { \\i1}b", "a b", (), id="tags alone"),
        pytest.param(  # ffmpeg's decoder drops ASS's tags first: a block once they are off
            "x {a{\\i1}b}c",
            "x c",
            (
                "1 braced runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {ab}",
            ),
            id="tags inside",
        ),
        pytest.param("a \\{\\i1\\} b", "a \\ b", (), id="a backslash before tags"),
        pytest.param(  # a < no tag (ffmpeg's decoder): the block after it libass's
            "1 < 2 {note} and 3 > 2",
            "1 < 2 and 3 > 2",
            (
                "1 braced runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {note}",
            ),
            id="after a < no tag",
        ),
    ],
)
def test_a_subrips_braced_run_is_a_block_hidden_as_libass_hides_it(
    tmp_path: Path, text: str, shown: str, notes: tuple[str, ...]
) -> None:
    t = ingested(put(tmp_path, "a.srt", f"1\n00:00:00,000 --> 00:00:00,400\n{text}\n"))
    assert ([c.text for c in t.chunks], t.notes) == ([shown], notes)


def test_another_formats_braced_run_is_text(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "a.vtt", "WEBVTT\n\n00:00.000 --> 00:00.400\na{note}b\n"))
    assert ([c.text for c in t.chunks], t.notes) == (["a{note}b"], ())


def test_a_highlighted_subrips_words_read_its_escapes_too(tmp_path: Path) -> None:
    cues = "".join(
        f"{i}\n00:00:0{i},000 --> 00:00:0{i + 1},000\n{text}\n\n"
        for i, text in enumerate(["<u>New\\hYork</u> City", "New\\hYork <u>City</u>"], 1)
    )
    t = ingested(put(tmp_path, "h.srt", cues))
    assert [w.text for w in t.words] == ["New\u00a0York", "City"]


def test_an_override_opening_with_an_escape_is_dropped_but_in_webvtt_and_lrc(
    tmp_path: Path,
) -> None:
    # {\t(...)}: ASS's animation -- dropped, as ffmpeg's subrip decoder and VLC drop it; in
    # WebVTT (6.8.2) and LRC (the `lrc` box), text, as every reader shows it
    srt = ingested(put(tmp_path, "a.srt", "1\n00:00:00,000 --> 00:00:00,400\n{\\t(0,1)}a {\\n}b\n"))
    lrc = ingested(put(tmp_path, "a.lrc", "[00:00.00]{\\t(0,1)}a \\N\n[00:00.40]\n"))
    vtt = ingested(put(tmp_path, "a.vtt", "WEBVTT\n\n00:00.000 --> 00:00.400\n{\\t(0,1)}a \\N\n"))
    texts = (srt.chunks[0].text, lrc.chunks[0].text, vtt.chunks[0].text)
    assert texts == ("a b", "{\\t(0,1)}a \\N", "{\\t(0,1)}a \\N")


def test_lrc_lines_sharing_a_stamp_are_one_chunk_noted(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "shared.lrc", HOSTILE["shared.lrc"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (1000, 4000, "line one line two"),  # as the SubRip it was written from reads
        (4000, 7000, "next"),
    ]
    assert t.notes == (
        "1 LRC lines shared a stamp with a line before, joined to it, as Navidrome and Jellyfin show both (ffmpeg shows the last alone): the first, [00:01.00]line two on line 5",
    )


def test_an_lrc_text_its_start_shows_already_is_shown_once(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "twice.lrc", HOSTILE["twice.lrc"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (100, 200, "twice"),
        (200, 3200, "next"),
    ]
    assert t.notes == (
        "1 LRC lines dropped, opened by no stamp ffman reads nor a tag: the first, [00:099.00]none on line 4",
    )


def test_an_lrc_line_of_several_stamps_is_a_line_each(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "chorus.lrc", HOSTILE["chorus.lrc"]))
    assert [(c.start, c.end, c.text) for c in t.chunks] == [
        (0, 150, "chorus"),
        (150, 300, "spaced"),
        (300, 350, "chorus"),
        (350, 3350, "spaced"),
    ]


def test_whisperx_ties_and_gaps(tmp_path: Path) -> None:
    doc = {"segments": [{"start": 1, "end": 2, "text": "a b c", "words": [{"word": "a", "start": 1.0}, {"word": "b", "start": 1.0}, {"word": "c"}]}, {"start": 3, "end": 4, "text": "bare", "words": [{"word": "bare"}]}]}  # fmt: skip
    t = ingested(put(tmp_path, "x.json", json.dumps(doc)))
    assert [(w.text, w.start, w.end) for w in t.words] == [
        ("a", 1000, 1333),
        ("b", 1333, 1667),
        ("c", 1667, 2000),
    ]
    assert t.notes == (
        "2 words had no usable time of their own (untimed, tied, out of order or outside their sentence): placed between their neighbours",
        "1 sentences had no word timings: shown without word highlighting",
    )


# a sentence of no words, each source's: WhisperX's segment its aligner could not align
# (`alignment.py`: `"words": []`), whisper-cli's of special tokens alone, a highlighted run
# without `<u>`
_WORDLESS: Final = {
    "unaligned.json": json.dumps({"segments": [
        {"start": 1, "end": 2, "text": "one two", "words": [{"word": "one", "start": 1.0, "end": 1.5}, {"word": "two", "start": 1.5, "end": 2.0}]},
        {"start": 3, "end": 4, "text": "2024", "words": []},
    ]}),
    "specials.json": json.dumps({"result": {"language": "en"}, "transcription": [
        {"offsets": {"from": 1000, "to": 2000}, "text": " one two", "tokens": [{"text": " one", "offsets": {"from": 1000, "to": 1500}, "t_dtw": -1}, {"text": " two", "offsets": {"from": 1500, "to": 2000}, "t_dtw": -1}]},
        {"offsets": {"from": 3000, "to": 4000}, "text": "", "tokens": [{"text": "[_BEG_]", "offsets": {"from": 3000, "to": 3000}, "t_dtw": -1}]},
        {"offsets": {"from": 4000, "to": 5000}, "text": " music", "tokens": [{"text": "[_TT_250]", "offsets": {"from": 5000, "to": 5000}, "t_dtw": -1}]},
    ]}),
    "plain-run.srt": "1\n00:00:01,000 --> 00:00:01,500\n<u>one</u> two\n\n2\n00:00:01,500 --> 00:00:02,000\none <u>two</u>\n\n3\n00:00:03,000 --> 00:00:04,000\nmusic\n\n4\n00:00:04,000 --> 00:00:05,000\nmusic\n",
}  # fmt: skip


@pytest.mark.parametrize("name", list(_WORDLESS))
def test_a_sentence_of_no_words_is_counted_as_one_without_timings(
    tmp_path: Path, name: str
) -> None:
    t = ingested(put(tmp_path, name, _WORDLESS[name]))
    assert [(w.text, w.start, w.end) for w in t.words] == [
        ("one", 1000, 1500),
        ("two", 1500, 2000),
    ]
    assert t.notes == ("1 sentences had no word timings: shown without word highlighting",)


@pytest.mark.parametrize(
    ("name", "text", "message"),
    [
        ("a.txt", "x", "a .txt transcript has no timestamps"),
        ("a.xyz", "x", "unsupported subtitle format '.xyz'"),
        ("a.json", "{", "not valid JSON"),
        (
            "b.json",
            "[]",
            "not a whisper-cli (.transcription), OpenAI whisper or WhisperX (.segments) JSON transcript",
        ),
        (
            "c.json",
            '{"transcription": [{"tokens": [{"text": 5}]}]}',
            "unreadable whisper-cli -ojf JSON",
        ),
        ("a.srt", "1\n00:00:01,000 --> 00:00:01,000\nzero\n", "no timed text found"),
    ],
)
def test_refusals(tmp_path: Path, name: str, text: str, message: str) -> None:
    with pytest.raises(REFUSALS, match=re.escape(message)):
        _ = ingested(put(tmp_path, name, text))
    with pytest.raises(REFUSALS, match="no such file"):
        _ = ingested(str(tmp_path / "missing.srt"))


@pytest.mark.parametrize("fmt", ["ass", "ssa"])
def test_ass_and_ssa_pass_through(tmp_path: Path, fmt: str) -> None:
    t = ingested(put(tmp_path, f"a.{fmt}", "[Script Info]\nScriptType: v4.00+\n"))
    assert (t.fmt, t.chunks, t.has_words) == (fmt, (), False)


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_what_holds_of_any_transcript(tmp_path: Path, name: str) -> None:
    try:
        t = ingested(put(tmp_path, name, HOSTILE[name]))
    except REFUSALS:
        return  # a refusal is an answer (stage A proved each one bash's)
    windows = {c.segment: (c.start, c.end) for c in t.chunks}
    assert all(c.start < c.end and c.text for c in t.chunks)
    assert all(
        a.end <= b.start for a, b in zip(t.chunks, t.chunks[1:], strict=False)
    )  # ordered, apart
    for w in t.words:
        start, end = windows[w.segment]
        assert start <= w.start <= w.end <= end, (w, start, end)
    for a, b in zip(t.words, t.words[1:], strict=False):
        assert a.segment != b.segment or a.start <= b.start


def test_a_reversed_cue_is_dropped_noted(tmp_path: Path) -> None:
    # its text lost: ffmpeg shows one to the next cue's start, VLC none (measured, by source)
    srt = (
        "1\n00:00:02,000 --> 00:00:01,000\n<i>back</i>\n\n2\n00:00:03,000 --> 00:00:04,000\nfore\n"
        "\n3\n00:00:06,000 --> 00:00:05,000\nagain\n\n4\n00:00:07,000 --> 00:00:07,000\nzero\n"
        "\n5\n00:00:-2,000 --> 00:00:-1,000\nbefore\n"
        "\n6\n00:00:-1,000 --> 00:00:-2,000\nbefore, reversed\n"  # ffmpeg: from 0 to the next
    )
    t = ingested(put(tmp_path, "r.srt", srt))
    assert t.chunks == (Chunk(3000, 4000, "fore", ""),)
    # first by start: the cue reversed before 0; no length, before 0: shown by none
    assert t.notes == (REVERSED.format(n=3, text="before, reversed"),)


def test_a_time_past_a_doubles_range_in_ms_is_no_time(tmp_path: Path) -> None:
    """1e306 s is a number, and 1e309 ms is none: that segment untimed, noted, the other kept."""
    doc = {
        "segments": [
            {"start": 1e306, "end": 1e306, "text": "far"},
            {"start": 1, "end": 2, "text": "near"},
        ]
    }
    t = ingested(put(tmp_path, "x.json", json.dumps(doc)))
    assert (t.chunks, t.notes) == (
        (Chunk(1000, 2000, "near", "1"),),
        (UNTIMED.format(n=1, text="far"),),
    )


_FAR: Final = "9" * 400  # a number, but past a double's range in ms: no time


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("a.csv", "start,end,text\n0,500,kept\nabc,900,lost words\n1000,y,also lost\n"),
        ("a.tsv", "start\tend\ttext\n0\t500\tkept\n1000\t\tlost words\nx\t9\talso lost\n"),
        (
            "wx.json",
            (
                '{"segments": [{"start": 0, "end": 0.5, "text": "kept"}, '
                '{"start": NaN, "end": 1, "text": "lost words"}, '
                '{"start": 1, "end": null, "text": "also lost"}]}'
            ),
        ),
        (
            "cli.json",
            json.dumps(
                {
                    "transcription": [
                        {"offsets": {"from": 0, "to": 500}, "text": "kept"},
                        {"offsets": {"from": "x", "to": 900}, "text": " lost words"},
                        {"offsets": {"from": 1000, "to": "y"}, "text": " also lost"},
                    ]
                }
            ),
        ),
        (
            "f.json",
            (
                f'{{"start":0,"end":500,"text":"kept"}}\n{{"start":{_FAR},"end":1,"text":"lost words"}}\n'
                f'{{"start":1,"end":{_FAR},"text":"also lost"}}\n'
            ),
        ),
        (
            "a.srt",
            (
                f"1\n00:00:00,000 --> 00:00:00,500\nkept\n\n2\n{_FAR}:00:00,000 --> 00:00:01,000\n"
                f"<i>lost</i> words\n\n3\n00:00:01,000 --> {_FAR}:00:00,000\nalso lost\n"
            ),
        ),
        (
            "a.vtt",
            (
                f"WEBVTT\n\n00:00.000 --> 00:00.500\nkept\n\n{_FAR}:00:00.000 --> 00:01.000\n"
                f"lost words\n\n00:01.000 --> {_FAR}:00:00.000\nalso lost\n"
            ),
        ),
        (  # a highlighted sentence takes its first cue's start: none, the sentence none
            "a.srt",
            (
                f"1\n00:00:00,000 --> 00:00:00,500\n<u>kept</u>\n\n2\n{_FAR}:00:00,000 --> 00:00:01,000\n"
                "<u>lost</u> words\n\n3\n00:00:01,000 --> 00:00:02,000\nlost <u>words</u>\n\n"
                f"4\n{_FAR}:00:00,000 --> 00:00:03,000\n<u>also</u> lost\n\n"
                "5\n00:00:03,000 --> 00:00:04,000\nalso <u>lost</u>\n"
            ),
        ),
    ],
    ids=[
        "CSV",
        "TSV",
        "WhisperX JSON",
        "whisper-cli JSON",
        "whisper filter JSON",
        "SubRip",
        "WebVTT",
        "highlighted",
    ],
)
def test_a_cue_of_no_time_is_dropped_noted(tmp_path: Path, name: str, text: str) -> None:
    # its text lost -- a CSV or TSV field no number, a JSON NaN, null or text, a time past a
    # double's range: counted, the first named, as the other cues dropped (decisions' "Dropped cues")
    t = ingested(put(tmp_path, name, text))
    assert [c.text for c in t.chunks] == ["kept"]
    assert t.notes == (UNTIMED.format(n=2, text="lost words"),)


def test_a_cue_of_no_time_and_no_text_is_dropped_silently(tmp_path: Path) -> None:
    # nothing lost: no note, as an empty cue's
    t = ingested(put(tmp_path, "a.csv", 'start,end,text\n0,500,kept\nabc,900,\nx,9,"  "\n'))
    assert ([c.text for c in t.chunks], t.notes) == (["kept"], ())


def test_a_cue_the_next_one_starts_with_is_cut_to_nothing_noted(tmp_path: Path) -> None:
    """Each cue ends where the next starts: one sharing its start is left no time, dropped --
    its text lost, noted (libass draws both) -- but one of the text shown (ffmpeg drops the
    duplicate)."""
    srt = (
        "1\n00:00:01,000 --> 00:00:03,000\nfirst\n\n2\n00:00:01,000 --> 00:00:02,000\nsecond\n\n"
        "3\n00:00:05,000 --> 00:00:06,000\nsame\n\n4\n00:00:05,000 --> 00:00:07,000\nsame\n"
    )
    t = ingested(put(tmp_path, "s.srt", srt))
    assert t.chunks == (Chunk(1000, 2000, "second", ""), Chunk(5000, 7000, "same", ""))
    assert t.notes == (SAME_START.format(n=1, text="first"),)


def test_a_json_text_is_read_as_written(tmp_path: Path) -> None:
    """No @tsv between: a backslash stays one (bash's jq doubled it), a CR is a break (a literal \\r)."""
    doc = {
        "segments": [
            {"start": 1, "end": 2, "text": "a \\ b"},
            {"start": 2, "end": 3, "text": "c\rd"},
        ]
    }
    chunks = ingested(put(tmp_path, "t.json", json.dumps(doc))).chunks
    assert [c.text for c in chunks] == ["a \\ b", "c d"]


BACKSLASHED: Final = {  # one text with a backslash, in every format a transcript comes in
    "a.srt": "1\n00:00:01,000 --> 00:00:02,000\na\\b\n",
    "a.vtt": "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\na\\b\n",
    "a.lrc": "[00:01.00]a\\b\n",
    "a.csv": "start,end,text\n1000,2000,a\\b\n",
    "a.tsv": "start\tend\ttext\n1000\t2000\ta\\b\n",
    "cli.json": json.dumps(
        {
            "transcription": [
                {
                    "offsets": {"from": 1000, "to": 2000},
                    "text": "a\\b",
                    "tokens": [{"text": " a\\b", "offsets": {"from": 1000, "to": 2000}}],
                }
            ]
        }
    ),
    "wx.json": json.dumps(
        {
            "segments": [
                {
                    "start": 1,
                    "end": 2,
                    "text": "a\\b",
                    "words": [{"word": "a\\b", "start": 1, "end": 2}],
                }
            ]
        }
    ),
}


@pytest.mark.parametrize("name", list(BACKSLASHED))
def test_a_backslash_is_one_in_every_format(tmp_path: Path, name: str) -> None:
    """Read once; burned and attached as one, before a word joiner (no escape from the text)."""
    t = ingested(put(tmp_path, name, BACKSLASHED[name]))
    assert [c.text for c in t.chunks] == ["a\\b"]
    assert all(w.text == "a\\b" for w in t.words)
    burned = script(t, 1920, 1080, Style())[0]
    assert "a\\\u2060b" in burned
    assert "a\\\\" not in burned
    assert "\na\\\u2060b\n" in srt(t.chunks, None, codec="srt")


REFERENCED: Final = (
    "A &amp; B &lt; C &gt; D &nbsp;E &#x263A; &copy; <b>bold</b> &lt;b&gt; &bogus; &"
)


def test_a_vtts_character_references_are_decoded_once_its_tags_are_off(tmp_path: Path) -> None:
    """WebVTT's cue text: HTML's references (W3C); a decoded tag is text, an unknown one kept."""
    t = ingested(put(tmp_path, "a.vtt", f"WEBVTT\n\n00:01.000 --> 00:02.000\n{REFERENCED}\n"))
    shown = "A & B < C > D \u00a0E \u263a \u00a9 bold <b> &bogus; &"
    assert [c.text for c in t.chunks] == [shown]
    assert f",{shown}\n" in script(t, 1920, 1080, Style())[0]  # the burn's ASS: as shown


def test_a_break_a_reference_decodes_to_is_a_space(tmp_path: Path) -> None:
    vtt = "WEBVTT\n\n00:01.000 --> 00:02.000\na&#10;b&Tab;c&#13;d&#12;e\n"
    assert [c.text for c in ingested(put(tmp_path, "a.vtt", vtt)).chunks] == ["a b c d e"]


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("&am<b>p;", "&amp;"),  # a reference a tag splits: none (WebVTT's tokens)
        ("&am{\\b1}p;", "&am{\\b1}p;"),  # an override is text: no reference (Chromium's)
        ("C:&bsol;new &bsol;table", "C:\\new \\table"),  # a decoded backslash: no escape
        ("&#123;&#92;an8&#125; up", "{\\an8} up"),  # a decoded override: text
        ("{<b>\\an8}up", "{\\an8}up"),  # the tag off, the braces text
    ],
)
def test_each_run_between_tags_is_decoded_alone(tmp_path: Path, text: str, shown: str) -> None:
    t = ingested(put(tmp_path, "a.vtt", f"WEBVTT\n\n00:01.000 --> 00:02.000\n{text}\n"))
    assert [c.text for c in t.chunks] == [shown]


def test_a_vtts_lt_with_no_gt_after_it_is_a_tag_to_its_texts_end_noted(tmp_path: Path) -> None:
    """A tag no > closes runs to the text's end (W3C), as Chromium 141 and ffmpeg 8.1.2 show it."""
    t = ingested(put(tmp_path, "unclosed.vtt", HOSTILE["unclosed.vtt"]))
    assert [c.text for c in t.chunks] == ["I", "before", "R&D <5 kg"]
    how = "a tag to their end (W3C)"
    assert t.notes == (f"2 texts cut at a < with no > after it, {how}: the first, <3 you",)


@pytest.mark.parametrize(
    ("name", "data", "shown"),
    [
        (
            "a.srt",
            f"1\n00:00:01,000 --> 00:00:02,000\na{{{'n' * 100}}}b\n",
            f"the first, {{{'n' * 56}...",
        ),
        (
            "a.vtt",
            f"WEBVTT\n\n00:01.000 --> 00:02.000\na <{'n' * 100}\n",
            f"the first, <{'n' * 56}...",
        ),
    ],
    ids=["braced", "unclosed"],
)
def test_ffmans_notes_quote_their_text_shown(
    tmp_path: Path, name: str, data: str, shown: str
) -> None:
    """``errors.shown``: on one line, each character visible, 60 characters at most."""
    (note,) = ingested(put(tmp_path, name, data)).notes
    assert note.endswith(shown)


def test_a_long_text_is_named_by_its_first_57_characters(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "quoted.srt", HOSTILE["quoted.srt"]))
    how = "read as theirs, as ffmpeg reads them"
    first = "word " * 11 + "wo..."  # its first 57 characters, then the cut's mark
    assert t.notes == (
        f"1 cues held text after an empty line, {how}: the first, {first} on line 5",
    )


def test_a_notes_control_characters_are_written_as_python_does(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "controls.vtt", HOSTILE["controls.vtt"]))
    how = "after an empty line, in no cue (W3C)"
    first = "\\x1b]0;title\\x07\\x1b[31mred"
    assert t.notes == (f"1 text blocks dropped: {how}, the first {first} on line 6",)


def test_a_srts_lt_with_no_gt_after_it_is_text(tmp_path: Path) -> None:
    t = ingested(put(tmp_path, "a.srt", "1\n00:00:01,000 --> 00:00:02,000\nI <3 you\n"))
    assert ([c.text for c in t.chunks], t.notes) == (["I <3 you"], ())


def test_a_highlighted_vtts_words_are_decoded_too(tmp_path: Path) -> None:
    cues = "".join(
        f"00:00:0{i}.000 --> 00:00:0{i + 1}.000\n{text}\n\n"
        for i, text in enumerate(["<u>Tom</u> &amp;", "Tom <u>&amp;</u>"], 1)
    )
    t = ingested(put(tmp_path, "h.vtt", f"WEBVTT\n\n{cues}"))
    assert [c.text for c in t.chunks] == ["Tom &"]
    assert [w.text for w in t.words] == ["Tom", "&"]


def test_a_srts_ampersands_are_its_text(tmp_path: Path) -> None:
    """SubRip holds no references: ffmpeg's subrip decodes none."""
    t = ingested(put(tmp_path, "a.srt", "1\n00:00:01,000 --> 00:00:02,000\nA &amp; B\n"))
    assert [c.text for c in t.chunks] == ["A &amp; B"]


PAST_LIMITS: Final = {  # past what Python's float, int and csv hold, or JSON's depth: never a crash
    "a huge integer time": (
        "x.json",
        json.dumps({"segments": [{"start": 10**400, "end": 10**401, "text": "a"}]}),
    ),
    "nested 100000 deep": ("x.json", "[" * 100_000 + "]" * 100_000),
    "a 200 kB CSV field": ("x.csv", "start,end,text\n0,1000," + "a" * 200_000 + "\n"),
    "a 200 kB TSV field": ("x.tsv", "start\tend\ttext\n0\t1000\t" + "a" * 200_000 + "\n"),
    "LRC minutes past a double": ("x.lrc", "[" + "9" * 400 + ":00.00]a\n"),
    "SRT hours past a double": (
        "x.srt",
        "1\n" + "9" * 400 + ":00:00,000 --> " + "9" * 401 + ":00:00,000\na\n",
    ),
}


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("a huge integer time", "no timed text found"),  # no number, so no time
        ("nested 100000 deep", "JSON nested too deeply to be a transcript"),
        ("a 200 kB CSV field", "unreadable .csv: .*field larger than field limit"),
        ("a 200 kB TSV field", "unreadable .tsv: .*field larger than field limit"),
        ("LRC minutes past a double", "no timed text found"),
        ("SRT hours past a double", "no timed text found"),
    ],
)
def test_what_python_cannot_hold_is_refused_not_a_crash(
    tmp_path: Path, case: str, message: str
) -> None:
    name, text = PAST_LIMITS[case]
    with pytest.raises(REFUSALS, match=message):
        _ = ingested(put(tmp_path, name, text))


def test_a_huge_dtw_time_is_none_and_the_offsets_used(tmp_path: Path) -> None:
    token = {"text": " a", "offsets": {"from": 0, "to": 900}, "t_dtw": 10**400}
    doc = {"transcription": [{"offsets": {"from": 0, "to": 900}, "text": " a", "tokens": [token]}]}
    t = ingested(put(tmp_path, "x.json", json.dumps(doc)))
    assert [(w.start, w.end) for w in t.words] == [(0, 900)]


@pytest.mark.parametrize(
    ("name", "text", "start"),
    [  # each read through a float before (stage A): 500, 500, 999, 999
        ("a.lrc", "[00:00.5005]a\n[00:01.00]b\n", 501),
        ("wx.json", json.dumps({"segments": [{"start": 0.5005, "end": 1, "text": "a"}]}), 501),
        ("a.csv", "start,end,text\n999.5,2000,a\n", 1000),
        (
            "cli.json",
            json.dumps({"transcription": [{"offsets": {"from": 999.5, "to": 2000}, "text": "a"}]}),
            1000,
        ),
    ],
)
def test_a_time_is_its_decimal_rounded_half_up_to_the_ms(
    tmp_path: Path, name: str, text: str, start: int
) -> None:
    """Read exactly from the text, never a float; one rule, every format: half up, whole ms."""
    assert ingested(put(tmp_path, name, text)).chunks[0].start == start


def test_the_srt_clip_is_the_duration_floored_to_the_ms() -> None:
    """No cue outlasts the media: 1.005 s is 1005 ms (bash truncated a float: 1004)."""
    a, end = (Chunk(0, 2000, "a", ""),), (Chunk(1005, 1500, "at the end", ""),)
    assert "00:00:00,000 --> 00:00:01,005" in srt(a, Fraction("1.005"), codec="srt")
    assert srt(end, Fraction("1.005"), codec="srt") == ""
    assert "00:00:00,000 --> 00:00:02,000" in srt(a, None, codec="srt")


BOUNDLESS: Final = {  # a number no reader may expand: an exponent, or digits past int's 4300
    "x.csv": "start,end,text\n1e999999999,2000,a\n1e-999999999,1000,b\n" + "9" * 5000 + ",3000,c\n",
    "x.lrc": "[" + "9" * 5000 + ":00.00]a\n[00:01.00]b\n",
    "x.json": '{"segments": [{"start": 1e999999999, "end": 2, "text": "a"}, {"start": 0.'
    + "1" * 5000
    + ', "end": 1e-999999999, "text": "b"}, {"start": 0, "end": 1, "text": "c"}]}',
    "y.json": json.dumps(
        {
            "segments": [
                {"start": "1e999999999", "end": 2, "text": "a"},
                {"start": 0, "end": 1, "text": "b"},
            ]
        }
    ),
    "x.vtt": "WEBVTT\n\n00:01.000 --> 00:02.000\na&#" + "9" * 5000 + ";b\n",  # a reference
}


@pytest.mark.parametrize(
    ("name", "texts"),
    [
        ("x.csv", ["b"]),
        ("x.lrc", ["b"]),
        ("x.json", ["c"]),
        ("y.json", ["b"]),
        ("x.vtt", ["a\ufffdb"]),
    ],
)
def test_a_huge_or_long_number_is_read_in_bounded_work(
    tmp_path: Path, name: str, texts: list[str]
) -> None:
    """Past a double, no time; under one, zero; 5000 digits read as 400 and a sticky 1 -- at once.

    A reference of 5000 digits: U+FFFD, unread.
    """
    began = time.monotonic()
    assert [c.text for c in ingested(put(tmp_path, name, BOUNDLESS[name])).chunks] == texts
    assert time.monotonic() - began < 2  # 10**999999999 never built


_OPEN: Final = "{\\" * 60_000  # each {\ no } closes: a CSV field, under csv's 131072
_LT: Final = "a<" * 200_000  # each < no > closes


@pytest.mark.parametrize(
    ("name", "data", "text"),
    [
        ("x.lrc", f"[00:01.00]x{_OPEN}\n", f"x{_OPEN}"),
        ("x.csv", f"start,end,text\n0,1000,x{_OPEN}\n", f"x{_OPEN}"),
        ("x.tsv", f"start\tend\ttext\n0\t1000\tx{_OPEN}\n", f"x{_OPEN}"),
        (
            "x.json",
            json.dumps({"segments": [{"start": 0, "end": 1, "text": f"x{_OPEN}"}]}),
            f"x{_OPEN}",
        ),
        ("x.srt", f"1\n00:00:00,000 --> 00:00:01,000\n{_LT}\n", _LT),
        ("x.vtt", f"WEBVTT\n\n00:00.000 --> 00:01.000\n{_LT}\n", "a"),
    ],
    ids=["lrc", "csv", "tsv", "json", "srt", "vtt"],
)
def test_an_unclosed_override_or_tag_is_read_in_bounded_work(
    tmp_path: Path, name: str, data: str, text: str
) -> None:
    """No closer sought from each opener past the last one: squared steps, so many of them -- a
    CSV's, TSV's and JSON's seek none (plain texts), kept as guards."""
    began = time.monotonic()
    assert [c.text for c in ingested(put(tmp_path, name, data)).chunks] == [text]
    assert time.monotonic() - began < 1


# the marks of the formats' markup, and the plain texts' breaks
_MARKS: Final = ("{", "}", "\\", "{\\an8}", "<", ">", "<i>", "t", "n", "a", " ", "\t", "\n", "\r")


@given(
    st.lists(st.sampled_from((*_MARKS, "<0:1>", "<0:1.5>", "0", ":", ".")), max_size=12).map(
        "".join
    )
)
def test_an_lrcs_clean_is_its_word_stamps_off_alone(text: str) -> None:
    """LRC's: its word stamps' regex alone, then as a plain text's -- a line break (lines sharing a
    stamp) a space, blanks squeezed -- every other mark as written."""
    plain = re.sub(r"[\t\n\r]", " ", re.sub(r"<[0-9]+:[0-9]+(?:\.[0-9]+)?>", "", text))
    assert clean(text, Markup.LRC) == re.sub(r"[ \t]+", " ", plain).strip(" ")


@given(st.lists(st.sampled_from(_MARKS), max_size=12).map("".join))
def test_a_plain_clean_is_its_breaks_alone(text: str) -> None:
    """CSV's, TSV's and JSON's, plain: a tab or line break a space, then blanks squeezed -- every
    other mark as written."""
    plain = re.sub(r"[\t\n\r]", " ", text)
    assert clean(text, Markup.PLAIN) == re.sub(r"[ \t]+", " ", plain).strip(" ")


def test_an_lrc_time_its_parts_in_range_past_a_double_is_none(tmp_path: Path) -> None:
    """10**306 minutes reads; as milliseconds (x 60 000) it is past a double: no line."""
    lrc = "[1" + "0" * 306 + ":00.00]a\n[00:01.00]b\n"
    assert [c.text for c in ingested(put(tmp_path, "x.lrc", lrc)).chunks] == ["b"]


@pytest.mark.parametrize("part", ["1e999999999", "9" * 5000])
def test_a_subrip_part_past_a_double_is_no_time(tmp_path: Path, part: str) -> None:
    with pytest.raises(REFUSALS, match="no timed text found"):
        _ = ingested(put(tmp_path, "x.srt", f"1\n00:00:{part} --> 00:00:02,000\na\n"))
