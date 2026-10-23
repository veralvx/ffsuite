---
name: whisper-transcripts
description: Speech-to-text transcripts as the whisper tools write them - whisper.cpp's whisper-cli (-oj, -ojf, -ocsv; -ml, -di), ffmpeg's whisper filter, OpenAI whisper and WhisperX (json, tsv, txt) - their fields, times (centiseconds, float seconds, rounding to ms) and word timings (tokens, DTW, aligned words); where their readers - Python's json and csv, pandas, jq, ffman - disagree (a raw tab or newline, bytes not UTF-8, NaN, one object a line, a TSV row a newline breaks or a quote opens, a BOM, UTF-16); and the rules for a transcript all of them read alike. Use this whenever reading, writing, validating, fixing or converting a whisper JSON, CSV, TSV or TXT transcript; parsing one in Python, pandas or jq; choosing an output for word-level subtitles; explaining a transcript a parser rejects, a word without a time, a split character, a lost line or a time 1 ms off; or ffman's --burn-subs and --add-subs of one - even when the request names only a whisper or WhisperX transcript.
---

# whisper transcripts

What the whisper tools write besides subtitles: JSON, CSV, TSV and plain text, each defined by its
writer alone. Everything here is read in the sources and measured -- whisper.cpp v1.8.4, FFmpeg
n8.1.2's `whisper` filter, openai-whisper v20250625 and WhisperX v3.8.5, each writer run on the same
transcript; Python 3's json and csv, pandas 3.0.5, jq 1.7, ffmpeg 8.1.2 and ffman reading each file.
The full tables are in [references/format.md](references/format.md);
[scripts/measure.py](scripts/measure.py) re-measures them and checks this file's example and time
rule, failing on a difference (`python3 scripts/measure.py WHISPER_CPP OPENAI_WHISPER WHISPERX
FFMPEG [PYTHON]`: the four source trees, `PYTHON` an interpreter that imports ffman). Their SubRip,
WebVTT and LRC: the `subrip`, `webvtt` and `lrc` skills. Not here: the OpenAI API's `verbose_json`
(its top-level `words` ffman ignores) and faster-whisper's objects.

## The formats

**whisper.cpp** (`whisper-cli`) times a segment in centiseconds; every writer multiplies by 10, so
its milliseconds end in 0. A segment's text is its tokens' bytes joined, a leading space usually
first (`" Hello"`); a token is raw bytes, so one can hold part of a UTF-8 character, and `-ml N`
splits a segment between tokens -- at times inside a character (`-sow` splits only before a space).
`-oj` writes `{"systeminfo", "model", "params", "result": {"language"}, "transcription": [...]}`,
each entry `timestamps` (`"00:00:01,520"`), `offsets` (integer ms) and `text`; `-ojf` adds each
entry's `tokens`, each `text`, `timestamps`, `offsets`, `id`, `p` and `t_dtw` (the DTW time in cs,
`-1` without `-dtw`), special tokens by name (`[_BEG_]`, `[_TT_76]`); `-tdrz` adds each entry's
`speaker_turn_next`. Its JSON escapes `"` and `\` alone: a tab or a newline in a text is written
raw. `-ocsv` writes `start,end,text`, integer ms, the text always quoted, `"` doubled; `-di`
(stereo) adds a `speaker` column (`0`, `1`, `?`). `-otxt` writes the texts alone, no time.

**ffmpeg's `whisper` filter** (FFmpeg 8, built with whisper.cpp;
`-af whisper=model=M:destination=out.json:format=json`) writes as it goes, a window at a time:
`text`, the texts; `srt`, numbered from 0; `json`, one object a line,
`{"start":0,"end":1520,"text":"..."}`, integer ms -- its window's start plus whisper's -- the text
not escaped at all: a `"`, a `\` or a newline in it breaks the line's JSON. Each text loses its
first character when that is whitespace, and every `[BLANK_AUDIO]`, in any case; a segment left
empty is skipped.

**OpenAI whisper** (`--output_format`, `all` by default) writes `json`, the result itself: `{"text",
"segments": [...], "language"}`, each segment `id, seek, start, end, text, tokens, temperature,
avg_logprob, compression_ratio, no_speech_prob`, with `--word_timestamps True` its `words` (`word,
start, end, probability`, `round(t, 2)` but where `timing.py` trims a segment's first or last word);
times are seconds as floats, the JSON ASCII-only (`\uXXXX`). `tsv` writes `start\tend\ttext`,
`round(1000 * seconds)` -- a float, rounded to even -- the text stripped, its tabs made spaces, a
newline kept. `txt` writes each text stripped.

**WhisperX** (`--output_format`, `all` by default) writes `json` as `{"segments": [...],
"word_segments": [...], "language"}`, UTF-8 as is: each segment `start, end, text, words` -- `word,
start, end, score`, times `round(t, 3)` -- with `--diarize` a `speaker` on both; a `NaN` time
written `NaN`. A character its aligner lacks (a digit, a symbol) aligns as a wildcard, and a word
still without a time takes its sentence neighbour's, no `score` (`--interpolate_method`: `nearest`,
the default, copies it; `linear` interpolates, unrounded); 3.1.0 to 3.3.2 and the releases tagged
2026-03-10 (3.3.5, 3.4.4, 3.5.1, 3.6.1, 3.7.8, 3.8.2) wrote such a word alone, `{"word": "101"}`.
`tsv` and `txt` are OpenAI's (`txt` a `[SPEAKER_00]: ` before a text); `aud`, Audacity's labels,
`start\tend\ttext` in seconds.

## The readers

**Python's json** (`json.loads`, strict) and **csv**, **pandas** (`read_csv`), **jq** -- what a
script reading a transcript uses -- and **ffman**, through subverter (`readers/whisper.py`,
`readers/whisper_filter.py`, `readers/table.py`). No ffmpeg demuxer reads a JSON, CSV, TSV, `.aud`
or `.txt` ("Invalid data found when processing input") -- but a `.txt` whose first line opens with
`[` (WhisperX's `[SPEAKER_00]: `, a `[Music]`), which opens as an LRC (`lrc_probe`), no line timed:
no cue. A `-` below: not that reader's format.

| Where                                               | Python (`json`, `csv`)                                                                                                                    | pandas                                         | jq                                                | ffman                                             |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| whisper-cli `-oj`, a tab or newline in a text (raw) | refused: "Invalid control character"                                                                                                      | -                                              | refused: "control characters ... must be escaped" | read, a space                                     |
| `-ojf`, a character split across tokens             | refused: not UTF-8                                                                                                                        | -                                              | each lone byte U+FFFD: the character lost         | joined into the token where it starts             |
| WhisperX's `NaN`                                    | `nan`                                                                                                                                     | -                                              | `null`                                            | no time: that segment dropped, noted              |
| the filter's `json`, one object a line              | refused whole ("Extra data"); a `"` in a text breaks its line                                                                             | -                                              | one value a line; a `"` breaks it                 | read by its form: each text as written            |
| whisper-cli's CSV, a newline in a quoted text       | one record                                                                                                                                | one row                                        | -                                                 | one cue, a space                                  |
| OpenAI's and WhisperX's TSV, a newline in a text    | the rest a row of one field                                                                                                               | a row more: its `start` the rest, NaN after it | -                                                 | read back into its record, a space, noted         |
| Their TSV, a text or a line of it opening with `"`  | read as quoted: its `"` dropped, one left open taking the rows after it into its text; `quoting=csv.QUOTE_NONE` reads it as written       | as Python's `csv`                              | -                                                 | read as written                                   |
| A text `NA`, `None`, `null`, `nan` or empty         | as written                                                                                                                                | NaN (`keep_default_na=False` keeps it)         | -                                                 | as written (empty: no cue)                        |
| A UTF-8 BOM                                         | `json.loads(bytes)` skips it; text decoded `utf-8` refused ("Unexpected UTF-8 BOM": decode `utf-8-sig`); `csv` keeps it in the first name | skipped                                        | skipped                                           | skipped                                           |
| UTF-16, its BOM                                     | `json.loads(bytes)` reads it; `csv` needs its encoding named                                                                              | needs `encoding=`                              | refused                                           | read: CSV, TSV, JSON                              |
| Times                                               | as written: floats                                                                                                                        | integers; floats or text where a row breaks    | as written                                        | whole ms, half up, from the decimal written       |
| A text's `<`, `{`, `\`                              | as written                                                                                                                                | as written                                     | as written                                        | as written: none of these writers marks a text up |
| `.txt`; `.aud`                                      | -                                                                                                                                         | -                                              | -                                                 | refused: no times; not a format it reads          |

## What each holds

| Output                    | Times                                            | Words                                                                                                                   | Speakers                                       |
| ------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| whisper-cli `-oj`         | ms, multiples of 10                              | none                                                                                                                    | `-di`: `speaker`; `-tdrz`: `speaker_turn_next` |
| whisper-cli `-ojf`        | ms, multiples of 10; DTW in cs                   | tokens: their times, `p`, `t_dtw`; a word a token or more                                                               | as `-oj`                                       |
| whisper-cli `-ocsv`       | ms, multiples of 10                              | none                                                                                                                    | `-di`: a column                                |
| the filter's `json`       | ms, its window's start plus whisper's            | none                                                                                                                    | none                                           |
| OpenAI `json`             | seconds, floats; words 0.01 s, a trimmed one not | `--word_timestamps`: `word, start, end, probability`                                                                    | none                                           |
| WhisperX `json`           | seconds, 0.001 s where aligned                   | `word, start, end, score`; interpolated, no `score`; the word alone (3.1.0 to 3.3.2; 3.8.2 and its 2026-03-10 siblings) | `--diarize`: `speaker`                         |
| OpenAI and WhisperX `tsv` | ms, integers                                     | none                                                                                                                    | none                                           |
| `txt` (any)               | none                                             | none                                                                                                                    | WhisperX, whisper-cli: a prefix                |

## Writing one all of them read alike

1. JSON in UTF-8, no BOM, every control character escaped and no `NaN` (`json.dumps(result,
   ensure_ascii=False, allow_nan=False)`); one document, not one object a line.
2. WhisperX's shape -- `{"segments": [{"start", "end", "text", "words": [{"word", "start",
   "end"}]}]}`, seconds -- or whisper-cli's `{"transcription": [{"offsets": {"from", "to"},
   "text"}]}`, ms; every word timed, inside its segment and in order.
3. CSV with the header `start,end,text`, RFC 4180's quoting (`csv.writer`); pandas reads a text `NA`
   as NaN unless given `keep_default_na=False`. A TSV only where no text opens with `"` (`csv` and
   pandas read one as quoted), the same header, a text's tabs and line breaks made spaces (Python's
   csv and pandas take neither back; ffman a line break alone).
4. Times in whole ms, each end after its start, the segments in order. From seconds as written,
   round once, half up (toward +infinity, as ffman), exactly from the decimal -- not
   `round(1000 * t)`, which rounds the float to even, nor from a float, its binary value
   (`to_ms(1.0005)` is 1000, `to_ms("1.0005")` 1001):

   ```python
   import json
   import math
   import re
   from decimal import Decimal
   from fractions import Fraction

   NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")  # JSON's
   EXPONENT = 400  # past 10^±400, no time: Fraction would build a 10**N integer, as ffman bounds


   def transcript(text: str) -> object:
       """A whisper JSON, its numbers as written (`Decimal`), a raw control character as text."""
       return json.loads(text, parse_float=Decimal, strict=False)


   def to_ms(seconds: str | int | Decimal) -> int:
       """Seconds as written -- a JSON number's text, or `transcript`'s -- to whole ms, half up."""
       if isinstance(seconds, bool) or (isinstance(seconds, str) and not NUMBER.fullmatch(seconds)):
           raise ValueError(seconds)  # a bool, or a text Fraction reads but JSON does not
       if abs(Decimal(seconds).adjusted()) > EXPONENT:
           raise ValueError(seconds)
       return math.floor(Fraction(seconds) * 1000 + Fraction(1, 2))
   ```

5. Plain text: no tag, no override, no escape; a speaker in its own field, not in the text.

## Reading one correctly

JSON as whisper-cli writes it: a raw control character in a string is text
(`json.loads(text, strict=False)`); bytes not UTF-8 decoded with `surrogateescape`, then each
character joined across the texts it spans -- tokens, or segments `-ml` split -- given to the one
where it starts: a token holding only the end of one belongs to the word before it. A word starts at
a token with a leading space (in a language written without spaces, every token is one), special
tokens (`[_...]`) skipped; DTW times used only where they sit in order inside their segment.
whisper-cli's times from `offsets` (ms), or `timestamps` as `HH:MM:SS,mmm`; OpenAI's and WhisperX's
seconds read from the decimal written, half up to the ms (`transcript`, `to_ms`); `NaN`, `null` or a
string that is no number: no time (`to_ms` raises on anything not a JSON number, or one past
10^±400: test it first; ffman also reads a decimal in a string, blanks and a `+` allowed). Bytes, or
text decoded `utf-8-sig`: a BOM skipped. CSV and TSV by their header's names (`speaker` may sit
before `text`), integers of ms (pandas: `keep_default_na=False`, or a text `NA` is NaN); a TSV read
unquoted (`quoting=csv.QUOTE_NONE`), and a line holding no tab, after a record, is that record's
text, broken by a newline: join it back with one (an empty line too) -- or read its writer's JSON,
which keeps a text whole. The filter's `json`: each line opening `{"start":` an object, its text
from `"text":"` to its last `"}`, as written (no escape to undo); a line not so opened continues the
one before. Plain text: show it as written.

## Converting to subtitles

```sh
whisper-cli -m ggml-base.en.bin -f talk.wav -osrt -ovtt -ocsv -ojf -of talk  # tokens in talk.json
whisperx talk.wav --output_format json -o wx                     # words aligned: wx/talk.json
ffman convert -i talk.mp4 --burn-subs wx/talk.json --overlay-mode chunk-word
ffman convert -i talk.mp4 --add-subs talk.csv -o talk.mkv
```

ffman burns or attaches whisper-cli's JSON and CSV, OpenAI's and WhisperX's JSON and TSV -- their
words, where the JSON holds them, for its word modes; any CSV or TSV by its header's `start`, `end`
(ms) and `text`, any order; a JSON's or CSV's speaker before its text, as its writer's SubRip writes
it -- and the filter's `json` and `srt`: the `json` read as the filter writes it, each text as
written, the `srt` a SubRip, read from its cue 0. It refuses a `.txt` (no times) and an `.aud`. A
burn needs a video; an audio file takes a transcript as a track, `--add-subs` into an `.mka`.

## Example

```json
{"segments": [
  {"start": 0.512, "end": 2.004, "text": " Good morning, everyone.", "words": [
    {"word": "Good", "start": 0.512, "end": 0.73, "score": 0.97},
    {"word": "morning,", "start": 0.75, "end": 1.21, "score": 0.95},
    {"word": "everyone.", "start": 1.3, "end": 2.004, "score": 0.9}]},
  {"start": 2.5, "end": 3.8, "text": " Room 101 is open.", "words": [
    {"word": "Room", "start": 2.5, "end": 2.8, "score": 0.92},
    {"word": "101"},
    {"word": "is", "start": 3.1, "end": 3.2, "score": 0.8},
    {"word": "open.", "start": 3.25, "end": 3.8, "score": 0.88}]}],
 "language": "en"}
```

A WhisperX JSON, `101` written alone as 3.8.2 wrote a word it could not align: Python's json and jq
read it as written. ffman reads two sentences, `Good morning, everyone.` from 0.512 s to 2.004 s and
`Room 101 is open.` from 2.5 s to 3.8 s, and seven words; `101` is placed between its neighbours,
2.8 s to 3.1 s, noted.

## Sources

whisper.cpp v1.8.4 (`examples/cli/cli.cpp`, `examples/common-whisper.cpp`, `src/whisper.cpp`);
FFmpeg n8.1.2 (`libavfilter/af_whisper.c`); openai-whisper v20250625 (`whisper/utils.py`,
`transcribe.py`, `timing.py`); WhisperX v3.8.5 (`whisperx/utils.py`, `alignment.py`, `asr.py`);
RFC 8259 (JSON), RFC 4180 (CSV); pandas 3.0.5, jq 1.7, ffmpeg 8.1.2 (`libavformat/lrcdec.c`);
subverter's `readers/whisper.py`, `readers/whisper_filter.py`, `readers/table.py`,
`readers/utf8.py`, ffman's `subs/markup.py`; WhisperX's `alignment.py` at each tag from 3.0.0 to
3.8.6. Measurements: `scripts/measure.py`.
