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

import functools
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType

import files
from files import cues, lrc_clock, vtt_clock
from frames import chromium, dominant, ffmpeg, libass, words_in
from readers import read_back

FFMPEG, PYTHON, WHISPER_UTILS = sys.argv[1], sys.argv[2], Path(sys.argv[3])

# each sentence: its words, each (text, start ms, end ms)
SENTENCES = (
    (("one", 1000, 1500), ("two", 1500, 1800), ("three", 1800, 2000)),
    (("four", 3000, 3400), ("five", 3600, 4000)),
)


def a_cue_a_sentence(fmt: str) -> str:
    """A cue a sentence, no word timed: whisper-cli's `-osrt`, OpenAI's without words."""
    return cues(fmt, [(s[0][1], s[-1][2], " ".join(t for t, _, _ in s)) for s in SENTENCES])


def a_cue_a_word(fmt: str) -> str:
    """A cue a word: OpenAI's `--max_words_per_line 1` (whisper-cli's `-ml 1 -sow` alike, each
    text after a space)."""
    return cues(fmt, [(a, z, t) for s in SENTENCES for t, a, z in s])


def highlighted(fmt: str, *, unaligned: bool = False) -> str:
    """OpenAI's and WhisperX's `--highlight_words` (`utils.py`, `iterate_result`): a cue a word,
    the sentence with that word in `<u>`; a gap between words a cue of the sentence alone.

    ``unaligned``: `two` untimed, as WhisperX 3.8.2 writes a word it left so -- no cue of its own
    (compared once with its `WriteSRT`: equal; this script runs OpenAI whisper's alone).
    """
    timed: list[tuple[int, int, str]] = []
    for s in SENTENCES:
        words = [t for t, _, _ in s]
        last = s[0][1]
        for i, (t, a, z) in enumerate(s):
            if unaligned and t == "two":
                continue
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
    ``unaligned``: what WhisperX's aligner could not place (`alignment.py`) -- `two` its word
    alone, as 3.1.0 to 3.3.2 and the releases tagged 2026-03-10 write it (3.8.3 on, a
    neighbour's times), the second segment no words, as 3.8.5 writes one it fails to align.
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


def ass(*events: tuple[int, int, str], outline: int = 0) -> str:
    """A script of ``events``, each (start, end, text), at 640x360: the fill red, karaoke's
    before-colour blue, the outline green."""
    style = (
        "Arial,48,&H000000FF,&H00FF0000,&H0000FF00,&H00000000,0,0,0,0,100,100,0,0,"
        f"1,{outline},0,2,10,10,20,1"
    )
    return files.ass(*events, size=(640, 360), style=style)


# each form: its file's extension and text
FORMS: dict[str, tuple[str, str]] = {
    "SubRip, a cue a sentence": ("srt", a_cue_a_sentence("srt")),
    "SubRip, a cue a word": ("srt", a_cue_a_word("srt")),
    "SubRip, --highlight_words": ("srt", highlighted("srt")),
    "SubRip, --highlight_words, a word unaligned": ("srt", highlighted("srt", unaligned=True)),
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
    shown: list[str] = []
    for frame in libass(FFMPEG, script, times, (640, 360)):
        parts = [
            f"{100 * w['red'] // max(w['red'] + w['blue'], 1)}" + ("+o" if w["green"] else "")
            for w in words_in(frame, 640)
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


def browsed(work: Path) -> tuple[str, dict[str, list[str]]]:
    """Chromium's version, and each track's words by colour at each time."""
    version, drawn = chromium(FFMPEG, work, TRACKS, SEEN, (1280, 720))
    seen = {
        name: [" ".join(dominant(w) for w in words_in(f, 1280)) or "nothing" for f in frames]
        for name, frames in drawn.items()
    }
    return version, seen


def main() -> None:
    print(ffmpeg(FFMPEG, "-version").decode().splitlines()[0])
    print("\n## The forms OpenAI whisper writes, against its writers\n")
    for fmt in ("srt", "vtt"):
        one = whispers(fmt, {"max_words_per_line": 1}) == a_cue_a_word(fmt)
        lit = whispers(fmt, {"highlight_words": True}) == highlighted(fmt)
        print(f"{fmt}: a cue a word {'equal' if one else 'DIFFERENT'}; "
              f"--highlight_words {'equal' if lit else 'DIFFERENT'}")  # fmt: skip
    print("\n## What ffman reads back (subverter's cues and words; ffman's chunks and words)\n")
    for name, (fmt, data) in FORMS.items():
        found = read_back(PYTHON, fmt, data)
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
