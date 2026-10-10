"""subs.metrics: a font's advances and height, as libass scales it; anything else refused."""

from fractions import Fraction
from importlib import resources
from pathlib import Path

import pytest

from ffman.subs.metrics import Metrics, estimate, parse
from tests.support.fonts import font

CHARS = {"a": 500, "b": 600, "é": 700, "日": 1000}


@pytest.mark.parametrize("by_array", [False, True])
def test_the_bmp_by_delta_and_by_array(*, by_array: bool) -> None:
    m = parse(font(CHARS, by_array=by_array))
    assert (m.advances, m.height) == ({ord(c): a for c, a in CHARS.items()}, 1300)


def test_past_the_bmp_by_groups() -> None:
    wide = {**CHARS, "\U0001f600": 1100}  # format 12 maps past U+FFFF
    assert parse(font(wide, fmt=12)).advances[0x1F600] == 1100


def test_a_glyph_past_the_metrics_takes_the_last_advance() -> None:
    """hmtx holds 2 entries (.notdef, a): b, é and 日 take a's (the OpenType rule)."""
    assert set(parse(font(CHARS, fmt=12, metrics=2)).advances.values()) == {500}


def test_a_width_in_sizes_a_missing_character_as_given() -> None:
    m = parse(font(CHARS))  # 1300 units a size
    assert m.width("ab", Fraction(13), Fraction(1)) == Fraction(1100, 100)  # (500 + 600) / 100
    assert m.width("a?", Fraction(13), Fraction(1)) == 5 + 13  # ? is not in it: a size


@pytest.mark.parametrize(
    ("data", "said"),
    [
        (font(CHARS, drop="cmap"), "without its cmap table"),
        (font(CHARS, drop="OS/2"), "without its OS/2 table"),
        (font(CHARS, metrics=0), "no horizontal metrics"),
        (font(CHARS, ascent=0, descent=0), "no height"),
        (font(CHARS, fmt=6), "without a Unicode cmap"),  # a format it does not read
        (font(CHARS)[:200], "not a readable font"),  # truncated
        (b"not a font", "not a readable font"),
    ],
)
def test_anything_else_is_refused(data: bytes, said: str) -> None:
    with pytest.raises(ValueError, match=said):
        _ = parse(data)


def test_a_cmap_mapping_more_than_unicode_is_refused() -> None:
    """Two groups of all Unicode: refused before the second is built (a hostile font)."""
    data = bytearray(font({"a": 500}, fmt=12))
    at = data.index(b"\x00\x0c\x00\x00")  # the format 12 subtable
    every = (0).to_bytes(4, "big") + (0xFFFFFFFF).to_bytes(4, "big") + (1).to_bytes(4, "big")
    data[at + 12 : at + 16] = (2).to_bytes(4, "big")
    data[at + 16 : at + 40] = every * 2  # contiguous: over the maxp after it, which is not read
    with pytest.raises(ValueError, match="more than Unicode"):
        _ = parse(bytes(data))


SHIPPED = Path(str(resources.files("ffman") / "fonts")) / "IBMPlexSans-Regular.otf"  # ffman's own


def test_the_shipped_font() -> None:
    """IBM Plex Sans 1.1.0's Regular: 893 characters, 1300 units a size (winAscent 1025 +
    winDescent 275) -- as HarfBuzz and fontTools read it."""
    m = parse(SHIPPED.read_bytes())
    assert (len(m.advances), m.height) == (893, 1300)
    assert m.width("café", Fraction(1300), Fraction(1)) == 1910  # HarfBuzz's, shaped


def test_a_nonspacing_mark_advances_nothing_in_any_font() -> None:
    """A nonspacing mark the font lacks is drawn by another, yet advances nothing; a letter, a size."""
    m = Metrics({ord("a"): 1300}, 1300)
    assert m.width("a\u0301", Fraction(13), Fraction(1)) == 13  # an accent: nothing
    assert (
        m.width("\u0e27\u0e31", Fraction(13), Fraction(1)) == 13
    )  # Thai: the letter a size, its vowel mark nothing


def test_a_spacing_mark_counts_nothing_its_base_a_size() -> None:
    """Devanagari's AA (Mc) advances, but after a base the font lacks, measured a size: the
    cluster is one (``counts``: rendered, at most 1.01 of its measure in 11 scripts)."""
    m = Metrics({ord("a"): 1300}, 1300)
    assert m.width("\u0915\u093e", Fraction(13), Fraction(1)) == 13


@pytest.mark.parametrize("c", ["\u200e", "\u200f", "\u200b", "\ufe0f", "\U000e0041"])
def test_what_libass_skips_advances_nothing_mapped_or_not(c: str) -> None:
    """LRM, RLM (&lrm;, &rlm;), a zero-width space this font maps wide, a variation selector, a
    tag: drawn as nothing (+0 px rendered, libass 0.17.1)."""
    m = Metrics({ord("a"): 1300, 0x200B: 650}, 1300)
    assert m.width(f"a{c}a", Fraction(13), Fraction(1)) == 26


def test_a_format_character_libass_draws_is_a_size() -> None:
    """U+0600, an Arabic number sign: a format character libass draws (+32 px rendered)."""
    m = Metrics({ord("a"): 1300}, 1300)
    assert m.width("a\u0600a", Fraction(13), Fraction(1)) == 39


def test_the_shipped_font_skips_lrm_and_rlm() -> None:
    """Plex maps neither: measured as two fallback glyphs, they broke a line early."""
    m, size, missing = parse(SHIPPED.read_bytes()), Fraction(60), Fraction(1)
    assert 0x200E not in m.advances
    assert 0x200F not in m.advances
    assert m.width("M\u200e\u200fM", size, missing) == m.width("MM", size, missing)


@pytest.mark.parametrize(
    ("c", "sizes"),
    [
        ("a", Fraction("0.55")),  # Latin, Greek, Cyrillic: a font's own
        ("\u03b1", Fraction("0.55")),
        ("\u0434", Fraction("0.55")),
        (",", Fraction("0.55")),  # Common: punctuation, digits
        ("\u65e5", Fraction(1)),  # wide: a size
        ("\u0d15", Fraction(1)),  # Malayalam KA: another script, a fallback's glyph -- a size
        ("\u0e01", Fraction(1)),  # Thai
        ("\u05e9", Fraction(1)),  # Hebrew
        ("\u0378", Fraction(1)),  # unassigned: no script of a font's
        ("\u0d3e", Fraction(0)),  # a spacing mark: its base holds it (counts)
        ("\u0301", Fraction(0)),  # a mark
        ("\u200e", Fraction(0)),  # what libass skips
    ],
)
def test_the_estimate_a_font_s_scripts_at_0_55_another_s_a_size(c: str, sizes: Fraction) -> None:
    """The font unread: its own scripts' glyphs 0.55 sizes, any other's a fallback's, a size --
    the UDHR in 26 languages, rendered, at most 0.99 of it (Malayalam at 0.55: 1.64)."""
    assert estimate(c) == sizes
