"""The whisper tools' outputs, measured: each writer run on the same transcript, its file printed;
then each file as its readers take it -- Python's json and csv, pandas, jq and ffmpeg where found,
ffman.

whisper.cpp's writers (`examples/cli/cli.cpp`: `output_txt`, `_vtt`, `_srt`, `_csv`, `_json`,
`_lrc`, and `to_timestamp` from `examples/common-whisper.cpp`) are cut from the source verbatim
and compiled against stubs that serve their segments and tokens -- no model needed; so is
`-ml`'s `whisper_wrap_segment` (`src/whisper.cpp`), run on whisper's own tokens of a sentence
(its BPE: `multilingual.tiktoken`'s ranks), and ffmpeg's `whisper` filter's writer
(`libavfilter/af_whisper.c`, its loop over a window's segments), against libavutil. OpenAI
whisper's and WhisperX's (`utils.py`: `WriteTXT`, `WriteVTT`, `WriteSRT`, `WriteTSV`,
`WriteJSON`, WhisperX's `WriteAudacity`) are imported from the file and called.

Usage: python3 measure.py WHISPER_CPP OPENAI_WHISPER WHISPERX FFMPEG [PYTHON]  (the source trees:
whisper.cpp v1.8.4, openai-whisper v20250625, WhisperX v3.8.5, FFmpeg n8.1.2 -- nixpkgs' pins;
PYTHON an interpreter that imports ffman, for its reading). Needs g++, cc and pkg-config's
libavutil (FFmpeg's headers and library); pandas, jq and ffmpeg read where found, each reader
absent said "skipped". Prints what it found; references/format.md's tables are this output. Each
`-di` run holds a 3621 s stereo PCM, about 1.4 GB: run one measurement at a time.
"""

import base64
import csv
import importlib.util
import io
import itertools
import json
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

WHISPER_CPP_SRC, OPENAI_SRC, WHISPERX_SRC, FFMPEG_SRC = (Path(a) for a in sys.argv[1:5])
PYTHON = sys.argv[5] if len(sys.argv) > 5 else None  # noqa: PLR2004 -- the four trees, then it
CLI_CPP = WHISPER_CPP_SRC / "examples/cli/cli.cpp"
COMMON_CPP = WHISPER_CPP_SRC / "examples/common-whisper.cpp"
SRC_CPP = WHISPER_CPP_SRC / "src/whisper.cpp"
TIKTOKEN = OPENAI_SRC / "whisper/assets/multilingual.tiktoken"
AF_WHISPER = FFMPEG_SRC / "libavfilter/af_whisper.c"
OUTPUTS: dict[str, bytes] = {}  # each writer's file, by a name its readers take it under

# --- whisper.cpp ------------------------------------------------------------------------------

# its segments: t0, t1 in centiseconds (whisper.cpp's unit), text as bytes; its tokens: text, id,
# p, t0, t1, t_dtw -- a partial UTF-8 character, quotes, a backslash, a tab, a newline, markup,
# times past an hour and a t_dtw past 1e6 cs
SEGMENTS = [
    (
        0,
        152,
        b' Hello "world" \\ <b>bold</b> --> arrow',
        [
            (b"[_BEG_]", 50363, 0.987654321, 0, 0, -1),
            (b" Hello", 15947, 0.5, 0, 48, 31),
            (b' "', 366, 0.00001234, 48, 60, 52),
            (b"world", 1002, 0.25, 60, 99, 80),
            (b'"', 1, 1.0, 99, 100, 99),
            (b"[_TT_76]", 50440, 0.1, 152, 152, -1),
        ],
    ),
    (
        152,
        361999,
        b" caf\xc3\xa9 \xe6\x97\xa5",
        [
            (b" caf", 11, 0.9, 152, 200, 160),
            (b"\xc3", 12, 0.9, 200, 210, 205),  # half of an e acute: tokens are bytes
            (b"\xa9", 13, 0.9, 210, 220, 215),
            (b" \xe6\x97\xa5", 14, 0.9, 220, 361999, 1234567),
        ],
    ),
    (361999, 362005, b"tab\there\nnewline", []),
]

STUBS = r"""
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#define WHISPER_SAMPLE_RATE 16000
typedef int whisper_token;
struct whisper_token_data { whisper_token id, tid; float p, plog, pt, ptsum;
                            int64_t t0, t1, t_dtw; float vlen; };
struct Tok { std::string text; whisper_token_data data; };
struct Seg { int64_t t0, t1; std::string text; std::vector<Tok> tokens; };
struct whisper_context { std::vector<Seg> segs; };
struct whisper_params { int32_t offset_n = 0; bool diarize = false, tinydiarize = false,
                        output_jsn_full = false, translate = false;
                        std::string model = "models/ggml-base.en.bin", language = "en"; };
static int whisper_full_n_segments(whisper_context *c) { return c->segs.size(); }
static const char *whisper_full_get_segment_text(whisper_context *c, int i) { return c->segs[i].text.c_str(); }
static int64_t whisper_full_get_segment_t0(whisper_context *c, int i) { return c->segs[i].t0; }
static int64_t whisper_full_get_segment_t1(whisper_context *c, int i) { return c->segs[i].t1; }
static bool whisper_full_get_segment_speaker_turn_next(whisper_context *, int) { return false; }
static int whisper_full_n_tokens(whisper_context *c, int i) { return c->segs[i].tokens.size(); }
static whisper_token_data whisper_full_get_token_data(whisper_context *c, int i, int j) { return c->segs[i].tokens[j].data; }
static const char *whisper_full_get_token_text(whisper_context *c, int i, int j) { return c->segs[i].tokens[j].text.c_str(); }
static float whisper_full_get_token_p(whisper_context *c, int i, int j) { return c->segs[i].tokens[j].data.p; }
static const char *whisper_token_to_str(whisper_context *c, whisper_token id) {
    for (auto &s : c->segs) for (auto &t : s.tokens) if (t.data.id == id) return t.text.c_str();
    return "?"; }
static const char *whisper_print_system_info() { return "SYSTEM_INFO"; }
static const char *whisper_model_type_readable(whisper_context *) { return "base"; }
static int whisper_is_multilingual(whisper_context *) { return 0; }
static int whisper_model_n_vocab(whisper_context *) { return 51864; }
static int whisper_model_n_audio_ctx(whisper_context *) { return 1500; }
static int whisper_model_n_audio_state(whisper_context *) { return 512; }
static int whisper_model_n_audio_head(whisper_context *) { return 8; }
static int whisper_model_n_audio_layer(whisper_context *) { return 6; }
static int whisper_model_n_text_ctx(whisper_context *) { return 448; }
static int whisper_model_n_text_state(whisper_context *) { return 512; }
static int whisper_model_n_text_head(whisper_context *) { return 8; }
static int whisper_model_n_text_layer(whisper_context *) { return 6; }
static int whisper_model_n_mels(whisper_context *) { return 80; }
static int whisper_model_ftype(whisper_context *) { return 1; }
static int whisper_full_lang_id(whisper_context *) { return 0; }
static const char *whisper_lang_str(int) { return "en"; }
"""

MAIN = r"""
static std::string unhex(const std::string &h) {
    std::string out; for (size_t i = 0; i + 1 < h.size(); i += 2) out += (char)std::stoi(h.substr(i, 2), nullptr, 16);
    return out; }
int main(int argc, char **argv) {
    whisper_context ctx; whisper_params params; std::string what = argv[1];
    params.diarize = argc > 2 && std::string(argv[2]) == "diarize";
    params.output_jsn_full = what == "json-full";
    std::string kind; while (std::cin >> kind) {
        if (kind == "S") { Seg s; std::string h; std::cin >> s.t0 >> s.t1 >> h; s.text = unhex(h); ctx.segs.push_back(s); }
        else { Tok t{}; std::string h; std::cin >> h >> t.data.id >> t.data.p >> t.data.t0 >> t.data.t1 >> t.data.t_dtw;
               t.text = unhex(h); ctx.segs.back().tokens.push_back(t); } }
    // -di's stereo input: channel 0 the louder, past the last segment's end (3620.05 s)
    std::vector<std::vector<float>> pcm;
    if (params.diarize) pcm = {std::vector<float>(16000 * 3621, 0.9f), std::vector<float>(16000 * 3621, 0.1f)};
    std::ofstream out("/dev/stdout");
    if (what == "txt") output_txt(&ctx, out, params, pcm);
    else if (what == "vtt") output_vtt(&ctx, out, params, pcm);
    else if (what == "srt") output_srt(&ctx, out, params, pcm);
    else if (what == "csv") output_csv(&ctx, out, params, pcm);
    else if (what == "lrc") output_lrc(&ctx, out, params, pcm);
    else output_json(&ctx, out, params, pcm);
    return 0; }
"""


def cut(source: str, start: str, end: str) -> str:
    """The source from the line starting ``start`` to the line before the one starting ``end``."""
    a = source.index(start)
    return source[a : source.index(end, a)]


def whisper_cpp(work: Path) -> Path:
    """The harness: the stubs, the writers cut from the source, a main reading segments."""
    cli = CLI_CPP.read_text(encoding="utf-8")
    common = COMMON_CPP.read_text(encoding="utf-8")
    code = "\n".join((
        STUBS,
        cut(common, "std::string to_timestamp(", "bool speak_with_file("),
        cut(cli, "static std::string estimate_diarization_speaker(", "static void whisper_print_progress_callback("),
        cut(cli, "static void output_txt(", "// karaoke video generation"),
        cut(cli, "static void output_lrc(", "static void cb_log_disable("),
        MAIN,
    ))  # fmt: skip
    # the common header's declaration gives `comma` its default: false
    code = code.replace(
        "std::string to_timestamp(int64_t t, bool comma)",
        "std::string to_timestamp(int64_t t, bool comma = false)",
    )
    src, exe = work / "writers.cpp", work / "writers"
    _ = src.write_text(code, encoding="utf-8")
    subprocess.run(["g++", "-std=c++17", "-O1", "-w", str(src), "-o", str(exe)], check=True)
    return exe


def json_reads(given: bytes | str) -> str:
    """``json.loads`` (strict) of ``given``: read, or its error."""
    try:
        _ = json.loads(given)
    except ValueError as error:  # UnicodeDecodeError and JSONDecodeError both
        return f"{type(error).__name__}: {error}"
    return "read"


def segments_input() -> str:
    lines = []
    for t0, t1, text, tokens in SEGMENTS:
        lines.append(f"S {t0} {t1} {text.hex()}")
        lines += [f"T {t.hex()} {i} {p} {a} {b} {d}" for t, i, p, a, b, d in tokens]
    return "\n".join(lines) + "\n"


# the outputs the readers take, by a name each
CLI_SAVED = {"txt": "cli.txt", "csv": "cli.csv", "json": "cli-oj.json", "json-full": "cli-ojf.json"}


def run_whisper_cpp(work: Path) -> None:
    exe = whisper_cpp(work)
    data = segments_input()
    for what in ("txt", "srt", "vtt", "csv", "lrc", "json", "json-full"):
        out = subprocess.run(
            [str(exe), what], input=data.encode(), capture_output=True, check=True
        ).stdout
        if what in CLI_SAVED:
            OUTPUTS[CLI_SAVED[what]] = out
        if what.startswith("json"):
            print(
                f"-o{what}: {json_reads(out)}; its header: {out[: out.index(b'transcription')]!r}"
            )
            out = out[out.index(b'"transcription"') :]
        print(f"-o{what}:\n{out!r}\n")
    for what in ("txt", "srt", "vtt", "csv", "lrc", "json"):
        out = subprocess.run(
            [str(exe), what, "diarize"], input=data.encode(), capture_output=True, check=True
        ).stdout
        if what in {"txt", "csv"}:
            OUTPUTS[f"cli-di.{what}"] = out
        if what == "json":
            out = out[out.index(b'"transcription"') :]
        print(f"-o{what} -di (stereo, channel 0 louder):\n{out[:600]!r}\n")


# --- whisper.cpp's -ml: whisper_wrap_segment, a segment split between tokens -----------------

# a sentence as whisper's pattern splits it (a word with its space): its tokens, BPE's
WRAPPED = (" Это", " ёлка", " и", " 😀")

WRAP_STUBS = r"""
#include <cstdint>
#include <cstdio>
#include <iostream>
#include <string>
#include <vector>
typedef int whisper_token;
struct whisper_token_data { whisper_token id; int64_t t0, t1; };
struct whisper_segment { int64_t t0, t1; std::string text; float no_speech_prob;
                         std::vector<whisper_token_data> tokens; bool speaker_turn_next; };
struct whisper_state { std::vector<whisper_segment> result_all; };
struct whisper_context { std::vector<std::string> vocab; };
static const char *whisper_token_to_str(whisper_context *c, whisper_token id) { return c->vocab[id].c_str(); }
static whisper_token whisper_token_eot(whisper_context *c) { return (whisper_token) c->vocab.size(); }
"""

WRAP_MAIN = r"""
// argv: max_len, split_on_word; stdin: a token a line, in hex, each 10 cs; out: each segment
int main(int, char **argv) {
    whisper_context ctx; whisper_state state; whisper_segment seg{0, 0, "", 0, {}, false};
    std::string h;
    while (std::cin >> h) {
        std::string b; for (size_t i = 0; i + 1 < h.size(); i += 2) b += (char) std::stoi(h.substr(i, 2), nullptr, 16);
        int64_t t = 10 * (int64_t) ctx.vocab.size();
        seg.tokens.push_back({(whisper_token) ctx.vocab.size(), t, t + 10}); ctx.vocab.push_back(b); seg.text += b; }
    seg.t1 = 10 * (int64_t) ctx.vocab.size(); state.result_all.push_back(seg);
    whisper_wrap_segment(ctx, state, std::stoi(argv[1]), std::string(argv[2]) == "1");
    for (auto &s : state.result_all) {
        for (unsigned char c : s.text) printf("%02x", c);
        printf(" %lld %lld\n", (long long) s.t0, (long long) s.t1); } }
"""


def bpe(piece: bytes, ranks: dict[bytes, int]) -> list[bytes]:
    """tiktoken's byte-pair encoding: the adjacent pair of the lowest rank merged, until none."""
    parts = [bytes([b]) for b in piece]
    while True:
        pairs = [
            (ranks[a + b], i)
            for i, (a, b) in enumerate(itertools.pairwise(parts))
            if a + b in ranks
        ]
        if not pairs:
            return parts
        _, i = min(pairs)
        parts[i : i + 2] = [parts[i] + parts[i + 1]]


def run_wrap(work: Path) -> None:
    source = SRC_CPP.read_text(encoding="utf-8")
    code = "\n".join((
        WRAP_STUBS,
        cut(source, "static inline bool should_split_on_word(", "static void whisper_exp_compute_token_level_timestamps_dtw("),
        cut(source, "static int whisper_wrap_segment(", "static const std::vector<std::string> non_speech_tokens"),
        WRAP_MAIN,
    ))  # fmt: skip
    src, exe = work / "wrap.cpp", work / "wrap"
    _ = src.write_text(code, encoding="utf-8")
    subprocess.run(["g++", "-std=c++17", "-O1", "-w", str(src), "-o", str(exe)], check=True)
    ranks = {
        base64.b64decode(token): int(rank)
        for token, rank in (line.split() for line in TIKTOKEN.read_text().splitlines() if line)
    }
    tokens = [t for word in WRAPPED for t in bpe(word.encode(), ranks)]
    print(f"{''.join(WRAPPED)!r}, whisper's tokens: {tokens!r}")
    for max_len, sow in (("1", "0"), ("1", "1"), ("16", "0")):
        run = subprocess.run(
            [str(exe), max_len, sow],
            input="\n".join(t.hex() for t in tokens).encode(),
            capture_output=True,
            check=True,
        )
        segments = [bytes.fromhex(line.split()[0]) for line in run.stdout.decode().splitlines()]
        print(f"-ml {max_len}{' -sow' if sow == '1' else ''}: {segments!r}")
    print()


# --- OpenAI whisper and WhisperX --------------------------------------------------------------


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def segment(
    i: int, start: float, end: float, text: str, words: list[dict[str, object]] | None = None
) -> dict[str, object]:
    """OpenAI whisper's segment, as `transcribe` makes it (its keys, in its order)."""
    s: dict[str, object] = {"id": i, "seek": 0, "start": start, "end": end, "text": text,
                            "tokens": [50364, 2425], "temperature": 0.0, "avg_logprob": -0.25,
                            "compression_ratio": 1.2, "no_speech_prob": 0.01}  # fmt: skip
    if words is not None:
        s["words"] = words
    return s


OPENAI = {
    "text": " Hello world.",
    "segments": [
        segment(0, 0.0, 1.0005, " Hello <b>world</b> --> arrow\twith tab"),
        segment(1, 1.0015, 2.675, " café 日本"),
        segment(2, 3599.9995, 3725.5, " past an hour\nnewline"),
    ],
    "language": "en",
}
OPENAI_WORDS = {
    "text": " Hello world.",
    "segments": [
        segment(0, 0.0, 2.0, " Hello world.", [
            {"word": " Hello", "start": 0.0, "end": 0.5, "probability": 0.9},
            {"word": " world.", "start": 0.62, "end": 1.4, "probability": 0.8},
        ]),
        segment(1, 2.5, 4.0, " Again here.", [
            {"word": " Again", "start": 2.5, "end": 3.0, "probability": 0.9},
            {"word": " here.", "start": 3.1, "end": 3.9, "probability": 0.9},
        ]),
    ],
    "language": "en",
}  # fmt: skip
# a text opening with a quote, one quote open over three; one "NA"
QUOTED = (' "Stop," he said.', ' "Wait', " and then", ' he left."', " NA", " End.")
OPENAI_QUOTED = {
    "text": "",
    "segments": [segment(i, i, i + 1, text) for i, text in enumerate(QUOTED)],
    "language": "en",
}
WHISPERX = {
    "segments": [
        {"start": 0.031, "end": 1.4, "text": " Hello world.", "words": [
            {"word": "Hello", "start": 0.031, "end": 0.5, "score": 0.9, "speaker": "SPEAKER_00"},
            {"word": "world.", "start": 0.62, "end": 1.4, "score": 0.8, "speaker": "SPEAKER_00"},
        ], "speaker": "SPEAKER_00"},
        {"start": 2.5, "end": 3.9, "text": " 2024 again.", "words": [
            {"word": "2024"},  # unalignable: no start, end or score
            {"word": "again.", "start": 3.1, "end": 3.9, "score": 0.7},
        ]},
    ],
    "word_segments": [],
    "language": "en",
}  # fmt: skip
WHISPERX_JA = {
    "segments": [{"start": 0.0, "end": 1.0, "text": "日本語です", "words": [
        {"word": "日", "start": 0.0, "end": 0.2, "score": 0.9},
        {"word": "本", "start": 0.2, "end": 0.4, "score": 0.9},
    ]}],
    "language": "ja",
}  # fmt: skip
WHISPERX_UNALIGNED = {  # --no_align: transcribe's own segments (asr.py), times round(x, 3)
    "segments": [{"text": " Hello world.", "start": 0.031, "end": 1.4}],
    "language": "en",
}
WHISPERX_NAN = {
    "segments": [{"start": float("nan"), "end": 1.0, "text": " nan", "words": []}],
    "language": "en",
}


def write(writer: object, result: dict[str, object], options: dict[str, object] | None) -> str:
    out = io.StringIO()
    if options is None:
        writer.write_result(result, file=out)  # type: ignore[attr-defined]
    else:
        writer.write_result(result, file=out, options=options)  # type: ignore[attr-defined]
    return out.getvalue()


# the cases whose JSON and TSV the readers take, by a name each
SAVED = {("whisper", "segments"): "openai", ("whisper", "words"): "openai-words",
         ("whisper", "quoted"): "openai-quoted", ("whisperx", "aligned"): "whisperx",
         ("whisperx", "NaN"): "whisperx-nan"}  # fmt: skip


def run_python() -> None:
    whisper = load(OPENAI_SRC / "whisper/utils.py", "whisper_utils")
    whisperx = load(WHISPERX_SRC / "whisperx/utils.py", "whisperx_utils")
    plain = {"max_line_width": None, "max_line_count": None, "highlight_words": False}
    lit = plain | {"highlight_words": True}
    wrapped = {"max_line_width": 8, "max_line_count": 1, "highlight_words": False}
    for tool, mod, cases in (
        ("whisper", whisper, [("segments", OPENAI, None), ("quoted", OPENAI_QUOTED, None),
                              ("words", OPENAI_WORDS, None),
                              ("words --highlight_words", OPENAI_WORDS, {"highlight_words": True}),
                              ("words --max_line_width 8 --max_line_count 1", OPENAI_WORDS,
                               {"max_line_width": 8, "max_line_count": 1})]),
        ("whisperx", whisperx, [("aligned", WHISPERX, plain), ("aligned --highlight_words", WHISPERX, lit),
                                ("aligned --max_line_width 8 --max_line_count 1", WHISPERX, wrapped),
                                ("ja", WHISPERX_JA, plain), ("--no_align", WHISPERX_UNALIGNED, plain),
                                ("NaN", WHISPERX_NAN, plain)]),
    ):  # fmt: skip
        writers = [
            n
            for n in ("WriteTXT", "WriteSRT", "WriteVTT", "WriteTSV", "WriteJSON", "WriteAudacity")
            if hasattr(mod, n)
        ]
        for case, result, options in cases:
            for name in writers:
                if case == "quoted":
                    if name != "WriteTSV":
                        continue  # its readers' case: its TSV alone
                elif case != cases[0][0] and name in {"WriteTXT", "WriteTSV", "WriteAudacity"}:
                    continue  # segment writers: the first case says it
                if case.startswith(("ja", "--no_align", "NaN")) and name not in {
                    "WriteSRT",
                    "WriteJSON",
                }:
                    continue
                writer = getattr(mod, name)(".")
                try:
                    text = write(writer, result, options)
                except Exception as error:  # noqa: BLE001 -- the writer's own failure is the finding
                    text = f"{type(error).__name__}: {error}"
                print(f"{tool} {name} [{case}]:\n{text!r}\n")
                if (tool, case) in SAVED and name in {"WriteJSON", "WriteTSV"}:
                    ext = "json" if name == "WriteJSON" else "tsv"
                    OUTPUTS[f"{SAVED[tool, case]}.{ext}"] = text.encode("utf-8")
                if case == cases[0][0] and name in {"WriteTXT", "WriteAudacity"}:
                    ext = "txt" if name == "WriteTXT" else "aud"
                    OUTPUTS[f"{tool}.{ext}"] = text.encode("utf-8")
    for seconds in (1.0005, 1.0015, 0.0005, 2.675):  # round(seconds * 1000): ties to even
        print(f"format_timestamp({seconds}) -> {whisper.format_timestamp(seconds)}"
              f" ({seconds} * 1000.0 = {seconds * 1000.0!r})")  # fmt: skip


# --- ffmpeg's whisper filter: its writer, a window's segments as text, SubRip or JSON ----------

# a window's segments, as whisper.cpp gives them: t0, t1 in cs, text (whisper_full's)
FILTERED = [
    (0, 152, ' Hello "world" \\ <b>bold</b>'),
    (152, 300, " [BLANK_AUDIO]"),
    (300, 420, "[blank_audio] tab\there\nnewline"),
    (420, 500, " caf\u00e9"),
]
WINDOWS = "0,5000"  # two windows' starts, ms: the queue's next window, its times offset
PLAIN = [(0, 152, " Hello"), (152, 300, " again")]  # no `"`, no break: its lines JSON each

AF_STUBS = r"""
#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "libavutil/avstring.h"
#include "libavutil/log.h"
#include "libavutil/mem.h"
typedef struct { int64_t t0, t1; char *text; } Seg;
static Seg segs[64];
static int n_segs;
typedef struct { void *ctx_wsp; int max_len; void *avio_context; char *format; int index; } WhisperContext;
static const char *whisper_full_get_segment_text(void *c, int i) { return segs[i].text; }
static bool whisper_full_get_segment_speaker_turn_next(void *c, int i) { return false; }
static int64_t whisper_full_get_segment_t0(void *c, int i) { return segs[i].t0; }
static int64_t whisper_full_get_segment_t1(void *c, int i) { return segs[i].t1; }
static void avio_write(void *s, const void *buf, int size) { fwrite(buf, 1, size, stdout); }
static void run(void *ctx, WhisperContext *wctx, int64_t timestamp_ms) {
    const int n_segments = n_segs;
    char *segments_text = NULL;
"""

AF_MAIN = r"""
    av_freep(&segments_text);
}
// argv: the format, the windows' starts (ms, comma-separated); stdin: t0 t1 hex-text a line
int main(int argc, char **argv) {
    WhisperContext w = {NULL, 0, (void *) 1, argv[1], 0};
    long long t0, t1; char hex[4096];
    while (n_segs < 64 && scanf("%lld %lld %4095s", &t0, &t1, hex) == 3) {
        size_t len = strlen(hex) / 2; char *text = calloc(len + 1, 1);
        for (size_t i = 0; i < len; i++) sscanf(hex + 2 * i, "%2hhx", &text[i]);
        segs[n_segs++] = (Seg) {t0, t1, text};
    }
    for (char *start = strtok(argv[2], ","); start; start = strtok(NULL, ","))
        run(NULL, &w, atoll(start));
    return 0;
}
"""


def run_filter(work: Path) -> None:
    """The filter's writer: its loop over a window's segments, cut verbatim, against libavutil."""
    source = AF_WHISPER.read_text(encoding="utf-8")
    loop = cut(source, "    for (int i = 0; i < n_segments; ++i) {", "    AVDictionary **metadata")
    src, exe = work / "af_whisper.c", work / "af_whisper"
    _ = src.write_text(AF_STUBS + loop + AF_MAIN, encoding="utf-8")
    flags = subprocess.run(["pkg-config", "--cflags", "--libs", "libavutil"], capture_output=True,
                           text=True, check=True).stdout.split()  # fmt: skip
    subprocess.run(["cc", "-std=c11", "-w", str(src), "-o", str(exe), *flags], check=True)
    data = "".join(f"{a} {b} {t.encode().hex()}\n" for a, b, t in FILTERED)
    print(f"ffmpeg's whisper filter, cut from {AF_WHISPER}; windows at {WINDOWS} ms\n")
    for fmt in ("text", "srt", "json"):
        out = subprocess.run([str(exe), fmt, WINDOWS], input=data.encode(), capture_output=True,
                             check=True).stdout  # fmt: skip
        if fmt != "text":
            OUTPUTS[f"filter.{fmt}"] = out
        print(f"format={fmt}:\n{out!r}\n")
    plain = "".join(f"{a} {b} {t.encode().hex()}\n" for a, b, t in PLAIN)
    out = subprocess.run([str(exe), "json", "0"], input=plain.encode(), capture_output=True,
                         check=True).stdout  # fmt: skip
    OUTPUTS["filter-plain.json"] = out
    print(f"format=json, texts of no quote or break:\n{out!r}\n")


# --- the readers: each file above as Python's json and csv, pandas, jq, ffmpeg and ffman take it --


def python_reads(name: str, data: bytes, *, unquoted: bool = False) -> str:
    """Python's own reader: ``json.loads`` (strict; its bytes' encoding detected, then its text),
    or ``csv`` on the UTF-8 text -- ``unquoted``, a TSV's with ``quoting=csv.QUOTE_NONE``."""
    kind = name.rsplit(".", 1)[1]
    if kind not in {"json", "csv", "tsv"} or (unquoted and kind != "tsv"):
        return ""
    if kind == "json":  # its bytes, and its text decoded as UTF-8 (``json.load(open(path))``)
        given = json_reads(data)
        try:
            text = json_reads(data.decode("utf-8"))
        except UnicodeDecodeError as error:
            text = f"UnicodeDecodeError: {error}"
        return given if given == text else f"bytes {given}; text {text}"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        return f"{type(error).__name__}: {error}"
    quoting = csv.QUOTE_NONE if unquoted else csv.QUOTE_MINIMAL
    delimiter = "\t" if kind == "tsv" else ","
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quoting=quoting))
    texts = [r[-1] for r in rows[1:] if len(r) > 1]
    return (f"{len(rows)} rows of {sorted({len(r) for r in rows})} fields, header {rows[0]!r},"
            f" texts {texts!r}")  # fmt: skip


def pandas_reads(name: str, data: bytes, *, advised: bool = False) -> str:
    """pandas' ``read_csv`` (a TSV's ``sep``), its defaults otherwise: what it makes of the file;
    ``advised``, as the skill reads one: ``keep_default_na=False``, a TSV's ``quoting=QUOTE_NONE``."""
    kind = name.rsplit(".", 1)[1]
    if kind not in {"csv", "tsv"}:
        return ""
    try:
        import pandas as pd  # noqa: PLC0415 -- a reader of its own, where installed
    except ImportError:
        return "skipped: pandas not installed"
    options: dict[str, object] = {"keep_default_na": False} if advised else {}
    if advised and kind == "tsv":
        options["quoting"] = csv.QUOTE_NONE
    try:
        frame = pd.read_csv(io.BytesIO(data), sep="\t" if kind == "tsv" else ",", **options)
    except Exception as error:  # noqa: BLE001 -- the reader's own failure is the finding
        return f"{type(error).__name__}: {str(error).splitlines()[0]}"
    return f"{frame.shape[0]} rows: {frame.to_dict('records')!r}"


def jq_reads(name: str, data: bytes) -> str:
    """jq: each JSON value it reads, or its error."""
    if not name.endswith(".json"):
        return ""
    jq = shutil.which("jq")
    if jq is None:
        return "skipped: jq not found"
    texts = (  # what it reads of the texts (and WhisperX's times): the readings that differ
        'if has("transcription") then [.transcription[] | .text, (.tokens[]?.text)]'
        ' elif has("segments") then [.segments[] | .start, .text] else [.start, .text] end'
    )
    r = subprocess.run([jq, "-c", texts], input=data, capture_output=True, check=False)
    if r.returncode:
        return f"exit {r.returncode}: {r.stderr.decode(errors='replace').strip()}"
    values = r.stdout.decode().splitlines()  # what it read of the texts and times, in brief
    return f"{len(values)} values, " + " ".join(f"{v[:200]!r}" for v in values)


def ffmpeg_reads(name: str, data: bytes, work: Path) -> str:
    """ffmpeg: the demuxer that opens the file under its name and the cues it converts to SubRip;
    or its error."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return "skipped: ffmpeg not found"
    path = work / name
    _ = path.write_bytes(data)
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path), "-f", "srt", "-"],
                       capture_output=True, text=True, check=False)  # fmt: skip
    opened = re.search(r"Input #0, (\w+)", r.stderr)
    if opened is None:
        return r.stderr.strip().splitlines()[-1].replace(str(path), name)
    if r.returncode:  # opened, but no subtitle stream to convert
        return f"opened as {opened[1]}: {r.stderr.strip().splitlines()[-1]}"
    return f"opened as {opened[1]}: {r.stdout.count(' --> ')} cues"


FFMAN_PROBE = """
import json, sys
from ffman.errors import REFUSALS
from ffman.subs.ingest import ingest
for name, hexed in json.load(sys.stdin).items():
    try:
        t = ingest(name, bytes.fromhex(hexed))
        found = {"chunks": [(c.start, c.end, c.text) for c in t.chunks],
                 "words": len(t.words), "notes": list(t.notes)}
    except REFUSALS as e:
        found = {"refused": str(e), "notes": list(getattr(e, "notes", ()))}
    print(json.dumps([name, found]))
"""


def ffman_reads() -> dict[str, object]:
    """ffman's reading of each file, in PYTHON: its chunks, words and notes, or its refusal."""
    if PYTHON is None:
        return {}
    files = {name: data.hex() for name, data in OUTPUTS.items()}
    r = subprocess.run([PYTHON, "-c", FFMAN_PROBE], input=json.dumps(files).encode(),
                       capture_output=True, check=True)  # fmt: skip
    return dict(json.loads(line) for line in r.stdout.decode().splitlines())


def encodings() -> None:
    """A writer's file with a UTF-8 BOM, and in UTF-16 (its BOM): the readers' encodings. And
    ``-ojf``'s with its raw tab and newline escaped: its bytes alone not UTF-8."""
    raw = OUTPUTS["cli-ojf.json"]
    OUTPUTS["cli-ojf-escaped.json"] = raw.replace(b"tab\there\nnewline", b"tab\\there\\nnewline")
    for name in ("cli.csv", "whisperx.tsv", "whisperx.json"):
        stem, ext = name.rsplit(".", 1)
        text = OUTPUTS[name].decode("utf-8")
        OUTPUTS[f"{stem}-bom.{ext}"] = "\ufeff".encode() + OUTPUTS[name]
        OUTPUTS[f"{stem}-utf16.{ext}"] = ("\ufeff" + text).encode("utf-16-le")


def rule_three() -> None:
    """A CSV as the skill's rule 3 writes one (``csv.writer``), of the quoted TSV's texts."""
    out = io.StringIO()
    rows = [(1000 * i, 1000 * (i + 1), text.strip()) for i, text in enumerate(QUOTED)]
    csv.writer(out, lineterminator="\n").writerows([("start", "end", "text"), *rows])
    OUTPUTS["rule-3.csv"] = out.getvalue().encode("utf-8")


def run_readers() -> None:
    print("\n## The readers: Python's json (strict) and csv, pandas, jq, ffmpeg, ffman\n")
    encodings()
    rule_three()
    ffman = ffman_reads()
    if PYTHON is None:
        print("ffman: skipped, no PYTHON\n")
    with tempfile.TemporaryDirectory() as tmp:
        for name, data in OUTPUTS.items():
            print(f"{name}:")
            for reader, found in (
                ("python", python_reads(name, data)),
                ("python, QUOTE_NONE", python_reads(name, data, unquoted=True)),
                ("pandas", pandas_reads(name, data)),
                ("pandas, as advised", pandas_reads(name, data, advised=True)),
                ("jq", jq_reads(name, data)),
                ("ffmpeg", ffmpeg_reads(name, data, Path(tmp))),
            ):
                if found:
                    print(f"    {reader}: {found}")
            if name in ffman:
                print(f"    ffman: {ffman[name]!r}")


# --- the skill, checked from its own text: its example, its time rule ---------------------------

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
# what the skill states of its example (SKILL.md, "Example"): ffman's sentences and words, in ms
EXAMPLE_CHUNKS = [(512, 2004, "Good morning, everyone."), (2500, 3800, "Room 101 is open.")]
EXAMPLE_WORDS = [(512, 730, "Good"), (750, 1210, "morning,"), (1300, 2004, "everyone."),
                 (2500, 2800, "Room"), (2800, 3100, "101"), (3100, 3200, "is"),
                 (3250, 3800, "open.")]  # fmt: skip
EXAMPLE_NOTES = [
    "1 words had no usable time of their own (untimed, tied, out of order or outside their"
    " sentence): placed between their neighbours"
]
# the time rule's edges, each its ms by hand: ties at the ms (a negative one up, toward +inf, as
# ffman), a float under or over its decimal
EDGES = {"0": 0, "0.0005": 1, "0.0004999": 0, "1.0005": 1001, "1.0015": 1002, "2.675": 2675,
         "3599.9995": 3600000, "0.0015": 2, "1e-3": 1, "2": 2000, "-0.0005": 0,
         "-1.0005": -1000}  # fmt: skip
# what JSON's grammar refuses but Fraction or Decimal would read, what is no number at all, and
# exponents past 10^±400 (their bound: unbounded, 1e999999999 builds a billion-digit integer)
NOT_NUMBERS = ["1/2", "1_0", " 2.5", "+1", ".5", "NaN", "Infinity", "", True, None, float("nan"),
               "1e401", "1e-401"]  # fmt: skip

READ_EXAMPLE = """
import json, sys
from ffman.subs.ingest import ingest
t = ingest("x.json", sys.stdin.buffer.read())
print(json.dumps({"chunks": [(c.start, c.end, c.text) for c in t.chunks],
                  "words": [(w.start, w.end, w.text) for w in t.words], "notes": list(t.notes)}))
"""
READ_STARTS = """
import json, sys
import subverter
print(json.dumps([c.start for c in subverter.read("json", sys.stdin.buffer.read(), "x.json").cues]))
"""


def fenced(text: str, lang: str) -> list[str]:
    """The skill's code blocks in ``lang``, as written (a list item's indentation off)."""
    found = re.finditer(rf"^( *)```{lang}\n(.*?)^\1```$", text, re.MULTILINE | re.DOTALL)
    return [textwrap.dedent(m[2]) for m in found]


def attempt(rule: Callable[..., object], *args: object) -> object:
    """``rule(*args)``, or its failure -- the skill's code run as written, a failure the finding."""
    try:
        return rule(*args)
    except Exception as error:  # noqa: BLE001 -- the rule's own failure is the finding
        return f"{type(error).__name__}: {error}"


def checked(what: str, found: object, stated: object) -> bool:
    """One of the skill's claims against its measurement, printed either way."""
    print(f"{'ok' if found == stated else 'MISMATCH'}: {what}: {found!r}")
    if found != stated:
        print(f"    stated: {stated!r}")
    return found == stated


def skill() -> bool:
    """The skill's example read by Python's json, jq and ffman; its time rule by hand and against
    ffman's."""
    print("\n## The skill, checked from its own text\n")
    text = SKILL.read_text(encoding="utf-8")
    example = fenced(text, "json")[0].encode()
    results = [checked("the example, Python's json", python_reads("x.json", example), "read")]
    if shutil.which("jq"):
        results.append(checked("    jq", jq_reads("x.json", example).split(",")[0], "1 values"))
    else:
        print("skipped: the example, jq: not found")
    if PYTHON:
        r = subprocess.run([PYTHON, "-c", READ_EXAMPLE], input=example, capture_output=True,
                           check=False)  # fmt: skip
        if r.returncode:
            error = r.stderr.decode(errors="replace").strip().splitlines()[-1:]
            results.append(checked("    ffman", error, []))
        else:
            read = json.loads(r.stdout)
            results.append(checked("    ffman's sentences", [tuple(c) for c in read["chunks"]],
                                   EXAMPLE_CHUNKS))  # fmt: skip
            results.append(checked("    its words", [tuple(w) for w in read["words"]],
                                   EXAMPLE_WORDS))  # fmt: skip
            results.append(checked("    its notes", read["notes"], EXAMPLE_NOTES))
    else:
        print("skipped: the example, ffman: no PYTHON")

    space: dict[str, object] = {}
    exec(fenced(text, "python")[0], space)  # noqa: S102 -- the skill's own rule, run as written
    to_ms, transcript = space.get("to_ms"), space.get("transcript")
    if not callable(to_ms) or not callable(transcript):
        print(f"MISMATCH: the rule's to_ms and transcript: {to_ms!r}, {transcript!r}")
        return False
    edges = {s: attempt(to_ms, s) for s in EDGES}
    results.append(checked("the time rule, its edges", edges, EDGES))
    # the skill's reader on a raw tab, its numbers as written
    parsed = attempt(transcript, '{"start": 1.0005, "end": 2, "text": "a\tb"}')
    times = (
        [attempt(to_ms, parsed[k]) for k in ("start", "end")]
        if isinstance(parsed, dict)
        else parsed
    )
    results.append(checked("    read by its transcript()", times, [1001, 2000]))
    results.append(checked("    1.0005 as a float", attempt(to_ms, 1.0005), 1000))
    refused = [x for x in NOT_NUMBERS if isinstance(attempt(to_ms, x), int)]
    results.append(checked("    no time for what is no JSON number", refused, []))
    every = [*EDGES, *(f"{k // 10000}.{k % 10000:04d}" for k in range(0, 4_000_000, 997))]
    ruled = [attempt(to_ms, s) for s in every]
    floats = sum(round(1000 * float(s)) != ms for s, ms in zip(every, ruled, strict=True))
    what = f"    {len(every)} times; round(1000 * t) differs on"
    results.append(checked(what, found=floats > 0, stated=True))
    print(f"    {floats} of them, 1.0005 s: {round(1000 * 1.0005)} against {edges['1.0005']}")
    if PYTHON:
        doc = (
            '{"segments": ['
            + ", ".join(f'{{"start": {s}, "end": {s}, "text": "x"}}' for s in every)
            + "]}"
        )
        r = subprocess.run([PYTHON, "-c", READ_STARTS], input=doc.encode(), capture_output=True,
                           check=True)  # fmt: skip
        what = "    ffman reads each as the rule writes it"
        results.append(checked(what, json.loads(r.stdout) == ruled, stated=True))
    else:
        print("skipped: the time rule, ffman: no PYTHON")
    results.append(checked("missing from the prose", missing(text), []))
    return all(results)


def missing(text: str) -> list[str]:
    """What the skill's prose must say of its example, from the measured values: those missing."""
    prose = " ".join(text.split())
    count = ["", "one", "two", "three", "four", "five", "six", "seven"]
    said = [f"`{t}` from {a / 1000:g} s to {z / 1000:g} s" for a, z, t in EXAMPLE_CHUNKS]
    said.append(f"{count[len(EXAMPLE_CHUNKS)]} sentences")
    late = next(w for w in EXAMPLE_WORDS if w[2] == "101")
    said.append(
        f"`101` is placed between its neighbours, {late[0] / 1000:g} s to {late[1] / 1000:g} s"
    )
    said.append(f"{count[len(EXAMPLE_WORDS)]} words")
    return [x for x in said if x not in prose]


def main() -> None:
    print(f"whisper.cpp's writers, cut from {CLI_CPP}\n")
    with tempfile.TemporaryDirectory() as tmp:
        run_whisper_cpp(Path(tmp))
        run_wrap(Path(tmp))
        run_filter(Path(tmp))
    run_python()
    run_readers()
    if not skill():
        sys.exit(1)


if __name__ == "__main__":
    main()
