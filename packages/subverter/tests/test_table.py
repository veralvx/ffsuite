"""CSV and TSV against their rules (``readers/table.py``, docs/decisions.md's rows): columns by
header, a time read or none, RFC 4180 quoting in CSV, none in TSV.

Every expectation is worked by hand from a rule, not taken from a run: what a reader yields
before ffman's normalising (no trim, no sort, no clamp, no cue dropped).
"""

import pytest
import subverter
from subverter import Cue

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
