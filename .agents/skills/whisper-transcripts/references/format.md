# The whisper tools' outputs: whisper.cpp, OpenAI whisper, WhisperX

Each output is defined by its writer alone. Researched at nixpkgs' pins: whisper.cpp v1.8.4
(`examples/cli/cli.cpp`, `examples/common-whisper.cpp`, `src/whisper.cpp`,
`models/convert-pt-to-ggml.py`), openai-whisper v20250625 (`whisper/utils.py`, `transcribe.py`,
`timing.py`, `assets/multilingual.tiktoken`), WhisperX v3.8.5 (`whisperx/utils.py`,
`transcribe.py`, `asr.py`, `alignment.py`, `diarize.py`, `schema.py`, `__main__.py`). Measured
by `../scripts/measure.py`: whisper.cpp's writers cut from `cli.cpp` verbatim and compiled
against stubs serving their segments and tokens, and `whisper_wrap_segment` from
`src/whisper.cpp`, fed tokens by openai-whisper's `multilingual.tiktoken`; OpenAI's and
WhisperX's writers imported and called (its output is the tables marked *measured*). SubRip,
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
| `-tdrz` | `.json` | `speaker_turn_next` (true/false) per segment                                                                                                                                                                      |

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

## OpenAI whisper (`whisper`)

`--output_format` `txt`, `vtt`, `srt`, `tsv`, `json` or `all` (the default). The result:
`{"text", "segments": [...], "language"}`; each segment `id, seek, start, end, text, tokens,
temperature, avg_logprob, compression_ratio, no_speech_prob`, and with `--word_timestamps True`
`words: [{word, start, end, probability}]`. Segment times are floats in seconds (an offset plus
multiples of 0.02 s, `transcribe.py`; with words, the first and last word's); word times
`round(t, 2)` (`timing.py`).

| Writer      | Content                                                                                                                                                                                                                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `WriteJSON` | `json.dump(result)`: ASCII, every other character `\uXXXX`; floats as Python writes them                                                                                                                                                                                                 |
| `WriteTSV`  | `start\tend\ttext` header; `round(1000 * t)` integer ms; the text stripped, tabs made spaces -- a newline kept, breaking the row                                                                                                                                                         |
| `WriteTXT`  | each segment's text, stripped, a line each                                                                                                                                                                                                                                               |
| `WriteSRT`  | ms by `round(seconds * 1000)`, `HH:MM:SS,mmm`; without words, a cue per segment, its text stripped and `-->` made `->`; with words, cues from the words (`--max_line_width`, `--max_line_count`, `--max_words_per_line`), `--highlight_words` a cue per word span with the word in `<u>` |
| `WriteVTT`  | as SRT, `WEBVTT` first, `MM:SS.mmm` (hours only when non-zero), no identifiers                                                                                                                                                                                                           |

*Measured*: `round(seconds * 1000)` rounds a tie to even -- 1.0005 s, 1.0015 s and 0.0005 s
make the floats 1000.5, 1001.5 and 0.5, written 1000, 1002 and 0 ms; `-->` replaced in segment cues, not in word cues; `<b>` and `&` never
escaped (an SRT or VTT cue's markup is the transcript's text); with `--highlight_words` the gaps
between words get a cue of their own without `<u>`; `--max_line_width 8 --max_line_count 1` made
a cue per word.

## WhisperX (`whisperx`)

`--output_format` `all` (the default: `srt vtt txt tsv json`) or one of them, or `aud`. The
result: `{"segments": [...], "word_segments": [...], "language"}`. Aligned (the default), each
segment `start, end, text, words: [{word, start, end, score}]` -- a word the aligner could not
place has `word` alone -- plus `speaker` (segment and words) with `--diarize`, `chars` with
`--return_char_alignments`, `avg_logprob` when the model gave one; times `round(t, 3)` where
aligned (`alignment.py`), interpolated values unrounded. `--no_align`: `{text, start, end}` per
segment, `round(t, 3)` (`asr.py`).

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

| Output                  | Times                                    | Text                      | Words                                              | Speakers           |
| ----------------------- | ---------------------------------------- | ------------------------- | -------------------------------------------------- | ------------------ |
| whisper.cpp `-oj`       | ms, multiples of 10 (`offsets`)          | segments                  | none                                               | `-di`: `0 1 ?`     |
| whisper.cpp `-ojf`      | ms, multiples of 10; DTW in cs (a float) | segments; tokens as bytes | tokens with times, `p`, `t_dtw`, specials          | `-di`, `-tdrz`     |
| whisper.cpp `-ocsv`     | ms, multiples of 10                      | segments                  | none                                               | `-di` column       |
| whisper.cpp `-olrc`     | starts only, cs                          | segments                  | none                                               | `(speaker 0)` text |
| whisper.cpp `-otxt`     | none                                     | segments                  | none                                               | `(speaker 0)` text |
| OpenAI `json`           | seconds, floats; words 0.01 s            | segments, `text`          | `--word_timestamps`: word, start, end, probability | none               |
| OpenAI / WhisperX `tsv` | ms, integers                             | segments                  | none                                               | none               |
| OpenAI / WhisperX `txt` | none                                     | segments                  | none                                               | WhisperX: prefix   |
| WhisperX `json`         | seconds, 0.001 s where aligned           | segments                  | word, start, end, score (or the word alone)        | `speaker` fields   |
| WhisperX `aud`          | seconds, floats                          | segments                  | none                                               | `[[...]]` prefix   |

How ffman reads their words back, and the other formats' word timings: `subtitle-mappings`'
`words.md`.
