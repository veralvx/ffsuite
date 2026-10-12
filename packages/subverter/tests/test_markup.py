"""markup: a text's tags off; WebVTT's character references decoded as HTML decodes them; a SubRip's
text as ffmpeg and libass draw it."""

import html
import time
from typing import Final

import pytest
import subverter
from hypothesis import given
from hypothesis import strategies as st


def test_untagged_puts_what_it_is_given_where_each_tag_was() -> None:
    assert subverter.untagged("a<b>c</b>") == "ac"
    assert subverter.untagged("a<b>c</b>", into="|") == "a|c|"


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("A &amp; B &lt;b&gt; &#x263A; &#9786; &copy;", "A & B <b> \u263a \u263a \u00a9"),
        ("&amp &notit; &AMP;", "& \u00acit; &"),  # HTML's legacy names, as its data state
        ("&bogus; &#; &# & x", "&bogus; &#; &# & x"),  # no reference: as written
        ("&#0; &#55296; &#1114112; &#x80;", "\ufffd \ufffd \ufffd \u20ac"),  # HTML's numerics
        ("&#" + "9" * 5000 + ";x", "\ufffdx"),  # past int's 4300 digits: no crash
        ("&#" + "0" * 5000 + "65;", "A"),  # its zeros no digits
        ("&#1000000; &#1114111;", "\U000f4240 "),  # 7 digits: read (U+10FFFF a noncharacter)
        ("&#65;;", "A;"),  # its own ; consumed, the next kept
    ],
)
def test_a_webvtt_runs_references_decoded_as_html_does(text: str, shown: str) -> None:
    assert subverter.decoded(text) == shown


# what references are made of
_PARTS: Final = ("&", "#", ";", "x", "X", "0", "9", "65", "amp", "AMP", "lt", "not", "it", " ")
_NUMBERS: Final = ("1114111", "1114112", "\ufffd")  # each side of U+10FFFF, and its stand-in


@given(st.lists(st.sampled_from(_PARTS + _NUMBERS), max_size=12).map("".join))
def test_decoded_is_html_unescape_wherever_that_reads_the_text(text: str) -> None:
    assert subverter.decoded(text) == html.unescape(text)


@pytest.mark.parametrize(
    ("text", "drawn", "blocks"),
    [
        ("one\\Ntwo", "one\ntwo", ()),  # a line break
        ("a\\hb", "a\u00a0b", ()),  # a no-break space
        ("a\\nb \\t", "a\\nb \\t", ()),  # libass's soft break and others: as written
        ("a\\\\Nb", "a\\\nb", ()),  # a backslash, then the escape: as libass reads them
        ("\\N\\h\\N", "\n\u00a0\n", ()),
        ("a\\{b\\}", "a{b}", ()),  # braces
        ("a\\\\{x}", "a\\{x}", ()),  # a backslash, then a brace: no block
        ("a{note}b", "ab", ("note",)),  # a block, hidden: ASS's comment
        ("{a\\}b}", "b}", ("a\\",)),  # to the first }
        ("{{x}y", "y", ("{x",)),
        ("{}a", "a", ("",)),
        # ffmpeg's decoder first: ASS's tags and MicroDVD's style off, to the first }
        ("{\\an8}top {\\an8}{y:i}x", "top x", ("\\an8",)),  # the first {\anN} kept: libass's
        ("{\\N}a", "a", ()),  # tags: a block's escapes none
        ("a \\{\\i1\\} b", "a \\ b", ()),  # a backslash before them or not
        ("a\\{y:i\\}b", "a\\b", ()),
        ("{a{\\i1}b}c", "c", ("ab",)),  # a block, once its tags are off
        ("{\\an8}a\\{\\i1}b", "a{\\i1}b", ("\\an8",)),  # one {\anN} alone: tags kept
        ("{\\an8}{\\an8}a\\{\\i1}b", "a\\b", ("\\an8",)),  # two: off again, the first kept
        ("{\\an8\\i1}a\\{\\i1}b", "a\\b", ()),  # {\anN} exactly, no other tag
        ("a{\\i1 b", "a{\\i1 b", ()),  # no } after it: kept
        ("a{b", "a{b", ()),  # no } after it: a character
        ("a}b", "a}b", ()),
    ],
)
def test_unescaped_reads_a_subrip_text_as_ffmpeg_and_libass_draw_it(
    text: str, drawn: str, blocks: tuple[str, ...]
) -> None:
    assert subverter.unescaped(text) == subverter.Unescaped(drawn, blocks)


_ALIGNED: Final = tuple(f"{n}}}" for n in range(10))  # scanbraces: {\an, a digit, }


def _ffmpeg(text: str) -> str:
    """ffmpeg 8.1's subrip decoder, character by character: ``htmlsubtitles.c``'s braces."""
    shown, k, alignments, unclosed = "", 0, 0, False
    while k < len(text):
        if text[k] == "{":
            alignments += text[k : k + 4] == "{\\an" and text[k + 4 : k + 6] in _ALIGNED
            tags = alignments != 1 and text[k + 1 : k + 2] == "\\"
            style = text[k + 1 : k + 2] in tuple("CcFfoPSsYy") and text[k + 2 : k + 3] == ":"
            end = text.find("}", k + 2)
            if not unclosed and (tags or style) and end >= 0:
                k = end + 1
                continue
            unclosed = unclosed or ((tags or style) and end < 0)
        shown += text[k]
        k += 1
    return shown


def _libass(text: str) -> tuple[str, tuple[str, ...]]:
    """libass 0.17.1, character by character: ``ass_render.c``'s block, ``ass_get_next_char``."""
    shown, k = "", 0
    blocks: list[str] = []
    while k < len(text):
        if text[k] == "{" and (end := text.find("}", k)) >= 0:
            blocks.append(text[k + 1 : end])
            k = end + 1
        elif text[k] == "\\" and text[k + 1 : k + 2] in ("N", "h", "{", "}"):
            shown += {"N": "\n", "h": "\u00a0"}.get(text[k + 1], text[k + 1])
            k += 2
        else:
            shown += text[k]
            k += 1
    return shown, tuple(blocks)


# what a SubRip's braced runs are made of: ASS's tags, MicroDVD's style, escapes
_RUNS: Final = ("{", "}", "\\", "{\\an8}", "{\\an8", "{\\i1", "y:", "N", "h", "n", "x", " ")


@given(st.lists(st.sampled_from(_RUNS), max_size=12).map("".join))
def test_unescaped_is_ffmpeg_then_libass_wherever_they_read(text: str) -> None:
    assert tuple(subverter.unescaped(text)) == _libass(_ffmpeg(text))


@pytest.mark.parametrize(
    ("text", "drawn"),
    [
        ("}" + "{" * 200_000, "}" + "{" * 200_000),  # each unclosed {: no scan to the end
        ("}" + "{\\" * 100_000, "}" + "{" * 100_000 + "\\"),  # its \{ a brace
        ("{\\an8}" + "{\\" * 100_000 + "}", ""),  # each kept {\: no scan to its }, one block
    ],
)
def test_unescaped_is_bounded_whatever_its_braces(text: str, drawn: str) -> None:
    began = time.monotonic()
    assert subverter.unescaped(text).text == drawn
    assert time.monotonic() - began < 1
