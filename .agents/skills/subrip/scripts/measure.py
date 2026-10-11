"""SubRip, measured: what ffmpeg's `srt` demuxer reads of a file, what its `subrip` decoder makes
of the text (ASS), and what its `subrip` encoder and `srt` muxer write.

Usage: python3 measure.py [FFMPEG]  (default: ffmpeg on PATH; ffprobe beside it). Prints what
it found; references/format.md's tables are this output, at ffmpeg n8.1.2.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FFMPEG = sys.argv[1] if len(sys.argv) > 1 else "ffmpeg"
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
    "guillemets <<": "<<quote>>",
    "entity": "A &amp; B &lt; C",
    "literal \\N": "one\\Ntwo",
    "two lines": "one\ntwo",
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


if __name__ == "__main__":
    main()
