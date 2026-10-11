"""The whisper tools' outputs, measured: each writer run on the same transcript, its file printed.

whisper.cpp's writers (`examples/cli/cli.cpp`: `output_txt`, `_vtt`, `_srt`, `_csv`, `_json`,
`_lrc`, and `to_timestamp` from `examples/common-whisper.cpp`) are cut from the source verbatim
and compiled against stubs that serve their segments and tokens -- no model needed. OpenAI
whisper's and WhisperX's (`utils.py`: `WriteTXT`, `WriteVTT`, `WriteSRT`, `WriteTSV`,
`WriteJSON`, WhisperX's `WriteAudacity`) are imported from the file and called.

Usage: python3 measure.py CLI_CPP COMMON_WHISPER_CPP WHISPER_UTILS_PY WHISPERX_UTILS_PY
(whisper.cpp v1.8.4, openai-whisper v20250625, WhisperX v3.8.5: nixpkgs' pins). Needs g++.
Prints what it found; references/format.md's tables are this output.
"""

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType

CLI_CPP, COMMON_CPP, WHISPER_UTILS, WHISPERX_UTILS = (Path(a) for a in sys.argv[1:5])

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


def json_verdict(out: bytes) -> str:
    """Whether the bytes are JSON a strict reader takes: UTF-8, no raw control character."""
    try:
        _ = json.loads(out.decode("utf-8"))
    except UnicodeDecodeError as error:
        return f"not UTF-8 ({error.reason} at byte {error.start})"
    except json.JSONDecodeError as error:
        return f"not JSON ({error.msg} at line {error.lineno} column {error.colno})"
    return "valid JSON"


def segments_input() -> str:
    lines = []
    for t0, t1, text, tokens in SEGMENTS:
        lines.append(f"S {t0} {t1} {text.hex()}")
        lines += [f"T {t.hex()} {i} {p} {a} {b} {d}" for t, i, p, a, b, d in tokens]
    return "\n".join(lines) + "\n"


def run_whisper_cpp(work: Path) -> None:
    exe = whisper_cpp(work)
    data = segments_input()
    for what in ("txt", "srt", "vtt", "csv", "lrc", "json", "json-full"):
        out = subprocess.run(
            [str(exe), what], input=data.encode(), capture_output=True, check=True
        ).stdout
        if what.startswith("json"):
            print(
                f"-o{what}: {json_verdict(out)}; its header: {out[: out.index(b'transcription')]!r}"
            )
            out = out[out.index(b'"transcription"') :]
        print(f"-o{what}:\n{out!r}\n")
    for what in ("txt", "srt", "vtt", "csv", "lrc", "json"):
        out = subprocess.run(
            [str(exe), what, "diarize"], input=data.encode(), capture_output=True, check=True
        ).stdout
        if what == "json":
            out = out[out.index(b'"transcription"') :]
        print(f"-o{what} -di (stereo, channel 0 louder):\n{out[:600]!r}\n")


# --- OpenAI whisper and WhisperX --------------------------------------------------------------


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
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


def run_python() -> None:
    whisper = load(WHISPER_UTILS, "whisper_utils")
    whisperx = load(WHISPERX_UTILS, "whisperx_utils")
    plain = {"max_line_width": None, "max_line_count": None, "highlight_words": False}
    lit = plain | {"highlight_words": True}
    wrapped = {"max_line_width": 8, "max_line_count": 1, "highlight_words": False}
    for tool, mod, cases in (
        ("whisper", whisper, [("segments", OPENAI, None), ("words", OPENAI_WORDS, None),
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
                if case != cases[0][0] and name in {"WriteTXT", "WriteTSV", "WriteAudacity"}:
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
    for seconds in (1.0005, 1.0015, 0.0005, 2.675):  # round(seconds * 1000): ties to even
        print(f"format_timestamp({seconds}) -> {whisper.format_timestamp(seconds)}"
              f" ({seconds} * 1000.0 = {seconds * 1000.0!r})")  # fmt: skip


def main() -> None:
    print(f"whisper.cpp's writers, cut from {CLI_CPP}\n")
    with tempfile.TemporaryDirectory() as tmp:
        run_whisper_cpp(Path(tmp))
    run_python()


if __name__ == "__main__":
    main()
