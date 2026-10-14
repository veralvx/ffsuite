# Word timings: how each format holds them, what ffman reads back, how they are drawn

The same words in every form -- `one` 1.0-1.5 s, `two` 1.5-1.8, `three` 1.8-2.0, a sentence; `four`
3.0-3.4, a 200 ms gap, `five` 3.6-4.0, another -- read back by ffman (subverter's readers, then
`ffman.subs.ingest`; measured again once a sentence of no words was counted), ASS's karaoke drawn by
libass 0.17.1 (FFmpeg n8.1.2's `ass` filter, a frame at each millisecond asked) and WebVTT's
timestamps by Chromium 141.0.7390.37 (a `<track>`, its frames read by colour). Measured by
`../scripts/words.py` (its output is the tables marked *measured*), which checks its SubRip and
WebVTT cues equal to OpenAI whisper's own (`WriteSRT`, `WriteVTT`, v20250625). Each format alone:
the `subrip`, `webvtt`, `ass`, `lrc` and `whisper-transcripts` records; ffmpeg's conversions of
these forms: `ffmpeg.md`.

## How each holds a word's time

| Form                                                                                                                   | A word's start, its end                                                                                                                             | Its sentence                       | Source                                                    |
| ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- | --------------------------------------------------------- |
| whisper-cli `-ojf`: tokens -- to ffman, a word from a token opening with a space (every token, in `zh ja th lo km my`) | its tokens' offsets, ms (multiples of 10); with `-dtw`, one time a token (`t_dtw`, cs), read as its start -- the word ends at the next's            | the `transcription[]` entry        | `cli.cpp`; subverter's `whisper.py`                       |
| WhisperX's and OpenAI's JSON `words`                                                                                   | `start`, `end`, seconds (WhisperX 0.001 where aligned, OpenAI 0.01); a word WhisperX could not place, its `word` alone                              | the segment                        | `whisper-transcripts`                                     |
| SubRip and WebVTT `--highlight_words` (OpenAI, WhisperX)                                                               | a cue a word: the sentence, that word in `<u>`; a gap between words, a cue of the sentence alone                                                    | the run of cues of one text        | `utils.py`, `iterate_result`                              |
| WebVTT timestamp tags, `<00:01.500>` before a word                                                                     | a start alone, ms -- each later than the cue's start and the last tag, earlier than its end: a word ends at the next tag, the last at the cue's end | the cue (its first word starts it) | W3C WebVTT, "WebVTT cue timestamp"                        |
| ASS `\k` (`\kf`, `\ko`)                                                                                                | durations, cs, consecutive from the event's start: a word ends where the next starts; a gap, a tag of no text                                       | the event                          | `ass` record; `ass_parse.c`                               |
| Enhanced LRC (A2), `<mm:ss.xx>` before a word                                                                          | a start alone, cs: a word ends at the next's, a line's last at the next line                                                                        | the line                           | Wikipedia's "LRC (file format)"                           |
| A cue, row or line a word: whisper-cli `-ml 1 -sow` (`-ml 1` alone, a token), OpenAI `--max_words_per_line 1`          | its cue's (LRC: a start alone)                                                                                                                      | none                               | whisper.cpp's README ("Word-level timestamp"); `utils.py` |

ASS's `\k` and its kin time syllables, not words: karaoke splits a word where it is sung.

## What ffman reads back

*Measured* -- subverter's reading (its cues and words), then ffman's (its chunks and words):

| Form                                                       | subverter                                                            | ffman                                                                                                                       |
| ---------------------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| a cue a sentence                                           | the cues; no words                                                   | the chunks; no words                                                                                                        |
| a cue (CSV, TSV row) a word                                | a cue a word; no words, no sentence                                  | a chunk a word -- whisper-cli's leading space trimmed                                                                       |
| LRC, a line a word                                         | each to the next start: `three` to 3.0, `four` to 3.6, `five` 3 s on | the same: the ends and the gap lost                                                                                         |
| SubRip or WebVTT `--highlight_words`                       | the sentences (1-2 s, 3-4 s) and every word, the gap kept            | the same                                                                                                                    |
| WebVTT timestamps, words bare or in `<c>`                  | the cue, its tags in its text; no words                              | the text, its tags dropped: the times lost                                                                                  |
| ASS `\k`                                                   | refused: no ASS reader                                               | nothing read: burned as it is                                                                                               |
| Enhanced LRC, a space after each tag or none               | each line to the next, its tags in its text; no words                | the text, its tags dropped: the times lost; the empty last line (the end) dropped                                           |
| whisper-cli `-ojf`, token offsets                          | every word, the gap kept                                             | the same, the leading spaces trimmed                                                                                        |
| whisper-cli `-ojf -dtw`                                    | every word; `four` to 3.6: DTW times read as starts                  | the same                                                                                                                    |
| WhisperX JSON                                              | every word, the gap kept                                             | the same                                                                                                                    |
| WhisperX, `two` unaligned, the second segment's words `[]` | `two` untimed; the second sentence no words                          | `two` placed between its neighbours (1.5-1.8 s), noted; the second sentence no words, counted in the "no word timings" note |

## A chunk's words, and chunks from words

- **A chunk's words from none: impossible.** A form holds a word's time or it does not; a chunk
  shared among its words by characters would be a time no source gave. ffman places a word only
  inside a sentence with a timed word (`subs.normalize._place`, bash's `place()`); a sentence
  with none is shown without highlighting, and `--overlay-mode chunk-word` refuses a source
  without words.
- **Chunks from words, by segment.** Every form but a cue a word names each word's sentence; a chunk
  is that sentence. Its times: whisper-cli's entry's offsets; WhisperX's segment's, from the
  same characters' times as its words' (`alignment.py`); OpenAI's, its first word's start and its
  last word's end, unless that word overruns it by more than 0.5 s -- then the word is shortened
  (`timing.py`); a highlighted run's first and last cue's; the cue's, the event's, the line's (to
  the next). A form of a cue a word names none: its sentences are not in the file, and
  `chunk-word` refuses it.

## How each is drawn

*Measured* -- libass: each word's share of the fill (PrimaryColour) among its fill and karaoke
pixels (SecondaryColour), %, through an event from 1 s:

| Event                                | At (ms): each word's fill                                                                       |
| ------------------------------------ | ----------------------------------------------------------------------------------------------- |
| `{\k50}one {\k30}two {\k20}three`    | 999: nothing; 1000: 100 0 0; 1499: 100 0 0; 1500: 100 100 0; 1799: 100 100 0; 1800: 100 100 100 |
| the same in `\kf`                    | 1000: 0 0 0; 1250: 61 0 0; 1499: 100 0 0; 1650: 100 63 0; 1900: 100 100 53; 2000: 100 100 100   |
| the same in `\ko`, an outline of 3   | 1000: 100 0 0, the first's outline alone drawn; 1500: 100 100 0, two outlines                   |
| `{\k40}four {\k20}{\k40}five`: a gap | 1599: 100 0; 1600: 100 100                                                                      |
| `{\k30}one {\kt100}{\k30}two`        | 1999: 100 0; 2000: 100 100: `\kt` the next syllable's start, cs from the event's                |
| `{\k12.59}one {\k10}two`             | 1124: 100 0; 1125: 100 100: 125.9 ms truncated                                                  |

| Rule                                                                                                                                                                  | Source                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| A `\k` argument is centiseconds read as a decimal, made ms by `* 10` and truncated (`dtoi32`); none, 100                                                              | `ass_parse.c`                    |
| `\k`: the syllable in SecondaryColour, then PrimaryColour at once at its start -- the first at the event's start. `\kf` (`\K`): swept left to right over its duration | `ass_process_karaoke_effects`    |
| `\ko`: as `\k`, its outline not drawn before its start                                                                                                                | `ass_render.c` (`EF_KARAOKE_KO`) |
| Alike in 0.17.1 (ffmpeg's here) and 0.17.4                                                                                                                            | the two tags' diff               |

*Measured* -- Chromium: each word's colour at 1.2, 1.6 and 1.9 s (`::cue(:past)` red,
`::cue(:future)` blue; neither, white):

| Cue                                | 1.2 s             | 1.6 s             | 1.9 s             |
| ---------------------------------- | ----------------- | ----------------- | ----------------- |
| bare words, the page's CSS         | white white white | white white white | white white white |
| words in `<c>`, the page's CSS     | red blue blue     | red red blue      | red red red       |
| words in `<c>`, the file's `STYLE` | red blue blue     | red red blue      | red red red       |
| words in `<c>`, no CSS             | white grey grey   | white white grey  | white white white |

| Rule                                                                                                                                                                          | Source                                                                      |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `:past` and `:future` match a cue's elements alone: a bare word is never either                                                                                               | W3C WebVTT, "The :past and :future pseudo-classes"; Chromium's `vtt_cue.cc` |
| Chromium: an element is `:past` unless a timestamp past the current time precedes it -- the word being spoken is `:past` (the specification: neither); its own FIXME notes it | `VTTCue::UpdatePastAndFutureNodes`                                          |
| With no CSS, Chromium greys what is to come: its own `video::cue(:future) { color: gray; }`                                                                                   | `mediaControls.css`                                                         |
| A file's `STYLE` block styles them as the page's CSS                                                                                                                          | measured                                                                    |
| ffmpeg's decoder drops every timestamp                                                                                                                                        | `ffmpeg.md`                                                                 |

## What a by-word output is, in each

| Target     | A cue a word                                                                    | Timed within the chunk                                                                                                          |
| ---------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| SubRip     | `--highlight_words`' cues: the sentence, the word in `<u>` -- read back exactly | none: SubRip has no time inside a cue                                                                                           |
| WebVTT     | the same                                                                        | timestamps before each word, each word in `<c>`: starts alone (a gap lost); Chromium greys the words to come; ffmpeg drops them |
| ASS        | an event a word (ffman's own burn draws its words so)                           | `\k` (`\kf`, `\ko`): durations, a gap its own tag -- every time kept, to the cs; libass draws them                              |
| LRC        | a line a word: starts alone, no sentence                                        | Enhanced LRC: starts alone, cs; Navidrome and Jellyfin read them, ffmpeg, libass and ffman none                                 |
| CSV, TSV   | a row a word: no sentence                                                       | none                                                                                                                            |
| JSON       | a segment a word (whisper-cli `-ml 1 -sow -oj`): no sentence                    | whisper-cli's tokens, WhisperX's words: both read back exactly                                                                  |
| Plain text | none                                                                            | none                                                                                                                            |

What ffman reads today keeps every word only from the JSON forms and the highlighted cues;
WebVTT's timestamps, ASS's `\k` and Enhanced LRC's tags hold word times its readers drop.
