"""ffmpeg's whisper filter's JSON against its rules (``readers/whisper_filter.py``, docs/decisions.md's
"whisper filter JSON" row): one object a line, as ``af_whisper.c`` prints it, its text as written.

Every expectation is worked by hand from the writer's ``av_asprintf``, not taken from a run: what a
reader yields before ffman's normalising (no trim, no sort, no clamp, no cue dropped).
"""

import re
import time
from typing import Final

import pytest
import subverter
from subverter import Cue

_SOURCE: Final = "ffmpeg whisper filter JSON"
_DROPPED: Final = "{n} records not as ffmpeg's whisper filter writes one dropped: the first, {first} on line {line}"
# measured: the filter's own loop, cut from FFmpeg n8.1.2's af_whisper.c against libavutil, on two
# windows (0 and 5000 ms) of the same segments (the whisper-transcripts skill's scripts/measure.py)
_MEASURED: Final = (
    b'{"start":0,"end":1520,"text":"Hello "world" \\ <b>bold</b>"}\n'
    b'{"start":3000,"end":4200,"text":" tab\there\nnewline"}\n'
    b'{"start":4200,"end":5000,"text":"caf\xc3\xa9"}\n'
    b'{"start":5000,"end":6520,"text":"Hello "world" \\ <b>bold</b>"}\n'
    b'{"start":8000,"end":9200,"text":" tab\there\nnewline"}\n'
    b'{"start":9200,"end":10000,"text":"caf\xc3\xa9"}\n'
)


def _written(segments: list[tuple[int, int, str]]) -> str:
    """The filter's ``format=json``: ``{"start":S,"end":E,"text":"T"}`` and a line feed each."""
    return "".join(f'{{"start":{a},"end":{z},"text":"{t}"}}\n' for a, z, t in segments)


def test_the_filters_json_is_read_record_by_record_its_texts_as_written() -> None:
    found = subverter.read("json", _MEASURED, "ep12.json")
    window = [
        (0, 1520, 'Hello "world" \\ <b>bold</b>'),
        (3000, 4200, " tab\there\nnewline"),
        (4200, 5000, "caf\u00e9"),
    ]
    assert found.cues == tuple(Cue(a + at, z + at, t) for at in (0, 5000) for a, z, t in window)
    assert (found.source, found.has_words, found.notes) == (_SOURCE, False, ())


@pytest.mark.parametrize(
    "text",
    [
        "C:\\new",  # JSON's escapes are no escapes here: json.loads reads a line break
        "caf\\u00e9",
        'say \\"hi\\"',
        "a \\\\ b",
        'ends in "}',
        "",
    ],
    ids=["backslash n", "backslash u", "escaped quote", "two backslashes", "a closing", "empty"],
)
def test_a_text_is_as_the_filter_wrote_it_no_escape_undone(text: str) -> None:
    data = _written([(0, 1000, text), (1000, 2000, "next")])
    found = subverter.read("json", data.encode(), "a.json")
    assert found.cues == (Cue(0, 1000, text), Cue(1000, 2000, "next"))
    assert found.notes == ()


@pytest.mark.parametrize(
    ("data", "cues", "notes"),
    [
        # one record, no line feed: valid JSON, still the filter's -- its text as written
        ('{"start":0,"end":1000,"text":"C:\\new"}', (Cue(0, 1000, "C:\\new"),), ()),
        # a text's own line breaks, an empty line among them: the record's
        (
            _written([(0, 1, "a\n\nb\n"), (2, 3, "c")]),
            (Cue(0, 1, "a\n\nb\n"), Cue(2, 3, "c")),
            (),
        ),
        # a line opening as a record is one: a text's line so opened ends it, both dropped
        (
            _written([(0, 1, 'x\n{"start":5')]),
            (),
            (_DROPPED.format(n=2, first='{"start":0,"end":1,"text":"x', line=1),),
        ),
        # a re-saved file's line ends, CR LF or a CR alone, each the filter's LF: a text's own one
        (
            '{"start":0,"end":1,"text":"a\r\nb"}\r\n{"start":2,"end":3,"text":"c"}\r\n',
            (Cue(0, 1, "a\nb"), Cue(2, 3, "c")),
            (),
        ),
        (
            '{"start":0,"end":1,"text":"a\rb"}\r{"start":2,"end":3,"text":"c"}\r',
            (Cue(0, 1, "a\nb"), Cue(2, 3, "c")),
            (),
        ),
        # blank lines after a record's "} -- between records, at the end -- in no text: none
        (
            _written([(0, 1, "a")]) + "\n" + _written([(2, 3, "b\n")]) + "\n\n",
            (Cue(0, 1, "a"), Cue(2, 3, "b\n")),
            (),
        ),
        # a line after a record's "} that is no record: no text ends there, the record dropped
        (
            _written([(0, 1, "a")]) + "stray\n" + _written([(2, 3, "b")]),
            (Cue(2, 3, "b"),),
            (_DROPPED.format(n=1, first='{"start":0,"end":1,"text":"a"}\\nstray', line=1),),
        ),
        # a text's line opening with a brace but not as a record: the record's
        (_written([(0, 1, "a\n{laughs}")]), (Cue(0, 1, "a\n{laughs}"),), ()),
        # a time PRId64 prints none of -- empty, of other digits -- no record: dropped
        (
            '{"start":,"end":1,"text":"t"}\n',
            (),
            (_DROPPED.format(n=1, first='{"start":,"end":1,"text":"t"}', line=1),),
        ),
        (
            '{"start":\u0663,"end":1,"text":"t"}\n',
            (),
            (_DROPPED.format(n=1, first='{"start":\u0663,"end":1,"text":"t"}', line=1),),
        ),
        # a record dropped is named as written but its blank lines: a blank after its "} kept
        (
            '{"start":0,"end":1,"text":"t"} \n\n',
            (),
            (_DROPPED.format(n=1, first='{"start":0,"end":1,"text":"t"} ', line=1),),
        ),
        # a time before 0, as PRId64 prints a frame's negative pts: read, ffman clamping it
        (_written([(-20, -10, "early")]), (Cue(-20, -10, "early"),), ()),
        # a time no double holds: none (the whisper-transcripts box's bound), its text kept
        (_written([(int("9" * 400), 1, "far")]), (Cue(None, 1, "far"),), ()),
    ],
    ids=[
        "one record",
        "line breaks",
        "a record's signature",
        "CR LF",
        "CR",
        "blank lines",
        "a stray line",
        "a brace",
        "no time",
        "other digits",
        "a blank after it",
        "a time before 0",
        "a time past a double",
    ],
)
def test_a_record_opens_a_line_and_runs_to_the_next(
    data: str, cues: tuple[Cue, ...], notes: tuple[str, ...]
) -> None:
    found = subverter.read("json", data.encode(), "a.json")
    assert (found.cues, found.notes) == (cues, notes)


def test_a_record_not_as_the_filter_writes_one_is_dropped_noted_before_its_nuls() -> None:
    data = (
        _written([(0, 1000, "kept\x00")])
        + '{"start":x,"end":2,"text":"t"}\n\n{"start":1000,"end":2'
    )
    found = subverter.read("json", data.encode(), "a.json")
    assert found.cues == (Cue(0, 1000, "kept\ufffd"),)
    first = '{"start":x,"end":2,"text":"t"}'
    nul = "1 NULs read as U+FFFD, as the W3C reads them: the first in line 1"
    assert found.notes == (_DROPPED.format(n=2, first=first, line=2), nul)


@pytest.mark.parametrize("codec", ["utf-8-sig", "utf-16-le", "utf-16-be"])
def test_the_filters_json_with_a_bom_is_read(codec: str) -> None:
    text = _written([(0, 1000, "caf\u00e9 \U0001f600")])
    data = text.encode(codec) if codec == "utf-8-sig" else ("\ufeff" + text).encode(codec)
    found = subverter.read("json", data, "a.json")
    assert (found.cues, found.notes) == ((Cue(0, 1000, "caf\u00e9 \U0001f600"),), ())


@pytest.mark.parametrize("end", ["\n", "\r"], ids=["LF", "CR"])
def test_a_unit_not_utf16_is_refused_by_its_line(end: str) -> None:
    text = "\ufeff" + _written([(0, 1, "a"), (1, 2, "b\nc\ud800")]).replace("\n", end)
    with pytest.raises(subverter.Error, match=r"^not UTF-16: a\.json \(line 3\)$"):
        _ = subverter.read("json", text.encode("utf-16-le", "surrogatepass"), "a.json")


def test_a_character_split_across_records_is_given_to_the_one_it_starts_in() -> None:
    """``max_len`` splits a segment between tokens, at times inside a character (8.1.2)."""
    data = b'{"start":0,"end":1,"text":"caf\xc3"}\n{"start":1,"end":2,"text":"\xa9 au lait"}\n'
    found = subverter.read("json", data, "a.json")
    assert found.cues == (Cue(0, 1, "caf\u00e9"), Cue(1, 2, " au lait"))


def test_a_text_not_utf8_is_refused_by_its_records_line_its_nul_noted() -> None:
    data = _written([(0, 1, "a"), (1, 2, "b\nc")]).encode().replace(b"c", b"\xff")
    with pytest.raises(subverter.Error, match=r"^not UTF-8: a\.json \(line 2\)$"):
        _ = subverter.read("json", data, "a.json")
    found = subverter.read("json", _written([(0, 1, "a\x00")]).encode(), "a.json")
    assert found.cues == (Cue(0, 1, "a\ufffd"),)
    assert found.notes == ("1 NULs read as U+FFFD, as the W3C reads them: the first in line 1",)


def test_only_the_filters_signature_takes_its_reader() -> None:
    whisperx = b'{"segments": [{"start": 0, "end": 1, "text": "a"}]}'
    assert subverter.read("json", whisperx, "a.json").source == "WhisperX JSON"
    refusal = "not a whisper-cli (.transcription), OpenAI whisper or WhisperX (.segments) JSON transcript: a.json"
    with pytest.raises(subverter.Error, match=f"^{re.escape(refusal)}$"):  # a blank first: JSON's
        _ = subverter.read("json", b' {"start":0,"end":1,"text":"a"}', "a.json")


def test_json_lines_of_its_signature_not_its_form_are_dropped_each_noted() -> None:
    """Python's ``json.dumps``, a space after each colon: no record as the filter writes one."""
    data = b'{"start": 0, "end": 1, "text": "a"}\n{"start": 1, "end": 2, "text": "b"}\n'
    found = subverter.read("json", data, "a.json")
    first = '{"start": 0, "end": 1, "text": "a"}'
    assert (found.cues, found.notes) == ((), (_DROPPED.format(n=2, first=first, line=1),))


def test_a_record_of_many_lines_is_read_in_bounded_work() -> None:
    data = ('{"start":0,"end":1,"text":"x' + "\ny" * 400_000 + '"}\n').encode()
    began = time.monotonic()
    found = subverter.read("json", data, "a.json")
    assert time.monotonic() - began < 1
    assert found.cues == (Cue(0, 1, "x" + "\ny" * 400_000),)


def test_a_long_dropped_record_is_named_shown() -> None:
    data = _written([(0, 1, "a")]) + '{"start":' + "9" * 100 + "\n"
    (note,) = subverter.read("json", data.encode(), "a.json").notes
    assert re.fullmatch(r'1 records .* the first, \{"start":9{48}\.\.\. on line 2', note)
