r"""whisper-cli's and WhisperX's JSON: chunks and word timings, their values as they are typed.

A time is a number (fields.number: a JSON number, or a decimal string); any other value
is no time. A text is the JSON string, or a non-string written as JSON (jq's tostring).

whisper-cli writes each token's bytes as they are (``whisper_token_to_str``) and escapes only
``"`` and ``\`` (``cli.cpp``): a character whisper's vocabulary lacks spans tokens -- 1,476 of
its 50,257 are not UTF-8 alone -- and, with ``-ml``, sentences; a tab or newline is written raw.
So the file is read as bytes where it is not UTF-8, and each character joined across the texts
it spans, given to the one it starts in (``_spread``); a control character is text, as its
escaped form reads. What still is no UTF-8 is refused where it is.
"""

import codecs
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal, cast

from subverter._errors import refuse
from subverter.readers.fields import json_number, ms, number, time_ms
from subverter.transcript import Cue, Reading, Timing

__all__ = ["read"]

# Valid JSON whose arrays and objects nest deeper is refused alike on every machine: Python
# 3.14 bounds json's recursion by the thread's C stack, not a fixed count (CPython's
# InternalDocs/stack_protection.md), so what parses varies with the machine -- 100000 levels
# do with a 64 MiB stack, not with 8 MiB. A whisper-cli transcript nests 6 deep.
_DEEPEST: Final = 1000


# how a file's strings give back their bytes: as UTF-8, or each surrogate U+DC80-DCFF its byte
type _Errors = Literal["strict", "surrogateescape"]


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
    doc, source = _obj(root), _Source(name, errors)
    if isinstance(doc.get("transcription"), list):
        return _whisper_cli(doc, source)
    if not isinstance(doc.get("segments"), list):
        kinds = "a whisper-cli (.transcription) or WhisperX (.segments) JSON transcript"
        refuse(f"not {kinds}: {name}")
    cues, words = _whisperx(doc, source)
    return Reading("WhisperX JSON", has_words=bool(words), cues=cues, words=words)


def _loads(data: bytes) -> tuple[object, _Errors]:
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


@dataclass(frozen=True, slots=True)
class _Source:
    """The file read: its name, for messages; how its strings give back their bytes (``_loads``)."""

    name: str
    errors: _Errors


def _spread(texts: Sequence[str], source: _Source, where: Callable[[int], str]) -> list[str]:
    """``texts`` as UTF-8, each character joined across the texts it spans, in the one it starts.

    Refused at ``where``, the text's jq path: a byte no character takes, a character the texts
    end inside, a lone surrogate (a JSON escape) -- but in a file not UTF-8, an escaped
    U+DC80-DCFF reads as the byte ``surrogateescape`` keeps so: the two are one string.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    spread: list[str] = []
    started: int | None = None  # the text an unfinished character starts in
    for k, text in enumerate(texts):
        pending = len(decoder.getstate()[0])  # the unfinished character's bytes, in ``started``
        try:
            found = decoder.decode(text.encode("utf-8", source.errors))
        except UnicodeEncodeError:  # a lone surrogate
            refuse(f"not UTF-8: {source.name} ({where(k)})")
        except UnicodeDecodeError as e:  # a byte no character takes: in ``started``'s, or here
            at = k if started is None or e.start >= pending else started
            refuse(f"not UTF-8: {source.name} ({where(at)})")
        if started is not None and found:  # its first character, the one started before
            spread[started] += found[0]
            found, started = found[1:], None
        spread.append(found)
        if started is None and decoder.getstate()[0]:
            started = k
    if started is not None:
        refuse(f"not UTF-8: {source.name} ({where(started)})")
    return spread


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


def _whisper_cli(doc: dict[str, object], source: _Source) -> Reading:
    entries = [_obj(e) for e in _list(doc["transcription"])]
    texts = _spread(
        [_text(e.get("text")) for e in entries], source, lambda k: f".transcription[{k}].text"
    )
    cues = tuple(
        Cue(*_window(e), text, str(key))
        for key, (e, text) in enumerate(zip(entries, texts, strict=True))
    )
    if not any("tokens" in e for e in entries):
        return Reading("whisper-cli JSON", has_words=False, cues=cues)
    language = _text(_obj(doc.get("result")).get("language"))
    words, fallback, timed = _tokens(entries, no_spaces=language in _NO_SPACES, source=source)
    notes: tuple[str, ...] = ()
    if fallback:
        where = f"outside their sentence or not in order in {fallback} of {timed} sentences"
        notes = (f"DTW word times were {where}: used token offsets there",)
    return Reading("whisper-cli -ojf JSON", has_words=True, cues=cues, words=words, notes=notes)


def _window(value: dict[str, object]) -> tuple[int | None, int | None]:
    """A sentence's or a token's offsets, in ms."""
    offsets = _obj(value.get("offsets"))
    return time_ms(offsets.get("from"), 1), time_ms(offsets.get("to"), 1)


def _tokens(
    entries: list[dict[str, object]], *, no_spaces: bool, source: _Source
) -> tuple[tuple[Timing, ...], int, int]:
    """Words from tokens, timed by DTW where its times sit in order inside their sentence."""
    words: list[Timing] = []
    fallback: set[int] = set()
    timed: set[int] = set()
    for key, (e, tokens) in enumerate(zip(entries, _sentences(entries, source), strict=True)):
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
        if ws and has:
            timed.add(key)
            if not dtw_ok:
                fallback.add(key)
    return tuple(words), len(fallback), len(timed)


@dataclass(frozen=True, slots=True)
class _Token:
    """A token, as it reads once its characters are joined (``_spread``).

    Its whole characters; whether its bytes only continue a character an earlier token began;
    its offsets; its DTW time.
    """

    text: str
    continues: bool
    start: int | None
    end: int | None
    dtw: Fraction | None


def _sentences(entries: list[dict[str, object]], source: _Source) -> list[list[_Token]]:
    """Each sentence's tokens ([_...] tokens dropped), their texts spread over them all."""
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
    texts = _spread(
        [text for _, _, text, _ in found],
        source,
        lambda n: f".transcription[{found[n][0]}].tokens[{found[n][1]}].text",
    )
    sentences: list[list[_Token]] = [[] for _ in entries]
    for (key, _, raw, t), text in zip(found, texts, strict=True):
        sentences[key].append(
            _Token(text, bool(raw) and not text, *_window(t), number(t.get("t_dtw")))
        )
    return sentences


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


# WhisperX: .segments[] -- seconds; their words, each its own


def _whisperx(
    doc: dict[str, object], source: _Source
) -> tuple[tuple[Cue, ...], tuple[Timing, ...]]:
    segments = [_obj(s) for s in _list(doc["segments"])]
    texts = _spread(
        [_text(s.get("text")) for s in segments], source, lambda k: f".segments[{k}].text"
    )
    cues = tuple(
        Cue(time_ms(s.get("start"), 1000), time_ms(s.get("end"), 1000), text, str(key))
        for key, (s, text) in enumerate(zip(segments, texts, strict=True))
    )
    found = [
        (key, j, cast("dict[str, object]", word))
        for key, s in enumerate(segments)
        for j, word in enumerate(_list(s.get("words")))
        if isinstance(word, dict)
    ]
    spoken = _spread(
        [_text(w.get("word")) for _, _, w in found],
        source,
        lambda n: f".segments[{found[n][0]}].words[{found[n][1]}].word",
    )
    words = tuple(
        Timing(str(key), time_ms(w.get("start"), 1000), time_ms(w.get("end"), 1000), text)
        for (key, _, w), text in zip(found, spoken, strict=True)
    )
    return cues, words
