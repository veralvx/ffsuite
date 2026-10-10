"""subs.ucd: the generator's output, byte for byte, from Unicode 15.1's files; Python 3.13's."""

import os
import unicodedata
from pathlib import Path

import pytest

from ffman.subs import ucd
from ffman.subs.breaks import is_mark, is_wide
from tests.support.ucd import source

UCD = Path(os.environ.get("FFMAN_UCD", "/usr/share/texlive/texmf-dist/tex/generic/unicode-data"))
FILES = ("LineBreak.txt", "PropList.txt", "Scripts.txt", "EastAsianWidth.txt")
DATA = "UnicodeData.txt"  # no version in it: 15.1's own characters checked instead


@pytest.mark.skipif(
    not all((UCD / name).is_file() for name in (*FILES, DATA)),
    reason="the Unicode Character Database: FFMAN_UCD",
)
def test_the_module_is_unicodes() -> None:
    """ucd.py is what the generator makes of Unicode 15.1's files."""
    for name in FILES:
        assert (
            f"{name.removesuffix('.txt')}-15.1.0" in (UCD / name).read_text(encoding="utf-8")[:40]
        )
    data = (UCD / DATA).read_text(encoding="utf-8")
    assert ";<CJK Ideograph Extension I, First>;" in data  # new in 15.1
    assert ";TODHRI LETTER A;" not in data  # new in 16.0
    assert source(UCD) == Path(ucd.__file__).read_text(encoding="utf-8")


@pytest.mark.skipif(unicodedata.unidata_version != "15.1.0", reason="Python's Unicode is not 15.1")
def test_the_tables_are_python_3_13_s() -> None:
    """Under Unicode 15.1 (Python 3.13), the tables answer as unicodedata, every code point."""
    for c in map(chr, range(0x110000)):
        assert is_mark(c) == unicodedata.category(c).startswith("M"), hex(ord(c))
        assert is_wide(c) == (unicodedata.east_asian_width(c) in ("W", "F")), hex(ord(c))
        assert (c in ucd.VIRAMAS) == (unicodedata.combining(c) == 9), hex(ord(c))
