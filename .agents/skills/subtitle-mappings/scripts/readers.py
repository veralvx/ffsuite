"""What becomes of a subtitle file: converted by ffmpeg, read by subverter and by ffman. Shared by
`ffmpeg.py`, `words.py` and `mappings.py`.
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def logged(stderr: str) -> str:
    """ffmpeg's messages on one line, without their context's address (``[srt @ 0x...]``)."""
    return re.sub(r" @ 0x[0-9a-f]+", "", stderr.strip()).replace("\n", "; ")


def converted(ffmpeg: str, src: Path, out: Path) -> tuple[str, str]:
    """``src`` converted by ffmpeg into ``out``: the file written (or why none was), its warnings.

    ``-fflags +bitexact``: no version in what it writes (LRC's `[re:]`, `[ve:]`).
    """
    _ = out.unlink(missing_ok=True)
    argv = [ffmpeg, "-v", "warning", "-y", "-i", str(src), "-fflags", "+bitexact", str(out)]
    r = subprocess.run(argv, capture_output=True, text=True, check=False)
    if r.returncode or not out.exists():  # its message without the temporary directory
        return f"[failed: {logged(r.stderr).replace(f'{out.parent}/', '')}]", ""
    return out.read_text(encoding="utf-8", errors="backslashreplace"), logged(r.stderr)


# subverter's reading, then ffman's: cues and words, then chunks, words and notes, as JSON
_READ = """
import json, sys
import subverter
from ffman.errors import FfmanError
from ffman.subs.ingest import ingest
fmt, data = sys.argv[1], sys.stdin.buffer.read()
out = {}
try:
    r = subverter.read(fmt, data, "in." + fmt)
    out["subverter"] = {"timed": [[c.start, c.end, c.text] for c in r.cues],
                        "words": [[w.segment, w.start, w.end, w.text] for w in r.words]}
except subverter.Error as e:
    out["subverter"] = f"refused: {e}"
try:
    t = ingest("in." + fmt, data)
    out["ffman"] = {"timed": [[c.start, c.end, c.text] for c in t.chunks],
                    "words": [[w.segment, w.start, w.end, w.text] for w in t.words],
                    "notes": list(t.notes)}
    if fmt == "ass" and not t.chunks:
        out["ffman"] = "nothing read: burned as it is"
except (subverter.Error, FfmanError) as e:
    out["ffman"] = f"refused: {e}"
print(json.dumps(out))
"""


def read_back(python: str, fmt: str, data: str) -> dict[str, Any]:
    """A file's reading by subverter and by ffman, in ``python`` (one that imports both)."""
    r = subprocess.run([python, "-c", _READ, fmt], input=data.encode(), capture_output=True,
                       check=True)  # fmt: skip
    return json.loads(r.stdout)
