"""markup: a text's tags off; WebVTT's character references decoded as HTML decodes them; a SubRip's
text as ffmpeg and libass draw it; an LRC's without its word stamps."""

import html
import re
import time
from typing import Final

import pytest
import subverter
from hypothesis import given, settings
from hypothesis import strategies as st


def test_untagged_puts_what_it_is_given_where_each_tag_was() -> None:
    assert subverter.untagged("a<b>c</b>") == "ac"
    assert subverter.untagged("a<b>c</b>", into="|") == "a|c|"


@pytest.mark.parametrize(
    ("text", "shown", "rest"),
    [  # each as Chromium 141 and ffmpeg 8.1.2's webvtt decoder show it (measured)
        ("before <b ends more", "before ", "<b ends more"),
        ("x <", "x ", "<"),
        ("a <> b", "a  b", ""),
        ("a <3 b > c <d", "a  c ", "<d"),
        ("a > <x <y", "a > ", "<x <y"),  # its first < after the last >
        ("<3 alone", "", "<3 alone"),
        ("a <b>c</b>", "a c", ""),  # closed: as ``untagged``
    ],
)
def test_a_webvtt_tag_no_gt_closes_runs_to_the_texts_end(text: str, shown: str, rest: str) -> None:
    assert subverter.untagged(text, webvtt=True) == shown
    assert subverter.unclosed(text) == rest


@pytest.mark.parametrize(
    ("text", "subrip", "webvtt"),
    [  # each < no > closes: no scan to the end from it
        ("a<" * 200_000, "a<" * 200_000, "a"),
        ("<>" + "<" * 200_000 + "x", "<" * 200_000 + "x", ""),
        ("<" * 200_000 + ">x", "x", "x"),  # one tag, to its >
    ],
    ids=["after each a", "after a tag", "closed once"],
)
def test_untagged_is_bounded_whatever_its_lts(text: str, subrip: str, webvtt: str) -> None:
    began = time.monotonic()
    assert subverter.untagged(text) == subrip
    assert subverter.untagged(text, webvtt=True) == webvtt
    assert time.monotonic() - began < 1


@given(st.lists(st.sampled_from(("<", ">", "a", "<b>", "\n")), max_size=12).map("".join))
def test_untagged_is_its_regex_wherever_that_reads_the_text(text: str) -> None:
    """The regexes alone, unbounded: a tag to its ``>``; in WebVTT, else to the text's end."""
    assert subverter.untagged(text, into="|") == re.sub(r"<[^>]*>", "|", text)
    assert subverter.untagged(text, into="|", webvtt=True) == re.sub(r"<[^>]*>?", "|", text)


def test_a_subrip_lt_with_no_gt_is_text() -> None:
    assert subverter.untagged("I <3 you") == "I <3 you"


@given(st.lists(st.sampled_from(("<", ">", "a", " ", "<b>", "\n")), max_size=12).map("".join))
def test_untagged_as_webvtt_is_untagged_up_to_its_unclosed_tag(text: str) -> None:
    rest = subverter.unclosed(text)
    head = text[: len(text) - len(rest)]
    assert subverter.untagged(text, webvtt=True, into="|") == (
        subverter.untagged(head, into="|") + ("|" if rest else "")
    )
    assert ">" not in rest
    assert rest == "" or rest.startswith("<")


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
    ("text", "as_drawn", "blocks"),
    [
        ("one\\Ntwo", "one\ntwo", ()),  # a line break
        ("a\\hb", "a\u00a0b", ()),  # a no-break space
        ("a\\nb", "a b", ()),  # libass's soft break: a space, ffmpeg's script setting no WrapStyle
        ("C:\\temp \\x", "C:\\temp \\x", ()),  # no escape: as written
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
        # its tags, as ffmpeg's decoder reads them (measured, 8.1.2): a <, then to its > a name
        # it knows, or "likely a tag", dropped; <br> a line break; else the < a character
        ("x<3 and y>2", "x2", ()),  # likely a tag: 3
        ("a < b and c > d", "a  d", ()),  # a space first, but a name it knows: b
        ("< i>x</i>", "x", ()),
        ("x <b class=a>y</b>", "x y", ()),
        ("a <3 b> c", "a  c", ()),
        ("1 < 2 and 3 > 2", "1 < 2 and 3 > 2", ()),  # a space first, no name it knows: text
        ("if x < 5 and y > 3", "if x < 5 and y > 3", ()),
        ("a < b < c > d", "a < b < c > d", ()),  # its scan ends at the next <
        ("<<quote>>", "<<quote>>", ()),  # after a <, no tag but a name it knows
        ("<c.yellow>c</c>", "<c.yellow>c", ()),  # a "." no tag's
        ("one<br>two<BR/>three", "one\ntwo\nthree", ()),
        ("one<br />two</br>x", "one\ntwo\nx", ()),
        ("a<brx>b", "ab", ()),  # likely a tag: dropped
        ("a < font color=red>b</font>", "a b", ()),  # a space first, but a name it knows
        ("<<font>x", "<x", ()),  # after a <, too
        ("a<</v>b <<v>c", "a<b <<v>c", ()),  # after a <, likely again if it closes
        ("heart <3", "heart <3", ()),  # no >
        ("<" + "x" * 127 + ">a", "a", ()),  # a tag of 127 characters at most
        ("<" + "x" * 128 + ">a", "<" + "x" * 128 + ">a", ()),
        ("{\\i1<b>x}y", "y", ()),  # a block's own < no tag: dropped with it
        ("<b{\\i1}>x", "<b>x", ()),  # its name no tag's (a {): text, the { then ASS's tags
    ],
)
def test_drawn_reads_a_subrip_text_as_ffmpeg_and_libass_draw_it(
    text: str, as_drawn: str, blocks: tuple[str, ...]
) -> None:
    assert subverter.drawn(text) == subverter.Drawn(as_drawn, blocks)


_ALIGNED: Final = tuple(f"{n}}}" for n in range(10))  # scanbraces: {\an, a digit, }


_LIKELY: Final = frozenset("0123456789_/abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _ffmpeg_tag(text: str, k: int) -> tuple[str, int]:
    """ffmpeg 8.1's subrip decoder at a ``<``: what it writes, and where it goes on."""
    shown, likely = "", True
    while text[k + 1 : k + 2] == "<":  # "<<": each < but the last a character
        shown, likely, k = shown + "<", False, k + 1
    closing = text[k + 1 : k + 2] == "/"
    scan = n = k + 1 + closing
    while n - scan < 128 and text[n : n + 1] not in ("", "<", ">"):  # scantag
        n += 1
    if n - scan == 128 or text[n : n + 1] != ">":  # 127 characters at most, then its >
        return shown + "<", k + 1
    name = text[scan:n]
    likely = (likely or closing) and not name.startswith(" ")
    name = name.lstrip(" ").split(" ", 1)[0]
    likely = likely and all(c in _LIKELY for c in name)
    lower = name.lower() if name.isascii() else ""
    if lower in ("br", "br/"):
        return shown + "\\N", n + 1
    if lower == "font" or (len(name) == 1 and lower in "bisu") or likely:
        return shown, n + 1
    return shown + "<", k + 1


def _ffmpeg(text: str) -> str:
    """ffmpeg 8.1's subrip decoder, character by character: ``htmlsubtitles.c``'s braces, tags."""
    shown, k, alignments, unclosed = "", 0, 0, False
    while k < len(text):
        if text[k] == "<":
            written, k = _ffmpeg_tag(text, k)
            shown += written
            continue
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
        elif text[k] == "\\" and text[k + 1 : k + 2] in ("N", "n", "h", "{", "}"):
            shown += {"N": "\n", "n": " ", "h": "\u00a0"}.get(text[k + 1], text[k + 1])
            k += 2
        else:
            shown += text[k]
            k += 1
    return shown, tuple(blocks)


# what a SubRip's braced runs and tags are made of: ASS's tags, MicroDVD's style, escapes, its
# tags' names, known and not
_RUNS: Final = (
    *("{", "}", "\\", "{\\an8}", "{\\an8", "{\\i1", "y:", "N", "h", "n", "t", "x", " "),
    *("<", ">", "/", "<<", "b", "br", "font", "c.y", "3"),
)


@settings(max_examples=1000)  # cheap, and a tag needs its < and > in a row
@given(st.lists(st.sampled_from(_RUNS), max_size=12).map("".join))
def test_drawn_is_ffmpeg_then_libass_wherever_they_read(text: str) -> None:
    assert tuple(subverter.drawn(text)) == _libass(_ffmpeg(text))


@pytest.mark.parametrize(
    ("text", "as_drawn"),
    [
        ("}" + "{" * 200_000, "}" + "{" * 200_000),  # each unclosed {: no scan to the end
        ("}" + "{\\" * 100_000, "}" + "{" * 100_000 + "\\"),  # its \{ a brace
        ("{\\an8}" + "{\\" * 100_000 + "}", ""),  # each kept {\: no scan to its }, one block
        ("a<" * 200_000, "a<" * 200_000),  # no > after them: no tag sought
        ("a<" * 200_000 + ">", "a<" * 199_999 + "a"),  # each scan ended by the next <
        ("<" * 200_000 + ">x", "<" * 200_000 + ">x"),  # a run: guillemets, scanned once
        ("}" + "{" * 200_000 + ">", "}" + "{" * 200_000 + ">"),  # past the last }, no { sought
    ],
)
def test_drawn_is_bounded_whatever_its_braces_and_lts(text: str, as_drawn: str) -> None:
    began = time.monotonic()
    assert subverter.drawn(text).text == as_drawn
    assert time.monotonic() - began < 1


@pytest.mark.parametrize(
    ("text", "shown"),
    [  # Enhanced LRC's word stamps off, as Navidrome 0.64.2 and Jellyfin 12.2 read them (by source)
        ("<00:12.00>Enhanced <00:12.40>word <00:12.90>times", "Enhanced word times"),
        ("wo<00:01.00>rd", "word"),  # a stamp inside a word: no space for it
        ("<00:01>a <00:01.5>b <61:00.000>c <00:01.00>", "a b c "),  # the line stamps' grammar
        # every other character as written: a stamp of hours, unclosed or spaced; a tag
        ("<1:02:03.00>a <00:01.00 b < 00:01.00>c", "<1:02:03.00>a <00:01.00 b < 00:01.00>c"),
        ("<i>x</i> x<3 and y>2 <v Bob>", "<i>x</i> x<3 and y>2 <v Bob>"),
        ("a\\nb\\tc {\\an8}d &amp;", "a\\nb\\tc {\\an8}d &amp;"),  # typed, braced, a reference
    ],
)
def test_unstamped_takes_an_lrcs_word_stamps_off_alone(text: str, shown: str) -> None:
    assert subverter.unstamped(text) == shown


def test_unstamped_is_bounded_whatever_its_lts() -> None:
    text = "<0:" * 100_000 + "0" * 100_000  # each < a stamp's start, none closed
    began = time.monotonic()
    assert subverter.unstamped(text) == text
    assert time.monotonic() - began < 1
