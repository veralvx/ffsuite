"""ASS and SSA through ffmpeg, measured: what its `ass` demuxer reads of a script, and what its
`ass` muxer writes back -- by a stream copy, and through the `ass` decoder and encoder; and
whether libass (through ffmpeg's `ass` filter) draws `\\{` and `\\}` as braces, what of a
script after a NUL, whether it draws a UTF-16 one, how a CP1252 one, and one of no type.

Usage: python3 measure_ffmpeg.py [FFMPEG [PYTHON]]  (default: ffmpeg on PATH; ffprobe beside it;
PYTHON an interpreter that imports ffman, for its reading). Prints what it found;
references/format.md's "ffmpeg" and "ffman" tables are this output, at ffmpeg n8.1.2.
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
PYTHON = sys.argv[2] if len(sys.argv) > 2 else None  # noqa: PLR2004 -- FFMPEG, then PYTHON

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

# the Events' fields in another order
CUSTOM = HEAD.replace(
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    "Format: Start, End, Style, Text",
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
    "a NUL in a text": HEAD + dialogue("fi\0rst") + dialogue("next", "0:00:03.00", "0:00:04.00"),
    "[script info], lower-cased": HEAD.replace("[Script Info]", "[script info]") + dialogue("lo"),
    "a comment first": "; by hand\n" + HEAD + dialogue("commented"),
    "spaces first": "  " + HEAD + dialogue("spaced"),
    "Format: Start, End, Style, Text": CUSTOM + "Dialogue: 0:00:01.00,0:00:02.00,Default,custom\n",
    "a comma before a time's fraction": HEAD + dialogue("comma", "0:00:01,00"),
    "CR line ends": (HEAD + dialogue("mac")).replace("\n", "\r"),
}
CAFE = HEAD + dialogue("café", "0:00:00.00", "0:00:01.00")
UTF16 = "\ufeff" + CAFE  # its BOM first
LONE = "\ufeff" + HEAD + dialogue("fi\ud800rst") + dialogue("next", "0:00:03.00", "0:00:04.00")
QUOTED = "café \u2019x\u2019"  # CP1252's 0x92 its right quote
# a script each, as bytes: UTF-16, valid or not; CP1252
ENCODED: dict[str, bytes] = {
    "UTF-16LE (its BOM)": UTF16.encode("utf-16-le"),
    "UTF-16BE (its BOM)": UTF16.encode("utf-16-be"),
    "UTF-16LE, a lone surrogate": LONE.encode("utf-16-le", "surrogatepass"),
    "UTF-16LE, an odd byte last": UTF16.encode("utf-16-le") + b"x",
    "CP1252, an event's text": (
        HEAD + dialogue(QUOTED) + dialogue("next", "0:00:03.00", "0:00:04.00")
    ).encode("cp1252"),
    "CP1252, a header's comment": (
        HEAD.replace("[Script Info]\n", "[Script Info]\n; é\n") + dialogue("plain")
    ).encode("cp1252"),
}


# a script each, and the times (s) to look at it: what libass alone draws of it (the `ass` filter,
# ffman's burn) against what it draws of ffmpeg's reading (the `subtitles` filter, mpv's path)
CR = "\r"
READERS: dict[str, tuple[bytes, tuple[float, ...]]] = {
    "canonical": ((HEAD + dialogue("x")).encode(), (0.5, 1.5, 2.5)),
    "[script info], lower-cased": (
        (HEAD.replace("[Script Info]", "[script info]") + dialogue("x")).encode(),
        (0.5, 1.5, 2.5),
    ),
    "a comment first": (("; by hand\n" + HEAD + dialogue("x")).encode(), (0.5, 1.5, 2.5)),
    "Format: Start, End, Style, Text": (
        (CUSTOM + "Dialogue: 0:00:01.00,0:00:02.00,Default,x\n").encode(),
        (0.5, 1.5, 2.5),
    ),
    "a comma before a time's fraction (start)": (
        (HEAD + dialogue("x", "0:00:01,00")).encode(),
        (0.5, 1.5, 2.5),
    ),
    "end before start, then another": (
        (
            HEAD
            + dialogue("x", "0:00:03.00", "0:00:01.00")
            + dialogue("y", "0:00:05.00", "0:00:06.00")
        ).encode(),
        (2.0, 3.5, 4.5, 5.5),
    ),
    "the last ending before it starts": (
        (HEAD + dialogue("x", "0:00:03.00", "0:00:01.00")).encode(),
        (2.0, 3.5, 5.5),
    ),
    "CR line ends": ((HEAD + dialogue("x")).replace("\n", CR).encode(), (0.5, 1.5, 2.5)),
    "no type": (
        (INFO.replace("ScriptType: v4.00+\n", "") + EVENTS + dialogue("x")).encode(),
        (0.5, 1.5, 2.5),
    ),
    "v4.00++": (
        (
            HEAD.replace("v4.00+", "v4.00++").replace("[V4+ Styles]", "[V4++ Styles]")
            + dialogue("x")
        ).encode(),
        (0.5, 1.5, 2.5),
    ),
    "a NUL in a text, then an event": (
        (HEAD + dialogue("x\0y") + dialogue("z", "0:00:03.00", "0:00:04.00")).encode(),
        (1.5, 3.5),
    ),
    "UTF-16LE (its BOM)": (("\ufeff" + HEAD + dialogue("x")).encode("utf-16-le"), (0.5, 1.5)),
    "CP1252, an event's text": ((HEAD + dialogue(QUOTED)).encode("cp1252"), (0.5, 1.5)),
}
FPS = 10  # the frames looked at, a second
INK = 100  # a frame's grey above it: something drawn on its black
# ffman's reading of each READERS script, in PYTHON: refused (its message), or its notes and the
# copy it burns and attaches (``passed``), as latin-1 text
FFMAN_PROBE = """
import json, sys
from ffman.errors import REFUSALS
from ffman.subs.ingest import ingest, passed
out = {}
for name, text in json.load(sys.stdin).items():
    data = text.encode("latin-1")
    try:
        notes = list(ingest("x.ass", data).notes)
        out[name] = {"notes": notes, "copy": passed(data, "x.ass").data.decode("latin-1")}
    except REFUSALS as e:
        out[name] = {"refused": str(e)}
print(json.dumps(out))
"""


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
        return f"[failed: {logged(r.stderr).replace(f'{out.parent}/', '')}]", ""
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


def drawn(work: Path, script: bytes) -> str:
    """The digest of the frame libass draws of ``script`` (320x180, grey), or why none was."""
    path = work / "drawn.ass"
    _ = path.write_bytes(script)
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1", "-vf",
         f"ass={path}", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=False,
    )  # fmt: skip
    if r.returncode:
        return f"[failed: {logged(r.stderr.decode()).replace(str(path), path.name)}]"
    return hashlib.sha256(r.stdout).hexdigest()


def drawn_at(work: Path, script: bytes, times: tuple[float, ...], how: str) -> str:
    """What ``how`` (``ass`` or ``subtitles``) draws of ``script`` at each time: ``x`` something,
    ``.`` nothing -- or why it drew no frame."""
    path = work / "shown.ass"
    _ = path.write_bytes(script)
    size, last = 160 * 90, max(times) + 1
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s=160x90:r={FPS}:d={last}",
         "-vf", f"{how}={path}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=False,
    )  # fmt: skip
    if r.returncode or not r.stdout:
        return f"[failed: {logged(r.stderr.decode()).replace(str(path), path.name)}]"
    frames = [r.stdout[k : k + size] for k in range(0, len(r.stdout), size)]
    return "".join("x" if max(frames[round(t * FPS)]) > INK else "." for t in times)


def frame(work: Path, *texts: str) -> str:
    """The digest of the frame libass draws for an event of each text at once."""
    events = "".join(dialogue(text, "0:00:00.00", "0:00:01.00") for text in texts)
    return drawn(work, (HEAD + events).encode("utf-8"))


def main() -> None:
    print(run(FFMPEG, "-version").stdout.splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src, out = work / "in.ass", work / "out.ass"
        print("\n## The demuxer's packets (start cs, duration cs, data); then the muxer's events,")
        print("## by a stream copy and by the ass decoder and encoder (a transcoding)\n")
        for name, data in {**{k: v.encode("utf-8") for k, v in SCRIPTS.items()}, **ENCODED}.items():
            _ = src.write_bytes(data)
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
        digests = {text: frame(work, text) for text in ("ab", "a{x}b", "a\\{x\\}b")}
        for text, digest in digests.items():
            print(f"{text!r}: {digest[:12]}" + (" -- as 'ab'" if digest == digests["ab"] else ""))
        alone, up = frame(work, "a"), "{\\an8}up"  # a second event, at the top
        for texts in (("a", up), ("a\0b", up)):
            digest = frame(work, *texts)
            print(f"{texts!r}: {digest[:12]}" + (" -- as 'a' alone" if digest == alone else ""))
        utf8 = drawn(work, CAFE.encode("utf-8"))
        for codec in ("utf-16-le", "utf-16-be"):
            digest = drawn(work, UTF16.encode(codec))
            shown = digest if digest.startswith("[") else digest[:12]
            print(
                f"'café' in {codec} (its BOM): {shown}" + (" -- as UTF-8" if digest == utf8 else "")
            )
        untyped = INFO.replace("ScriptType: v4.00+\n", "") + EVENTS + dialogue("x", "0:00:00.00")
        print(f"no type (no ScriptType, no styles section): {drawn(work, untyped.encode())}")
        events = HEAD + dialogue(QUOTED, "0:00:00.00", "0:00:01.00")
        cp1252, latin1 = drawn(work, events.encode("cp1252")), frame(work, "café \x92x\x92")
        same = " -- as Latin-1's (U+0092)" if cp1252 == latin1 else ""
        print(f"{QUOTED!r} in CP1252: {cp1252[:12]}{same}; UTF-8's {frame(work, QUOTED)[:12]}")

        print("\n## libass alone (the ass filter, ffman's burn) against ffmpeg's reading, then")
        print("## libass (the subtitles filter, mpv's path): x drawn, . not, at each time\n")
        for name, (script, times) in READERS.items():
            alone, read = (
                drawn_at(work, script, times, "ass"),
                drawn_at(work, script, times, "subtitles"),
            )
            print(
                f"{name} at {', '.join(f'{t:g}' for t in times)} s: ass {alone}; subtitles {read}"
            )

        ffman(work)


def cues(work: Path, script: bytes) -> int:
    """How many cues ffmpeg makes of ``script`` as text (its subrip encoder: what a track holds)."""
    path, out = work / "cues.ass", work / "cues.srt"
    _ = path.write_bytes(script)
    written, _warnings = converted(out, "-i", str(path), "-f", "srt")
    return 0 if written.startswith("[failed") else written.count(" --> ")


def ffman(work: Path) -> None:
    """Each READERS script through ffman, in PYTHON: refused, or its notes; what its burn draws
    of its copy (the ass filter), and how many cues ffmpeg makes of it for --add-subs."""
    if not PYTHON:
        return
    print("\n## ffman: refused, or its notes; its burn (x drawn, . not); --add-subs' cues\n")
    given = json.dumps({n: script.decode("latin-1") for n, (script, _) in READERS.items()})
    r = subprocess.run([PYTHON, "-c", FFMAN_PROBE], input=given,
                       capture_output=True, text=True, check=True)  # fmt: skip
    for name, found in json.loads(r.stdout).items():
        if "refused" in found:
            print(f"{name}: refused: {found['refused']}")
            continue
        copy, times = found["copy"].encode("latin-1"), READERS[name][1]
        said = f" ({'; '.join(found['notes'])})" if found["notes"] else ""
        burned = drawn_at(work, copy, times, "ass")
        print(f"{name}{said}: burned {burned}; attached, {cues(work, copy)} cues")


if __name__ == "__main__":
    main()
