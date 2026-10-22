"""subs/ucd.py, from the Unicode Character Database: the generator and its check.

Run with the UCD's directory -- UnicodeData.txt, EastAsianWidth.txt, LineBreak.txt,
PropList.txt, Scripts.txt and emoji-data.txt, Unicode 15.1 -- to print the module; the test
compares it with src's. Python's unicodedata is never asked: its version is the interpreter's.
"""

import sys
from collections.abc import Iterator
from pathlib import Path

# UAX #14: never before WJ (LB11), GL (LB12a -- even after BA or HY, stricter; never asked after
# a space), CL, CP, EX, IS (LB13), BA, HY, NS (LB21), IN (LB22), a postfix (PO: LB25's, wherever
# it is); CJ as NS (strict). Never after WJ (LB11), GL (LB12), OP (LB14), BB (LB21), PR (a prefix)
NO_START_CLASSES = ("WJ", "GL", "CL", "CP", "EX", "IS", "BA", "HY", "NS", "CJ", "IN", "PO")
NO_END_CLASSES = ("WJ", "GL", "OP", "BB", "PR")
# the scripts a font for subtitles carries -- what the estimate takes for its own glyphs
NARROW_SCRIPTS = ("Latin", "Greek", "Cyrillic", "Common", "Inherited")

HEADER = '''"""The Unicode Character Database's tables ffman reads: generated, never edited by hand.

python -m tests.support.ucd UCD_DIR > src/ffman/subs/ucd.py -- Unicode 15.1, every property
ffman reads, whatever the Python: unicodedata is the interpreter's (3.13's 15.1, 3.14's 16.0),
and a subtitle would break by which ran it. tests/test_ucd.py checks it is that output, byte
for byte.
"""

from typing import Final


def points(*spans: tuple[int, int]) -> frozenset[str]:
    """The characters of inclusive code point ranges."""
    return frozenset(chr(c) for first, last in spans for c in range(first, last + 1))

'''
NOTES = {
    "NO_START": "UAX #14's classes no line opens on, and a closing quote (breaks.py)",
    "NO_END": "UAX #14's classes no line ends on, and an opening quote (breaks.py)",
    "SA": "UAX #14's complex context: Thai, Lao, Khmer, Burmese... (breaks.py)",
    "PREPOSED": "PropList's Logical_Order_Exception: a vowel written before its consonant",
    "ATTACHED": "LB9's X (CM | ZWJ)*, held by the character before: CM, ZWJ, SA's marks (LB1)",
    "NARROW": "Scripts' Latin, Greek, Cyrillic, Common, Inherited: a font's own (metrics.py)",
    "MARKS": "UnicodeData's marks, Mn, Mc and Me: never parted from their character (breaks.py)",
    "VIRAMAS": "UnicodeData's canonical combining class 9: a virama, the consonant after it held",
    "WIDE": "EastAsianWidth's W and F: a size, breakable beside -- ranges, for bisect",
    "UNSPACED": "F, H, W but emoji, Hangul, U+20A9: a line break between two none (breaks.py)",
}
# emitted as ranges: 15.1's 182,521 wide points as a frozenset took 40-50 ms and 19 MiB to build
SPANS = ("WIDE", "UNSPACED")


def _values(path: Path) -> Iterator[tuple[int, str]]:
    """Each code point a line names, and its value: a point once per property it has."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        span, value = (x.strip() for x in line.split(";"))
        first, _, last = span.partition("..")
        for c in range(int(first, 16), int(last or first, 16) + 1):
            yield c, value


def _property(path: Path) -> dict[int, str]:
    """A file of one value a point: each point's."""
    return dict(_values(path))


def _unicode_data(path: Path) -> tuple[dict[int, str], dict[int, int]]:
    """Each code point's general category and canonical combining class -- a range's (its
    ``<..., First>`` and ``<..., Last>`` lines) to every point in it."""
    category: dict[int, str] = {}
    combining: dict[int, int] = {}
    first = None
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split(";")
        c = int(fields[0], 16)
        if fields[1].endswith(", First>"):
            first = c
            continue
        for point in range(c if first is None else first, c + 1):
            category[point], combining[point] = fields[2], int(fields[3])
        first = None
    return category, combining


def sets(ucd: Path) -> dict[str, list[int]]:
    """The module's sets, as code points."""
    category, combining = _unicode_data(ucd / "UnicodeData.txt")
    classes = _property(ucd / "LineBreak.txt")
    quote = [c for c, v in classes.items() if v == "QU"]
    no_start = [c for c, v in classes.items() if v in NO_START_CLASSES]
    no_start += [c for c in quote if category.get(c) == "Pf"]  # a closing quote
    no_end = [c for c, v in classes.items() if v in NO_END_CLASSES]
    no_end += [c for c in quote if category.get(c) == "Pi"]  # an opening quote
    complex_context = [c for c, v in classes.items() if v == "SA"]
    preposed = [c for c, v in _values(ucd / "PropList.txt") if v == "Logical_Order_Exception"]
    attached = [
        c
        for c, v in classes.items()
        if v in ("CM", "ZWJ") or (v == "SA" and category.get(c) in ("Mn", "Mc"))
    ]
    scripts = _property(ucd / "Scripts.txt")
    narrow = [c for c, v in scripts.items() if v in NARROW_SCRIPTS]
    width = _property(ucd / "EastAsianWidth.txt")
    wide = [c for c, v in width.items() if v in ("W", "F")]
    # CSS Text 3's segment break rule (2013) as Firefox keeps it: IsSegmentBreakSkipChar
    emoji = {c for c, v in _values(ucd / "emoji-data.txt") if v == "Emoji"}
    unspaced = [
        c
        for c, v in width.items()
        if (v in ("F", "H") or (v == "W" and c not in emoji))
        and scripts.get(c) != "Hangul"
        and c != 0x20A9
    ]
    found = {
        "NO_START": no_start,
        "NO_END": no_end,
        "SA": complex_context,
        "PREPOSED": preposed,
        "ATTACHED": attached,
        "NARROW": narrow,
        "MARKS": [c for c, v in category.items() if v.startswith("M")],
        "VIRAMAS": [c for c, v in combining.items() if v == 9],  # a virama's class
        "WIDE": wide,
        "UNSPACED": unspaced,
    }
    return {name: sorted(points) for name, points in found.items()}


def ranges(points: list[int]) -> list[tuple[int, int]]:
    """Consecutive code points as (first, last) ranges."""
    out: list[tuple[int, int]] = []
    for c in points:
        if out and c == out[-1][1] + 1:
            out[-1] = (out[-1][0], c)
        else:
            out.append((c, c))
    return out


def source(ucd: Path) -> str:
    """The module as Python: its header, then each set, a tuple of ranges, under its note."""
    out = [HEADER]
    for name, points in sets(ucd).items():
        rows = "".join(f"    (0x{a:04X}, 0x{b:04X}),\n" for a, b in ranges(points))
        call = "" if name in SPANS else "points"
        out.append(f"# {NOTES[name]}\n{name}: Final = {call}(\n{rows})\n")
    return "\n".join(out)


if __name__ == "__main__":
    _ = sys.stdout.write(source(Path(sys.argv[1])))
