"""SubRip, measured: what ffmpeg's `srt` demuxer reads of a file, what its `subrip` decoder makes
of the text (ASS), and what its `subrip` encoder and `srt` muxer write; what ffman reads and
burns of the same; then the skill checked from its own text -- its example, its time rule and
its commands, a mismatch failing the run.

Usage: python3 measure.py [FFMPEG [PYTHON]]  (default: ffmpeg on PATH, ffprobe beside it;
PYTHON an interpreter that imports subverter and ffman, for their readings). Prints what it
found; references/format.md's tables are this output, at ffmpeg n8.1.2.
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
PYTHON = sys.argv[2] if len(sys.argv) > 2 else None  # noqa: PLR2004 -- FFMPEG, then PYTHON
SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
FFPROBE = str(Path(FFMPEG).with_name("ffprobe")) if "/" in FFMPEG else "ffprobe"
CUE2 = b"\n\n2\n00:00:05,000 --> 00:00:06,000\nnext\n"  # a following cue, to end the one before

# the demuxer's reading: a file's bytes each
READS: dict[str, bytes] = {
    "canonical": b"1\n00:00:01,000 --> 00:00:02,500\nHello\nworld\n",
    "period": b"1\n00:00:01.000 --> 00:00:02.500\nperiod\n",
    "ms one digit (,5)": b"1\n00:00:01,5 --> 00:00:02,25\nshort\n",
    "ms four digits (,5000)": b"1\n00:00:01,5000 --> 00:00:02,0000\nlong\n",
    "no hours": b"1\n00:01,000 --> 00:02,000\nno hours\n",
    "hours 100": b"1\n100:00:00,000 --> 100:00:01,000\nhundred\n",
    "minutes 75": b"1\n00:75:00,000 --> 00:75:01,000\nseventy-five\n",
    "negative start": b"1\n-00:00:01,000 --> 00:00:02,000\nminus zero hours\n",
    "negative hour": b"1\n-01:00:00,000 --> 00:00:02,000\nminus one hour\n",
    "no spaces round -->": b"1\n00:00:01,000-->00:00:02,000\nno spaces\n",
    "no spaces, -f srt": b"1\n00:00:01,000-->00:00:02,000\nno spaces\n",
    "coordinates": b"1\n00:00:01,000 --> 00:00:02,000  X1:100 X2:300 Y1:400 Y2:450\nplaced\n",
    "trailing text on timing": b"1\n00:00:01,000 --> 00:00:02,000 garbage\nafter\n",
    "blank line in text": b"1\n00:00:01,000 --> 00:00:02,000\nfirst\n\nsecond\n" + CUE2,
    "no number line": b"00:00:01,000 --> 00:00:02,000\nno number\n" + CUE2,
    "text ends with a number line": b"1\n00:00:01,000 --> 00:00:02,000\nthe year\n2024\n" + CUE2,
    "text line '3 apples' last": b"1\n00:00:01,000 --> 00:00:02,000\nbuy\n3 apples\n" + CUE2,
    "text line '3 apples' alone": b"1\n00:00:01,000 --> 00:00:02,000\n3 apples\n" + CUE2,
    "a number-led last line, next cue unnumbered": b"1\n00:00:01,000 --> 00:00:02,000\nbuy\n3 apples\n\n00:00:05,000 --> 00:00:06,000\nnext\n",
    "a number last line, next cue unnumbered": b"1\n00:00:01,000 --> 00:00:02,000\nthe year\n2024\n\n00:00:05,000 --> 00:00:06,000\nnext\n",
    "'3 apples' alone, next cue unnumbered": b"1\n00:00:01,000 --> 00:00:02,000\n3 apples\n\n00:00:05,000 --> 00:00:06,000\nnext\n",
    "'2024' alone, next cue unnumbered": b"1\n00:00:01,000 --> 00:00:02,000\n2024\n\n00:00:05,000 --> 00:00:06,000\nnext\n",
    "last cue ends with a number": b"1\n00:00:01,000 --> 00:00:02,000\nthe year\n2024\n",
    "end before start": b"1\n00:00:03,000 --> 00:00:01,000\nbackwards\n" + CUE2,
    "out of order": b"1\n00:00:05,000 --> 00:00:06,000\nlater\n\n2\n00:00:01,000 --> 00:00:02,000\nearlier\n",
    "duplicate cue": b"1\n00:00:01,000 --> 00:00:02,000\nsame\n\n2\n00:00:01,000 --> 00:00:02,000\nsame\n",
    "overlap": b"1\n00:00:01,000 --> 00:00:04,000\nlong\n\n2\n00:00:02,000 --> 00:00:03,000\ninside\n",
    "empty cue": b"1\n00:00:01,000 --> 00:00:02,000\n" + CUE2,
    "zero duration": b"1\n00:00:01,000 --> 00:00:01,000\nzero\n",
    "CRLF": b"1\r\n00:00:01,000 --> 00:00:02,000\r\nwindows\r\nline\r\n",
    "CR only": b"1\r00:00:01,000 --> 00:00:02,000\rmac\rline\r",
    "UTF-8 BOM": b"\xef\xbb\xbf1\n00:00:01,000 --> 00:00:02,000\nbom\n",
    "UTF-16LE BOM": "\ufeff1\n00:00:01,000 --> 00:00:02,000\nsixteen é\n".encode("utf-16-le"),
    "Latin-1 byte": b"1\n00:00:01,000 --> 00:00:02,000\ncaf\xe9\n",
    "NUL in the second cue": b"1\n00:00:00,000 --> 00:00:00,500\nfirst\n\n2\n00:00:01,000 --> 00:00:02,000\nbefore\x00after\n"
    + CUE2.replace(b"2\n", b"3\n", 1),
    "line of 5000 bytes": b"1\n00:00:01,000 --> 00:00:02,000\n" + b"x" * 5000 + b"\n",
    "spaces around lines": b"1\n00:00:01,000 --> 00:00:02,000\n  lead and trail  \n",
    "leading blank lines": b"\n\n\n1\n00:00:01,000 --> 00:00:02,000\nlate start\n",
    "no final newline": b"1\n00:00:01,000 --> 00:00:02,000\nunterminated",
}
FORCED = {"no spaces, -f srt"}  # read with -f srt: the probe needs " --> "

# the decoder's reading: a cue's text each, into ASS
MARKUP: dict[str, str] = {
    "b i u s": "<b>b</b> <i>i</i> <u>u</u> <s>s</s>",
    "upper case tags": "<B>bold</B> <I>it</I>",
    "font color name": '<font color="red">red</font>',
    "font color hex": '<font color="#00ff80">green</font>',
    "font size face": '<font size="30" face="Serif">big</font>',
    "nested font": '<font color="red">r <font size="40">R</font> r</font>',
    "br": "one<br>two<br/>three",
    "an8": "{\\an8}top",
    "an8 mid-text": "top? {\\an8}here",
    "other override": "{\\b1}bold?{\\pos(10,10)} {\\fad(1,2)}",
    "microdvd style": "{y:i}italic?",
    "unknown tag": "<v Bob>speaker</v> <c.yellow>class</c>",
    "unclosed tag": "<b>open",
    "lone <": "a < b and c > d",
    "< then > later": "x<3 and y>2",
    "< and no >": "heart <3",
    "full-width <": "a \uff1c b",
    "guillemets <<": "<<quote>>",
    "entity": "A &amp; B &lt; C",
    "literal \\N": "one\\Ntwo",
    "literal \\h": "hard\\hspace",
    "two lines": "one\ntwo",
    "a line of spaces": "first\n   \nsecond",
    "brace text": "{not an override}",
}

# the encoder's writing: an ASS event's text each, into SubRip
ENCODE: dict[str, str] = {
    "bold italic": "{\\b1}b{\\b0} {\\i1}i{\\i0} {\\u1}u{\\u0} {\\s1}s{\\s0}",
    "colour": "{\\c&H0000FF&}red{\\c} plain",
    "secondary colour": "{\\2c&H0000FF&}karaoke colour",
    "font name size": "{\\fnSerif\\fs30}big",
    "alignment an8": "{\\an8}top",
    "legacy \\a6": "{\\a6}top centre",
    "position": "{\\pos(100,200)}placed",
    "move": "{\\move(0,0,100,100)}moving",
    "karaoke": "{\\k50}kar{\\k50}a{\\k50}oke",
    "fade": "{\\fad(200,200)}faded",
    "\\N and \\n": "hard\\Nbreak soft\\nbreak",
    "\\h": "hard\\hspace",
    "unclosed {": "{\\b1 broken",
    "plain braces": "{text in braces}",
    "reset": "{\\b1}bold{\\r}plain",
    "markup-like text": "a <b> c & d",
}

# ffman's reading (subverter's cues) and burn (its chunks, as its ASS draws them): a file each
FFMAN: dict[str, bytes] = {
    "short fraction": READS["ms one digit (,5)"],
    "blank line in text": READS["blank line in text"],
    "line of spaces": b"1\n00:00:01,000 --> 00:00:02,000\nfirst\n   \nsecond\n" + CUE2,
    "number last, next cue unnumbered": READS["a number last line, next cue unnumbered"],
    "number last, no blank line, next cue unnumbered": b"1\n00:00:01,000 --> 00:00:02,000\n"
    b"the year\n2024\n00:00:05,000 --> 00:00:06,000\nnext\n",
    "no blank line before the next index": b"1\n00:00:01,000 --> 00:00:02,000\nfirst\n2\n"
    b"00:00:03,000 --> 00:00:04,000\nsecond\n",
    "a --> line": b"1\n00:00:01,000 --> 00:00:02,000\na --> b\nc\n",
    "end before start": READS["end before start"],
    "zero duration": READS["zero duration"],
    "out of order": READS["out of order"],
    "duplicate cue": READS["duplicate cue"],
    "tags": b'1\n00:00:01,000 --> 00:00:02,000\n<b>b</b> <font color="red">r</font> <v Bob>v</v>\n',
    "< then > later": b"1\n00:00:01,000 --> 00:00:02,000\nx<3 and y>2\n",
    "lone <": b"1\n00:00:01,000 --> 00:00:02,000\na < b and c > d\n",
    "< and no >": b"1\n00:00:01,000 --> 00:00:02,000\nheart <3\n",
    "an8": b"1\n00:00:01,000 --> 00:00:02,000\n{\\an8}top\n",
    "typed \\N \\n \\h": b"1\n00:00:01,000 --> 00:00:02,000\none\\Ntwo a\\nb hard\\hspace\n",
    "braces, backslashes": b"1\n00:00:01,000 --> 00:00:02,000\na {b} c\\x \\{d\\}\n",
    "entity": b"1\n00:00:01,000 --> 00:00:02,000\nA &amp; B\n",
    "spaces around lines": READS["spaces around lines"],
    "Latin-1 byte": READS["Latin-1 byte"],
    "CRLF": READS["CRLF"],
    "CR only": READS["CR only"],
    "UTF-8 BOM": READS["UTF-8 BOM"],
    "UTF-16LE BOM": READS["UTF-16LE BOM"],
}
FFMAN_PROBE = """
import json, sys
import subverter
from ffman.subs.ingest import ingest
for name, text in json.load(sys.stdin).items():
    data = text.encode("latin-1")
    try:
        cues = [(c.start, c.end, c.text) for c in subverter.read("srt", data, "x.srt").cues]
    except Exception as e:
        cues = f"refused: {e}"
    try:
        chunks = [(c.start, c.end, c.text) for c in ingest("x.srt", data).chunks]
    except Exception as e:
        chunks = f"refused: {e}"
    print(f"{name}: subverter {cues!r}; ffman burns {chunks!r}")
"""

# the cases also remuxed: through the demuxer and the muxer alone (-c copy)
REMUXED = {"coordinates", "hours 100", "negative hour", "end before start",
           "ms four digits (,5000)", "zero duration"}  # fmt: skip

# the muxer: times, from an ASS event each (start, end as ASS writes them)
TIMES = {
    "100 h": ("100:00:00.00", "100:00:01.00"),
    "centiseconds": ("0:00:01.23", "0:00:04.56"),
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
    """ffmpeg's messages on one line, without their context's address (``[srt @ 0x...]``)."""
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


def packets(path: Path, *, forced: bool) -> tuple[str, list[tuple[int, int, str]]]:
    """The format ffprobe detects and each packet: start and duration (ms), text."""
    fmt = ["-f", "srt"] if forced else []
    probe = run(FFPROBE, "-v", "error", *fmt, "-i", str(path), "-show_packets", "-show_data",
                "-show_entries", "format=format_name", "-of", "json")  # fmt: skip
    if probe.returncode:  # the message without the file's path
        return probe.stderr.strip().splitlines()[-1].rsplit(": ", 1)[-1], []
    data = json.loads(probe.stdout)
    found = [
        (
            int(p["pts"]),
            int(p.get("duration", 0)),
            unhex(p["data"]).decode("utf-8", "backslashreplace"),
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
        srt, ass, out_srt, out_ass = (work / n for n in ("in.srt", "in.ass", "out.srt", "out.ass"))

        print("\n## The demuxer: start ms, duration ms, text (and the -c copy remux)\n")
        for name, data in READS.items():
            _ = srt.write_bytes(data)
            fmt, found = packets(srt, forced=name in FORCED)
            if name == "line of 5000 bytes":  # its lines' lengths, not its text
                lengths = [(s, d, [len(line) for line in text.split("\n")]) for s, d, text in found]
                print(f"{name}: [{fmt}] {lengths!r}")
            else:
                print(f"{name}: [{fmt}] {found!r}")
            if name in REMUXED:
                print("    remux: " + shown(*converted(out_srt, "-i", str(srt), "-c", "copy")))

        print("\n## The decoder: cue text -> ASS event text\n")
        for name, text in MARKUP.items():
            _ = srt.write_text(f"1\n00:00:01,000 --> 00:00:02,000\n{text}\n", encoding="utf-8")
            script, warnings = converted(out_ass, "-i", str(srt))
            print(f"{name}: {text!r} -> " + shown(dialogue(script), warnings))
        for name, box in (("box", "X1:100 X2:300 Y1:400 Y2:450"),
                          ("corner", "X1:100 X2:100 Y1:400 Y2:400")):  # fmt: skip
            _ = srt.write_text(f"1\n00:00:01,000 --> 00:00:02,000  {box}\np\n", encoding="utf-8")
            script, warnings = converted(out_ass, "-i", str(srt))
            print(f"coordinates ({name}): " + shown(dialogue(script), warnings))
        head = script.split("[Events]")[0].strip().splitlines()
        _ = srt.write_bytes(READS["Latin-1 byte"] + CUE2)
        latin, warnings = converted(out_ass, "-i", str(srt))
        print("not UTF-8 (caf\\xe9, then ok): " + shown(dialogue(latin), warnings))
        print("the decoder's ASS header:\n    " + "\n    ".join(head))

        print("\n## The encoder and muxer: ASS event -> SubRip\n")

        def subrip(events: str, *, head: str = ASS_HEAD, codec: str = "subrip") -> str:
            _ = ass.write_text(head + events, encoding="utf-8")
            return shown(*converted(out_srt, "-i", str(ass), "-c:s", codec))

        for name, text in ENCODE.items():
            print(f"{name}: {text!r} -> " + subrip(event(text)))
        styled = ASS_HEAD.replace(
            "Style: Default,Arial,16,&Hffffff,&Hffffff,&H0,&H0,0,0,0,0",
            "Style: Default,Serif,24,&H0000ff,&Hffffff,&H0,&H0,-1,-1,-1,0",
        ).replace(",1,1,0,2,10,10,10,0", ",1,1,0,8,10,10,10,0")
        print("a style (Serif 24, red, bold, italic, underline, top): "
              + subrip(event("styled"), head=styled))  # fmt: skip
        for name, (start, end) in TIMES.items():
            print(f"times {name}: " + subrip(event("t", start, end)))
        overlapping = event("first", end="0:00:03.00") + event("second", "0:00:02.00", "0:00:04.00")
        print("overlapping events: " + subrip(overlapping))
        written = out_srt.read_bytes()
        crlf, bom = b"\r\n" in written, written.startswith(b"\xef\xbb\xbf")
        print(f"bytes: line ends {'CRLF' if crlf else 'LF'}, BOM {bom}")
        print("-c:s text (no markup): " + subrip(event("{\\b1}b{\\b0} \\Nx"), codec="text"))

        ffman()

        print("\n## The skill, from its own text\n")
        if not skill(work):
            sys.exit("the skill and its measurement disagree")


def ffman() -> None:
    """Each FFMAN file through subverter and ffman's ingest, in PYTHON."""
    if not PYTHON:
        return
    print("\n## ffman: subverter's cues, and the chunks its burn draws\n")
    cases = json.dumps({n: d.decode("latin-1") for n, d in FFMAN.items()})
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
    (4000, 2250, '{\\an8}<font color="#ffff00">CLOSED</font>'),
    (62005, 1995, "Fish & chips, 1,99 €"),
]
EXAMPLE_ASS = [
    "{\\i1}Previously:{\\i0} the road\\Nnorth, at night",
    "{\\an8}{\\c&HFFFF&}CLOSED{\\c}",
    "Fish & chips, 1,99 €",
]
EXAMPLE_SUBVERTER = [
    [1000, 3500, "<i>Previously:</i> the road north, at night"],
    [4000, 6250, '{\\an8}<font color="#ffff00">CLOSED</font>'],
    [62005, 64000, "Fish & chips, 1,99 €"],
]
ROUND_TRIP = "00:01:02,010 --> 00:01:04,010"  # the third cue, through ASS and back
STREAMS = {  # each command's output: its streams (the inputs' audio kept)
    "out.ass": ["ass,subtitle"],
    "out.srt": ["subrip,subtitle"],
    "out.mp4": ["mpeg4,video", "aac,audio", "mov_text,subtitle"],
    "out.mkv": ["mpeg4,video", "aac,audio", "subrip,subtitle"],
    "out-burn.mp4": ["h264,video", "aac,audio"],  # the build's default encoder: libx264
}


def checked(what: str, found: object, stated: object) -> bool:
    """One of the skill's claims against its measurement, printed either way."""
    print(f"{'ok' if found == stated else 'MISMATCH'}: {what}: {found!r}")
    if found != stated:
        print(f"    stated: {stated!r}")
    return found == stated


def skill(work: Path) -> bool:
    """The skill's example read and its prose on it, its time rule, its commands run."""
    text = SKILL.read_text(encoding="utf-8")
    example = fenced(text, "srt")[0]
    _ = (work / "in.srt").write_text(example, encoding="utf-8")
    results = [
        checked("the example, ffmpeg", packets(work / "in.srt", forced=False)[1], EXAMPLE_FFMPEG)
    ]
    script, _w = converted(work / "example.ass", "-i", str(work / "in.srt"))
    results.append(checked("    its ASS", dialogue(script), EXAMPLE_ASS))
    if PYTHON:
        read = (
            "import json, subverter, sys; r = subverter.read('srt', sys.stdin.buffer.read(), 'x'); "
            "print(json.dumps([(c.start, c.end, c.text) for c in r.cues]))"
        )
        r = subprocess.run([PYTHON, "-c", read], input=example.encode(), capture_output=True,
                           check=True)  # fmt: skip
        results.append(checked("    subverter", json.loads(r.stdout), EXAMPLE_SUBVERTER))

    space: dict[str, object] = {}
    exec(fenced(text, "python")[0], space)  # noqa: S102 -- the skill's own rule, run as written
    srt_time = space["srt_time"]
    if not callable(srt_time):
        raise TypeError(srt_time)
    edges = [0, 1, 999, 1000, 59999, 60000, 3599999, 3600000, 359999999, 360000000]
    times = sorted({*edges, *range(0, 7200000, 997)})
    rule = "".join(
        f"{i}\n{srt_time(t)} --> {srt_time(t + 1)}\nt\n\n" for i, t in enumerate(times, 1)
    )
    _ = (work / "rule.srt").write_text(rule, encoding="utf-8")
    written, _w = converted(work / "rule-out.srt", "-i", str(work / "rule.srt"), "-c", "copy")
    what = f"the time rule: {len(times)} times to 2 h and the edges to 100 h, as ffmpeg's muxer"
    results.append(checked(what, found=written == rule, stated=True))

    for video in ("video.mp4", "video.mkv"):
        _ = run(FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:d=70",
                "-f", "lavfi", "-i", "sine=d=70", "-c:v", "mpeg4", "-c:a", "aac",
                str(work / video))  # fmt: skip
    for line in fenced(text, "sh")[0].splitlines():
        args = shlex.split(line, comments=True)
        if args[-1] == "out.srt":  # its input, the ASS the line before wrote
            _ = (work / "in.ass").write_bytes((work / "out.ass").read_bytes())
        r = subprocess.run([FFMPEG, "-v", "error", "-y", *args[1:]], cwd=work,
                           capture_output=True, text=True, check=False)  # fmt: skip
        probe = run(FFPROBE, "-v", "error", "-show_entries", "stream=codec_name,codec_type",
                    "-of", "csv=p=0", str(work / args[-1]))  # fmt: skip
        found = probe.stdout.split() if r.returncode == 0 else r.stderr.strip()
        results.append(checked(" ".join(args), found, STREAMS[args[-1]]))
    third = (work / "out.srt").read_text(encoding="utf-8").split("\n\n")[2].split("\n")[1]
    results.append(checked("    the third cue, through ASS and back", third, ROUND_TRIP))
    results.append(checked("missing from the prose", stated(text), []))
    return all(results)


def seconds(time: str) -> float:
    """A SubRip time, ``HH:MM:SS,mmm``, in seconds."""
    hours, minutes, rest = time.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def stated(text: str) -> list[str]:
    """What the skill's prose must say of its example, from the measured values: those missing."""
    prose = " ".join(text.split())
    said = [f"{a / 1000:g} s for {d / 1000:g} s" for a, d, _ in EXAMPLE_FFMPEG]
    said += [f"`{t}`" for t in EXAMPLE_ASS[:2]] + [f"`{EXAMPLE_SUBVERTER[0][2]}`"]
    start, length, _ = EXAMPLE_FFMPEG[2]
    back = [seconds(t) for t in ROUND_TRIP.split(" --> ")]
    said.append(f"{start / 1000:.3f}-{(start + length) / 1000:.3f} s came back "
                f"{back[0]:.3f}-{back[1]:.3f}")  # fmt: skip
    whole = r"(?<![\w.]){}(?![\w]|\.\d)"  # no digit nor word glued to it
    return [x for x in said if not re.search(whole.format(re.escape(x)), prose)]


if __name__ == "__main__":
    main()
