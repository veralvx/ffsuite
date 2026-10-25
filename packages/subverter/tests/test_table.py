"""CSV and TSV against their rules (``readers/table.py``, docs/decisions.md's rows): columns by
header, a time read or none, RFC 4180 quoting in CSV, none in TSV; UTF-8, or UTF-16 by its BOM.

Every expectation is worked by hand from a rule, not taken from a run: what a reader yields
before ffman's normalising (no trim, no sort, no clamp, no cue dropped).
"""

import re
import time
from typing import Final

import pytest
import subverter
from hypothesis import given
from hypothesis import strategies as st
from subverter import Cue

# --- CSV and TSV: start, end, text in ms; a header names start and end, any order


@pytest.mark.parametrize(
    ("data", "cues"),
    [
        ('start,end,text\n0,1000,"a, b"\n', (Cue(0, 1000, "a, b"),)),  # RFC 4180 quoting
        # by header; whisper-cli's -di speaker before its text, as its SubRip writes it
        (
            "speaker,end,start,text\nS1,2000,1000, hi\n",
            (Cue(1000, 2000, "(speaker S1) hi", "", "(speaker S1)"),),
        ),
        ("start,end,speaker,text\n0,1,,x\n", (Cue(0, 1, "x"),)),  # an empty one: none
        ("start,end,speaker,text\n0,1,S1, \n", (Cue(0, 1, " "),)),  # of no text: none
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


# --- a TSV text broken by a line break: OpenAI whisper's and WhisperX's WriteTSV (utils.py) write
# each text stripped, its tabs spaces, its line breaks kept -- a line of no tab after a record is
# that record's text
_JOINED: Final = (
    "{n} TSV lines of no tab read as the text of the record before, a line break in it (OpenAI "
    "whisper's and WhisperX's TSV): the first, {first} on line {line}"
)


def _write_tsv(segments: list[tuple[int, int, str]]) -> str:
    """OpenAI whisper's ``WriteTSV`` (v20250625; WhisperX 3.8.5's the same), ms given."""
    texts = [text.strip().replace("\t", " ") for _, _, text in segments]
    rows = [f"{a}\t{z}\t{text}\n" for (a, z, _), text in zip(segments, texts, strict=True)]
    return "start\tend\ttext\n" + "".join(rows)


@pytest.mark.parametrize(
    ("text", "joined", "notes"),
    [
        (
            "past an hour\nnewline",
            "past an hour\nnewline",
            (_JOINED.format(n=1, first="newline", line=4),),
        ),
        # every line end csv reads, each run of them one break: a blank line no line of the text
        ("a\r\nb\rc\n\nd \n", "a\nb\nc\nd", (_JOINED.format(n=3, first="b", line=4),)),
        ("\tone\ttwo\t", "one two", ()),  # tabs spaces, stripped: no line of no tab
    ],
    ids=["a line break", "every line end", "tabs"],
)
def test_a_tsv_line_of_no_tab_is_the_text_of_the_record_before(
    text: str, joined: str, notes: tuple[str, ...]
) -> None:
    data = _write_tsv([(0, 1000, "first"), (1000, 2000, text), (2000, 3000, "last")])
    found = subverter.read("tsv", data.encode(), "a.tsv")
    assert found.cues == (Cue(0, 1000, "first"), Cue(1000, 2000, joined), Cue(2000, 3000, "last"))
    assert found.notes == notes


def test_a_tsv_of_no_header_joins_a_broken_text_as_one_of_start_end_text() -> None:
    found = subverter.read("tsv", b"0\t1\tx\nmore\n2\t3\ty\n", "a.tsv")
    assert found.cues == (Cue(0, 1, "x\nmore"), Cue(2, 3, "y"))
    assert found.notes == (_JOINED.format(n=1, first="more", line=2),)


def test_a_tsv_texts_lines_are_its_records_in_a_refusal_and_a_nul_note() -> None:
    """A byte not UTF-8 or a NUL on a text's later line is told at its record's first, as a quoted
    CSV field's (``by_line``)."""
    with pytest.raises(subverter.Error, match=r"^not UTF-8: a\.tsv \(line 2\)$"):
        _ = subverter.read("tsv", b"start\tend\ttext\n0\t1\ta\nb\xffc\n", "a.tsv")
    found = subverter.read("tsv", b"start\tend\ttext\n0\t1\ta\nb\x00\n", "a.tsv")
    assert found.cues == (Cue(0, 1, "a\nb\ufffd"),)
    assert found.notes == (
        _JOINED.format(n=1, first="b\\x00", line=3),
        "1 NULs read as U+FFFD, as the W3C reads them: the first in line 2",
    )


@pytest.mark.parametrize(
    ("data", "cues"),
    [
        ("start\tend\ttext\nalone\n0\t1\tx\n", (Cue(None, None, ""), Cue(0, 1, "x"))),
        ("text\tstart\tend\nhi\t0\t1\nmore\n", (Cue(0, 1, "hi"), Cue(None, None, "more"))),
        ("start\tend\ttext\n0\t1\tx\nan\tother\n", (Cue(0, 1, "x"), Cue(None, None, ""))),
        ("start\tend\ttext\n0\t1\nmore\n", (Cue(0, 1, ""), Cue(None, None, ""))),
        # no TSV writer writes a speaker (WriteTSV: start, end, text): none read
        ("start\tend\ttext\tspeaker\n0\t1\thi\tS1\nmore\n", (Cue(0, 1, "hi"), Cue(None, None, ""))),
        ("start\tend\ttext\tspeaker\n0\t1\thi\nmore\n", (Cue(0, 1, "hi"), Cue(None, None, ""))),
        ("start\tend\ttext\n0\t1\tx\tS1\nmore\n", (Cue(0, 1, "x"), Cue(None, None, ""))),
        ("0\t1\tx\tS1\nmore\n", (Cue(0, 1, "x"), Cue(None, None, ""))),
    ],
    ids=[
        "no record before",
        "the text not last",
        "a tab",
        "a record short of its text",
        "a column after the text",
        "a record short of the column after its text",
        "a record past its header",
        "a record past its text, no header",
    ],
)
def test_a_tsv_line_no_writer_breaks_is_a_record(data: str, cues: tuple[Cue, ...]) -> None:
    found = subverter.read("tsv", data.encode(), "a.tsv")
    assert (found.cues, found.notes) == (cues, ())


def test_a_csv_line_of_one_field_is_a_record() -> None:
    data = 'start,end,text\n0,1,"quoted\nwhole"\nalone\n'  # CSV quotes a break: none to join
    found = subverter.read("csv", data.encode(), "a.csv")
    assert (found.cues, found.notes) == ((Cue(0, 1, "quoted\nwhole"), Cue(None, None, "")), ())


@given(
    st.lists(
        st.tuples(
            st.integers(0, 10**7),
            st.integers(0, 10**7),
            st.lists(st.sampled_from(("a", "b", " ", "\t", "\n", "\r", "\r\n")), max_size=8).map(
                "".join
            ),
        ),
        max_size=6,
    )
)
def test_a_tsv_whisper_wrote_is_read_back_record_by_record(
    segments: list[tuple[int, int, str]],
) -> None:
    """Each text as written: stripped, its tabs spaces, each run of line ends one line break."""
    found = subverter.read("tsv", _write_tsv(segments).encode(), "a.tsv")
    texts = [text.strip().replace("\t", " ") for _, _, text in segments]
    expected = [re.sub(r"(?:\r\n|\r|\n)+", "\n", t) for t in texts]
    assert [(c.start, c.end, c.text) for c in found.cues] == [
        (a, z, t) for (a, z, _), t in zip(segments, expected, strict=True)
    ]


def test_a_tsv_text_of_many_broken_lines_is_read_in_bounded_work() -> None:
    """Its lines joined once: 0.09 s under coverage; one by one, each join a copy of the text so
    far, 6.2 s -- its lines' count squared times their length, so long lines, not many short."""
    line = "y" * 100
    data = ("start\tend\ttext\n0\t1\tx\n" + f"{line}\n" * 40_000).encode()
    began = time.process_time()
    found = subverter.read("tsv", data, "a.tsv")
    assert time.process_time() - began < 1
    assert found.cues == (Cue(0, 1, "x" + f"\n{line}" * 40_000),)


def test_a_tsv_quotes_nothing() -> None:
    data = 'start\tend\ttext\n0\t1000\t"as written"\n'
    assert subverter.read("tsv", data.encode(), "a.tsv").cues == (Cue(0, 1000, '"as written"'),)


def test_a_field_past_csvs_limit_is_refused_by_name() -> None:
    data = "start,end,text\n0,1," + "x" * (128 * 1024 + 1) + "\n"
    with pytest.raises(
        subverter.Error, match=r"^unreadable \.csv: big\.csv: field larger than field limit"
    ):
        _ = subverter.read("csv", data.encode(), "big.csv")


# --- encodings: UTF-8, or UTF-16 by its BOM, as a SubRip's and an LRC's (Excel's "Unicode Text"
# is UTF-16 LE, a BOM first); a refusal's line by csv's line ends, a CR, an LF or a CRLF each one
_CSV: Final = 'start,end,text\r\n0,1000,"café \U0001f600\r\nline"\r\n1000,2000,two\r\n'
_TSV: Final = "start\tend\ttext\r\n0\t1000\tcafé \U0001f600\r\n1000\t2000\ttwo\r\n"


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be"])
@pytest.mark.parametrize(
    ("fmt", "text", "first"),
    [("csv", _CSV, "café \U0001f600\r\nline"), ("tsv", _TSV, "café \U0001f600")],
    ids=["csv", "tsv"],
)
def test_a_table_in_utf16_by_its_bom_reads_as_in_utf8(
    fmt: str, text: str, first: str, codec: str
) -> None:
    found = subverter.read(fmt, ("\ufeff" + text).encode(codec), f"a.{fmt}")
    assert found.cues == (Cue(0, 1000, first), Cue(1000, 2000, "two"))
    assert found.notes == ()


@pytest.mark.parametrize(
    ("data", "line"),
    [
        pytest.param(
            ("\ufeff" + _CSV.replace("two", "t\ud800wo")).encode("utf-16-le", "surrogatepass"),
            4,
            id="a lone surrogate",
        ),
        pytest.param(("\ufeff" + _CSV).encode("utf-16-le") + b"x", 5, id="an odd byte"),
        pytest.param(
            "\ufeffstart,end\r\r\n\udc00".encode("utf-16-be", "surrogatepass"), 3, id="BE"
        ),
    ],
)
def test_a_tables_unit_not_utf16_is_refused_by_its_line(data: bytes, line: int) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(f'not UTF-16: a.csv (line {line})')}$"):
        _ = subverter.read("csv", data, "a.csv")


def test_a_csv_speaker_not_utf8_is_refused_by_its_line_a_nul_noted() -> None:
    with pytest.raises(subverter.Error, match=r"^not UTF-8: a\.csv \(line 2\)$"):
        _ = subverter.read("csv", b"start,end,speaker,text\n0,1000,\xff,hi\n", "a.csv")
    found = subverter.read("csv", b"start,end,speaker,text\n0,1000,\x00,hi\n", "a.csv")
    assert found.cues == (Cue(0, 1000, "(speaker \ufffd)hi", "", "(speaker \ufffd)"),)
    assert found.notes == ("1 NULs read as U+FFFD, as the W3C reads them: the first in line 2",)


def test_a_csv_nul_note_names_the_first_in_the_file() -> None:
    # whisper-cli's -di column, before its text: its NUL on line 2 the first
    found = subverter.read("csv", b"start,end,speaker,text\n0,1,\x00,a\n1,2,0,\x00\n", "a.csv")
    assert found.notes == ("2 NULs read as U+FFFD, as the W3C reads them: the first in line 2",)
    with pytest.raises(subverter.Error, match=r"^not UTF-8: a\.csv \(line 2\)$"):
        _ = subverter.read("csv", b"start,end,speaker,text\n0,1,\xe4\xbd,a\n1,2,\xa0,b\n", "a.csv")
