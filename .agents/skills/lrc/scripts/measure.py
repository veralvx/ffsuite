"""LRC, measured: what ffmpeg's `lrc` demuxer reads of a file (each line's times, text, the
metadata tags) and what its `lrc` muxer writes from SubRip cues.

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

READS: dict[str, str] = {
    "canonical": "[00:01.00]one\n[00:02.50]two\n",
    "three fraction digits": "[00:01.234]ms\n[00:02.000]next\n",
    "one fraction digit": "[00:01.5]tenths\n[00:02.0]next\n",
    "no fraction": "[00:01]whole\n[00:02]next\n",
    "minutes 61": "[61:00.00]past an hour\n",
    "hours h:mm:ss": "[1:02:03.00]three fields\n",
    "seconds 60.5": "[00:60.50]bad seconds\n[00:01.00]ok\n",
    "negative": "[-00:01.00]before zero\n[00:01.00]after\n",
    "repeated stamps": "[00:01.00][00:05.00]chorus\n[00:03.00]verse\n",
    "a blank between stamps": "[00:01.00] [00:05.00]chorus\n[00:03.00]verse\n",
    "out of order": "[00:05.00]later\n[00:01.00]earlier\n",
    "empty line text": "[00:01.00]sung\n[00:03.00]\n[00:05.00]again\n",
    "enhanced word times": "[00:01.00]<00:01.00>one <00:01.50>two <00:02.00>three\n[00:03.00]end\n",
    "metadata": "[ti:Title]\n[ar:Artist]\n[al:Album]\n[au:Author]\n[by:Maker]\n[re:Tool]\n[ve:1.0]\n"
    "[length: 03:20]\n[xx:unknown]\n[00:01.00]line\n",
    "offset +500": "[offset:+500]\n[00:01.00]line\n[00:02.00]next\n",
    "offset -500": "[offset:-500]\n[00:01.00]line\n[00:02.00]next\n",
    "offset after a line": "[00:01.00]before\n[offset:+500]\n[00:02.00]after\n",
    "upper-case tag": "[TI:Upper]\n[00:01.00]line\n",
    "text without stamp": "just text\n[00:01.00]line\n",
    "CRLF": "[00:01.00]windows\r\n[00:02.00]next\r\n",
    "BOM": "\ufeff[00:01.00]bom\n",
    "spaces before stamp": "  [00:01.00]  spaced text  \n",
    "whisper-cli": "[by:whisper.cpp]\n[00:00.00] Hello world\n[60:19.99] past an hour\n",
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


def logged(stderr: str) -> str:
    """ffmpeg's messages on one line, without their context's address (``[srt @ 0x...]``)."""
    return re.sub(r" @ 0x[0-9a-f]+", "", stderr.strip()).replace("\n", "; ")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


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


def unhex(dump: str) -> bytes:
    """ffprobe's -show_data hexdump, back to bytes (each line: an offset, 16 bytes in hex)."""
    return b"".join(
        bytes.fromhex(line[10:50].replace(" ", "")) for line in dump.strip("\n").split("\n")
    )


def main() -> None:
    print(run(FFMPEG, "-version").stdout.splitlines()[0])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src = work / "in.lrc"
        print("\n## The demuxer: start us, duration us, text; the file's tags\n")
        for name, text in READS.items():
            _ = src.write_bytes(text.encode("utf-8"))
            p = run(FFPROBE, "-v", "error", "-i", str(src), "-show_packets", "-show_data",
                    "-show_entries", "format=format_name:format_tags", "-of", "json")  # fmt: skip
            if p.returncode:  # the message without the file's path
                print(f"{name}: [{p.stderr.strip().splitlines()[-1].rsplit(': ', 1)[-1]}]")
                continue
            data = json.loads(p.stdout)
            found = [
                (
                    int(k["pts"]),
                    int(k.get("duration", 0)),
                    unhex(k["data"]).decode("utf-8", "backslashreplace"),
                )
                for k in data.get("packets", [])
            ]
            tags = data["format"].get("tags", {})
            print(
                f"{name}: [{data['format']['format_name']}] {found!r}"
                + (f" tags {tags}" if tags else "")
            )
        print("\n## The muxer: SubRip in, LRC out\n")
        srt, out = work / "in.srt", work / "out.lrc"
        for name, text in WRITES.items():
            _ = srt.write_text(text, encoding="utf-8")
            print(f"{name}: " + shown(*converted(out, "-i", str(srt))))
        _ = srt.write_text(WRITES["canonical"], encoding="utf-8")
        options = ("-metadata", "title=T", "-metadata", "artist=A", "-fflags", "+bitexact",
                   "-precision", "3")  # fmt: skip
        print(
            "-metadata, bitexact, -precision 3: " + shown(*converted(out, "-i", str(srt), *options))
        )


if __name__ == "__main__":
    main()
