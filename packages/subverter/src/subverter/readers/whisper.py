r"""whisper-cli's, OpenAI whisper's and WhisperX's JSON: chunks and word timings, values as typed.

A time is a number (fields.number: a JSON number, or a decimal string); any other value
is no time. A text is the JSON string, or a non-string written as JSON (jq's tostring).

whisper-cli writes each token's bytes as they are and escapes only ``"`` and ``\``
(``cli.cpp``): the file is read as bytes where it is not UTF-8, each character joined across
the texts it spans (``utf8``) -- what still is not, refused by the text's jq path; a tab or
newline, written raw, is text, as its escaped form reads.

OpenAI whisper's ``.segments`` are shaped as WhisperX's, read alike; its result's top-level
``text`` names it (``transcribe.py``: ``dict(text, segments, language)``, ``WriteJSON`` dumping it
whole, ``""`` when nothing is decoded) -- no WhisperX JSON holds one (``asr.py``, ``alignment.py``,
``diarize.py``, ``transcribe.py`` at the tags docs/decisions.md's "Whisper names" row names).
"""

import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, cast

from subverter._errors import refuse
from subverter.readers.fields import json_number, ms, number, time_ms
from subverter.readers.utf8 import Errors, Nuls, Source, joined, nul_notes
from subverter.transcript import Cue, Reading, Timing

__all__ = ["read"]

# Valid JSON whose arrays and objects nest deeper is refused alike on every machine: Python
# 3.14 bounds json's recursion by the thread's C stack, not a fixed count (CPython's
# InternalDocs/stack_protection.md), so what parses varies with the machine -- 100000 levels
# do with a 64 MiB stack, not with 8 MiB. A whisper-cli transcript nests 6 deep.
_DEEPEST: Final = 1000


def read(data: bytes, name: str) -> Reading:
    """A whisper JSON's source name, word timings or not, its cues, its words, its notes."""
    too_deep = f"JSON nested too deeply to be a transcript: {name}"
    try:
        root, errors = _loads(data)
    except ValueError:
        refuse(f"not valid JSON: {name}")
    except RecursionError:  # deeper than this machine's parser holds: deeper than _DEEPEST
        refuse(too_deep)
    if _deeper_than(root, _DEEPEST):
        refuse(too_deep)
    doc, source = _obj(root), Source(name, errors)
    if isinstance(doc.get("transcription"), list):
        return _whisper_cli(doc, source)
    if not isinstance(doc.get("segments"), list):
        kinds = "a whisper-cli (.transcription), OpenAI whisper or WhisperX (.segments) JSON"
        refuse(f"not {kinds} transcript: {name}")
    writer = "OpenAI whisper" if isinstance(doc.get("text"), str) else "WhisperX"
    cues, words, notes = _segments(doc, source)
    return Reading(f"{writer} JSON", has_words=bool(words), cues=cues, words=words, notes=notes)


def _loads(data: bytes) -> tuple[object, Errors]:
    """The JSON's value, and how its strings give back their bytes.

    Its numbers exact; a control character in a string, text. ``strict`` for UTF-8;
    ``surrogateescape`` if the file is not -- each byte no character takes kept as a surrogate,
    U+DC80-DCFF.
    """
    try:
        return json.loads(data, parse_float=json_number, strict=False), "strict"
    except UnicodeDecodeError:  # -ojf's tokens, a character split across them
        text = data.decode("utf-8", "surrogateescape").removeprefix("\ufeff")
        return json.loads(text, parse_float=json_number, strict=False), "surrogateescape"


def _deeper_than(root: object, limit: int) -> bool:
    """Whether ``root``'s arrays and objects nest past ``limit`` (walked, not recursed)."""
    pending: list[tuple[object, int]] = [(root, 1)] if _is_container(root) else []
    while pending:
        container, depth = pending.pop()
        if depth > limit:
            return True
        pending.extend((c, depth + 1) for c in _children(container) if _is_container(c))
    return False


def _is_container(value: object) -> bool:
    return isinstance(value, (dict, list))


def _children(container: object) -> list[object]:
    """An array's items, or an object's values."""
    if isinstance(container, dict):
        return list(cast("dict[str, object]", container).values())
    return cast("list[object]", container)


def _obj(value: object) -> dict[str, object]:
    """``value`` if an object, else an empty one: a missing key and a wrong type alike."""
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def _text(value: object) -> str:
    """``.text // "" | tostring``: a string as is, null or false nothing, else its JSON."""
    if value is None or value is False:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=float)


# whisper-cli: .transcription[] -- offsets in ms; with -ojf, its tokens (and their DTW times)

# the languages written without spaces between words: every token a word
_NO_SPACES: Final = frozenset({"zh", "yue", "ja", "th", "lo", "km", "my"})


def _whisper_cli(doc: dict[str, object], source: Source) -> Reading:
    entries = [_obj(e) for e in _list(doc["transcription"])]
    texts = joined(
        [_text(e.get("text")) for e in entries], source, lambda k: f".transcription[{k}].text"
    )
    cues = tuple(
        Cue(*_window(e), text, str(key))
        for key, (e, text) in enumerate(zip(entries, texts.texts, strict=True))
    )
    if not any("tokens" in e for e in entries):
        return Reading("whisper-cli JSON", has_words=False, cues=cues, notes=nul_notes(texts.nuls))
    language = _text(_obj(doc.get("result")).get("language"))
    sentences, nuls = _sentences(entries, source)
    words, fallback, timed = _tokens(entries, sentences, no_spaces=language in _NO_SPACES)
    notes: tuple[str, ...] = ()
    if fallback:
        where = f"outside their sentence or not in order in {fallback} of {timed} sentences"
        notes = (f"DTW word times were {where}: used token offsets there",)
    notes += nul_notes(texts.nuls, nuls)
    return Reading("whisper-cli -ojf JSON", has_words=True, cues=cues, words=words, notes=notes)


def _window(value: dict[str, object]) -> tuple[int | None, int | None]:
    """A sentence's or a token's offsets, in ms."""
    offsets = _obj(value.get("offsets"))
    return time_ms(offsets.get("from"), 1), time_ms(offsets.get("to"), 1)


def _tokens(
    entries: list[dict[str, object]], sentences: list[list["_Token"]], *, no_spaces: bool
) -> tuple[tuple[Timing, ...], int, int]:
    """Words from tokens, timed by DTW where its times sit in order inside their sentence.

    The sentences counted, and those fallen back on token offsets: of a window a player shows
    alone, read, its end past its start and past 0 -- one of none has no time to check DTW's
    against, and a cue its consumer drops (no time, ending before it begins, no length, before 0).
    """
    words: list[Timing] = []
    fallback: set[int] = set()
    timed: set[int] = set()
    for key, (e, tokens) in enumerate(zip(entries, sentences, strict=True)):
        a, z = _window(e)
        ws = _token_words(tokens, no_spaces=no_spaces)
        # t_dtw: in 10 ms units
        dtws = [ms(w.dtw, 10) if w.dtw is not None and w.dtw >= 0 else None for w in ws]
        has = bool(dtws) and all(t is not None for t in dtws)
        times = [t for t in dtws if t is not None] if has else []
        inside = has and a is not None and z is not None and all(a <= t < z for t in times)
        dtw_ok = inside and all(times[i] > times[i - 1] for i in range(1, len(times)))
        for k, w in enumerate(ws):
            if dtw_ok:
                words.append(
                    Timing(str(key), times[k], times[k + 1] if k + 1 < len(ws) else z, w.text)
                )
            else:
                words.append(Timing(str(key), w.start, w.end, w.text))
        if ws and has and a is not None and z is not None and max(a, 0) < z:
            timed.add(key)
            if not dtw_ok:
                fallback.add(key)
    return tuple(words), len(fallback), len(timed)


@dataclass(frozen=True, slots=True)
class _Token:
    """A token, as it reads once its characters are joined (``utf8.joined``).

    Its whole characters; whether its bytes only continue a character an earlier token began;
    its offsets; its DTW time.
    """

    text: str
    continues: bool
    start: int | None
    end: int | None
    dtw: Fraction | None


def _sentences(entries: list[dict[str, object]], source: Source) -> tuple[list[list[_Token]], Nuls]:
    """Each sentence's tokens ([_...] tokens dropped), their texts joined; their NULs."""
    found: list[tuple[int, int, str, dict[str, object]]] = []
    for key, e in enumerate(entries):
        for j, token in enumerate(_list(e.get("tokens"))):
            if not isinstance(token, dict):
                continue
            t = cast("dict[str, object]", token)
            text = t.get("text")
            if _text(text).startswith("[_"):
                continue
            if not isinstance(text, str):  # malformed: bash's jq stopped here, "unreadable"
                refuse(f"unreadable whisper-cli -ojf JSON: {source.name}")
            found.append((key, j, text, t))
    texts = joined(
        [text for _, _, text, _ in found],
        source,
        lambda n: f".transcription[{found[n][0]}].tokens[{found[n][1]}].text",
    )
    sentences: list[list[_Token]] = [[] for _ in entries]
    for (key, _, raw, t), text in zip(found, texts.texts, strict=True):
        sentences[key].append(
            _Token(text, bool(raw) and not text, *_window(t), number(t.get("t_dtw")))
        )
    return sentences, texts.nuls


@dataclass(slots=True)
class _Word:
    """A word gathered from its tokens: its text, its token offsets, its first token's DTW time."""

    text: str
    start: int | None
    end: int | None
    dtw: Fraction | None


def _token_words(tokens: list[_Token], *, no_spaces: bool) -> list[_Word]:
    """A sentence's words from its tokens: a leading space starts one.

    A token that only continues a character begun before it extends that character's word, or
    is dropped if that word is in the sentence before.
    """
    ws: list[_Word] = []
    for t in tokens:
        if t.continues:
            if ws:
                ws[-1].end = t.end
        elif not ws or t.text.startswith(" ") or no_spaces:
            ws.append(_Word(t.text, t.start, t.end, t.dtw))
        else:
            ws[-1].text += t.text
            ws[-1].end = t.end
    return ws


# OpenAI whisper's and WhisperX's: .segments[] -- seconds; their words, each its own


def _segments(
    doc: dict[str, object], source: Source
) -> tuple[tuple[Cue, ...], tuple[Timing, ...], tuple[str, ...]]:
    segments = [_obj(s) for s in _list(doc["segments"])]
    texts = joined(
        [_text(s.get("text")) for s in segments], source, lambda k: f".segments[{k}].text"
    )
    cues = tuple(
        Cue(time_ms(s.get("start"), 1000), time_ms(s.get("end"), 1000), text, str(key))
        for key, (s, text) in enumerate(zip(segments, texts.texts, strict=True))
    )
    found = [
        (key, j, cast("dict[str, object]", word))
        for key, s in enumerate(segments)
        for j, word in enumerate(_list(s.get("words")))
        if isinstance(word, dict)
    ]
    spoken = joined(
        [_text(w.get("word")) for _, _, w in found],
        source,
        lambda n: f".segments[{found[n][0]}].words[{found[n][1]}].word",
    )
    words = tuple(
        Timing(str(key), time_ms(w.get("start"), 1000), time_ms(w.get("end"), 1000), text)
        for (key, _, w), text in zip(found, spoken.texts, strict=True)
    )
    return cues, words, nul_notes(texts.nuls, spoken.nuls)
