"""LRC, measured: what ffmpeg's `lrc` demuxer reads of a file (each line's times and text, the
file's tags), what its `lrc` muxer writes from SubRip cues, what a conversion to SubRip, WebVTT
and ASS makes of a line's text, and what its `subtitles` filter draws; what ffman reads of each
file; then the skill checked from its own text -- its example, its time rule and its commands, a
mismatch failing the run.

Usage: python3 measure.py [FFMPEG [PYTHON]]  (default: ffmpeg on PATH, ffprobe beside it; PYTHON
an interpreter that imports ffman, for its reading). Prints what it found; references/format.md's
tables are this output, at ffmpeg n8.1.2.
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
PYTHON = sys.argv[2] if len(sys.argv) > 2 else None  # noqa: PLR2004 -- FFMPEG, then PYTHON
SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"

# the demuxer's reading, and ffman's: a file's text each
READS: dict[str, str] = {
    "canonical": "[00:01.00]one\n[00:02.50]two\n",
    "three fraction digits": "[00:01.234]ms\n[00:02.000]next\n",
    "one fraction digit": "[00:01.5]tenths\n[00:02.0]next\n",
    "no fraction": "[00:01]whole\n[00:02]next\n",
    "a comma before the fraction": "[00:01.00]one\n[00:02,50]two\n",
    "minutes 61": "[61:00.00]past an hour\n",
    "minutes 100": "[00:01.00]one\n[100:00.00]far\n",
    "hours h:mm:ss": "[1:02:03.00]three fields\n",
    "seconds 60.5": "[00:60.50]bad seconds\n[00:01.00]ok\n",
    "negative": "[-00:01.00]before zero\n[00:01.00]after\n",
    "repeated stamps": "[00:01.00][00:05.00]chorus\n[00:03.00]verse\n",
    "a blank between stamps": "[00:01.00] [00:05.00]chorus\n[00:03.00]verse\n",
    "a stamp after the text": "[00:01.00]text [00:05.00]later\n",
    "blanks before a line's stamp": "[00:01.00]one\n \t[00:02.00]two\n",
    "a line without a stamp": "[00:01.00]one\nmore\n[00:03.00]two\n",
    "out of order": "[00:05.00]later\n[00:01.00]earlier\n",
    "a line twice": "[00:01.00]same\n[00:01.00]same\n[00:02.00]next\n",
    "empty line text": "[00:01.00]sung\n[00:03.00]\n[00:05.00]again\n",
    "a space after the stamp": "[00:01.00] Hello\n[00:02.00]next\n",
    "enhanced word times": "[00:01.00]<00:01.00>one <00:01.50>two <00:02.00>three\n[00:03.00]end\n",
    "markup": "[00:01.00]x<3 and y>2 <i>i</i> a\\nb {\\an8}c &amp;\n",
    "metadata": "[ti:Title]\n[ar:Artist]\n[al:Album]\n[au:Author]\n[by:Maker]\n[re:Tool]\n[ve:1.0]\n"
    "[length: 03:20]\n[xx:unknown]\n[00:01.00]line\n",
    "offset +500": "[offset:+500]\n[00:01.00]line\n[00:02.00]next\n",
    "offset -500": "[offset:-500]\n[00:01.00]line\n[00:02.00]next\n",
    "offset after a line": "[00:01.00]before\n[offset:+500]\n[00:02.00]after\n",
    "upper-case tag": "[TI:Upper]\n[00:01.00]line\n",
    "text without stamp first": "just text\n[00:01.00]line\n",
    "spaces before the first stamp": "  [00:01.00]  spaced text  \n",
    "CRLF": "[00:01.00]windows\r\n[00:02.00]next\r\n",
    "CR only": "[00:01.00]first\r[00:03.00]second\r",
    "BOM": "\ufeff[00:01.00]bom\n[00:02.00]next\n",
    "a NUL in a line": "[00:01.00]fi\0rst\n[00:02.00]next\n",
    "whisper-cli": "[by:whisper.cpp]\n[00:00.00] Hello world\n[60:19.99] past an hour\n",
}
# the same, as bytes: UTF-16 by its BOM; CP1252
SONG = "\ufeff[00:01.00]café\n[00:02.00]next\n"
CP1252 = "CP1252 (café ’x’)"
ENCODED: dict[str, bytes] = {
    "UTF-16LE (its BOM)": SONG.encode("utf-16-le"),
    "UTF-16BE (its BOM)": SONG.encode("utf-16-be"),
    CP1252: "[00:01.00]café ’x’\n[00:02.00]next\n".encode("cp1252"),
}

# SubRip cues, into LRC: the muxer's writing
WRITES: dict[str, str] = {
    "canonical": "1\n00:00:01,000 --> 00:00:02,000\none\n\n2\n00:00:02,500 --> 00:00:04,000\ntwo\n",
    "1.995 s": "1\n00:00:01,995 --> 00:00:03,000\nnear two\n",
    "1.994 s": "1\n00:00:01,994 --> 00:00:03,000\nbelow\n",
    "past an hour": "1\n01:01:01,500 --> 01:01:02,000\nhour\n",
    "two lines": "1\n00:00:01,000 --> 00:00:02,000\nline one\nline two\n",
    "starts with [": "1\n00:00:01,000 --> 00:00:02,000\n[music]\n",
    "markup": "1\n00:00:01,000 --> 00:00:02,000\n<i>italic</i> & more\n",
}

# drawn by the subtitles filter, at each time (s): the last line, no end of its own; then ended
LAST = "[00:01.00]x\n[00:02.00]y\n", "[00:01.00]x\n[00:02.00]y\n[00:04.00]\n"
DRAWN_AT = (1.5, 2.5, 5.0, 9.5)
FPS, INK = 10, 100  # the frames looked at, a second; a frame's grey above it: something drawn

# ffman's reading of each file, in PYTHON: refused (its message), or its chunks; its notes
FFMAN_PROBE = """
import json, sys
from ffman.errors import REFUSALS
from ffman.subs.ingest import ingest
out = {}
for name, text in json.load(sys.stdin).items():
    try:
        t = ingest("x.lrc", text.encode("latin-1"))
        out[name] = {"chunks": [(c.start, c.end, c.text) for c in t.chunks], "notes": t.notes}
    except REFUSALS as e:
        out[name] = {"refused": str(e), "notes": getattr(e, "notes", ())}  # ffman's refusal's
print(json.dumps(out))
"""


def logged(stderr: str) -> str:
    """ffmpeg's messages on one line, without their context's address (``[lrc @ 0x...]``)."""
    return re.sub(r" @ 0x[0-9a-f]+", "", stderr.strip()).replace("\n", "; ")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def converted(out: Path, *args: str) -> tuple[str, str]:
    """ffmpeg run on ``args``, writing ``out``: the file written (or why none was), its warnings."""
    _ = out.unlink(missing_ok=True)
    r = run(FFMPEG, "-v", "warning", "-y", *args, str(out))
    if r.returncode or not out.exists():
        return f"[failed: {logged(r.stderr).replace(f'{out.parent}/', '')}]", ""
    return out.read_text(encoding="utf-8", errors="backslashreplace"), logged(r.stderr)


def shown(text: object, warnings: str) -> str:
    """A result and, when there are any, its warnings."""
    return f"{text!r}" + (f" | {warnings}" if warnings else "")


def unhex(dump: str) -> bytes:
    """ffprobe's -show_data hexdump, back to bytes (each line: an offset, 16 bytes in hex)."""
    return b"".join(
        bytes.fromhex(line[10:50].replace(" ", "")) for line in dump.strip("\n").split("\n")
    )


def packets(path: Path) -> tuple[str, list[tuple[int, int, str]], dict[str, str]]:
    """The format ffprobe detects, each packet (start and duration in us, text), the tags."""
    p = run(FFPROBE, "-v", "error", "-i", str(path), "-show_packets", "-show_data",
            "-show_entries", "format=format_name:format_tags", "-of", "json")  # fmt: skip
    if p.returncode:  # the message without the file's path
        return f"[{p.stderr.strip().splitlines()[-1].rsplit(': ', 1)[-1]}]", [], {}
    data = json.loads(p.stdout)
    found = [
        (
            int(k["pts"]),
            int(k.get("duration", 0)),
            unhex(k["data"]).decode("utf-8", "backslashreplace"),
        )
        for k in data.get("packets", [])
    ]
    return data["format"]["format_name"], found, data["format"].get("tags", {})


# a cue's head as ffmpeg writes it: SubRip's index, then the timing line; WebVTT's timing line
CUE_HEAD = re.compile(
    r"^(?:[0-9]+\n)?([0-9:]+[.,][0-9]{3} --> [0-9:]+[.,][0-9]{3})[^\n]*\n", re.MULTILINE
)


def cues(written: str) -> list[tuple[str, str]]:
    """A SubRip's or WebVTT's cues: each timing and its text, what follows its head to the next."""
    parts = CUE_HEAD.split(written)
    return [
        (timing, text.rstrip("\n")) for timing, text in zip(parts[1::2], parts[2::2], strict=True)
    ]


def cue_texts(written: str) -> list[str]:
    """A SubRip's or WebVTT's cue texts (``cues``)."""
    return [text for _timing, text in cues(written)]


def dialogue(script: str) -> list[str]:
    """An ASS script's events, from the start time on (``0:00:01.00,0:00:02.00,Default,...``)."""
    return [line.split(",", 1)[1] for line in script.splitlines() if line.startswith("Dialogue:")]


def drawn_at(work: Path, lrc: str, times: tuple[float, ...]) -> str:
    """What the subtitles filter draws of ``lrc`` at each time: ``x`` something, ``.`` nothing."""
    path = work / "drawn.lrc"
    _ = path.write_text(lrc, encoding="utf-8")
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s=160x90:r={FPS}:d={max(times) + 1}",
         "-vf", f"subtitles={path}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=False,
    )  # fmt: skip
    if r.returncode or not r.stdout:
        return f"[failed: {logged(r.stderr.decode())}]"
    size = 160 * 90
    frames = [r.stdout[k : k + size] for k in range(0, len(r.stdout), size)]
    return "".join("x" if max(frames[round(t * FPS)]) > INK else "." for t in times)


def main() -> None:
    print(run(FFMPEG, "-version").stdout.splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        demuxed(work)
        muxed(work)
        decoded(work)
        ffman()
        print("\n## The skill, checked from its own text\n")
        ok = skill(work)
    sys.exit(0 if ok else 1)


def demuxed(work: Path) -> None:
    """The demuxer's reading of each file: its format, packets and tags."""
    print("\n## The demuxer: start us, duration us, text; the file's tags\n")
    src = work / "in.lrc"
    for name, data in {**{k: v.encode("utf-8") for k, v in READS.items()}, **ENCODED}.items():
        _ = src.write_bytes(data)
        fmt, found, tags = packets(src)
        print(f"{name}: {fmt} {found!r}" + (f" tags {tags}" if tags else ""))


def muxed(work: Path) -> None:
    """The muxer's writing of SubRip cues."""
    print("\n## The muxer: SubRip in, LRC out\n")
    srt, out = work / "in.srt", work / "out.lrc"
    for name, text in WRITES.items():
        _ = srt.write_text(text, encoding="utf-8")
        print(f"{name}: " + shown(*converted(out, "-i", str(srt))))
    _ = srt.write_text(WRITES["canonical"], encoding="utf-8")
    options = ("-metadata", "title=T", "-metadata", "artist=A", "-fflags", "+bitexact",
               "-precision", "3")  # fmt: skip
    print("-metadata, bitexact, -precision 3: " + shown(*converted(out, "-i", str(srt), *options)))


def decoded(work: Path) -> None:
    """A line's text through the text decoder, into SubRip, WebVTT and ASS; a last line drawn."""
    print("\n## Converted: a line's text into SubRip, WebVTT, ASS; an empty last line\n")
    src = work / "in.lrc"
    for name in ("markup", "enhanced word times", "empty line text", "canonical"):
        _ = src.write_text(READS[name], encoding="utf-8")
        srt, _w = converted(work / "out.srt", "-i", str(src))
        vtt, _w = converted(work / "out.vtt", "-i", str(src))
        ass, _w = converted(work / "out.ass", "-i", str(src))
        print(f"{name}: srt {cues(srt)!r}; vtt {cue_texts(vtt)!r}; ass {dialogue(ass)!r}")
    _ = src.write_text(READS["metadata"], encoding="utf-8")
    ass, _w = converted(work / "out.ass", "-i", str(src))
    print(
        f"metadata into ASS, its [Script Info]: {ass.split('[V4+ Styles]')[0].splitlines()[1:]!r}"
    )
    _ = src.write_bytes(ENCODED[CP1252])
    for options in ((), ("-sub_charenc", "CP1252")):
        srt, warnings = converted(work / "out.srt", *options, "-i", str(src))
        print(f"CP1252{', ' if options else ''}{' '.join(options)}: " + shown(cues(srt), warnings))
    _ = src.write_text(READS["canonical"], encoding="utf-8")
    for ext, video, audio in (
        ("mkv", "mpeg4", "aac"),
        ("mp4", "mpeg4", "aac"),
        ("webm", "libvpx-vp9", "libopus"),
    ):
        media = work / f"media.{ext}"
        _ = run(FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:d=4",
                "-f", "lavfi", "-i", "sine=d=4", "-c:v", video, "-c:a", audio, str(media))  # fmt: skip
        out = work / f"out.{ext}"
        r = run(FFMPEG, "-v", "error", "-y", "-i", str(media), "-i", str(src), "-map", "0",
                "-map", "1", "-c", "copy", str(out))  # fmt: skip
        probe = run(FFPROBE, "-v", "error", "-select_streams", "s", "-show_entries",
                    "stream=codec_name", "-of", "csv=p=0", str(out))  # fmt: skip
        kept = (
            probe.stdout.strip()
            if r.returncode == 0
            else f"[failed: {logged(r.stderr).split('; ')[0]}]"
        )
        print(f"-c copy into {ext}: {kept}")
    at = ", ".join(f"{t:g}" for t in DRAWN_AT)
    for lrc in LAST:
        print(f"the subtitles filter at {at} s, {lrc!r}: {drawn_at(work, lrc, DRAWN_AT)}")


def ffman() -> None:
    """Each file through ffman's reading, in PYTHON: refused, or its chunks; its notes."""
    if not PYTHON:
        return
    print("\n## ffman: refused, or its chunks (start ms, end ms, text); its notes\n")
    files = {**{k: v.encode("utf-8") for k, v in READS.items()}, **ENCODED}
    given = json.dumps({n: data.decode("latin-1") for n, data in files.items()})
    r = subprocess.run([PYTHON, "-c", FFMAN_PROBE], input=given,
                       capture_output=True, text=True, check=True)  # fmt: skip
    for name, found in json.loads(r.stdout).items():
        notes = f" ({'; '.join(found['notes'])})" if found["notes"] else ""
        if "refused" in found:
            print(f"{name}: refused: {found['refused']}{notes}")
        else:
            print(f"{name}: {[tuple(c) for c in found['chunks']]!r}{notes}")


def fenced(text: str, lang: str) -> list[str]:
    """The skill's code blocks in ``lang``, as written (a list item's indentation off)."""
    found = re.finditer(rf"^( *)```{lang}\n(.*?)^\1```$", text, re.MULTILINE | re.DOTALL)
    return [textwrap.dedent(m[2]) for m in found]


# what the skill states of its example and commands (SKILL.md, "Example" and "Converting")
EXAMPLE_FFMPEG = [(1000, 2500), (3500, 1500), (5000, 3000), (8000, None)]  # ms: start, length
EXAMPLE_FFMAN = [(1000, 3500, "Wake up, it's six"), (3500, 5000, "Rise & shine"),
                 (5000, 8000, "Wake up, it's six")]  # fmt: skip
EXAMPLE_SRT = ["Wake up, it's six", "Rise & shine", "Wake up, it's six", ""]
# Navidrome 0.64.2's line stamp (``model/lyrics_lrc.go``, ``timeRegexString``) and LrcParser
# 2025.623.0's (Jellyfin 12.2's; ``TimeTagUtils.LINE_TIME_TAG_REGEX``), quoted
NAVIDROME = re.compile(r"\[([0-9]{1,2}:)?([0-9]{1,2}):([0-9]{1,2})(\.[0-9]{1,3})?\]")
LRCPARSER = re.compile(r"\[(\d{1,}):(\d{2})\.(\d{2,3})\]")
STREAMS = {  # each command's output: its streams (the inputs' audio kept)
    "out-burn.mp4": ["h264,video", "aac,audio"],  # the build's default encoder: libx264
    "out.mkv": ["mpeg4,video", "aac,audio", "subrip,subtitle"],
    "out.mp4": ["mpeg4,video", "aac,audio", "mov_text,subtitle"],
    "out.srt": ["subrip,subtitle"],
    "out.lrc": ["text,subtitle"],
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
    example = fenced(text, "lrc")[0]
    _ = (work / "in.lrc").write_text(example, encoding="utf-8")
    _fmt, found, _tags = packets(work / "in.lrc")
    times = [(start // 1000, length // 1000 if length >= 0 else None) for start, length, _ in found]
    results = [checked("the example, ffmpeg's events", times, EXAMPLE_FFMPEG)]
    srt, _w = converted(work / "example.srt", "-i", str(work / "in.lrc"))
    results.append(checked("    as SubRip", cue_texts(srt), EXAMPLE_SRT))
    if PYTHON:
        probe = (
            "import json, sys; from ffman.subs.ingest import ingest; "
            "t = ingest('x.lrc', sys.stdin.buffer.read()); "
            "print(json.dumps([(c.start, c.end, c.text) for c in t.chunks]))"
        )
        r = subprocess.run([PYTHON, "-c", probe], input=example.encode(), capture_output=True,
                           check=True)  # fmt: skip
        read = [tuple(c) for c in json.loads(r.stdout)]
        results.append(checked("    ffman", read, EXAMPLE_FFMAN))

    space: dict[str, object] = {}
    exec(fenced(text, "python")[0], space)  # noqa: S102 -- the skill's own rule, run as written
    lrc_time = space["lrc_time"]
    if not callable(lrc_time):
        raise TypeError(lrc_time)
    edges = [0, 4, 5, 994, 995, 999, 1000, 59994, 59995, 3599994, 5999994]
    every = sorted({*edges, *range(0, 6000000, 997)})  # under 100 minutes, the rule's range
    stamps = [str(lrc_time(t)) for t in every]
    lines = "".join(f"{s}t{i}\n" for i, s in enumerate(stamps))  # each its own: none a duplicate
    _ = (work / "rule.lrc").write_text(lines, encoding="utf-8")
    read = sorted(start for start, _length, _data in packets(work / "rule.lrc")[1])
    exact = read == [(t + 5) // 10 * 10000 for t in every]
    what = f"the time rule: {len(every)} times to 100 minutes, as ffmpeg reads them"
    results.append(checked(what, found=exact, stated=True))
    alike = all(NAVIDROME.fullmatch(s) and LRCPARSER.fullmatch(s) for s in stamps)
    results.append(checked("    each stamp Navidrome's and LrcParser's", found=alike, stated=True))

    for video in ("video.mp4", "video.mkv"):
        _ = run(FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:d=10",
                "-f", "lavfi", "-i", "sine=d=10", "-c:v", "mpeg4", "-c:a", "aac",
                str(work / video))  # fmt: skip
    for line in fenced(text, "sh")[0].splitlines():
        args = shlex.split(line, comments=True)
        if args[-1] == "out.lrc":  # its input, the SubRip the line before wrote
            _ = (work / "in.srt").write_bytes((work / "out.srt").read_bytes())
        r = subprocess.run([FFMPEG, "-v", "error", "-y", *args[1:]], cwd=work,
                           capture_output=True, text=True, check=False)  # fmt: skip
        probe = run(FFPROBE, "-v", "error", "-show_entries", "stream=codec_name,codec_type",
                    "-of", "csv=p=0", str(work / args[-1]))  # fmt: skip
        streams = probe.stdout.split() if r.returncode == 0 else r.stderr.strip()
        results.append(checked(" ".join(args), streams, STREAMS[args[-1]]))
    results.append(checked("missing from the prose", missing(text), []))
    return all(results)


def missing(text: str) -> list[str]:
    """What the skill's prose must say of its example, from the measured values: those missing."""
    prose = " ".join(text.split())
    said = [f"{a / 1000:g} s for {d / 1000:g} s" for a, d in EXAMPLE_FFMPEG if d is not None]
    said += [f"`{line}`" for line in EXAMPLE_SRT[:2]]
    whole = r"(?<![\w.]){}(?![\w]|\.\d)"  # no digit nor word glued to it
    return [x for x in said if not re.search(whole.format(re.escape(x)), prose)]


if __name__ == "__main__":
    main()
