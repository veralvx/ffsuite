"""Where a line may break: the units no break enters, and, between two unspaced, whether it may.

Spaces always may. Between characters with none: never inside a cluster (a mark, what LB9 holds
to the character before it, an Indic conjunct, an emoji's joiners, what libass skips); always
after a zero-width space (LB8); never where UAX #14 forbids -- before a zero-width space (LB7),
WJ (LB11), GL (LB12a), CL, CP, EX, IS (LB13), BA, HY, NS (LB21), IN (LB22), PO (LB25's,
anywhere) and CJ (strict, as its default resolves it), after a zero-width joiner (LB8a), WJ, GL
(LB12), OP (LB14), BB (LB21) and PR, and a quote by its side; otherwise beside a wide character
(an ideograph, kana, hangul), and between Thai's and its kin's syllables -- not inside a word,
which needs a dictionary (UAX #14: SA), but never after a vowel written before its consonant,
nor before one written after.

The data: UAX #14's classes, PropList's Logical_Order_Exception, the marks, viramas and wide
characters, and those a line break between two of reads as nothing (``joined``; emoji-data's
read too) -- Unicode 15.1, generated (``ucd.py``), whatever Python's unicodedata; and what
libass skips (``SKIPPED``), its own list.
"""

import re
from bisect import bisect_right
from typing import Final

from ffman.subs.ucd import (
    ATTACHED,
    MARKS,
    NO_END,
    NO_START,
    PREPOSED,
    SA,
    UNSPACED,
    VIRAMAS,
    WIDE,
    points,
)

# not Unicode's, libass's own: what it skips, every font alike -- no glyph, no advance. Its
# is_harfbuzz_ignorable (ass_shaper.c, 0.17.1 and 0.17.4), HarfBuzz's default ignorables
# (is_default_ignorable, 8.3.0 and 13.2.1), which HarfBuzz zeroes when it shapes; LRM and RLM
# (&lrm;, &rlm;) among them
SKIPPED: Final = points(
    (0x00AD, 0x00AD),  # soft hyphen
    (0x034F, 0x034F),  # combining grapheme joiner
    (0x061C, 0x061C),  # Arabic letter mark
    (0x17B4, 0x17B5),  # Khmer inherent vowels
    (0x180B, 0x180E),  # Mongolian variation selectors, vowel separator
    (0x200B, 0x200F),  # zero-width space, ZWNJ, ZWJ, LRM, RLM
    (0x202A, 0x202E),  # bidirectional embeddings and overrides
    (0x2060, 0x206F),  # word joiner, invisible operators, isolates, deprecated formats
    (0xFE00, 0xFE0F),  # variation selectors
    (0xFEFF, 0xFEFF),  # zero-width no-break space (BOM)
    (0xFFF0, 0xFFF8),  # unassigned
    (0x1D173, 0x1D17A),  # musical formatting
    (0xE0000, 0xE0FFF),  # tags, variation selectors 17 to 256
)

# Thai's and Lao's vowels and repetition marks written after their consonant: letters (Lo, Lm),
# not marks, so a cluster does not hold them
_FOLLOWING: Final = frozenset("\u0e30\u0e32\u0e33\u0e45\u0e46\u0eb0\u0eb2\u0eb3\u0ec6")
_ZWJ: Final = "\u200d"  # the zero-width joiner: one sequence of the characters around it
_ZW: Final = "\u200b"  # the zero-width space: a break after it, none before (LB7, LB8)
_WIDE_FIRSTS: Final = tuple(first for first, _ in WIDE)  # each wide range's first, for bisect
_UNSPACED_FIRSTS: Final = tuple(first for first, _ in UNSPACED)
_FIELDS: Final = re.compile(r"[ \t\n]+")  # awk's split(t, a, " "): not NBSP, not U+3000


def segments(text: str) -> tuple[list[str], list[str]]:
    """A text's units -- its clusters -- and the gap before each: " " where spaces were, else "".

    What libass skips is no letter of its own: in the unit before it, or, opening a word, the
    unit after it.
    """
    units: list[str] = []
    gaps: list[str] = []
    blank = False  # the unit so far is what libass skips alone: it takes the next character
    for k, field in enumerate(f for f in _FIELDS.split(text) if f):
        for i, c in enumerate(field):
            if i > 0 and (blank or _joins(units[-1], c)):
                units[-1] += c
            else:
                units.append(c)
                # a space before a field's first unit, but the text's first
                gaps.append(" " if i == 0 and k > 0 else "")
                blank = True
            blank = blank and c in SKIPPED
    return units, gaps


def breakable(before: str, after: str) -> bool:
    """Whether a line may break between two units with no space between them.

    UAX #14's rules in its order: never before a zero-width space (LB7), always after one
    (LB8); never after a zero-width joiner (LB8a), nor before what attaches to the character
    before it (LB9), whose class is that character's; then the classes'.
    """
    last = _base(before)
    first = after[0]
    if first == _ZW:
        return False
    if last == _ZW:
        return True
    if before.endswith(_ZWJ) or first in ATTACHED or first in NO_START or last in NO_END:
        return False
    if is_wide(last) or is_wide(first):
        return True
    return last in SA and first in SA and last not in PREPOSED and first not in _FOLLOWING


def is_mark(c: str) -> bool:
    """A combining mark (Mn, Mc, Me): never parted from its character.

    An accent; Thai's vowels and tones (combining class 0, yet marks); an Indic vowel sign.
    """
    return c in MARKS


def _joins(unit: str, c: str) -> bool:
    """Whether ``c`` belongs to the unit before it, never broken from it.

    A mark; what attaches to it (LB9: ``ATTACHED``); what libass skips; a character past a
    virama (an Indic conjunct: combining class 9) or a zero-width joiner (an emoji sequence).
    """
    return is_mark(c) or c in ATTACHED or c in SKIPPED or unit.endswith(_ZWJ) or unit[-1] in VIRAMAS


def _base(unit: str) -> str:
    """A unit's last character not attached to the one before it: what it is, for breaking after."""
    for c in reversed(unit):
        if c not in ATTACHED:
            return c
    return unit[-1]


def is_wide(c: str) -> bool:
    """East Asian Width W or F: ideographs, kana, hangul, fullwidth -- a size, breakable beside."""
    return _within(c, WIDE, _WIDE_FIRSTS)


def joined(text: str, start: int, end: int) -> bool:
    """Whether a line break, ``text[start:end]`` with its blanks, is read as nothing, not a space.

    CSS Text 3's rule (2013), as Firefox keeps it (``IsSegmentBreakSkipChar``): beside a
    zero-width space, or between two characters of East Asian Width F, H or W -- not an emoji,
    not Hangul, not the won sign -- what libass skips passed over. Firefox also joins beside a
    wide punctuation mark in Chinese and Japanese: a text's language, which ffman is not told.
    """
    if text[start - 1 : start] == _ZW or text[end : end + 1] == _ZW:
        return True
    while start > 0 and text[start - 1] in SKIPPED:
        start -= 1
    while end < len(text) and text[end] in SKIPPED:
        end += 1
    return (
        start > 0
        and end < len(text)
        and _within(text[start - 1], UNSPACED, _UNSPACED_FIRSTS)
        and _within(text[end], UNSPACED, _UNSPACED_FIRSTS)
    )


def _within(c: str, spans: tuple[tuple[int, int], ...], firsts: tuple[int, ...]) -> bool:
    """Whether ``c`` is in ``spans``, inclusive ranges in order (``firsts``: their firsts)."""
    point = ord(c)
    k = bisect_right(firsts, point) - 1
    return k >= 0 and point <= spans[k][1]
