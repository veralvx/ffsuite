"""SubRip, WebVTT, ASS and LRC converted into one another by ffmpeg, measured -- and what ffman's
readers (subverter) read of each source.

Each case is one subject (text, markup, positions, speakers, overlaps, empty cues, word timing,
times) written in each format that can hold it. Every source is converted into every format
(`ffmpeg -i in.X out.Y`: the source's decoder into ASS, the target's encoder from it), and each
result back into the source's format; ffman's reading is `subverter.read` on the source.

Usage: python3 ffmpeg.py FFMPEG PYTHON  (PYTHON: an interpreter that imports subverter and
ffman). Prints what it found; references/ffmpeg.md's tables are this output, at ffmpeg n8.1.2.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from readers import converted, read_back

FFMPEG, PYTHON = sys.argv[1], sys.argv[2]
FORMATS = ("srt", "vtt", "ass", "lrc")

ASS_HEAD = (
    "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,"
    "1,1,0,2,10,10,10,1\n\n[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


def srt(*cues: tuple[str, str, str]) -> str:
    """SubRip: each cue's start, end (HH:MM:SS,mmm) and text."""
    return "".join(f"{n}\n{a} --> {z}\n{t}\n\n" for n, (a, z, t) in enumerate(cues, 1))


def vtt(*cues: tuple[str, str, str]) -> str:
    """WebVTT: each cue's start, end (and settings) and text."""
    return "WEBVTT\n\n" + "".join(f"{a} --> {z}\n{t}\n\n" for a, z, t in cues)


def ass(*events: tuple[str, str, str] | tuple[str, str, str, str]) -> str:
    """ASS: each event's start, end (h:mm:ss.cc), text and, optionally, its Name."""
    lines = [
        f"Dialogue: 0,{e[0]},{e[1]},Default,{e[3] if len(e) > 3 else ''},0,0,0,,{e[2]}\n"
        for e in events
    ]
    return ASS_HEAD + "".join(lines)


def lrc(*lines: tuple[str, str]) -> str:
    """LRC: each line's start (mm:ss.xx) and text."""
    return "".join(f"[{a}]{t}\n" for a, t in lines)


# a subject each: its source in every format that holds it
CASES: dict[str, dict[str, str]] = {
    "text": {
        "srt": srt(
            ("00:00:01,230", "00:00:02,340", "A & B < C > D\nsecond line"),
            ("00:00:03,000", "00:00:04,000", "  spaced  "),
        ),
        "vtt": vtt(
            ("00:01.230", "00:02.340", "A &amp; B &lt; C &gt; D\nsecond line"),
            ("00:03.000", "00:04.000", "  spaced  "),
        ),
        "ass": ass(
            ("0:00:01.23", "0:00:02.34", "A & B < C > D\\Nsecond line"),
            ("0:00:03.00", "0:00:04.00", "  spaced  "),
        ),
        "lrc": lrc(("00:01.23", "A & B < C > D"), ("00:03.00", "  spaced  "), ("00:04.00", "")),
    },
    "markup": {
        "srt": srt(
            (
                "00:00:01,000",
                "00:00:02,000",
                '<b>bold</b> <i>it</i> <u>un</u> <s>st</s> <font color="#ff0000">red</font>',
            )
        ),
        "vtt": vtt(
            (
                "00:01.000",
                "00:02.000",
                "<b>bold</b> <i>it</i> <u>un</u> <c.red>red</c> <c.yellow>class</c>",
            )
        ),
        "ass": ass(
            (
                "0:00:01.00",
                "0:00:02.00",
                (
                    "{\\b1}bold{\\b0} {\\i1}it{\\i0} {\\u1}un{\\u0} {\\s1}st{\\s0} "
                    "{\\c&H0000FF&}red{\\c} {\\fnSerif\\fs30}font"
                ),
            )
        ),
    },
    "positions": {
        "srt": srt(
            ("00:00:01,000", "00:00:02,000", "{\\an8}top"),
            ("00:00:03,000", "00:00:04,000  X1:100 X2:300 Y1:400 Y2:450", "box"),
        ),
        # an identifier, `intro`, which vtt() does not write, and settings
        "vtt": "WEBVTT\n\nintro\n00:01.000 --> 00:02.000 line:0 align:start position:10%\ntop\n",
        "ass": ass(
            ("0:00:01.00", "0:00:02.00", "{\\an8}top"),
            ("0:00:03.00", "0:00:04.00", "{\\pos(10,20)}placed"),
        ),
    },
    "speakers": {
        "vtt": vtt(("00:01.000", "00:02.000", "<v Bob>Hello</v>")),
        "ass": ass(("0:00:01.00", "0:00:02.00", "Hello", "Bob")),
    },
    "overlaps": {
        "srt": srt(
            ("00:00:01,000", "00:00:04,000", "long"), ("00:00:02,000", "00:00:03,000", "inside")
        ),
        "vtt": vtt(("00:01.000", "00:04.000", "long"), ("00:02.000", "00:03.000", "inside")),
        "ass": ass(("0:00:01.00", "0:00:04.00", "long"), ("0:00:02.00", "0:00:03.00", "inside")),
    },
    "empty and zero-length cues": {
        "srt": srt(
            ("00:00:01,000", "00:00:02,000", ""),
            ("00:00:03,000", "00:00:03,000", "zero"),
            ("00:00:05,000", "00:00:06,000", "after"),
        ),
        "vtt": vtt(
            ("00:01.000", "00:02.000", ""),
            ("00:03.000", "00:03.000", "zero"),
            ("00:05.000", "00:06.000", "after"),
        ),
        "ass": ass(
            ("0:00:01.00", "0:00:02.00", ""),
            ("0:00:03.00", "0:00:03.00", "zero"),
            ("0:00:05.00", "0:00:06.00", "after"),
        ),
        "lrc": lrc(
            ("00:01.00", ""),
            ("00:03.00", "zero"),
            ("00:03.00", "same start"),
            ("00:05.00", "after"),
        ),
    },
    "word timing": {
        "srt": srt(
            ("00:00:01,000", "00:00:01,500", "<u>one</u> two three"),
            ("00:00:01,500", "00:00:01,800", "one <u>two</u> three"),
            ("00:00:01,800", "00:00:02,000", "one two <u>three</u>"),
        ),
        "vtt": vtt(("00:01.000", "00:02.000", "one <00:00:01.500>two <00:00:01.800>three")),
        "ass": ass(("0:00:01.00", "0:00:02.00", "{\\k50}one {\\k30}two {\\k20}three")),
        "lrc": lrc(("00:01.00", "<00:01.00>one <00:01.50>two <00:01.80>three"), ("00:02.00", "")),
    },
    "times": {
        "srt": srt(
            ("00:00:01,234", "00:00:02,345", "ms"),
            ("00:00:03,005", "00:00:04,995", "half cs"),
            ("10:00:00,000", "10:00:01,000", "ten hours"),
        ),
        "vtt": vtt(
            ("00:01.234", "00:02.345", "ms"),
            ("00:03.005", "00:04.995", "half cs"),
            ("10:00:00.000", "10:00:01.000", "ten hours"),
        ),
        "ass": ass(("0:00:01.23", "0:00:02.34", "cs"), ("9:59:59.00", "9:59:59.99", "last")),
        "lrc": lrc(
            ("00:01.234", "ms"),
            ("00:03.005", "half cs"),
            ("61:00.00", "an hour on"),
            ("61:01.00", ""),
        ),
    },
}


def body(fmt: str, text: str) -> list[str]:
    """A file's timed content: its cues' lines (SubRip's indexes and blank lines gone), its
    Dialogue events (from their Start), its timed LRC lines."""
    if text.startswith("[failed"):
        return [text]
    lines = text.splitlines()
    if fmt == "ass":
        return [line.split(",", 1)[1] for line in lines if line.startswith("Dialogue:")]
    if fmt == "lrc":
        return [line for line in lines if re.match(r"\[\d", line)]
    if fmt == "vtt":
        lines = lines[1:]
    return [line for line in lines if line and not (fmt == "srt" and line.isdigit())]


def ffman(fmt: str, data: str) -> object:
    """subverter's reading of a source: its cues, then its words (none for ASS: ffman burns it as
    it is)."""
    if fmt == "ass":
        return "no reader: burned as it is"
    got = read_back(PYTHON, fmt, data)["subverter"]
    if isinstance(got, str):
        return ["refused", got.removeprefix("refused: ")]
    words = [["words", *(w[1:] for w in got["words"])]] if got["words"] else []
    return got["timed"] + words


def main() -> None:
    version = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True, check=True)
    print(version.stdout.splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for case, sources in CASES.items():
            print(f"\n## {case}\n")
            for fmt, data in sources.items():
                src = work / f"in.{fmt}"
                _ = src.write_text(data, encoding="utf-8")
                print(f"{fmt}: {body(fmt, data)!r}")
                print(f"    ffman: {ffman(fmt, data)!r}")
                for target in FORMATS:
                    out = work / f"out.{target}"
                    text, warnings = converted(FFMPEG, src, out)
                    line = f"    -> {target}: {body(target, text)!r}"
                    if target != fmt and not text.startswith("[failed"):
                        back, back_warnings = converted(FFMPEG, out, work / f"back.{fmt}")
                        line += f"\n         back to {fmt}: {body(fmt, back)!r}"
                        warnings = "; ".join(w for w in (warnings, back_warnings) if w)
                    print(line + (f"\n         | {warnings}" if warnings else ""))


if __name__ == "__main__":
    main()
