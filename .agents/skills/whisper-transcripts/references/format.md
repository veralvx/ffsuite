# The whisper tools' outputs: whisper.cpp, ffmpeg's filter, OpenAI whisper, WhisperX

Each output is defined by its writer alone. Researched at nixpkgs' pins: whisper.cpp v1.8.4
(`examples/cli/cli.cpp`, `examples/common-whisper.cpp`, `src/whisper.cpp`,
`models/convert-pt-to-ggml.py`), FFmpeg n8.1.2 (`libavfilter/af_whisper.c`), openai-whisper
v20250625 (`whisper/utils.py`, `transcribe.py`, `timing.py`, `assets/multilingual.tiktoken`),
WhisperX v3.8.5 (`whisperx/utils.py`, `transcribe.py`, `asr.py`, `alignment.py`, `diarize.py`,
`schema.py`, `__main__.py`). Measured by `../scripts/measure.py`: whisper.cpp's writers cut from
`cli.cpp` verbatim and compiled against stubs serving their segments and tokens, and
`whisper_wrap_segment` from `src/whisper.cpp`, fed tokens by openai-whisper's
`multilingual.tiktoken`; the `whisper` filter's writer cut from `af_whisper.c`, against libavutil;
OpenAI's and WhisperX's writers imported and called; then each file read by Python's json and csv,
pandas 3.0.5, jq 1.7, ffmpeg 8.1.2 and ffman (its output is the tables marked *measured*). SubRip,
WebVTT and LRC as formats: the `subrip`, `webvtt` and `lrc` skills.

## whisper.cpp (`whisper-cli`)

Times are integers of **centiseconds** (`whisper_full_get_segment_t0`); every writer multiplies
by 10, so milliseconds always end in 0. A segment's text is its tokens' bytes joined -- a
leading space usually included (`" Hello"`); tokens are raw bytes of the byte-level BPE
(`convert-pt-to-ggml.py`'s `byte_decoder`), so one token can be part of a UTF-8 character, and
`-ml N` splits a segment between tokens (`whisper_wrap_segment`, counting characters by their
first bytes), so at times inside one -- *measured*: at `-ml 1`, `" Это ёлка и 😀"` in whisper's own
tokens became the segments `" Это"`, `" \xd1"`, `"\x91л"`, `"ка"`, `" и"`, `" \xf0\x9f\x98"`,
`"\x80"`; with `-sow` (a split only before a token opening with a space) `ё` and `😀` stayed
whole; at `-ml 16`, one segment. No writer escapes anything but what its row says.

| Flag    | File    | Content                                                                                                                                                                                                           |
| ------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-otxt` | `.txt`  | each segment's text and a newline                                                                                                                                                                                 |
| `-osrt` | `.srt`  | index from 1 (`+ -on`), `HH:MM:SS,mmm --> HH:MM:SS,mmm`, the text, a blank line                                                                                                                                   |
| `-ovtt` | `.vtt`  | `WEBVTT`, a blank line, then `HH:MM:SS.mmm --> HH:MM:SS.mmm`, the text, a blank line: no identifiers, hours always                                                                                                |
| `-ocsv` | `.csv`  | `start,end,text` header; `ms,ms,"text"` -- the text always quoted, `"` doubled (RFC 4180)                                                                                                                         |
| `-olrc` | `.lrc`  | `[by:whisper.cpp]`, then `[mm:ss.cc]text` per segment: starts only, minutes past 59 not wrapped                                                                                                                   |
| `-oj`   | `.json` | an object: `systeminfo`, `model` (`type`, `multilingual`, `vocab`, `audio` and `text` `ctx/state/head/layer`, `mels`, `ftype`), `params` (`model`, `language`, `translate`), `result.language`, `transcription[]` |
| `-ojf`  | `.json` | `-oj` with each segment's `tokens[]`; token timestamps are computed for it (`token_timestamps`)                                                                                                                   |
| `-di`   | (any)   | stereo input: a speaker per segment from the channels' energy, `0`, `1` or `?`                                                                                                                                    |
| `-tdrz` | `.json` | `speaker_turn_next` (true/false) per segment; with `-di`, refused: `cannot use both --diarize and --tinydiarize`, exit 0, no file                                                                                 |

`transcription[]`, each: `timestamps: {from, to}` (`HH:MM:SS,mmm` strings), `offsets: {from,
to}` (integer ms), `text`; with `-di`, `speaker`; with `-ojf`, `tokens[]`, each `text` (special
tokens included, by name: `[_BEG_]`, `[_TT_76]`, ...), `timestamps` and `offsets` (only when the
token has times), `id`, `p` (probability), `t_dtw` (the DTW time, centiseconds, `-1` without
`-dtw`).

*Measured* (segments 0-152 cs, 152-361999 cs, 361999-362005 cs; text with quotes, a backslash,
markup, `-->`, a tab and a newline; a token holding half an `é`):

| Output                             | What the writer made of it                                                                                                           |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| times                              | `00:00:01,520` (SRT, JSON), `00:00:01.520` (VTT), `1520` (CSV, JSON offsets), `[00:01.52]` and `[60:19.99]` (LRC)                    |
| `-otxt`, `-osrt`, `-ovtt`, `-olrc` | the text as is: leading space kept, `<b>` and `-->` unescaped, the tab and the newline raw (a newline breaks SRT, VTT and LRC lines) |
| `-ocsv`                            | `" Hello ""world"" \ <b>bold</b> --> arrow"`; the newline inside the quotes                                                          |
| `-oj`                              | `"` and `\` escaped, nothing else: the tab and newline written raw -- not JSON to a strict reader                                    |
| `-ojf`                             | the half `é` written as its single byte: not UTF-8                                                                                   |
| `p`                                | 6 significant digits: `0.987654`, `1.234e-05`, `1`                                                                                   |
| `t_dtw`                            | a float of 6 significant digits: `31`, `-1`, and `1234567` as `1.23457e+06` -- past 999999 cs (2 h 46 min) the time is rounded       |
| `-di`                              | `(speaker 0)` before the text (TXT, SRT, LRC), `<v Speaker0>` (VTT, never closed), a `speaker` column (CSV), `"speaker": "0"` (JSON) |

## ffmpeg's `whisper` filter (FFmpeg 8)

`-af whisper=model=M:destination=FILE:format=F` (in a build with whisper.cpp: nixpkgs'
`ffmpeg-full`) transcribes the audio a window at a time (`queue`, 3 s by default; `vad_model` cuts
at speech) and writes each segment as it comes, its times the window's start plus whisper.cpp's:
integer ms -- the start its first frame's time, or, after a `vad_model` cut, the last start plus the
duration transcribed, summed in a float and truncated (past 2^24 ms, about 4 h 40 min, a ms or more
off). Each text has its first character off when whitespace (`av_isspace`), every `[BLANK_AUDIO]`
removed (`av_strireplace`, any case); one left empty is skipped (with `max_len`, a lone `[`, `]`,
`BLANK`, `_` or `AUDIO` too). Nothing is escaped.

| `format` | Content                                                                             |
| -------- | ----------------------------------------------------------------------------------- |
| `text`   | each text and a newline (the default)                                               |
| `srt`    | `N`, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, the text, a blank line -- numbered from 0     |
| `json`   | one object a line: `{"start":S,"end":E,"text":"T"}` -- `T` as is: no JSON's escapes |

*Measured* (windows at 0 and 5000 ms, the same segments in each): `Hello "world" \ <b>bold</b>`
written into `json` as is -- a `"` that ends the string early; `[blank_audio] tab` kept as
` tab` (its space after the removal); ` [BLANK_AUDIO]` alone skipped; `srt` numbered 0 to 5 across
the two windows, the second's from 5000 ms.

## OpenAI whisper (`whisper`)

`--output_format` `txt`, `vtt`, `srt`, `tsv`, `json` or `all` (the default). The result: `{"text",
"segments": [...], "language"}`; each segment `id, seek, start, end, text, tokens, temperature,
avg_logprob, compression_ratio, no_speech_prob`, and with `--word_timestamps True` `words: [{word,
start, end, probability}]`. Segment times are floats in seconds (an offset plus multiples of 0.02 s,
`transcribe.py`; with words, the first and last word's); word times `round(t, 2)` (`timing.py`), but
a segment's first or last word that it trims, unrounded.

| Writer      | Content                                                                                                                                                                                                                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `WriteJSON` | `json.dump(result)`: ASCII, every other character `\uXXXX`; floats as Python writes them                                                                                                                                                                                                 |
| `WriteTSV`  | `start\tend\ttext` header; `round(1000 * t)` integer ms; the text stripped, tabs made spaces -- a newline kept, breaking the row                                                                                                                                                         |
| `WriteTXT`  | each segment's text, stripped, a line each                                                                                                                                                                                                                                               |
| `WriteSRT`  | ms by `round(seconds * 1000)`, `HH:MM:SS,mmm`; without words, a cue per segment, its text stripped and `-->` made `->`; with words, cues from the words (`--max_line_width`, `--max_line_count`, `--max_words_per_line`), `--highlight_words` a cue per word span with the word in `<u>` |
| `WriteVTT`  | as SRT, `WEBVTT` first, `MM:SS.mmm` (hours only when non-zero), no identifiers                                                                                                                                                                                                           |

*Measured*: `round(seconds * 1000)` rounds a tie to even -- 1.0005 s, 1.0015 s and 0.0005 s make the
floats 1000.5, 1001.5 and 0.5, written 1000, 1002 and 0 ms; `<b>` and `&` never escaped (an SRT or
VTT cue's markup is the transcript's text); with `--highlight_words` the gaps between words get a
cue of their own without `<u>`; `--max_line_width 8 --max_line_count 1` made a cue per word. By
source (`utils.py`): `-->` is made `->` in segment cues, not in word cues.

## WhisperX (`whisperx`)

`--output_format` `all` (the default: `srt vtt txt tsv json`) or one of them, or `aud`. The result:
`{"segments": [...], "word_segments": [...], "language"}`. Aligned (the default), each segment
`start, end, text, words: [{word, start, end, score}]` plus `speaker` (segment and words) with
`--diarize`, `chars` with `--return_char_alignments`, `avg_logprob` when the model gave one; times
`round(t, 3)` where aligned (`alignment.py`). A character the alignment model lacks (a digit, a
symbol, another script) is aligned as a wildcard (the best other column); a word still without a
time takes its sentence neighbours' by `--interpolate_method` (`nearest`, the default, copies the
nearest word's start and end, rounded; `linear` interpolates, unrounded), no `score`; a sentence
none of whose words has a time keeps them alone. `--no_align`: `{text, start, end}` per segment,
`round(t, 3)` (`asr.py`).

By release (`alignment.py` at each tag, read): 3.1.0 to 3.3.2 wrote a word without a time alone,
`{"word": "2024"}`; from 3.3.3, an unknown character is mapped to a `*` aligned as a wildcard; the
patch releases tagged 2026-03-10 (3.3.5, 3.4.4, 3.5.1, 3.6.1, 3.7.8, 3.8.2) dropped that -- the word
alone again; those tagged 2026-03-25 (3.3.6, 3.4.5, 3.5.2, 3.6.2, 3.7.9, 3.8.3) and every release
since align it on the wildcard column and interpolate as above. 3.8.4's notes credit this to
PR #1386 ("restore word-level timestamps for unalignable characters"); its `alignment.py` is
3.8.3's.

| Writer          | Content                                                                                                                                                                                                                                                        |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `WriteJSON`     | `json.dump(result, ensure_ascii=False)`: UTF-8 as is; a NaN time written `NaN` -- not JSON                                                                                                                                                                     |
| `WriteTSV`      | as OpenAI's                                                                                                                                                                                                                                                    |
| `WriteTXT`      | the stripped text, `[SPEAKER_00]: ` before it when diarized                                                                                                                                                                                                    |
| `WriteSRT/VTT`  | as OpenAI's, but: a cue's text is its words joined by a space (by nothing for `ja`, `zh`), not the segment's text; its times the earliest and latest aligned word's (none aligned: the segment's); `[SPEAKER_00]: ` before it; `--highlight_words` as OpenAI's |
| `WriteAudacity` | `.aud`: `start\tend\ttext` in seconds as Python writes floats, `[[SPEAKER_00]]` before the text; no header                                                                                                                                                     |

*Measured*: the aligned cue `Hello world.` at `00:00:00,031 --> 00:00:01,400` and the
segment `2024 again.` (its first word unaligned) at `00:00:03,100 --> 00:00:03,900` -- the
unaligned word's span lost; a `ja` segment `日本語です` whose words cover `日本` gave the cue
`日本`; a segment with `start: NaN` gave no cue and `"start": NaN` in the JSON.

## What each holds

| Output                  | Times                                                | Text                      | Words                                                                        | Speakers                |
| ----------------------- | ---------------------------------------------------- | ------------------------- | ---------------------------------------------------------------------------- | ----------------------- |
| whisper.cpp `-oj`       | ms, multiples of 10 (`offsets`)                      | segments                  | none                                                                         | `-di`: `0 1 ?`; `-tdrz` |
| whisper.cpp `-ojf`      | ms, multiples of 10; DTW in cs (a float)             | segments; tokens as bytes | tokens with times, `p`, `t_dtw`, specials                                    | `-di`, `-tdrz`          |
| whisper.cpp `-ocsv`     | ms, multiples of 10                                  | segments                  | none                                                                         | `-di` column            |
| whisper.cpp `-olrc`     | starts only, cs                                      | segments                  | none                                                                         | `(speaker 0)` text      |
| whisper.cpp `-otxt`     | none                                                 | segments                  | none                                                                         | `(speaker 0)` text      |
| ffmpeg's filter `json`  | ms, its window's start plus whisper's                | segments, unescaped       | none                                                                         | none                    |
| OpenAI `json`           | seconds, floats; words 0.01 s, a trimmed one not     | segments, `text`          | `--word_timestamps`: word, start, end, probability                           | none                    |
| OpenAI / WhisperX `tsv` | ms, integers                                         | segments                  | none                                                                         | none                    |
| OpenAI / WhisperX `txt` | none                                                 | segments                  | none                                                                         | WhisperX: prefix        |
| WhisperX `json`         | seconds, 0.001 s where aligned; `linear`'s unrounded | segments                  | word, start, end, score (no score interpolated; alone in the releases above) | `speaker` fields        |
| WhisperX `aud`          | seconds, floats                                      | segments                  | none                                                                         | `[[...]]` prefix        |

## Their readers

*Measured*: each file above as Python's `json.loads` (strict, given the bytes, then its text decoded
as UTF-8) and `csv` (on the text decoded as UTF-8; a TSV also with `quoting=csv.QUOTE_NONE`), pandas
3.0.5's `read_csv` (also with `keep_default_na=False`, a TSV's with `quoting=csv.QUOTE_NONE` too),
jq 1.7 (`jq -c`), ffmpeg 8.1.2 (`-i FILE -f srt -`) and ffman (`ingest`) read it; then a CSV, a TSV
and a JSON with a UTF-8 BOM, and in UTF-16 (LE, its BOM). ffmpeg opened none of the JSON, CSV, TSV
and `.aud` files, nor whisper-cli's and OpenAI's `.txt` ("Invalid data found when processing
input"); WhisperX's diarized `.txt`, its first line `[SPEAKER_00]: ...`, it opened as `lrc`, 0 cues.

| File                                                            | Python                                                                                                                                         | pandas                                                                              | jq                                                              | ffman                                                                                             |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| whisper-cli `-oj` (a raw tab, a newline)                        | `JSONDecodeError`: "Invalid control character"                                                                                                 | -                                                                                   | "control characters from U+0000 through U+001F must be escaped" | read: `tab here newline`                                                                          |
| `-ojf` (an `é` over two tokens)                                 | `UnicodeDecodeError`                                                                                                                           | -                                                                                   | with its raw tab escaped: each token's lone byte U+FFFD         | read: `café`, the `é` in the word where it starts                                                 |
| whisper-cli `-ocsv` (a quoted newline)                          | 4 rows of 3 fields                                                                                                                             | 3 rows, the newline in the text                                                     | -                                                               | read: `tab here newline`                                                                          |
| the filter's `json`                                             | `JSONDecodeError`: "Expecting ',' delimiter" (its `"`)                                                                                         | -                                                                                   | "Invalid numeric literal"                                       | read: `Hello "world" \ <b>bold</b>`, `tab here newline`, each text as written                     |
| the filter's `json`, no `"` nor break                           | `JSONDecodeError`: "Extra data"                                                                                                                | -                                                                                   | 2 values, one a line                                            | read: `Hello`, `again`                                                                            |
| OpenAI `tsv` (a newline in a text)                              | 5 rows, the last of 1 field                                                                                                                    | 4 rows, the last `start` `newline`, `end` and `text` NaN                            | -                                                               | `past an hour newline`, noted (`1 TSV lines of no tab read as the text of the record before ...`) |
| OpenAI `tsv`, a text opening with `"` (`"Wait` ... `he left."`) | 5 rows: the quotes dropped, three records one text; `QUOTE_NONE`: 7 rows, as written                                                           | 4 rows, the same; `NA` NaN; `QUOTE_NONE, keep_default_na=False`: 6 rows, as written | -                                                               | read as written                                                                                   |
| the same texts, a CSV by `csv.writer` (rule 3)                  | 7 rows, as written                                                                                                                             | 6 rows, `NA` NaN; `keep_default_na=False`: as written                               | -                                                               | read as written                                                                                   |
| OpenAI `json`                                                   | read                                                                                                                                           | -                                                                                   | read                                                            | read: `past an hour newline`; 1.0005 s 1001 ms (TSV: 1000)                                        |
| WhisperX `json`, a `NaN` start                                  | read: `nan`                                                                                                                                    | -                                                                                   | read: `null`                                                    | that segment no time: dropped (alone, `no timed text`)                                            |
| a UTF-8 BOM                                                     | `json.loads(bytes)`: read; text decoded `utf-8`: "Unexpected UTF-8 BOM (decode using utf-8-sig)"; `csv`: the header's first name `\ufeffstart` | read                                                                                | read                                                            | read                                                                                              |
| UTF-16, its BOM                                                 | `json.loads(bytes)`: read; `csv`: `UnicodeDecodeError`                                                                                         | `UnicodeDecodeError`                                                                | "Invalid numeric literal"                                       | read                                                                                              |

How ffman reads their words back, and the other formats' word timings: `subtitle-mappings`'
`words.md`.
