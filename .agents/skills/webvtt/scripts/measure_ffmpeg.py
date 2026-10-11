"""WebVTT through ffmpeg, measured: what its `webvtt` demuxer reads of a file, what its `webvtt`
decoder makes of a cue's text (ASS), and what its `webvtt` encoder and muxer write.

Usage: python3 measure_ffmpeg.py [FFMPEG]  (default: ffmpeg on PATH; ffprobe beside it). Prints
what it found; references/format.md's "ffmpeg" tables are this output, at ffmpeg n8.1.2.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FFMPEG = sys.argv[1] if len(sys.argv) > 1 else "ffmpeg"
FFPROBE = str(Path(FFMPEG).with_name("ffprobe")) if "/" in FFMPEG else "ffprobe"
HEAD = "WEBVTT\n\n"
NEXT = "\n\n00:05.000 --> 00:06.000\nnext\n"  # a following cue, to show the reading went on

# the demuxer's reading: a file each
READS: dict[str, str] = {
    "canonical": HEAD + "00:01.000 --> 00:02.500\nHello\nworld\n",
    "hours": HEAD + "01:00:01.000 --> 01:00:02.000\nan hour in\n",
    "minutes 75, no hours": HEAD + "75:00.000 --> 75:01.000\nseventy-five\n",
    "ms one digit (.5)": HEAD + "00:01.5 --> 00:02.25\nshort\n" + NEXT,
    "ms four digits (.5000)": HEAD + "00:01.5000 --> 00:02.0000\nlong\n" + NEXT,
    "comma (00:01,000)": HEAD
    + "00:00.000 --> 00:00.500\nfirst\n\n00:01,000 --> 00:02,000\ncomma"
    + NEXT,
    "identifier": HEAD + "intro-1\n00:01.000 --> 00:02.000\nnamed\n",
    "identifier with -->": HEAD + "a --> b\n00:01.000 --> 00:02.000\narrow id\n" + NEXT,
    "identifier NOTE": HEAD + "NOTE\n00:01.000 --> 00:02.000\nnamed NOTE\n" + NEXT,
    "settings": HEAD + "00:01.000 --> 00:02.000 align:start line:0 position:10%\nplaced\n",
    "NOTE, STYLE, REGION": HEAD + "NOTE a comment\n\nSTYLE\n::cue { color: red }\n\n"
    "REGION\nid:r1 width:40%\n\n00:01.000 --> 00:02.000 region:r1\nafter blocks\n",
    "NOTE between cues": HEAD + "00:01.000 --> 00:02.000\none\n\nNOTE between\n\n"
    "00:03.000 --> 00:04.000\ntwo\n",
    "header text": "WEBVTT - a title\nKind: captions\n\n00:01.000 --> 00:02.000\ntitled\n",
    "no blank line after the header": "WEBVTT\n00:01.000 --> 00:02.000\nglued\n",
    "UTF-8 BOM": "﻿" + HEAD + "00:01.000 --> 00:02.000\nbom\n",
    "CRLF": (HEAD + "00:01.000 --> 00:02.000\nwindows\nline\n").replace("\n", "\r\n"),
    "no blank line between cues": HEAD + "00:01.000 --> 00:02.000\none\n00:03.000 --> 00:04.000\n"
    "two\n",
    "a bad timing line mid-file": HEAD + "00:01.000 --> 00:02.000\none\n\nnot a time --> x\n"
    "lost?\n" + NEXT,
    "a cue without text": HEAD + "00:01.000 --> 00:02.000\n\n00:03.000 --> 00:04.000\nafter\n",
    "zero duration": HEAD + "00:01.000 --> 00:01.000\nzero\n",
    "end before start": HEAD + "00:03.000 --> 00:01.000\nbackwards\n" + NEXT,
    "out of order": HEAD + "00:05.000 --> 00:06.000\nlater\n\n00:01.000 --> 00:02.000\nearlier\n",
    "overlap": HEAD + "00:01.000 --> 00:04.000\nlong\n\n00:02.000 --> 00:03.000\ninside\n",
    "duplicate cue": HEAD + "00:01.000 --> 00:02.000\nsame\n\n00:01.000 --> 00:02.000\nsame\n",
}

# the cases also remuxed (-c copy): the demuxer's packets, their identifiers and settings
REMUXED = {"identifier", "settings", "hours", "end before start", "header text"}

# the decoder's reading: a cue's text each, into ASS
MARKUP: dict[str, str] = {
    "b i u": "<b>b</b> <i>i</i> <u>u</u>",
    "classes on b i u": "<b.loud>b</b> <i.x>i</i>",
    "any tag led by b, i or u": "<bogus>x</bogus> <image>y</image> <underline>z</underline>",
    "c, v, lang": "<c.yellow>c</c> <v Bob>v</v> <lang en>l</lang>",
    "ruby": "<ruby>kanji<rt>reading</rt></ruby>",
    "timestamp tags": "one <00:00:01.500>two <00:00:01.800>three",
    "the six references": "&amp; &lt; &gt; &lrm;&rlm; &nbsp;",
    "other references": "&copy; &#38; &#x26; &bogus;",
    "lone <": "a < b and c > d",
    "an unclosed tag": "before <b ends",
    "braces": "{\\an8}not an override {x}",
    "backslash": "one\\Ntwo \\h",
    "two lines": "one\ntwo",
    "two lines, CRLF": "one\r\ntwo",
    "leading and trailing spaces": "  spaced  ",
}

# the encoder's writing: an ASS event's text each, into WebVTT
ENCODE: dict[str, str] = {
    "b i u s": "{\\b1}b{\\b0} {\\i1}i{\\i0} {\\u1}u{\\u0} {\\s1}s{\\s0}",
    "unclosed b": "{\\b1}bold to the end",
    "colour, font, size": "{\\c&H0000FF&}red {\\fnSerif}serif {\\fs30}big",
    "alignment, position, move": "{\\an8}top {\\pos(10,10)}at {\\move(0,0,9,9)}moving",
    "karaoke": "{\\k50}kar{\\k50}a{\\k50}oke",
    "\\N, \\n, \\h": "hard\\Nbreak soft\\nbreak hard\\hspace",
    "markup-like text": "a <b> c & d < e",
    "reset": "{\\b1}bold{\\r}plain",
    "empty": "",
}

# the muxer's times: an ASS event's start and end each
TIMES = {
    "under an hour": ("0:00:01.23", "0:00:04.56"),
    "an hour": ("1:00:00.00", "1:00:01.00"),
    "100 h": ("100:00:00.00", "100:00:01.00"),
}

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 384
PlayResY: 288

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, \
Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, \
Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,16,&Hffffff,&Hffffff,&H0,&H0,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def event(text: str, start: str = "0:00:01.00", end: str = "0:00:02.00") -> str:
    """An ASS Dialogue line in the Default style."""
    return f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"


def logged(stderr: str) -> str:
    """ffmpeg's messages on one line, without their context's address (``[webvtt @ 0x...]``)."""
    return re.sub(r" @ 0x[0-9a-f]+", "", stderr.strip()).replace("\n", "; ")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def unhex(dump: str) -> bytes:
    """ffprobe's -show_data hexdump, back to bytes (each line: an offset, 16 bytes in hex)."""
    return b"".join(
        bytes.fromhex(line[10:50].replace(" ", "")) for line in dump.strip("\n").split("\n")
    )


def converted(out: Path, *args: str) -> tuple[str, str]:
    """ffmpeg run on ``args``, writing ``out``: the file written (or why none was), its warnings."""
    _ = out.unlink(missing_ok=True)
    r = run(FFMPEG, "-v", "warning", "-y", *args, str(out))
    if r.returncode or not out.exists():
        return f"[failed: {logged(r.stderr)}]", ""
    return out.read_text(encoding="utf-8", errors="backslashreplace"), logged(r.stderr)


def shown(text: object, warnings: str) -> str:
    """A result and, when there are any, its warnings."""
    return f"{text!r}" + (f" | {warnings}" if warnings else "")


def packets(path: Path) -> tuple[str, list[tuple[int, int, str]]]:
    """The format ffprobe detects and each packet: start and duration (ms), text."""
    probe = run(FFPROBE, "-v", "error", "-i", str(path), "-show_packets", "-show_data",
                "-show_entries", "format=format_name", "-of", "json")  # fmt: skip
    if probe.returncode:  # the message without the file's path
        return probe.stderr.strip().splitlines()[-1].rsplit(": ", 1)[-1], []
    data = json.loads(probe.stdout)
    found = [
        (
            int(p["pts"]),
            int(p.get("duration", 0)),
            unhex(p["data"]).decode("utf-8", "backslashreplace") if "data" in p else "",
        )
        for p in data.get("packets", [])
    ]
    return data["format"]["format_name"], found


def dialogue(ass: str) -> list[str]:
    """An ASS file's events' text (after the ninth comma of each Dialogue line)."""
    return [line.split(",", 9)[9] for line in ass.splitlines() if line.startswith("Dialogue:")]


def main() -> None:
    print(run(FFMPEG, "-version").stdout.splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        vtt, ass, out_vtt, out_ass = (work / n for n in ("in.vtt", "in.ass", "out.vtt", "out.ass"))

        print("\n## The demuxer: start ms, duration ms, text (and the -c copy remux)\n")
        for name, text in READS.items():
            _ = vtt.write_bytes(text.encode("utf-8"))
            fmt, found = packets(vtt)
            print(f"{name}: [{fmt}] {found!r}")
            if name in REMUXED:
                print("    remux: " + shown(*converted(out_vtt, "-i", str(vtt), "-c", "copy")))

        print("\n## The decoder: cue text -> ASS event text\n")
        for name, text in MARKUP.items():
            _ = vtt.write_text(f"{HEAD}00:01.000 --> 00:02.000\n{text}\n", encoding="utf-8")
            script, warnings = converted(out_ass, "-i", str(vtt))
            print(f"{name}: {text!r} -> " + shown(dialogue(script), warnings))
        _ = vtt.write_text(f"{HEAD}id\n00:01.000 --> 00:02.000 line:0 align:start\nset\n",
                           encoding="utf-8")  # fmt: skip
        script, warnings = converted(out_ass, "-i", str(vtt))
        print("identifier and settings: " + shown(dialogue(script), warnings))
        _ = vtt.write_text(f"{HEAD}00:01.000 --> 00:02.000\n\n00:03.000 --> 00:04.000\nnext\n",
                           encoding="utf-8")  # fmt: skip
        emptied, warnings = converted(out_ass, "-i", str(vtt))
        print("a cue of empty text, then one: " + shown(dialogue(emptied), warnings))
        head = script.split("[Events]")[0].strip().splitlines()
        print("the decoder's ASS header:\n    " + "\n    ".join(head))

        print("\n## The encoder and muxer: ASS event -> WebVTT\n")

        def webvtt(events: str, *, head: str = ASS_HEAD) -> str:
            _ = ass.write_text(head + events, encoding="utf-8")
            return shown(*converted(out_vtt, "-i", str(ass)))

        for name, text in ENCODE.items():
            print(f"{name}: {text!r} -> " + webvtt(event(text)))
            if name == "markup-like text":  # read back by the decoder
                script, warnings = converted(out_ass, "-i", str(out_vtt))
                print("    read back: " + shown(dialogue(script), warnings))
        styled = ASS_HEAD.replace(
            "Style: Default,Arial,16,&Hffffff,&Hffffff,&H0,&H0,0,0,0,0",
            "Style: Default,Serif,24,&H0000ff,&Hffffff,&H0,&H0,-1,-1,-1,-1",
        ).replace(",1,1,0,2,10,10,10,0", ",1,1,0,8,10,10,10,0")
        print("a style (Serif 24, red, bold, italic, underline, strike, top): "
              + webvtt(event("styled"), head=styled))  # fmt: skip
        for name, (start, end) in TIMES.items():
            print(f"times {name}: " + webvtt(event("t", start, end)))
        overlapping = event("first", end="0:00:03.00") + event("second", "0:00:02.00", "0:00:04.00")
        print("overlapping events: " + webvtt(overlapping))
        written = out_vtt.read_bytes()
        crlf, bom = b"\r\n" in written, written.startswith(b"\xef\xbb\xbf")
        print(f"bytes: line ends {'CRLF' if crlf else 'LF'}, BOM {bom}")


if __name__ == "__main__":
    main()
