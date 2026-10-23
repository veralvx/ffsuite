"""whisper JSON against its rules (``readers/whisper.py``, docs/decisions.md's rows): whisper-cli's
offsets and tokens, OpenAI whisper's and WhisperX's seconds and words, each value as typed; its
refusals.

Every expectation is worked by hand from a rule, not taken from a run: what a reader yields
before ffman's normalising (no trim, no sort, no clamp, no cue dropped).
"""

import json
import re
from typing import Final

import pytest
import subverter
from subverter import Cue, Reading, Timing

_NUL_NOTE: Final = "{n} NULs read as U+FFFD, as the W3C reads them: the first in {where}"

# --- whisper JSON: refused unless whisper-cli's, OpenAI whisper's or WhisperX's

_NOT_A_TRANSCRIPT: Final = (
    "not a whisper-cli (.transcription), OpenAI whisper or WhisperX (.segments) JSON transcript"
)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"{", "not valid JSON"),
        # closed: an unclosed one is invalid JSON too, which a machine whose parser holds
        # 100000 levels reports first
        pytest.param(
            b"[" * 100_000 + b"]" * 100_000,
            "JSON nested too deeply to be a transcript",
            id="100000 deep",
        ),
        pytest.param(
            b"[" * 1001 + b"]" * 1001, "JSON nested too deeply to be a transcript", id="1001 deep"
        ),
        pytest.param(b"[" * 1000 + b"]" * 1000, _NOT_A_TRANSCRIPT, id="1000 deep"),
        (b"[]", _NOT_A_TRANSCRIPT),
        (b"5", _NOT_A_TRANSCRIPT),
        (b'{"transcription": [{"tokens": [{"text": 5}]}]}', "unreadable whisper-cli -ojf JSON"),
    ],
)
def test_a_json_not_a_transcript_is_refused(data: bytes, message: str) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}: a\\.json$"):
        _ = subverter.read("json", data, "a.json")


def test_json_past_the_parsers_stack_is_refused_as_too_deep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # the machine's limit, wherever it falls: a RecursionError from json.loads itself
    def out_of_stack(*_args: object, **_kwargs: object) -> object:
        raise RecursionError

    monkeypatch.setattr(json, "loads", out_of_stack)
    message = "JSON nested too deeply to be a transcript: a.json"
    with pytest.raises(subverter.Error, match=f"^{re.escape(message)}$"):
        _ = subverter.read("json", b"[]", "a.json")


# --- whisper-cli: offsets in ms; with -ojf, words from tokens, DTW times where they hold


def _cli(entries: list[object], language: str = "en") -> bytes:
    return json.dumps({"result": {"language": language}, "transcription": entries}).encode()


def test_whisper_cli_without_tokens_is_cues_alone_their_text_as_written() -> None:
    data = _cli([{"offsets": {"from": 0, "to": 1500}, "text": " Hi"}])
    assert subverter.read("json", data, "a.json") == Reading(
        "whisper-cli JSON", has_words=False, cues=(Cue(0, 1500, " Hi", "0"),)
    )


def _token(text: object, start: int, end: int, dtw: object = None) -> dict[str, object]:
    token: dict[str, object] = {"text": text, "offsets": {"from": start, "to": end}}
    if dtw is not None:
        token["t_dtw"] = dtw
    return token


def test_words_from_tokens_timed_by_dtw_where_inside_and_in_order() -> None:
    # " He" + "llo" one word (a leading space starts one); [_TT_] skipped; t_dtw in 10 ms units
    tokens = [_token(" He", 0, 200, 5), _token("llo", 200, 400, 15), _token(" world", 400, 900, 50)]
    tokens.append(_token("[_TT_150]", 900, 1000))
    data = _cli([{"offsets": {"from": 0, "to": 1000}, "text": " Hello world", "tokens": tokens}])
    reading = subverter.read("json", data, "a.json")
    assert (reading.source, reading.has_words, reading.notes) == ("whisper-cli -ojf JSON", True, ())
    # each word from its DTW time to the next's; the last to the sentence's end
    assert reading.words == (Timing("0", 50, 500, " Hello"), Timing("0", 500, 1000, " world"))


def test_dtw_out_of_order_falls_back_to_the_offsets_and_says_so() -> None:
    tokens = [_token(" one", 0, 400, 60), _token(" two", 400, 900, 20)]  # 600 ms, then 200: back
    data = _cli([{"offsets": {"from": 0, "to": 1000}, "text": " one two", "tokens": tokens}])
    reading = subverter.read("json", data, "a.json")
    assert reading.words == (Timing("0", 0, 400, " one"), Timing("0", 400, 900, " two"))
    assert reading.notes == (
        "DTW word times were outside their sentence or not in order in 1 of 1 sentences: used token offsets there",
    )


@pytest.mark.parametrize(
    "window",
    [
        {"from": None, "to": 900},
        {"from": 0, "to": "zz"},
        {"from": 900, "to": 100},
        {"from": 500, "to": 500},
        {"from": -900, "to": 0},
    ],
    ids=["no start", "no end", "ending before it begins", "of no length", "before 0"],
)
def test_a_sentence_no_player_shows_is_no_dtw_sentence(window: dict[str, object]) -> None:
    # no time, or none a player shows, to check its DTW times against: its cue its consumer's to
    # drop, noted -- before, counted a fallback too (`2 of 2`, then `1 cues dropped`)
    data = _cli(
        [
            {"offsets": window, "text": " gone", "tokens": [_token(" gone", 0, 900, 10)]},
            {
                "offsets": {"from": 1000, "to": 2000},
                "text": " late",
                "tokens": [_token(" late", 1000, 2000, 50)],
            },
        ]
    )
    reading = subverter.read("json", data, "a.json")
    assert reading.notes == (
        "DTW word times were outside their sentence or not in order in 1 of 1 sentences: used token offsets there",
    )
    assert [w.start for w in reading.words] == [0, 1000]  # its token offsets, as before


def test_a_language_without_spaces_makes_every_token_a_word() -> None:
    tokens = [_token("東", 0, 300), _token("京", 300, 600)]
    data = _cli(
        [{"offsets": {"from": 0, "to": 600}, "text": "東京", "tokens": tokens}], language="ja"
    )
    assert subverter.read("json", data, "a.json").words == (
        Timing("0", 0, 300, "東"),
        Timing("0", 300, 600, "京"),
    )


# whisper-cli writes each token's bytes (whisper_token_to_str) and escapes only `"` and `\`: a
# character its vocabulary lacks spans tokens, so the file is not UTF-8; a control character raw


def _with_bytes(value: object, texts: list[bytes]) -> bytes:
    """``value`` as JSON, each ``"@N@"`` string written as ``texts[N]``'s bytes: whisper-cli's way."""
    data = json.dumps(value).encode()
    for k, text in enumerate(texts):
        data = data.replace(f'"@{k}@"'.encode(), b'"' + text + b'"')
    return data


def _sentence(start: int, end: int, text: str, *tokens: dict[str, object]) -> dict[str, object]:
    return {"offsets": {"from": start, "to": end}, "text": text, "tokens": list(tokens)}


# " café", its é split over two tokens: C3, then A9
_SPLIT: Final = _with_bytes(
    {
        "transcription": [
            _sentence(0, 1000, "@0@", _token("@1@", 0, 500, 10), _token("@2@", 500, 1000, 60))
        ]
    },
    [" café".encode(), b" caf\xc3", b"\xa9"],
)


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"], ids=["", "a BOM"])
def test_a_character_split_across_tokens_is_joined_into_its_word(bom: bytes) -> None:
    reading = subverter.read("json", bom + _SPLIT, "a.json")
    assert reading.cues == (Cue(0, 1000, " café", "0"),)
    assert reading.words == (Timing("0", 100, 1000, " café"),)


def test_without_spaces_a_split_character_is_one_word_over_its_tokens() -> None:
    # 鬱 (E9 AC B1), not one of whisper's tokens: two of them -- one word, from the first's start
    tokens = (_token("@1@", 0, 300), _token("@2@", 300, 600), _token("は", 600, 900))
    sentence = _sentence(0, 900, "@0@", *tokens)
    data = _with_bytes(
        {"result": {"language": "ja"}, "transcription": [sentence]},
        ["鬱は".encode(), b"\xe9\xac", b"\xb1"],
    )
    assert subverter.read("json", data, "a.json").words == (
        Timing("0", 0, 600, "鬱"),
        Timing("0", 600, 900, "は"),
    )


def test_a_character_over_three_tokens_is_one() -> None:
    # 😀 (F0 9F 98 80) over " F0 9F", "98", "80": one word, the three tokens' span
    tokens = (_token("@0@", 0, 100), _token("@1@", 100, 200), _token("@2@", 200, 300))
    sentence = _sentence(0, 300, " 😀", *tokens)
    data = _with_bytes({"transcription": [sentence]}, [b" \xf0\x9f", b"\x98", b"\x80"])
    assert subverter.read("json", data, "a.json").words == (Timing("0", 0, 300, " 😀"),)


def test_a_character_split_across_sentences_is_the_one_where_it_starts() -> None:
    # -ml N splits a sentence between tokens: é's C3 ends one, its A9 starts the next
    first = _sentence(0, 500, "@0@", _token("@0@", 0, 500))
    second = _sentence(500, 1000, "@1@", _token("@2@", 500, 600), _token(" ok", 600, 1000))
    data = _with_bytes({"transcription": [first, second]}, [b" caf\xc3", b"\xa9 ok", b"\xa9"])
    reading = subverter.read("json", data, "a.json")
    assert reading.cues == (Cue(0, 500, " café", "0"), Cue(500, 1000, " ok", "1"))
    assert reading.words == (Timing("0", 0, 500, " café"), Timing("1", 600, 1000, " ok"))


@pytest.mark.parametrize(
    ("data", "where"),
    [
        (_with_bytes({"transcription": [{"text": "@0@"}]}, [b"caf\xe9"]), ".transcription[0].text"),
        (
            _with_bytes(
                {"transcription": [_sentence(0, 500, " ok", _token("@0@", 0, 500))]}, [b" \xc3"]
            ),
            ".transcription[0].tokens[0].text",
        ),
        (
            _with_bytes({"transcription": [{"text": "@0@"}, {"text": "@1@"}]}, [b"\xc3", b"x"]),
            ".transcription[0].text",
        ),
        (
            _with_bytes(
                {"transcription": [{"text": "@0@"}, {"text": "@1@"}]}, [b"\xc3", b"\xa9\xff"]
            ),
            ".transcription[1].text",
        ),
        (_with_bytes({"segments": [{"text": "@0@"}]}, [b"\xff"]), ".segments[0].text"),
        (
            b'{"segments": [{"text": "a", "words": [{"word": "\\ud800"}]}]}',
            ".segments[0].words[0].word",
        ),
    ],
    ids=[
        "a Latin-1 byte",
        "a character never completed",
        "a character broken by the next text",
        "a byte past a character joined",
        "WhisperX",
        "a lone surrogate",
    ],
)
def test_text_not_utf8_once_joined_is_refused_where_it_is(data: bytes, where: str) -> None:
    with pytest.raises(subverter.Error, match=f"^{re.escape(f'not UTF-8: a.json ({where})')}$"):
        _ = subverter.read("json", data, "a.json")


def test_in_a_file_not_utf8_an_escaped_byte_surrogate_is_its_byte() -> None:
    # surrogateescape's: the raw byte B1 and the escape \udcb1 are one string once read
    data = b'{"segments": [{"text": "\xe9\xac"}, {"text": "\\udcb1"}]}'
    assert [c.text for c in subverter.read("json", data, "a.json").cues] == ["鬱", ""]


def test_a_nul_in_a_word_reads_as_u_fffd_noted_by_its_path() -> None:
    whisperx = {"segments": [{"start": 1, "end": 2, "text": "ab", "words": [{"word": "a\u0000b"}]}]}
    reading = subverter.read("json", json.dumps(whisperx).encode(), "a.json")
    assert [w.text for w in reading.words] == ["a\ufffdb"]
    assert reading.notes == (_NUL_NOTE.format(n=1, where=".segments[0].words[0].word"),)
    tokens = [_token(" a\u0000b", 0, 500)]
    cli = _cli([{"offsets": {"from": 0, "to": 500}, "text": " ab", "tokens": tokens}])
    reading = subverter.read("json", cli, "a.json")
    assert [w.text for w in reading.words] == [" a\ufffdb"]
    where = ".transcription[0].tokens[0].text"
    assert reading.notes == (_NUL_NOTE.format(n=1, where=where),)


def test_a_raw_control_character_reads_as_its_escaped_form() -> None:
    escaped = _cli([{"offsets": {"from": 0, "to": 1500}, "text": " a\tb\nc"}])
    raw = escaped.replace(b"\\t", b"\t").replace(b"\\n", b"\n")
    assert raw != escaped
    assert subverter.read("json", raw, "a.json") == subverter.read("json", escaped, "a.json")


# --- WhisperX: segments in seconds, their words their own; a value of the wrong kind is none


def test_whisperx_segments_and_words_in_seconds() -> None:
    words = [{"word": "Hi", "start": 0.5, "end": 0.8}, {"word": "there", "start": 0.9, "end": 1.25}]
    data = json.dumps(
        {"segments": [{"start": 0.5, "end": 1.25, "text": "Hi there", "words": words}]}
    )
    assert subverter.read("json", data.encode(), "a.json") == Reading(
        "WhisperX JSON",
        has_words=True,
        cues=(Cue(500, 1250, "Hi there", "0"),),
        words=(Timing("0", 500, 800, "Hi"), Timing("0", 900, 1250, "there")),
    )


def test_whisperx_values_as_typed() -> None:
    # a decimal string a number, rounded half up to the ms (1.0005 s: 1000.5 ms, 1001); true no
    # time; null text nothing; a number as text its JSON; a JSON number past a double no time
    segments = [
        {"start": "1.0005", "end": True, "text": None},
        {"start": 1e999, "end": 0, "text": 5},
    ]
    data = b'{"segments": ' + json.dumps(segments).replace("Infinity", "1e999").encode() + b"}"
    assert subverter.read("json", data, "a.json") == Reading(
        "WhisperX JSON", has_words=False, cues=(Cue(1001, None, "", "0"), Cue(None, 0, "5", "1"))
    )


# --- OpenAI whisper: .segments shaped as WhisperX's, by the same rules; its top-level text names it

# transcribe() returns dict(text, segments, language), WriteJSON dumping it whole -- its text ""
# when nothing is decoded; no WhisperX result writes a top-level text (decisions' "Whisper names")
_OPENAI_SEGMENT: Final = {
    "id": 0, "seek": 0, "start": 0.5, "end": 1.25, "text": " Hi there", "tokens": [50364],
    "temperature": 0.0, "avg_logprob": -0.2, "compression_ratio": 0.9, "no_speech_prob": 0.01,
}  # fmt: skip
_OPENAI_WORDS: Final = [
    {"word": " Hi", "start": 0.5, "end": 0.8, "probability": 0.9},
    {"word": " there", "start": 0.9, "end": 1.25, "probability": 0.8},
]


@pytest.mark.parametrize(
    ("doc", "source", "words"),
    [
        (
            {"text": " Hi there", "segments": [_OPENAI_SEGMENT], "language": "en"},
            "OpenAI whisper JSON",
            (),
        ),
        (
            {
                "text": " Hi there",
                "segments": [{**_OPENAI_SEGMENT, "words": _OPENAI_WORDS}],
                "language": "en",
            },
            "OpenAI whisper JSON",
            (Timing("0", 500, 800, " Hi"), Timing("0", 900, 1250, " there")),
        ),
        (
            {"segments": [{"start": 0.5, "end": 1.25, "text": " Hi there"}], "language": "en"},
            "WhisperX JSON",
            (),
        ),
        (
            {"text": 5, "segments": [{"start": 0.5, "end": 1.25, "text": " Hi there"}]},
            "WhisperX JSON",
            (),
        ),
        (
            {"text": " Hi there", "segments": [{"start": 0.5, "end": 1.25, "text": " Hi there"}]},
            "OpenAI whisper JSON",
            (),
        ),
    ],
    ids=[
        "OpenAI",
        "OpenAI, --word_timestamps",
        "WhisperX unaligned",
        "a text no string",
        "a text, no other key",
    ],
)
def test_a_segments_json_is_named_by_its_writers_keys(
    doc: dict[str, object], source: str, words: tuple[Timing, ...]
) -> None:
    found = subverter.read("json", json.dumps(doc).encode(), "a.json")
    assert found == Reading(
        source, has_words=bool(words), cues=(Cue(500, 1250, " Hi there", "0"),), words=words
    )


def test_openai_whispers_json_of_nothing_decoded_is_named_so() -> None:
    doc: dict[str, object] = {"text": "", "segments": [], "language": "en"}
    found = subverter.read("json", json.dumps(doc).encode(), "a.json")
    assert (found.source, found.cues) == ("OpenAI whisper JSON", ())


@pytest.mark.parametrize(("seconds", "end"), [("1e305", 10**308), ("1e306", None)])
def test_a_time_past_a_doubles_range_is_none(seconds: str, end: int | None) -> None:
    # in ms: 10**308 is inside a double's range (its largest, ~1.8e308), 10**309 past it
    data = f'{{"segments": [{{"start": 0, "end": {seconds}, "text": "x"}}]}}'.encode()
    assert subverter.read("json", data, "a.json").cues == (Cue(0, end, "x", "0"),)


def test_a_token_or_word_not_an_object_is_no_value() -> None:
    tokens = [5, _token(" ok", 0, 500)]  # a malformed token: skipped
    cli = _cli([{"offsets": {"from": 0, "to": 500}, "text": " ok", "tokens": tokens}])
    assert subverter.read("json", cli, "a.json").words == (Timing("0", 0, 500, " ok"),)
    words = ["nope", {"word": "ok", "start": 0, "end": 0.5}]  # a malformed word: skipped
    wx = json.dumps({"segments": [{"start": 0, "end": 0.5, "text": "ok", "words": words}]}).encode()
    assert subverter.read("json", wx, "a.json").words == (Timing("0", 0, 500, "ok"),)
