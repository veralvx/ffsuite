"""WebVTT through ffmpeg, measured: what its `webvtt` demuxer reads of a file, what its `webvtt`
decoder makes of a cue's text (ASS), and what its `webvtt` encoder and muxer write; with PYTHON,
what ffman reads of the same files; then the skill checked from its own text -- its example's
readings and the prose stating them, its time rule, its commands -- exiting 1 on a difference.

Usage: python3 measure_ffmpeg.py [FFMPEG [PYTHON]]  (default: ffmpeg on PATH; ffprobe beside it;
PYTHON an interpreter that imports subverter and ffman). Prints what it found;
references/format.md's "ffmpeg" tables are this output, at ffmpeg n8.1.2.
"""

import json
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

FFMPEG = sys.argv[1] if len(sys.argv) > 1 else "ffmpeg"
FFPROBE = str(Path(FFMPEG).with_name("ffprobe")) if "/" in FFMPEG else "ffprobe"
PYTHON = sys.argv[2] if len(sys.argv) > 2 else None
SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"
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
    "no spaces round -->": HEAD + "00:01.000-->00:02.000\nglued\n" + NEXT,
    "tabs round -->": HEAD + "00:01.000\t-->\t00:02.000\ntabs\n" + NEXT,
    "an empty line in a cue": HEAD + "00:01.000 --> 00:02.000\none\n\ntwo\n" + NEXT,
    "a line of spaces in a cue": HEAD + "00:01.000 --> 00:02.000\none\n   \ntwo\n" + NEXT,
    "a text line holding -->": HEAD + "00:01.000 --> 00:02.000\none\nNote: 1 --> 2\ntwo\n" + NEXT,
    "a NUL in a cue": HEAD + "00:01.000 --> 00:02.000\na\x00b\n" + NEXT,
    "CR only": (HEAD + "00:01.000 --> 00:02.000\nmac\n" + NEXT).replace("\n", "\r"),
    "CR CR LF": (HEAD + "00:01.000 --> 00:02.000\nx\n" + NEXT).replace("\n", "\r\r\n"),
    "no signature (by its name)": "00:01.000 --> 00:02.000\nnone\n" + NEXT,
    "webvtt, lower-cased": "webvtt\n\n00:01.000 --> 00:02.000\nlow\n" + NEXT,
}

# the demuxer's reading of bytes not UTF-8
BYTES: dict[str, bytes] = {
    "Latin-1 \u00e9": (HEAD + "00:01.000 --> 00:02.000\ncaf").encode() + b"\xe9" + NEXT.encode(),
    "UTF-16LE, its BOM": ("\ufeff" + HEAD + "00:01.000 --> 00:02.000\ncaf\u00e9\n").encode(
        "utf-16-le"
    ),
}

# the cases also remuxed (-c copy): the demuxer's packets, their identifiers and settings
REMUXED = {"identifier", "settings", "hours", "end before start", "header text"}
# the cases also decoded into ASS: what the decoder keeps of what the demuxer read
DECODED = {"a NUL in a cue", "CR CR LF", "Latin-1 \u00e9", "UTF-16LE, its BOM"}

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
        for name, data in {**{k: v.encode() for k, v in READS.items()}, **BYTES}.items():
            _ = vtt.write_bytes(data)
            fmt, found = packets(vtt)
            print(f"{name}: [{fmt}] {found!r}")
            if name in REMUXED:
                print("    remux: " + shown(*converted(out_vtt, "-i", str(vtt), "-c", "copy")))
            if name in DECODED:
                script, warnings = converted(out_ass, "-i", str(vtt))
                print("    decoded: " + shown(dialogue(script) or script[:60], warnings))

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

        ffman()

        print("\n## The skill, from its own text\n")
        if not skill(work):
            sys.exit("the skill and its measurement disagree")


# ffman's reading of each file, in PYTHON: subverter's cues through ffman's ingest -- the chunks
# its burn draws and --add-subs writes -- and its notes, or its refusal
FFMAN_PROBE = """
import json, sys
from ffman.errors import REFUSALS
from ffman.subs.ingest import ingest
for name, text in json.load(sys.stdin).items():
    try:
        t = ingest("in.vtt", text.encode("latin-1"))
    except REFUSALS as refused:
        print(f"{name}: refused: {refused}")
    else:
        print(f"{name}: {[(c.start, c.end, c.text) for c in t.chunks]!r} {list(t.notes)!r}")
"""


def ffman() -> None:
    """READS, BYTES and the MARKUP texts through ffman's ingest, in PYTHON."""
    if not PYTHON:
        return
    print("\n## ffman: the chunks its burn draws, its notes or refusal\n")
    files = {k: v.encode() for k, v in READS.items()} | BYTES
    files |= {k: f"{HEAD}00:01.000 --> 00:02.000\n{v}\n".encode() for k, v in MARKUP.items()}
    cases = json.dumps({n: d.decode("latin-1") for n, d in files.items()})
    r = subprocess.run([PYTHON, "-c", FFMAN_PROBE], input=cases,
                       capture_output=True, text=True, check=True)  # fmt: skip
    print(r.stdout, end="")


def fenced(text: str, lang: str) -> list[str]:
    """The skill's code blocks in ``lang``, as written (a list item's indentation off)."""
    found = re.finditer(rf"^( *)```{lang}\n(.*?)^\1```$", text, re.MULTILINE | re.DOTALL)
    return [textwrap.dedent(m[2]) for m in found]


# what the skill states of its example and commands (SKILL.md, "Example" and "Converting")
EXAMPLE_FFMPEG = [
    (1000, 2500, "<i>Previously:</i> the road\nnorth, at night"),
    (4000, 2250, "<v Ana><c.yellow>CLOSED</c></v>"),
    (62005, 1995, "Fish &amp; chips &lt; 2 \u20ac"),
]
EXAMPLE_ASS = [
    "{\\i1}Previously:{\\i0} the road\\Nnorth, at night",
    "CLOSED",
    "Fish & chips < 2 \u20ac",
]
EXAMPLE_FFMAN = [
    [1000, 3500, "Previously: the road north, at night"],
    [4000, 6250, "CLOSED"],
    [62005, 64000, "Fish & chips < 2 \u20ac"],
]
ROUND_TRIP = "Fish & chips < 2 \u20ac"  # the third cue, into SubRip and back: unescaped
ASS_TIMES = ["0:01:02.01", "0:01:04.01"]  # the third cue written as ASS: centiseconds
STREAMS = {  # each command's output: its streams (the inputs' audio kept)
    "out.srt": ["subrip,subtitle"],
    "out.vtt": ["webvtt,subtitle"],
    "out.mp4": ["mpeg4,video", "aac,audio", "mov_text,subtitle"],
    "out.webm": ["vp9,video", "opus,audio", "webvtt,subtitle"],
    "out.mkv": ["mpeg4,video", "aac,audio", "webvtt,subtitle"],
    "out-burn.mp4": ["h264,video", "aac,audio"],  # the build's default encoder: libx264
}
KEPT = ("intro", "align:start", "line:0")  # what a stream copy keeps: the identifier, settings


def checked(what: str, found: object, stated: object) -> bool:
    """One of the skill's claims against its measurement, printed either way."""
    print(f"{'ok' if found == stated else 'MISMATCH'}: {what}: {found!r}")
    if found != stated:
        print(f"    stated: {stated!r}")
    return found == stated


def ffman_chunks(data: bytes) -> list[list[int | str]]:
    """ffman's chunks of a WebVTT file, in PYTHON: what it burns."""
    read = (
        "import json, sys; from ffman.errors import REFUSALS; from ffman.subs.ingest import ingest\n"
        "try: t = ingest('in.vtt', sys.stdin.buffer.read())\n"
        "except REFUSALS: print('[]')\n"  # no cue: an empty list, the check failing on it
        "else: print(json.dumps([(c.start, c.end, c.text) for c in t.chunks]))"
    )
    r = subprocess.run([PYTHON or "", "-c", read], input=data, capture_output=True, check=True)
    return json.loads(r.stdout)


def skill(work: Path) -> bool:
    """The skill's example read and its prose on it, its time rule, its commands run."""
    text = SKILL.read_text(encoding="utf-8")
    example = fenced(text, "vtt")[0]
    _ = (work / "in.vtt").write_text(example, encoding="utf-8")
    results = [checked("the example, ffmpeg", packets(work / "in.vtt")[1], EXAMPLE_FFMPEG)]
    script, _w = converted(work / "example.ass", "-i", str(work / "in.vtt"))
    results.append(checked("    its ASS", dialogue(script), EXAMPLE_ASS))
    third = [line.split(",")[1:3] for line in script.splitlines() if line.startswith("Dialogue:")]
    results.append(checked("    its third cue's ASS times", third[2], ASS_TIMES))
    if PYTHON:
        results.append(checked("    ffman", ffman_chunks(example.encode()), EXAMPLE_FFMAN))

    space: dict[str, object] = {}
    exec(fenced(text, "python")[0], space)  # noqa: S102 -- the skill's own rule, run as written
    vtt_time = space["vtt_time"]
    if not callable(vtt_time):
        raise TypeError(vtt_time)
    edges = [0, 1, 999, 1000, 59999, 60000, 3599999, 3600000, 359999999, 360000000]
    times = sorted({*edges, *range(0, 7200000, 997)})
    rule = HEAD + "".join(f"{vtt_time(t)} --> {vtt_time(t + 1)}\nt\n\n" for t in times)
    _ = (work / "rule.vtt").write_text(rule, encoding="utf-8")
    read = [start for start, _d, _t in packets(work / "rule.vtt")[1]]
    what = f"the time rule: {len(times)} times to 2 h and the edges to 100 h, read by ffmpeg"
    results.append(checked(what, found=read == times, stated=True))
    if PYTHON:
        starts = [chunk[0] for chunk in ffman_chunks(rule.encode())]
        results.append(checked("    and by ffman", found=starts == times, stated=True))

    for video, codecs in (("video.mp4", ("mpeg4", "aac")), ("video.mkv", ("mpeg4", "aac")),
                          ("video.webm", ("libvpx-vp9", "libopus"))):  # fmt: skip
        _ = run(FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:d=70",
                "-f", "lavfi", "-i", "sine=d=70", "-c:v", codecs[0], "-c:a", codecs[1],
                str(work / video))  # fmt: skip
    for line in fenced(text, "sh")[0].splitlines():
        args = shlex.split(line, comments=True)
        if args[-1] == "out.vtt":  # its input, the SubRip the line before wrote
            _ = (work / "in.srt").write_bytes((work / "out.srt").read_bytes())
        r = subprocess.run([FFMPEG, "-v", "error", "-y", *args[1:]], cwd=work,
                           capture_output=True, text=True, check=False)  # fmt: skip
        probe = run(FFPROBE, "-v", "error", "-show_entries", "stream=codec_name,codec_type",
                    "-of", "csv=p=0", str(work / args[-1]))  # fmt: skip
        found = probe.stdout.split() if r.returncode == 0 else r.stderr.strip()
        results.append(checked(" ".join(args), found, STREAMS[args[-1]]))
        if args[-1] in ("out.webm", "out.mkv"):  # the WebVTT track, copied back out
            back = run(FFMPEG, "-v", "error", "-i", str(work / args[-1]), "-map", "0:s",
                       "-c", "copy", "-f", "webvtt", "-").stdout  # fmt: skip
            kept = all(x in back for x in KEPT)
            results.append(checked("    its identifier and settings kept", kept, stated=True))
    third = (work / "out.vtt").read_text(encoding="utf-8").rstrip("\n").split("\n")[-1]
    results.append(checked("    the third cue, into SubRip and back", third, ROUND_TRIP))
    results.append(checked("missing from the prose", stated(text), []))
    return all(results)


def stated(text: str) -> list[str]:
    """What the skill's prose must say of its example, from the measured values: those missing."""
    prose = " ".join(text.split())
    said = [f"{a / 1000:g} s for {d / 1000:g} s" for a, d, _ in EXAMPLE_FFMPEG]
    said += [f"`{t}`" for t in EXAMPLE_ASS] + [f"`{EXAMPLE_FFMAN[0][2]}`", f"`{ROUND_TRIP}`"]
    start, length, _ = EXAMPLE_FFMPEG[2]
    cs = [int(t[-5:-3]) + int(t[-2:]) / 100 + 60 * int(t[-8:-6]) for t in ASS_TIMES]
    said.append(f"{start / 1000:.3f}-{(start + length) / 1000:.3f} s became "
                f"{cs[0]:.2f}-{cs[1]:.2f} s")  # fmt: skip
    whole = r"(?<![\w.]){}(?![\w]|\.\d)"  # no digit nor word glued to it
    return [x for x in said if not re.search(whole.format(re.escape(x)), prose)]


if __name__ == "__main__":
    main()
