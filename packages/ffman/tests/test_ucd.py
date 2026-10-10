"""subs.ucd: the generator's output, byte for byte, from Unicode 15.1's files."""

import os
from pathlib import Path

import pytest

from ffman.subs import ucd
from tests.support.ucd import source

UCD = Path(os.environ.get("FFMAN_UCD", "/usr/share/texlive/texmf-dist/tex/generic/unicode-data"))
FILES = ("LineBreak.txt", "PropList.txt", "Scripts.txt")


@pytest.mark.skipif(
    not all((UCD / name).is_file() for name in FILES),
    reason="the Unicode Character Database: FFMAN_UCD",
)
def test_the_module_is_unicodes() -> None:
    """ucd.py is what the generator makes of Unicode 15.1's files."""
    for name in FILES:
        assert (
            f"{name.removesuffix('.txt')}-15.1.0" in (UCD / name).read_text(encoding="utf-8")[:40]
        )
    assert source(UCD) == Path(ucd.__file__).read_text(encoding="utf-8")
