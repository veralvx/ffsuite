"""subs.breaks: where a line may break in unspaced text -- UAX #14's rules, Thai's syllables."""

import pytest

from ffman.subs.breaks import SKIPPED, breakable, is_wide, segments


@pytest.mark.parametrize(
    ("before", "after", "may"),
    [
        ("日", "本", True),  # ideographs: anywhere between (ID)
        ("日", "A", True),  # beside a wide character
        ("A", "B", False),  # Latin letters: never apart (AL)
        ("て", "、", False),  # no line opens on a comma (CL)
        ("す", "。", False),  # nor a full stop (CL)
        ("ト", "」", False),  # nor a closing bracket (CL)
        ("ね", "！", False),  # nor ! (EX)
        ("ち", "ょ", False),  # nor a small kana (CJ: strict)
        ("ス", "ー", False),  # nor the prolonged mark (CJ)
        ("時", "々", False),  # nor an iteration mark (NS)
        ("了", "…", False),  # nor an ellipsis (IN)
        ("０", "％", False),  # nor a postfix (PO)
        ("「", "明", False),  # no line ends on an opening bracket (OP)
        ("￥", "１", False),  # nor a prefix (PR)
        ("见", "”", False),  # a closing quote stays with its text
        ("“", "明", False),  # an opening quote with its
        ("ก", "ข", True),  # Thai: between syllables
        ("เ", "ช", False),  # never after a vowel written before its consonant
        ("ข", "า", False),  # never before one written after
        ("ใคร", "ๆ", False),  # nor a repetition mark
        ("\u0301", "日", True),  # a unit of a mark alone (a text opening on one): itself
        ("o", "\u200b", False),  # never before a zero-width space (LB7)
        ("o\u200b", "b", True),  # always after one (LB8), Latin letters too
        ("x\u200b", "\u200eY", True),  # whatever follows it (LB8 before LB9)
        ("\u200b", "\u200b", False),  # but another (LB7 before LB8)
        ("a\u200d", "日", False),  # never after a zero-width joiner (LB8a): a word ending on one
        ("日", "\u200e", False),  # an LRM: held by the character before it (LB9: CM)
        ("日", "\u0301", False),  # a word opening on a mark: held too (LB9)
        ("ก\u200e", "ข", True),  # its unit's class the character's: Thai's syllables part
        ("日", "\u2060", False),  # a word joiner (WJ): never before it (LB11)
        ("\u2060", "本", False),  # nor after it
        ("日", "\u00a0", False),  # a no-break space (GL): never before it (LB12a)
        ("\u00a0", "本", False),  # nor after it (LB12)
        ("日\u180e", "本", False),  # nor after a Mongolian vowel separator (GL)
        ("日\u034f", "本", False),  # nor a combining grapheme joiner: a mark, but GL, not CM
    ],
)
def test_where_a_line_may_break(before: str, after: str, *, may: bool) -> None:
    assert breakable(before, after) is may


# ICU 74.2's line breaker, strict (createLineInstance, "ja@lb=strict", "zh@lb=strict"):
# recorded, ICU being no dependency -- 339 of 339 break positions agreed on 31 texts
ICU_STRICT = [
    "ちょっ|と|待っ|て、|「ABC|テ|ス|ト」|は|今|日|で|す。|え|え、|そ|う|で|す|ね！",
    "気|温|は|３|０℃、|湿|度|は|８|０％|で|す。",
    "価|格|は|￥１，|０|０|０|で|す。",
    "他|说：|“明|天|见。”|然|后|就|走|了……",
    "《三|体》|是|刘|慈|欣|写|的|科|幻|小|说；|非|常|好|看。",
    "えーっ|と、|何|だっ|け……|そ|う|そ|う、|思|い|出|し|た。",
]


@pytest.mark.parametrize("expected", ICU_STRICT)
def test_the_breaks_are_icus_strict_ones(expected: str) -> None:
    units, gaps = segments(expected.replace("|", ""))
    found = units[0]
    for before, after, gap in zip(units[:-1], units[1:], gaps[1:], strict=True):
        found += ("|" if gap or breakable(before, after) else "") + gap + after
    assert found == expected


def test_a_text_s_units_and_gaps() -> None:
    """Its clusters, and the gap before each: spaces collapse, a mark stays with its own."""
    assert segments(" cafe\u0301  日本 ") == (
        ["c", "a", "f", "e\u0301", "日", "本"],
        ["", "", "", "", " ", ""],
    )


@pytest.mark.parametrize(
    ("text", "units"),
    [
        ("wo\u200erd", ["w", "o\u200e", "r", "d"]),  # in the unit before it
        ("\u200eword", ["\u200ew", "o", "r", "d"]),  # opening a word: the unit after it
        ("foo\u200bbar", ["f", "o", "o\u200b", "b", "a", "r"]),  # a zero-width space too
        ("日本\u2060語", ["日", "本\u2060", "語"]),  # a word joiner too
        ("\u200e\u200f", ["\u200e\u200f"]),  # nothing else: a unit of its own
    ],
)
def test_what_libass_skips_is_no_unit_of_its_own(text: str, units: list[str]) -> None:
    """Drawn as nothing, it is no letter: painted, it would be a colour step on nothing."""
    assert segments(text)[0] == units


# libass's is_harfbuzz_ignorable, read in ass_shaper.c (0.17.1, 0.17.4)
LIBASS = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x17B4, 0x17B5),
    (0x180B, 0x180E),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFF0, 0xFFF8),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)


@pytest.mark.parametrize(("first", "last"), LIBASS)
def test_what_libass_skips_is_its_list(first: int, last: int) -> None:
    """Each of its ranges whole, the code points beside it not (U+180F, U+FFF9: drawn)."""
    assert {chr(c) for c in range(first, last + 1)} <= SKIPPED
    assert chr(first - 1) not in SKIPPED
    assert chr(last + 1) not in SKIPPED


def test_libass_skips_nothing_else() -> None:
    """Its 13 ranges, 4165 code points: no other."""
    assert len(SKIPPED) == sum(last - first + 1 for first, last in LIBASS)


@pytest.mark.parametrize(
    ("text", "units"),
    [
        ("a\u0897", ["a", "\u0897"]),  # Arabic Pepet: a 16.0 mark, unassigned in 15.1
        ("\U000113ce\u0915", ["\U000113ce", "\u0915"]),  # a 16.0 virama: none in 15.1
    ],
)
def test_unicode_is_15_1_whatever_the_python(text: str, units: list[str]) -> None:
    """Python 3.14's unicodedata is Unicode 16.0, 3.13's 15.1: ffman reads its own 15.1 tables,
    so a subtitle breaks alike under both."""
    assert segments(text)[0] == units


def test_a_trigram_is_not_wide_whatever_the_python() -> None:
    """U+2630, wide in 16.0 (Python 3.14), not in 15.1: no size of its own, no break beside."""
    assert not is_wide("\u2630")
    assert not breakable("\u2630", "\u2630")
