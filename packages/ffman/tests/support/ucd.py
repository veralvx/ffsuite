"""subs/ucd.py, from the Unicode Character Database: the generator and its check.

Run with the UCD's directory -- LineBreak.txt, PropList.txt and Scripts.txt, Unicode 15.1 --
to print the module; the test compares it with src's.
"""

import sys
import unicodedata
from pathlib import Path

# UAX #14: never before WJ (LB11), GL (LB12a -- even after BA or HY, stricter; never asked after
# a space), CL, CP, EX, IS (LB13), BA, HY, NS (LB21), IN (LB22), a postfix (PO: LB25's, wherever
# it is); CJ as NS (strict). Never after WJ (LB11), GL (LB12), OP (LB14), BB (LB21), PR (a prefix)
NO_START_CLASSES = ("WJ", "GL", "CL", "CP", "EX", "IS", "BA", "HY", "NS", "CJ", "IN", "PO")
NO_END_CLASSES = ("WJ", "GL", "OP", "BB", "PR")
# the scripts a font for subtitles carries -- what the estimate takes for its own glyphs
NARROW_SCRIPTS = ("Latin", "Greek", "Cyrillic", "Common", "Inherited")

HEADER = '''"""The Unicode Character Database's tables ffman reads: generated, never edited by hand.

python -m tests.support.ucd UCD_DIR > src/ffman/subs/ucd.py -- Unicode 15.1, Python 3.13's
unicodedata's, so the tables and the categories agree (3.14's is 16.0: its new characters in no
table here); tests/test_ucd.py checks it is that output, byte for byte.
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
}


def _property(path: Path) -> dict[int, str]:
    found: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            continue
        span, value = (x.strip() for x in line.split(";"))
        first, _, last = span.partition("..")
        for c in range(int(first, 16), int(last or first, 16) + 1):
            found[c] = value
    return found


def sets(ucd: Path) -> dict[str, list[int]]:
    """The module's sets, as code points."""
    classes = _property(ucd / "LineBreak.txt")
    quote = [c for c, v in classes.items() if v == "QU"]
    no_start = [c for c, v in classes.items() if v in NO_START_CLASSES]
    no_start += [c for c in quote if unicodedata.category(chr(c)) == "Pf"]  # a closing quote
    no_end = [c for c, v in classes.items() if v in NO_END_CLASSES]
    no_end += [c for c in quote if unicodedata.category(chr(c)) == "Pi"]  # an opening quote
    complex_context = [c for c, v in classes.items() if v == "SA"]
    preposed = [
        c for c, v in _property(ucd / "PropList.txt").items() if v == "Logical_Order_Exception"
    ]
    attached = [
        c
        for c, v in classes.items()
        if v in ("CM", "ZWJ") or (v == "SA" and unicodedata.category(chr(c)) in ("Mn", "Mc"))
    ]
    narrow = [c for c, v in _property(ucd / "Scripts.txt").items() if v in NARROW_SCRIPTS]
    found = {
        "NO_START": no_start,
        "NO_END": no_end,
        "SA": complex_context,
        "PREPOSED": preposed,
        "ATTACHED": attached,
        "NARROW": narrow,
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
        out.append(f"# {NOTES[name]}\n{name}: Final = points(\n{rows})\n")
    return "\n".join(out)


if __name__ == "__main__":
    _ = sys.stdout.write(source(Path(sys.argv[1])))
