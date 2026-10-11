# SubRip, WebVTT, ASS and LRC through ffmpeg: what each conversion keeps

Every direction among the four, as FFmpeg n8.1.2 converts them (`ffmpeg -i in.X out.Y`), against
what ffman's readers (subverter, at `5853573`) read of each source. Measured by
`../scripts/ffmpeg.py`: a subject per table, each written in every format that holds it, each
converted into every format and back (its output is the tables). How each format is read and
written alone: the `subrip`, `webvtt`, `ass` and `lrc` records.

## How ffmpeg converts

| Rule                                                                                                                                                                                                                   | Source                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| A conversion decodes each cue into an ASS event and encodes it again: SubRip by `subrip`, WebVTT by `webvtt`, ASS by `ass`, LRC by `text` (its markup escaped: read literally); LRC is written by the `subrip` encoder | the decoders; `lrcenc.c` (`subtitle_codec`) |
| From SubRip, WebVTT or LRC, ffmpeg's default script -- PlayRes 384x288, one `Default` style; from ASS, its own                                                                                                         | `ff_ass_subtitle_header_default`            |
| A format into itself is a transcoding too, unless `-c copy`: SubRip's spaces trimmed and coordinates made `{\an5}`; WebVTT's identifiers and settings dropped                                                          | the decoders                                |
| Into ASS, a start and a duration are each rounded to centiseconds: the end is their sum -- `3.005 -> 4.995` becomes `3.01 -> 5.00`, and an end can pass the next start by 10 ms                                        | the time base, 1/100                        |
| ASS ends at 9:59:59.99: an event at 10 h is written there, start and end alike. LRC has no end: each line ends at the next start, the last at its own                                                                  | `assenc.c`; `lrcdec.c`                      |

*Measured* -- text (two cues: `A & B < C > D` over two lines, then `  spaced  `):

| Source | ffman reads                                                | ffmpeg into SubRip, WebVTT, ASS, LRC                                                                                                                            |
| ------ | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SubRip | the lines joined by a space; spaces kept                   | `A & B < C > D` written as is into all four -- invalid WebVTT, read back as `A & B  D`; spaces trimmed (SubRip's decoder); LRC: a line each, at the cue's start |
| WebVTT | `A &amp; B &lt; C &gt; D` (decoded after: `A & B < C > D`) | the references decoded, then written as is: SubRip and ASS right, WebVTT invalid; leading spaces dropped by every writer but ASS's                              |
| ASS    | none (burned as it is)                                     | `\N` a line break; leading spaces dropped by every writer but ASS's; into WebVTT unescaped (read back `A & B  D`)                                               |
| LRC    | each line to the next start, the last 3 s on               | each cue to the next start; the empty last line a cue of no length                                                                                              |

*Measured* -- markup:

| Source                                  | ffman reads                   | SubRip                                            | WebVTT                                   | ASS              | LRC                                           |
| --------------------------------------- | ----------------------------- | ------------------------------------------------- | ---------------------------------------- | ---------------- | --------------------------------------------- |
| SubRip `<b> <i> <u> <s> <font color>`   | as written (its chunks plain) | kept                                              | `<b> <i> <u>`; strike and colour dropped | `\b \i \u \s \c` | SubRip's tags, as text                        |
| WebVTT `<b> <i> <u> <c.red> <c.yellow>` | as written (its chunks plain) | `<b> <i> <u>`; classes dropped                    | the same                                 | `\b \i \u`       | SubRip's tags, as text                        |
| ASS `\b \i \u \s \c \fn \fs`            | none                          | all, font and size as `<font face>` `<font size>` | `<b> <i> <u>`; the rest dropped          | kept             | SubRip's tags, as text -- read back literally |

*Measured* -- positions:

| Source                                            | ffman reads                    | SubRip                        | WebVTT                 | ASS                               | LRC                                                      |
| ------------------------------------------------- | ------------------------------ | ----------------------------- | ---------------------- | --------------------------------- | -------------------------------------------------------- |
| SubRip `{\an8}`; `X1:100 X2:300 Y1:400 Y2:450`    | `{\an8}` in the text; box lost | `{\an8}`; the box as `{\an5}` | both lost              | `{\an8}`; `{\an5}{\pos(106,255)}` | `{\an8}` and `{\an5}` as text (read back escaped: shown) |
| WebVTT `intro`, `line:0 align:start position:10%` | lost                           | lost                          | lost, even into WebVTT | lost                              | lost                                                     |
| ASS `{\an8}`; `{\pos(10,20)}`                     | none                           | `{\an8}`; `\pos` lost         | both lost              | kept                              | `{\an8}` as text; `\pos` lost                            |

*Measured* -- speakers: WebVTT's `<v Bob>` and ASS's `Name` are lost in every conversion but ASS
into itself (ffman reads `<v Bob>Hello</v>`, its chunk `Hello`; SubRip and LRC hold none).

*Measured* -- overlaps (1-4 s and 2-3 s): kept in SubRip, WebVTT and ASS, every direction, and by
ffman's readers; into LRC, starts only: read back, the first cue ends where the second starts.

*Measured* -- an empty cue, a cue of no length (3 s to 3 s), then another:

| Source | ffman reads                       | ffmpeg                                                                                                                                                              |
| ------ | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SubRip | all three (ffman drops the empty) | the empty cue dropped (no text, no cue); the zero-length one kept in all four                                                                                       |
| WebVTT | all three                         | the same: the decoder drops the empty one                                                                                                                           |
| ASS    | none                              | the empty event written as a cue of no text into SubRip, WebVTT and LRC; read back from SubRip and WebVTT, dropped; from LRC, an event of no text to the next start |
| LRC    | all, the empty line a cue         | an empty line a cue of no text; two lines at 3 s: the first of no length                                                                                            |

*Measured* -- word timing:

| Source                                                         | ffman reads                                    | SubRip, WebVTT, ASS                                                | LRC                     |
| -------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------ | ----------------------- |
| SubRip, WhisperX's `--highlight_words` (a cue per word, `<u>`) | one sentence, its three words timed            | kept: a cue a word, `<u>` (ASS `\u`)                               | the cues, `<u>` as text |
| WebVTT `one <00:00:01.500>two <00:00:01.800>three`             | the text, the timestamps in it (dropped after) | `one two three`: the word times lost                               | the same                |
| ASS `{\k50}one {\k30}two {\k20}three`                          | none                                           | `one two three` in SubRip and WebVTT; kept in ASS                  | `one two three`         |
| Enhanced LRC `<00:01.00>one <00:01.50>two`                     | the text, the stamps in it (dropped after)     | the stamps as text (WebVTT then reads them as tags and drops them) | kept as text            |

*Measured* -- times (`1.234 -> 2.345`, `3.005 -> 4.995`, `10:00:00 -> 10:00:01`):

| Source | ffman reads           | SubRip, WebVTT                          | ASS                                                         | LRC                                                |
| ------ | --------------------- | --------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| SubRip | to the millisecond    | to the millisecond                      | `1.23 -> 2.34`, `3.01 -> 5.00`; 10 h at `9:59:59.99`        | `[00:01.23]`, `[00:03.01]`, `[600:00.00]`; no ends |
| WebVTT | to the millisecond    | to the millisecond                      | the same                                                    | the same                                           |
| ASS    | none                  | centiseconds as milliseconds            | kept                                                        | minutes past 59: `[599:59.00]`                     |
| LRC    | `[00:01.234]` 1234 ms | to the millisecond, ends the next start | `1.23 -> 3.00`, `3.01 -> 1:01:00.01` -- past the next start | hundredths                                         |

## What it means for ffman's converters

ffmpeg keeps text and times between SubRip and WebVTT (but `<` and `&`: its WebVTT writer
escapes neither, so they are lost on reading back, and SubRip's spaces are trimmed) and ASS into
itself (but past 9:59:59.99). Every other direction loses what the source holds and the target
or ffmpeg's ASS does not: WebVTT's identifiers, settings, classes, speakers and timestamps; ASS's
positions, colours, fonts and karaoke; SubRip's strike-through and colours into WebVTT -- and
milliseconds become centiseconds rounded apart. Into LRC, SubRip's markup is written as text,
and ends are gone. ffman's readers keep milliseconds and text exactly and read WhisperX's
highlighted cues as words, and nothing else: each chunk is plain text (tags, overrides and
settings dropped), ASS is not read at all. JSON, CSV, TSV and plain text have no reader or writer
in ffmpeg: ffman's alone.
