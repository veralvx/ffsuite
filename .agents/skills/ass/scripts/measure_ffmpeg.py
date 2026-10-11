"""ASS and SSA through ffmpeg, measured: what its `ass` demuxer reads of a script, and what its
`ass` muxer writes back -- by a stream copy, and through the `ass` decoder and encoder; and
whether libass (through ffmpeg's `ass` filter) draws `\\{` and `\\}` as braces.

Usage: python3 measure_ffmpeg.py [FFMPEG]  (default: ffmpeg on PATH; ffprobe beside it). Prints
what it found; references/format.md's "ffmpeg" tables are this output, at ffmpeg n8.1.2.
"""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FFMPEG = sys.argv[1] if len(sys.argv) > 1 else "ffmpeg"
FFPROBE = str(Path(FFMPEG).with_name("ffprobe")) if "/" in FFMPEG else "ffprobe"

INFO = "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\n\n"
STYLES = (
    "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, "
    "Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,"
    "1,1,0,2,10,10,10,1\n\n"
)
EVENTS = (
    "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)
HEAD = INFO + STYLES + EVENTS


def dialogue(text: str, start: str = "0:00:01.00", end: str = "0:00:02.00", layer: int = 0) -> str:
    """A Dialogue line in the Default style."""
    return f"Dialogue: {layer},{start},{end},Default,,0,0,0,,{text}\n"


SSA = (
    "[Script Info]\nScriptType: v4.00\n\n[V4 Styles]\nFormat: Name, Fontname, Fontsize, "
    "PrimaryColour, SecondaryColour, TertiaryColour, BackColour, Bold, Italic, BorderStyle, "
    "Outline, Shadow, Alignment, MarginL, MarginR, MarginV, AlphaLevel, Encoding\n"
    "Style: Default,Arial,16,16777215,65535,0,0,0,0,1,1,0,2,10,10,10,0,1\n\n[Events]\n"
    "Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: Marked=0,0:00:01.00,0:00:02.00,Default,,0000,0000,0000,,ssa\n"
)

# a script each: what the demuxer reads of it, and what the muxer writes back
SCRIPTS: dict[str, str] = {
    "canonical": HEAD + dialogue("Hello\\Nworld"),
    "fraction .5": HEAD + dialogue("half?", "0:00:01.5", "0:00:02.5"),
    "fraction .500": HEAD + dialogue("five hundred?", "0:00:01.500", "0:00:02.000"),
    "hours 10": HEAD + dialogue("ten hours", "10:00:00.00", "10:00:01.00"),
    "layers": HEAD + dialogue("under", layer=0) + dialogue("over", layer=5),
    "out of order": HEAD + dialogue("later", "0:00:05.00", "0:00:06.00") + dialogue("earlier"),
    "overlap": HEAD
    + dialogue("long", end="0:00:04.00")
    + dialogue("inside", "0:00:02.00", "0:00:03.00"),
    "duplicate": HEAD + dialogue("same") + dialogue("same"),
    "end before start": HEAD
    + dialogue("backwards", "0:00:03.00", "0:00:01.00")
    + dialogue("next", "0:00:05.00", "0:00:06.00"),
    "zero duration": HEAD + dialogue("zero", "0:00:01.00", "0:00:01.00"),
    "empty text": HEAD + dialogue("") + dialogue("next", "0:00:03.00", "0:00:04.00"),
    "a Comment line": HEAD + dialogue("one") + "Comment: 0,0:00:01.50,0:00:02.00,Default,,0,0,0,,"
    "a note\n" + dialogue("two", "0:00:03.00", "0:00:04.00"),
    "[Fonts] after the events": HEAD + dialogue("text") + "\n[Fonts]\nfontname: x.ttf\n",
    "a Dialogue without text fields": HEAD
    + "Dialogue: 0,0:00:01.00,0:00:02.00\n"
    + dialogue("next", "0:00:03.00", "0:00:04.00"),
    "commas in the text": HEAD + dialogue("one, two, three"),
    "no [Events] Format line": INFO + STYLES + "[Events]\n" + dialogue("formatless"),
    "CRLF": (HEAD + dialogue("windows")).replace("\n", "\r\n"),
    "UTF-8 BOM": "﻿" + HEAD + dialogue("bom"),
    "blank lines first": "\n\n" + HEAD + dialogue("late start"),
    "SSA v4": SSA,
    "v4.00++": HEAD.replace("v4.00+", "v4.00++").replace("[V4+ Styles]", "[V4++ Styles]")
    + dialogue("plus plus"),
}


def logged(stderr: str) -> str:
    """ffmpeg's messages on one line, without their context's address (``[ass @ 0x...]``)."""
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


def events_of(script: str) -> list[str]:
    """A script's lines from its [Events] section on: what a conversion changed."""
    lines = script.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip() == "[Events]"), len(lines))
    return lines[first + 1 :]


def packets(path: Path) -> tuple[str, list[tuple[int, int, str]]]:
    """The format ffprobe detects and each packet: start and duration (cs), data."""
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


def frame(work: Path, text: str) -> str:
    """The digest of the frame libass draws for one event of ``text`` (320x180, grey)."""
    script = work / "drawn.ass"
    _ = script.write_text(HEAD + dialogue(text, "0:00:00.00", "0:00:01.00"), encoding="utf-8")
    drawn = subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1", "-vf",
         f"ass={script}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return hashlib.sha256(drawn).hexdigest()


def main() -> None:
    print(run(FFMPEG, "-version").stdout.splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src, out = work / "in.ass", work / "out.ass"
        print("\n## The demuxer's packets (start cs, duration cs, data); then the muxer's events,")
        print("## by a stream copy and by the ass decoder and encoder (a transcoding)\n")
        for name, text in SCRIPTS.items():
            _ = src.write_bytes(text.encode("utf-8"))
            fmt, found = packets(src)
            print(f"{name}: [{fmt}] {found!r}")
            for how, args in (("copy", ("-c", "copy")), ("transcoded", ())):
                written, warnings = converted(out, "-i", str(src), *args)
                lines = events_of(written) if not written.startswith("[failed") else written
                print(f"    {how}: {lines!r}" + (f" | {warnings}" if warnings else ""))
        _ = src.write_text(SCRIPTS["canonical"], encoding="utf-8")
        written, _warnings = converted(out, "-i", str(src))
        print(f"\nthe header written back, transcoded: {written.split('[Events]')[0]!r}")
        _ = src.write_bytes(SCRIPTS["CRLF"].encode("utf-8"))
        for how, args in (("copy", ("-c", "copy")), ("transcoded", ())):
            _ = converted(out, "-i", str(src), *args)
            ends = "CRLF" if b"\r" in out.read_bytes() else "LF"
            print(f"a CRLF script written back, {how}: line ends {ends}")
        _ = src.write_text(SCRIPTS["SSA v4"], encoding="utf-8")
        written, _warnings = converted(out, "-i", str(src))
        print(f"SSA v4 written back, transcoded: {written!r}")

        print("\n## libass, through the ass filter: what each event draws (a frame's digest)\n")
        drawn = {text: frame(work, text) for text in ("ab", "a{x}b", "a\\{x\\}b")}
        for text, digest in drawn.items():
            print(f"{text!r}: {digest[:12]}" + (" -- as 'ab'" if digest == drawn["ab"] else ""))


if __name__ == "__main__":
    main()
