"""The mappings between subtitle formats, measured where the format records leave them open.

Conversions: ffmpeg's (each source into the targets it writes) and ffman's reading (subverter's
cues and words, then ffman's chunks) of what crosses formats -- times into centiseconds, a text
line holding `-->`, LRC's header tags, speakers, comments, identifiers, breaks and quoted fields.
Renderers: libass through ffmpeg's `ass` filter and Chromium through a `<track>` (`frames.py`),
on 1280x720 black: where each places a cue (its ink's box, as fractions of the frame), what
colour, decoration and size each draws, and what spaces cost (the ink's size, in pixels).

Usage: python3 mappings.py FFMPEG PYTHON  (PYTHON: an interpreter that imports subverter and
ffman; this one, playwright and its Chromium). Prints what it found; references/mappings.md's
tables are this output, at ffmpeg n8.1.2 (libass 0.17.1) and Chromium 141.0.7390.37.
"""

import json
import statistics
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import files
from files import cues
from frames import INK, box, chromium, ffmpeg, libass, words_in
from readers import converted, read_back

FFMPEG, PYTHON = sys.argv[1], sys.argv[2]
SIZE = WIDTH, HEIGHT = 1280, 720
AT = (1500,)  # ms: inside every drawn cue (1 s to 3 s)


# white, Arial 48, no outline or shadow, bottom centre, margins 20 -- libass's measure of a cue
STYLE = (
    "Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,20,20,20,1"
)
# ffmpeg's own default style (`ff_ass_subtitle_header_default`): converted, it adds no markup
FFMPEG_STYLE = "Arial,16,&Hffffff,&Hffffff,&H0,&H0,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1"


def titled(title: str) -> str:
    """An ASS script's head in ffmpeg's default style, with a `Title`."""
    head = files.ass(size=(384, 288), style=FFMPEG_STYLE)
    return head.replace("ScriptType: v4.00+\n", f"ScriptType: v4.00+\nTitle: {title}\n")


# a case each: its source's extension and text, and the formats ffmpeg converts it into
CASES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # an end equal to the next start, 2.004 s; the first starting at 1.006 s
    "times into centiseconds": (
        "srt",
        cues("srt", [(1006, 2004, "first"), (2004, 3000, "second")]),
        ("ass", "lrc"),
    ),
    "a SubRip text line holding -->": (
        "srt",
        cues("srt", [(1000, 2000, "a --> b\nc"), (3000, 4000, "next")]),
        ("srt", "vtt", "ass"),
    ),
    "a WebVTT text line holding -->": (
        "vtt",
        cues("vtt", [(1000, 2000, "a --> b\nc"), (3000, 4000, "next")]),
        ("vtt", "srt"),
    ),
    "LRC's header tags and offset": (
        "lrc",
        "[ti:Title]\n[ar:Artist]\n[offset:+500]\n[00:01.00]one\n[00:02.00]two\n[00:03.00]\n",
        ("srt", "vtt", "ass"),
    ),
    "ASS's Title, a speaker (Name) and a Comment": (
        "ass",
        titled("The title")
        + "Dialogue: 0,0:00:01.00,0:00:02.00,Default,Bob,0,0,0,,hello\n"
        + "Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,a note\n",
        ("srt", "vtt", "lrc"),
    ),
    "WebVTT's title, identifier, NOTE and voice": (
        "vtt",
        "WEBVTT - The title\n\nNOTE a note\n\nintro\n00:01.000 --> 00:02.000\n<v Bob>hello</v>\n",
        ("srt", "ass", "lrc"),
    ),
    "whisper-cli -di: a speaker field": (
        "json",
        json.dumps(
            {
                "transcription": [
                    {"offsets": {"from": 1000, "to": 2000}, "text": " hello", "speaker": "0"}
                ]
            }
        ),
        (),
    ),
    "WhisperX --diarize: a speaker field": (
        "json",
        json.dumps(
            {"segments": [{"start": 1, "end": 2, "text": "hello", "speaker": "SPEAKER_00"}]}
        ),
        (),
    ),
    "two lines": ("srt", cues("srt", [(1000, 2000, "one\ntwo")]), ("vtt", "ass", "lrc")),
    "a CSV field quoted across lines, a comma": (
        "csv",
        'start,end,text\n1000,2000,"one\ntwo"\n2000,3000,"a, b"\n',
        (),
    ),
    "into plain text": ("srt", cues("srt", [(1000, 2000, "one")]), ("txt",)),
}


def written(fmt: str, text: str) -> list[str]:
    """What a file holds but its boilerplate: SubRip's indexes, blank lines, ASS's head but its
    `Title`."""
    if text.startswith("[failed"):
        return [text]
    lines = [line for line in text.splitlines() if line]
    if fmt == "srt":
        return [line for line in lines if not line.isdigit()]
    if fmt == "ass":
        kept = ("Title:", "Dialogue:", "Comment:")
        return [line for line in lines if line.startswith(kept)]
    return lines


def reading(fmt: str, data: str) -> list[str]:
    """subverter's cues and ffman's chunks, a line each."""
    found = read_back(PYTHON, fmt, data)
    said: list[str] = []
    for reader in ("subverter", "ffman"):
        got = found[reader]
        said.append(f"{reader}: {got if isinstance(got, str) else got['timed']}")
    return said


def text_colour(frame: bytes) -> str:
    """The text's colour: the median of its bright pixels (a channel at 160 or more: no edge's),
    `#rrggbb`."""
    lit = [frame[i : i + 3] for i in range(0, len(frame), 3) if max(frame[i : i + 3]) >= 160]
    if not lit:
        return "none"
    return "#" + "".join(f"{int(statistics.median(p[k] for p in lit)):02x}" for k in range(3))


def lines_across(frame: bytes) -> str:
    """The text's size (px), and its rows inked across nine tenths of its width -- an underline, a
    line through -- as fractions of its height."""
    found = box(frame, WIDTH)
    if found is None:
        return "nothing"
    left, top, right, bottom = found
    rows: list[float] = []
    for y in range(top, bottom):
        row = frame[3 * y * WIDTH : 3 * (y + 1) * WIDTH]
        inked = sum(1 for x in range(left, right) if max(row[3 * x : 3 * x + 3]) >= INK)
        if inked >= 0.9 * (right - left):
            rows.append((y - top) / (bottom - top))
    lines = f"{min(rows):.2f}-{max(rows):.2f}" if rows else "none"
    return f"{right - left} x {bottom - top}, a line across at {lines}"


def placed(frame: bytes) -> str:
    """The ink's box, as fractions of the frame: x from-to, y from-to."""
    found = box(frame, WIDTH)
    if found is None:
        return "nothing"
    left, top, right, bottom = found
    return f"x {left / WIDTH:.2f}-{right / WIDTH:.2f}, y {top / HEIGHT:.2f}-{bottom / HEIGHT:.2f}"


def spaced(frame: bytes) -> str:
    """The ink's left and right edges, its width and height (px), and how many runs of ink."""
    found = box(frame, WIDTH)
    if found is None:
        return "nothing"
    left, top, right, bottom = found
    runs = len(words_in(frame, WIDTH))
    return f"{left}-{right}, {right - left} x {bottom - top}, {runs} runs"


def drawn_by_libass(work: Path, texts: dict[str, str]) -> dict[str, bytes]:
    """Each event's text drawn by libass, at ``AT``."""
    script = work / "drawn.ass"
    frames: dict[str, bytes] = {}
    for name, text in texts.items():
        _ = script.write_text(
            files.ass((1000, 3000, text), size=SIZE, style=STYLE), encoding="utf-8"
        )
        frames[name] = libass(FFMPEG, script, AT, SIZE)[0]
    return frames


def vtt(text: str, settings: str = "", style: str = "") -> str:
    """A WebVTT file of one cue, 1 s to 3 s; ``style``: a STYLE block's CSS."""
    head = f"STYLE\n{style}\n\n" if style else ""
    return f"WEBVTT\n\n{head}00:01.000 --> 00:03.000{settings}\n{text}\n"


# libass's alignments, and the WebVTT settings that place a cue so in Chromium
ALIGNED = {f"\\an{n}": f"{{\\an{n}}}Placed" for n in range(1, 10)}
SETTINGS = {
    f"{line or 'line auto'}{align or ' align center'}": f"{' ' + line if line else ''}{align}"
    for line in ("line:0", "line:50%", "", "line:-1", "line:90%")
    for align in (
        " align:left",
        "",
        " align:right",
        " align:start",
        " position:10% align:left",
        " position:90% align:right",
    )
}
COLOURS = ("white", "lime", "cyan", "red", "yellow", "magenta", "blue", "black")
DECORATED = {  # libass's event text, Chromium's cue
    "plain": ("Struck through", vtt("Struck through")),
    "\\s1 / STYLE line-through": (
        "{\\s1}Struck through",
        vtt("<c.s>Struck through</c>", style="::cue(.s) { text-decoration: line-through }"),
    ),
    "\\u1 / <u>": ("{\\u1}Struck through", vtt("<u>Struck through</u>")),
    "\\fs96 / STYLE font-size 200%": (
        "{\\fs96}Struck through",
        vtt("<c.big>Struck through</c>", style="::cue(.big) { font-size: 200% }"),
    ),
    "\\fnSerif / STYLE font-family serif": (
        "{\\fnSerif}Struck through",
        vtt("<c.serif>Struck through</c>", style="::cue(.serif) { font-family: serif }"),
    ),
}
SPACES = {  # libass's event text, Chromium's cue
    "ab": ("ab", vtt("ab")),
    "a b": ("a b", vtt("a b")),
    "a  b (two spaces)": ("a  b", vtt("a  b")),
    "a     b (five)": ("a     b", vtt("a     b")),
    "  ab (leading)": ("  ab", vtt("  ab")),
    "ab  (trailing)": ("ab  ", vtt("ab  ")),
    "a, a tab, b": ("a\tb", vtt("a\tb")),
    "a, three hard spaces, b": ("a\\h\\h\\hb", vtt("a&nbsp;&nbsp;&nbsp;b")),
    "a, \\n, b (WrapStyle 0)": ("a\\nb", vtt("a\nb")),
}


def both(work: Path, cases: dict[str, tuple[str, str]], measure: Callable[[bytes], str]) -> None:
    """Each case drawn by libass (its event's text) and by Chromium (its WebVTT), measured alike."""
    ours = drawn_by_libass(work, {name: text for name, (text, _) in cases.items()})
    tracks = {name: (track, "") for name, (_, track) in cases.items()}
    _, theirs = chromium(FFMPEG, work, tracks, AT, SIZE)
    for name in cases:
        print(f"{name}: libass {measure(ours[name])}; Chromium {measure(theirs[name][0])}")


def main() -> None:
    print(ffmpeg(FFMPEG, "-version").decode().splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print("\n## Conversions: ffmpeg's into each target; subverter's and ffman's readings\n")
        for name, (fmt, data, targets) in CASES.items():
            src = work / f"in.{fmt}"
            _ = src.write_text(data, encoding="utf-8")
            print(f"{name} (.{fmt}): {written(fmt, data)!r}")
            for target in targets:
                text, warnings = converted(FFMPEG, src, work / f"out.{target}")
                print(
                    f"    -> {target}: {written(target, text)!r}"
                    + (f" | {warnings}" if warnings else "")
                )
            if fmt != "ass":
                for said in reading(fmt, data):
                    print(f"    {said}")

        print("\n## Positions: the ink's box, as fractions of the frame\n")
        for name, frame in drawn_by_libass(work, ALIGNED).items():
            print(f"libass {name}: {placed(frame)}")
        tracks = {name: (vtt("Placed", settings), "") for name, settings in SETTINGS.items()}
        version, frames = chromium(FFMPEG, work, tracks, AT, SIZE)
        for name, drawn in frames.items():
            print(f"Chromium {name}: {placed(drawn[0])}")

        print(f"\n## Colours: Chromium {version}'s default classes, a STYLE block's\n")
        tracks = {f"<c.{c}>": (vtt(f"<c.{c}>Coloured</c>"), "") for c in COLOURS}
        tracks["<c.x00ff80>, STYLE"] = (
            vtt("<c.x00ff80>Coloured</c>", style="::cue(.x00ff80) { color: #00ff80 }"),
            "",
        )
        _, frames = chromium(FFMPEG, work, tracks, AT, SIZE)
        for name, drawn in frames.items():
            print(f"{name}: {text_colour(drawn[0])}")

        print("\n## Decoration and size: the text's width x height (px), a line across it\n")
        both(work, DECORATED, lines_across)
        print("\n## Spaces: the ink's edges, its width x height (px), its runs\n")
        both(work, SPACES, spaced)


if __name__ == "__main__":
    main()
