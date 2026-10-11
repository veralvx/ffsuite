"""Word timings, measured: what ffman reads back of each format's by-word form, how libass
draws ASS's karaoke, and how Chromium draws WebVTT's timestamps.

The same words in every form: `one` 1.0-1.5 s, `two` 1.5-1.8, `three` 1.8-2.0, a sentence;
`four` 3.0-3.4 and, after a 200 ms gap, `five` 3.6-4.0, another. ffman's reading is
subverter's (`subverter.read`), then ffman's own (`ffman.subs.ingest`: its chunks and words).
libass draws through ffmpeg's `ass` filter, each frame at a chosen millisecond; Chromium through
a `<track>` on a video seeked to each time, `::cue(:past)` red and `::cue(:future)` blue. A
word's colour is read from the frame: its pixels by their dominant channel. The cues OpenAI
whisper writes are checked against its writers (`utils.py`, imported from the file and called).

Usage: python3 words.py FFMPEG PYTHON WHISPER_UTILS_PY  (PYTHON: an interpreter that imports
subverter and ffman; this one, playwright and its Chromium; openai-whisper v20250625's
`utils.py`). Prints what it found; references/words.md's tables are this output, at ffmpeg
n8.1.2 (libass 0.17.1) and Chromium 141.0.7390.37.
"""

import base64
import functools
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

from playwright.sync_api import Page, sync_playwright

FFMPEG, PYTHON, WHISPER_UTILS = sys.argv[1], sys.argv[2], Path(sys.argv[3])

# each sentence: its words, each (text, start ms, end ms)
SENTENCES = (
    (("one", 1000, 1500), ("two", 1500, 1800), ("three", 1800, 2000)),
    (("four", 3000, 3400), ("five", 3600, 4000)),
)


def clock(ms: int) -> str:
    """SubRip's ``HH:MM:SS,mmm``."""
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def vtt_clock(ms: int) -> str:
    """WebVTT's ``[HH:]MM:SS.mmm``, hours only when some (OpenAI's ``format_timestamp``)."""
    return clock(ms).replace(",", ".").removeprefix("00:")


def ass_clock(ms: int) -> str:
    """ASS's ``h:mm:ss.cc``."""
    return f"{ms // 3600000}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}"


def lrc_clock(ms: int) -> str:
    """LRC's ``mm:ss.xx``."""
    return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}"


def cues(fmt: str, timed: list[tuple[int, int, str]]) -> str:
    """SubRip or WebVTT cues: each (start, end, text)."""
    if fmt == "srt":
        return "".join(
            f"{n}\n{clock(a)} --> {clock(z)}\n{t}\n\n" for n, (a, z, t) in enumerate(timed, 1)
        )
    return "WEBVTT\n\n" + "".join(
        f"{vtt_clock(a)} --> {vtt_clock(z)}\n{t}\n\n" for a, z, t in timed
    )


def a_cue_a_sentence(fmt: str) -> str:
    """A cue a sentence, no word timed: whisper-cli's `-osrt`, OpenAI's without words."""
    return cues(fmt, [(s[0][1], s[-1][2], " ".join(t for t, _, _ in s)) for s in SENTENCES])


def a_cue_a_word(fmt: str) -> str:
    """A cue a word: OpenAI's `--max_words_per_line 1` (whisper-cli's `-ml 1 -sow` alike, each
    text after a space)."""
    return cues(fmt, [(a, z, t) for s in SENTENCES for t, a, z in s])


def highlighted(fmt: str) -> str:
    """OpenAI's and WhisperX's `--highlight_words` (`utils.py`, `iterate_result`): a cue a word,
    the sentence with that word in `<u>`; a gap between words a cue of the sentence alone."""
    timed: list[tuple[int, int, str]] = []
    for s in SENTENCES:
        words = [t for t, _, _ in s]
        last = s[0][1]
        for i, (_, a, z) in enumerate(s):
            if a != last:
                timed.append((last, a, " ".join(words)))
            lit = (f"<u>{w}</u>" if j == i else w for j, w in enumerate(words))
            timed.append((a, z, " ".join(lit)))
            last = z
    return cues(fmt, timed)


def stamped(*, wrap: bool = False, style: str = "") -> str:
    """WebVTT, a cue a sentence, a timestamp tag before each word but the first; ``wrap``: each
    word in `<c>`; ``style``: a STYLE block first."""
    blocks = [f"STYLE\n{style}\n\n"] if style else []
    for s in SENTENCES:
        words = [f"<c>{t}</c>" if wrap else t for t, _, _ in s]
        text = " ".join(
            [words[0]]
            + [f"<{vtt_clock(a)}>{w}" for w, (_, a, _) in zip(words[1:], s[1:], strict=True)]
        )
        blocks.append(f"{vtt_clock(s[0][1])} --> {vtt_clock(s[-1][2])}\n{text}\n\n")
    return "WEBVTT\n\n" + "".join(blocks)


def karaoke(s: tuple[tuple[str, int, int], ...], tag: str = "k") -> str:
    """ASS karaoke: each word its duration in centiseconds (``\\k`` and kin), a gap its own."""
    parts: list[str] = []
    last = s[0][1]
    for t, a, z in s:
        if a != last:
            parts.append(f"{{\\{tag}{(a - last) // 10}}}")
        parts.append(f"{{\\{tag}{(z - a) // 10}}}{t} ")
        last = z
    return "".join(parts).rstrip()


def enhanced_lrc(*, spaced: bool = False) -> str:
    """Enhanced LRC (A2): a line a sentence, `<mm:ss.xx>` before each word; a last line, its
    end (LRC has no end). ``spaced``: a space after each tag, as Wikipedia's example has."""
    gap = " " if spaced else ""
    lines = [
        f"[{lrc_clock(s[0][1])}]{gap}" + " ".join(f"<{lrc_clock(a)}>{gap}{t}" for t, a, _ in s)
        for s in SENTENCES
    ]
    return "\n".join([*lines, f"[{lrc_clock(SENTENCES[-1][-1][2])}]"]) + "\n"


def lrc_a_line_a_word() -> str:
    """whisper-cli's `-ml 1 -olrc`: a line a word, its start alone."""
    words = [f"[{lrc_clock(a)}] {t}" for s in SENTENCES for t, a, _ in s]
    return "\n".join(["[by:whisper.cpp]", *words, ""])


def table(sep: str) -> str:
    """A row a word: whisper-cli's `-ml 1 -ocsv` (its text quoted, after a space), or a TSV in
    OpenAI's columns (whose writer puts a row a segment)."""
    if sep == ",":
        rows = [f'{a},{z}," {t}"' for s in SENTENCES for t, a, z in s]
    else:
        rows = [f"{a}\t{z}\t{t}" for s in SENTENCES for t, a, z in s]
    return "\n".join([sep.join(("start", "end", "text")), *rows, ""])


def ojf(*, dtw: bool) -> str:
    """whisper-cli's `-ojf`, the fields ffman reads: a segment a sentence, a token a word -- its
    offsets (ms), and its DTW time (centiseconds; -1 without `-dtw`)."""
    segments = [
        {
            "offsets": {"from": s[0][1], "to": s[-1][2]},
            "text": "".join(f" {t}" for t, _, _ in s),
            "tokens": [
                {"text": f" {t}", "offsets": {"from": a, "to": z}, "t_dtw": a // 10 if dtw else -1}
                for t, a, z in s
            ],
        }
        for s in SENTENCES
    ]
    return json.dumps({"result": {"language": "en"}, "transcription": segments})


def segments(*, spaced: bool = False, unaligned: bool = False) -> list[dict[str, object]]:
    """The sentences as the whisper tools' segments: times in seconds, each with its words.

    ``spaced``: each word opens with its space, as OpenAI's do;
    ``unaligned``: as WhisperX writes what its aligner could not place (`alignment.py`) -- `two`
    its word alone, the second segment no words.
    """

    def word(t: str, a: int, z: int) -> dict[str, object]:
        text = f" {t}" if spaced else t
        if unaligned and t == "two":
            return {"word": text}
        return {"word": text, "start": a / 1000, "end": z / 1000}

    return [
        {
            "start": s[0][1] / 1000,
            "end": s[-1][2] / 1000,
            "text": " ".join(t for t, _, _ in s),
            "words": [] if unaligned and k == 1 else [word(*w) for w in s],
        }
        for k, s in enumerate(SENTENCES)
    ]


def whisperx(*, unaligned: bool = False) -> str:
    """WhisperX's JSON (OpenAI's with `--word_timestamps` alike)."""
    return json.dumps({"segments": segments(unaligned=unaligned)})


ASS_HEAD = (
    "[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    # the fill red, karaoke's before-colour blue, the outline green
    "Style: Default,Arial,48,&H000000FF,&H00FF0000,&H0000FF00,&H00000000,0,0,0,0,100,100,0,0,"
    "1,{outline},0,2,10,10,20,1\n\n[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


def ass(*events: tuple[int, int, str], outline: int = 0) -> str:
    """A script of ``events``, each (start, end, text)."""
    lines = [
        f"Dialogue: 0,{ass_clock(a)},{ass_clock(z)},Default,,0,0,0,,{t}\n" for a, z, t in events
    ]
    return ASS_HEAD.replace("{outline}", str(outline)) + "".join(lines)


# each form: its file's extension and text
FORMS: dict[str, tuple[str, str]] = {
    "SubRip, a cue a sentence": ("srt", a_cue_a_sentence("srt")),
    "SubRip, a cue a word": ("srt", a_cue_a_word("srt")),
    "SubRip, --highlight_words": ("srt", highlighted("srt")),
    "WebVTT, a cue a word": ("vtt", a_cue_a_word("vtt")),
    "WebVTT, --highlight_words": ("vtt", highlighted("vtt")),
    "WebVTT, timestamps": ("vtt", stamped()),
    "WebVTT, timestamps, words in <c>": ("vtt", stamped(wrap=True)),
    "ASS, \\k": ("ass", ass(*((s[0][1], s[-1][2], karaoke(s)) for s in SENTENCES))),
    "Enhanced LRC": ("lrc", enhanced_lrc()),
    "Enhanced LRC, a space after each tag": ("lrc", enhanced_lrc(spaced=True)),
    "LRC, a line a word": ("lrc", lrc_a_line_a_word()),
    "CSV, a row a word": ("csv", table(",")),
    "TSV, a row a word": ("tsv", table("\t")),
    "whisper-cli -ojf, token offsets": ("json", ojf(dtw=False)),
    "whisper-cli -ojf -dtw": ("json", ojf(dtw=True)),
    "WhisperX JSON": ("json", whisperx()),
    "WhisperX JSON, a word and a segment unaligned": ("json", whisperx(unaligned=True)),
}


@functools.cache
def whisper_utils() -> ModuleType:
    """OpenAI whisper's `utils.py`, imported from the file."""
    spec = importlib.util.spec_from_file_location("whisper_utils", WHISPER_UTILS)
    assert spec and spec.loader
    utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils)
    return utils


def whispers(fmt: str, options: dict[str, object]) -> str:
    """What OpenAI whisper's own writer makes of the sentences, as SubRip or WebVTT."""
    utils = whisper_utils()
    result = {"segments": segments(spaced=True)}
    writer = {"srt": utils.WriteSRT, "vtt": utils.WriteVTT}[fmt](".")
    out = io.StringIO()
    unset = {"max_line_width": None, "max_line_count": None, "highlight_words": False}
    writer.write_result(result, out, unset | options)
    return out.getvalue()


# subverter's reading, then ffman's: cues and words, then chunks and words, as JSON
READ = """
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


def read_back(fmt: str, data: str) -> dict[str, Any]:
    """A form's reading by subverter and by ffman, in PYTHON."""
    r = subprocess.run([PYTHON, "-c", READ, fmt], input=data.encode(), capture_output=True,
                       check=True)  # fmt: skip
    return json.loads(r.stdout)


# a pixel's channels (0-255): ink, at least INK in one; grey and white, channels within HUE of one
# another, CSS's gray (128) at least GREY, white at least WHITE; a colour, one at least LIT and
# the others under DARK -- anti-aliased edges fall between
INK, HUE, GREY, WHITE, LIT, DARK = 64, 16, 112, 192, 128, 96


def colour(r: int, g: int, b: int) -> str | None:
    """A pixel's colour: white, grey or one channel lit; none on an edge."""
    lo, hi = min(r, g, b), max(r, g, b)
    if hi - lo <= HUE:
        return "white" if lo >= WHITE else "grey" if lo >= GREY else None
    for name, (main, other) in {"red": (r, max(g, b)), "blue": (b, max(r, g)),
                                "green": (g, max(r, b))}.items():  # fmt: skip
        if main >= LIT and other < DARK:
            return name
    return None


def dominant(word: Counter[str]) -> str:
    """A word's colour: the one most of its classed pixels have."""
    return max((k for k in word if k != "ink"), key=word.__getitem__, default="unclassed")


GAP = 6  # columns without ink between words: more than between letters, less than a space


def words_in(rgb: bytes, width: int) -> list[Counter[str]]:
    """Each word drawn in an RGB frame, left to right: its pixels' colours, counted."""
    height = len(rgb) // (3 * width)
    columns: list[Counter[str]] = []
    for x in range(width):
        found: Counter[str] = Counter()
        for y in range(height):
            i = 3 * (y * width + x)
            if max(rgb[i : i + 3]) >= INK:
                found["ink"] += 1
                name = colour(*rgb[i : i + 3])
                if name:
                    found[name] += 1
        columns.append(found)
    words: list[Counter[str]] = []
    blank = GAP
    for found in columns:
        if not found:
            blank += 1
            continue
        if blank >= GAP:
            words.append(Counter())
        words[-1] += found
        blank = 0
    return words


def raw(args: list[str]) -> bytes:
    """ffmpeg's output on ``args``."""
    return subprocess.run([FFMPEG, "-v", "error", *args], capture_output=True, check=True).stdout


# libass: the karaoke tags, each event drawn alone at the times given (ms)
KARAOKE: dict[str, tuple[str, int, tuple[int, ...]]] = {
    "\\k": (karaoke(SENTENCES[0]), 0, (999, 1000, 1499, 1500, 1799, 1800, 1999, 2000, 2999)),
    "\\kf": (karaoke(SENTENCES[0], "kf"), 0, (1000, 1250, 1499, 1500, 1650, 1800, 1900, 2000)),
    "\\ko": (karaoke(SENTENCES[0], "ko"), 3, (1000, 1499, 1500, 2000)),
    "\\k, a gap": (karaoke(SENTENCES[1]), 0, (1399, 1400, 1599, 1600)),
    # two at 1 s from the event's start, `\\kt`'s (`ass_parse.c`: centiseconds from the start)
    "\\kt": ("{\\k30}one {\\kt100}{\\k30}two", 0, (1299, 1300, 1999, 2000)),
    "\\k12.59": ("{\\k12.59}one {\\k10}two", 0, (1124, 1125, 1126)),
}


def drawn(work: Path, text: str, outline: int, times: tuple[int, ...]) -> list[str]:
    """An event's words at each time: each word's share of fill (red) of its fill and
    karaoke-colour pixels, %, and ``+o`` where its outline (green) is drawn."""
    script = work / "k.ass"
    _ = script.write_text(ass((1000, 3000, text), outline=outline), encoding="utf-8")
    # each frame at its time + 0.5 ms (time base 1/2000): the filter truncates to whole ms
    at = "0"
    for n, ms in reversed(list(enumerate(times))):
        at = f"if(eq(N,{n}),{2 * ms + 1},{at})"
    graph = f"settb=1/2000,setpts='{at}',ass='{script}',crop=640:120:0:240"
    blank = f"color=c=black:s=640x360:r=1:d={len(times)}"  # a frame a time
    frames = raw(["-f", "lavfi", "-i", blank, "-vf", graph, "-fps_mode", "passthrough",
                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])  # fmt: skip
    size = 640 * 120 * 3
    if len(frames) != size * len(times):  # a frame lost would shift every later one
        raise SystemExit(f"{len(frames) // size} frames drawn of {len(times)}")
    shown: list[str] = []
    for k in range(len(times)):
        found = words_in(frames[k * size : (k + 1) * size], 640)
        parts = [
            f"{100 * w['red'] // max(w['red'] + w['blue'], 1)}" + ("+o" if w["green"] else "")
            for w in found
        ]
        shown.append(" ".join(parts) or "nothing")
    return shown


# Chromium: a cue's words at each time, by colour -- :past red, :future blue, neither white
# (Chromium's own `video::cue(:future)`: gray, `mediaControls.css`)
PAST_FUTURE = "::cue(:past) { color: #f00 }\n::cue(:future) { color: #00f }"
TRACKS: dict[str, tuple[str, str]] = {
    "bare words, the page's CSS": (stamped(), PAST_FUTURE),
    "words in <c>, the page's CSS": (stamped(wrap=True), PAST_FUTURE),
    "words in <c>, the file's STYLE": (stamped(wrap=True, style=PAST_FUTURE), ""),
    "words in <c>, no CSS": (stamped(wrap=True), ""),
}
SEEN = (1200, 1600, 1900)  # ms: within each word of the first sentence


def seek(page: Page, ms: int) -> None:
    """The video at ``ms``, its cues drawn (two frames after the seek)."""
    page.evaluate(
        """t => new Promise(done => {
            const v = document.querySelector("video");
            const drawn = () => requestAnimationFrame(() => requestAnimationFrame(done));
            v.addEventListener("seeked", drawn, {once: true});
            v.currentTime = t;
        })""",
        ms / 1000,
    )


def browsed(work: Path) -> tuple[str, dict[str, list[str]]]:
    clip = work / "clip.webm"
    _ = raw(["-f", "lavfi", "-i", "color=c=black:s=1280x720:r=10:d=3", "-c:v", "libvpx",
             "-y", str(clip)])  # fmt: skip
    video = base64.b64encode(clip.read_bytes()).decode()
    shot = work / "shot.png"
    seen: dict[str, list[str]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for name, (vtt, css) in TRACKS.items():
            track = base64.b64encode(vtt.encode()).decode()
            css = css.replace("::cue", "video::cue")
            page.set_content(
                f"<style>body {{ margin: 0; background: #000 }} {css}</style>"
                f'<video width="1280" height="720" src="data:video/webm;base64,{video}">'
                f'<track default kind="subtitles" src="data:text/vtt;base64,{track}"></video>'
            )
            loaded = "document.querySelector('video').readyState >= 1"
            page.wait_for_function(f"{loaded} && document.querySelector('track').readyState == 2")
            seen[name] = []
            for ms in SEEN:
                seek(page, ms)
                _ = page.screenshot(
                    path=shot, clip={"x": 0, "y": 540, "width": 1280, "height": 180}
                )
                rgb = raw(["-i", str(shot), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
                found = words_in(rgb, 1280)
                seen[name].append(" ".join(dominant(w) for w in found) or "nothing")
        version = browser.version
        browser.close()
    return version, seen


def main() -> None:
    print(raw(["-version"]).decode().splitlines()[0])
    print("\n## The forms OpenAI whisper writes, against its writers\n")
    for fmt in ("srt", "vtt"):
        one = whispers(fmt, {"max_words_per_line": 1}) == a_cue_a_word(fmt)
        lit = whispers(fmt, {"highlight_words": True}) == highlighted(fmt)
        print(f"{fmt}: a cue a word {'equal' if one else 'DIFFERENT'}; "
              f"--highlight_words {'equal' if lit else 'DIFFERENT'}")  # fmt: skip
    print("\n## What ffman reads back (subverter's cues and words; ffman's chunks and words)\n")
    for name, (fmt, data) in FORMS.items():
        found = read_back(fmt, data)
        print(f"{name} (.{fmt}):")
        for reader in ("subverter", "ffman"):
            got = found[reader]
            if isinstance(got, str):
                print(f"    {reader}: {got}")
            else:
                print(f"    {reader}: {got['timed']}\n        words: {got['words'] or 'none'}")
                for note in got.get("notes", []):
                    print(f"        note: {note}")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print("\n## libass: each word's fill, % of its pixels (the rest karaoke's colour);")
        print("## +o: its outline drawn\n")
        for name, (text, outline, times) in KARAOKE.items():
            print(f"{name}: {text!r}")
            for ms, shown in zip(times, drawn(work, text, outline, times), strict=True):
                print(f"    {ms} ms: {shown}")
        version, seen = browsed(work)
        print(f"\n## Chromium {version}: each word's colour at {SEEN} ms -- :past red, :future")
        print("## blue, neither white (the page's CSS, or the file's)\n")
        for name, shown in seen.items():
            print(f"{name}: {' | '.join(shown)}")


if __name__ == "__main__":
    main()
