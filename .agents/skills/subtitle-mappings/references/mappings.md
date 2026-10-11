# SubRip, WebVTT, ASS, LRC, CSV, TSV, whisper JSON and plain text: the mappings

Every direction among ffman's subtitle formats, element by element: how each format holds it,
what ffmpeg makes of it (FFmpeg n8.1.2; it converts SubRip, WebVTT, ASS and LRC alone), what
ffman reads of it (subverter's readers, then `ffman.subs.ingest`), and the candidates a converter
of ffman's could take -- marked *candidate*, for 6.8.3's model to decide. Sources: the format
records (`subrip`, `webvtt`, `ass`, `lrc`, `whisper-transcripts`), [`ffmpeg.md`](ffmpeg.md)
(every direction ffmpeg converts), [`words.md`](words.md) (word times); where they left a mapping
open, `../scripts/mappings.py` measured it (its output is the rows marked *measured*): ffmpeg's
conversions, ffman's readings, and libass 0.17.1 (through ffmpeg's `ass` filter) and Chromium
141.0.7390.37 (a `<track>`) drawing on 1280x720.

## Every direction: what each format holds

A direction loses what its target's column lacks of its source's, and what its converter drops
besides (the sections below).

| Element                 | SubRip                   | WebVTT                                       | ASS (SSA)                             | LRC                          | CSV                      | TSV      | whisper JSON                                               | Plain text |
| ----------------------- | ------------------------ | -------------------------------------------- | ------------------------------------- | ---------------------------- | ------------------------ | -------- | ---------------------------------------------------------- | ---------- |
| Times                   | start, end; ms           | start, end; ms                               | start, end; cs                        | start; cs                    | start, end; ms           | the same | whisper-cli ms (multiples of 10); WhisperX, OpenAI seconds | none       |
| Line breaks             | lines                    | lines                                        | `\N`                                  | none (a line each, repeated) | inside quotes            | none     | `\n`                                                       | none       |
| Bold, italic, underline | `b i u`, and `s`         | `b i u`; strike by `STYLE`                   | `\b \i \u \s`                         | none                         | none                     | none     | none                                                       | none       |
| Colour, font, size      | `<font color face size>` | by `STYLE` classes                           | styles, `\c \fn \fs`...               | none                         | none                     | none     | none                                                       | none       |
| Position                | `{\an1-9}`               | `line`, `position`, `align`, `size`, regions | alignment, margins, `\pos`, `\move`   | none                         | none                     | none     | none                                                       | none       |
| Speakers                | none (a text prefix)     | `<v name>`                                   | `Name`                                | none                         | whisper-cli `-di` column | none     | `speaker` (whisper-cli `-di`, WhisperX `--diarize`)        | none       |
| Word times              | a cue a word (`<u>`)     | timestamps; a cue a word                     | `\k` and kin                          | Enhanced LRC's tags          | a row a word             | the same | tokens, words                                              | none       |
| Identifiers, comments   | the index                | identifiers, `NOTE`                          | `Comment:` events                     | none                         | none                     | none     | none                                                       | none       |
| Title, header           | none                     | the `WEBVTT` line's text                     | `Title` and every `[Script Info]` key | `[ti:]` and the ID tags      | the header row           | the same | `result.language`, the model                               | none       |

## Times

| From -> to                        | ffmpeg                                                                                                                                          | ffman reads                                  | Candidate                                                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| ms -> ASS's cs                    | start and duration rounded apart: *measured*, `1.006 -> 2.004` and `2.004 -> 3.000` became `1.01 -> 2.01` and `2.00 -> 3.00` -- an overlap made | the source's ms exact (*measured*)           | each time rounded alone, half up, as ffman rounds a time: never an overlap a source lacks (rounding keeps order) |
| ms -> LRC                         | starts, `[mm:ss.xx]`; 1.995 s written `[00:01.100]` (the `lrc` record)                                                                          | --                                           | the same rounding; no end: below                                                                                 |
| LRC -> any                        | each line to the next start; the last of no length                                                                                              | each line to the next start, the last 3 s on | --                                                                                                               |
| whisper-cli's (10 ms), WhisperX's | --                                                                                                                                              | ms, half up (`fields.ms`)                    | --                                                                                                               |
| 10 h and later into ASS           | written `9:59:59.99`, no length (the `ass` record)                                                                                              | --                                           | written as is: libass reads hours past 9 (the `ass` record); Aegisub caps at `9:59:59.99`                        |

## Ends, overlaps, empty and reversed cues

| Element            | Formats                                                                                          | ffmpeg                                                                                                                   | ffman reads                                                                       | Candidate                                                                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| An end             | all but LRC and plain text                                                                       | into LRC lost; *measured*: LRC's empty last line `[00:03.00]` a cue of no length and no text into SubRip, WebVTT and ASS | kept by subverter; LRC's ends the next start                                      | into LRC, an empty timed line at a cue's end when the next starts later -- the convention ffmpeg and ffman both read as an end |
| Overlapping cues   | SubRip, WebVTT, ASS, the tables, JSON                                                            | kept (`ffmpeg.md`)                                                                                                       | subverter keeps them; ffman's burn cuts each at the next start (`normalize.cues`) | kept: a converter is not a burn                                                                                                |
| An empty cue       | WebVTT, ASS, LRC, the tables, JSON; SubRip cannot (a blank line ends a cue: ffmpeg reads no cue) | dropped from SubRip and WebVTT sources; ASS's written as a cue of no text (`ffmpeg.md`)                                  | dropped (no text, no chunk)                                                       | kept, but into SubRip, which cannot hold it                                                                                    |
| A cue of no length | all but plain text                                                                               | kept                                                                                                                     | dropped (`normalize.cues`)                                                        | kept: it is the source's                                                                                                       |
| End before start   | every format with an end (Chromium keeps one, `3 -> 1`)                                          | the gap to the next start (SubRip, WebVTT, ASS records)                                                                  | dropped                                                                           | dropped, noted                                                                                                                 |

## Text and its escapes

| Format     | What it cannot hold, and its escape                                                                                            | Source                |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------ | --------------------- |
| SubRip     | a blank line; no escape: `a < b and c > d` decoded `a {\b1} d`; a line of a number before an unindexed cue taken for its index | `subrip` record       |
| WebVTT     | a blank line; `-->`; `&` and `<` written `&amp;` `&lt;` (every HTML reference read)                                            | `webvtt` record       |
| ASS        | a line end (`\N` instead); `{` starts a block (`\{` `\}` literal); a `\` before `N`, `n` or `h` has no escape                  | `ass` record          |
| LRC        | a line end; a text starting with `[`: ffmpeg's muxer warns                                                                     | `lrc` record          |
| CSV        | nothing: RFC 4180 quotes (`"` doubled, line ends inside quotes)                                                                | `whisper-transcripts` |
| TSV        | a tab and a line end: OpenAI's writer makes a tab a space, a line end breaks the row                                           | `whisper-transcripts` |
| JSON       | nothing (whisper-cli escapes `"` and `\` alone; its raw tab and line end read as text)                                         | `whisper-transcripts` |
| Plain text | a line end (a line a cue)                                                                                                      | whisper's `-otxt`     |

*Measured* and recorded, what crosses:

| Case                                      | ffmpeg                                                                            | ffman reads                                                                                                      | Candidate                                                      |
| ----------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| SubRip or ASS `A & B < C > D` into WebVTT | written as is: invalid, read back `A & B  D` (`ffmpeg.md`)                        | --                                                                                                               | `&` `<` `>` written as references: what the specification asks |
| WebVTT `&amp; &lt;` into the others       | six references decoded (`ffmpeg.md`)                                              | every reference decoded (`subverter.decoded`)                                                                    | decoded, then escaped as the target needs                      |
| a SubRip text line `a --> b`              | text: kept into SubRip, WebVTT (where it ends the cue for a browser) and ASS      | text: `a --> b c` (*measured*; before 6.8.1's fix, a timing line: the cue lost)                                  | text, as ffmpeg                                                |
| a WebVTT text line `a --> b`              | kept, as SubRip's                                                                 | the cue's end, `c` no cue's: the cue empty (*measured*), as the specification and Chromium (the `webvtt` record) | as ffman reads it                                              |
| a CSV field over two lines; `a, b`        | --                                                                                | `one\ntwo` (a break, joined by ffman: `one two`); `a, b`                                                         | the break kept                                                 |
| into plain text                           | **none**: no muxer for `.txt` -- "Unable to choose an output format" (*measured*) | --                                                                                                               | ffman's: a line a cue, the text alone (whisper's `-otxt`)      |

## Line breaks and spaces

| Case                                | ffmpeg                                                                  | ffman reads                                                      | Candidate                                            |
| ----------------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------- |
| two lines, SubRip or WebVTT         | kept: lines, `\N`; into LRC a line each at the same start (*measured*)  | joined by a space: `one two`                                     | kept; into LRC, TSV and plain text joined by a space |
| ASS `\n` (WrapStyle 0)              | a line break into SubRip and WebVTT (the `subrip` and `webvtt` records) | --                                                               | a space, as libass draws it (below)                  |
| a SubRip line's spaces: `  a   b  ` | the leading and trailing trimmed by the decoder                         | kept by subverter; ffman trims them and collapses the run: `a b` | the leading and trailing trimmed, the run kept       |

*Measured* -- the ink's edges and width (px), libass and Chromium, the cue centred:

| Text                                 | libass           | Chromium                                  |
| ------------------------------------ | ---------------- | ----------------------------------------- |
| `ab`; `a b`                          | 44; 56           | 38; 48                                    |
| `a  b`; `a     b`                    | 68; 104: kept    | 58; 88: kept                              |
| `  ab` (leading); `ab  `             | 618-662, as `ab` | 631-669 and 611-649: each shifts the text |
| `a`, a tab, `b`                      | 56: a space      | 96: to a tab stop                         |
| `a\h\h\hb`; `a&nbsp;&nbsp;&nbsp;b`   | 80: three spaces | 68: three spaces                          |
| `a\nb` (ASS, WrapStyle 0); two lines | 56: a space      | 20 x 63: two lines                        |

| Rule                                                                                                                                                                  | Source                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| libass draws runs of spaces, and lays a line out without its leading and trailing spaces                                                                              | measured                                                   |
| Chromium keeps every space and tab: `white-space: pre-wrap` -- the specification asks `pre-line`, which collapses runs and drops a line's leading and trailing spaces | `mediaControls.css`; W3C WebVTT, "Applying CSS properties" |
| *Candidate*: inner runs kept (both draw them), a line's leading and trailing spaces trimmed, a tab written as a space                                                 | --                                                         |

## Bold, italic, underline, strike

| Source -> target                  | ffmpeg (`ffmpeg.md`)                     | Candidate                                                                          |
| --------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------- |
| `b i u` among SubRip, WebVTT, ASS | kept                                     | kept                                                                               |
| SubRip `<s>` -> WebVTT            | dropped                                  | a `STYLE` class, `text-decoration: line-through` -- Chromium draws it (*measured*) |
| ASS `\s` -> WebVTT                | dropped                                  | the same                                                                           |
| any -> LRC                        | SubRip's tags written as text            | dropped                                                                            |
| ffman reads                       | tags kept by subverter, dropped by ffman | kept in the model (6.8.3)                                                          |

*Measured* -- a line drawn across the text (rows inked across 90% of its width, as fractions of
its height): libass `\s1` 0.47-0.50, `\u1` 0.78-0.83; Chromium's `STYLE` line-through 0.38-0.44,
`<u>` 0.82-0.88.

## Colour, font and size

| Source -> target                                | ffmpeg (`ffmpeg.md`)      | Candidate                                                                            |
| ----------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------ |
| SubRip `<font color>`, ASS `\c` -> WebVTT       | dropped                   | a `STYLE` class per colour (`::cue(.c00ff80) { color: #00ff80 }`): Chromium draws it |
| SubRip `face`/`size`, ASS `\fn`/`\fs` -> WebVTT | dropped                   | a `STYLE` class: `font-family`, `font-size` (a percentage of the cue's)              |
| WebVTT classes -> SubRip, ASS                   | dropped                   | the colour of the file's `STYLE` rule for that class, where it is one                |
| ASS's style (font, size, colours) -> SubRip     | its tags around every cue | as ffmpeg: what differs from the target's default                                    |

*Measured*: Chromium draws a `STYLE` class's colour (`#00ff80`), `font-size: 200%` (34 to 68 px
high; libass `\fs96` from 48: 40 to 81) and `font-family: serif` (230 to 212 px wide; libass
`\fnSerif`, 275 to 316); it draws **none of WebVTT's default colour classes** -- `<c.red>`,
`<c.lime>` and the six others all white -- though the specification says they "must" set the colour
("Default classes"). A converter writes a `STYLE` block, never the default classes alone.

## Position

| Source -> target              | ffmpeg                                                                              | Candidate                                                                        |
| ----------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| ASS, SubRip `{\an}` -> WebVTT | dropped (`ffmpeg.md`)                                                               | the settings below                                                               |
| WebVTT settings -> any        | dropped                                                                             | the `{\an}` of the third of the frame `line` puts the cue in, and of its `align` |
| ASS `\pos`, `\move`           | `\pos` kept into ASS alone; SubRip's `X1..Y2` box `{\an5}{\pos(...)}` (`ffmpeg.md`) | ASS alone holds them: dropped elsewhere, noted                                   |

*Measured* -- where each draws, the ink's box as fractions of the frame (x, y):

| libass         | Box                                          | Chromium, the same place                        | Box                                          |
| -------------- | -------------------------------------------- | ----------------------------------------------- | -------------------------------------------- |
| `\an7` `8` `9` | 0.02-0.12, 0.45-0.55, 0.88-0.98; y 0.04-0.08 | `line:0` with `align:left`, none, `align:right` | 0.00-0.09, 0.46-0.54, 0.91-1.00; y 0.01-0.05 |
| `\an4` `5` `6` | the same x; y 0.48-0.52                      | `line:50%` with the same                        | the same x; y 0.48-0.52                      |
| `\an1` `2` `3` | the same x; y 0.92-0.96                      | no `line` (or `line:-1`), the same              | the same x; y 0.95-0.98                      |

| Rule (measured, Chromium)                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `align:start` is `align:left` (left-to-right text); `line:-1` is the default, the last line                                                                                |
| `line:50%` centres the cue; `line:90%`, y 0.86-0.89                                                                                                                        |
| No margin: a left or right cue touches the frame's edge, where libass keeps the style's margins (20 px here)                                                               |
| An inset by `position`: `position:10% align:left` x 0.10-0.19 and `position:90% align:right` x 0.81-0.90 -- but under a percentage `line`, the left one draws at 0.01-0.10 |

## Speakers

| Source -> target                                  | ffmpeg                | ffman reads (*measured*)             | Candidate                                                                         |
| ------------------------------------------------- | --------------------- | ------------------------------------ | --------------------------------------------------------------------------------- |
| WebVTT `<v Bob>` -> any                           | dropped (`ffmpeg.md`) | the tag in subverter's text; dropped | a speaker in the model: ASS `Name`, WebVTT `<v>`, JSON `speaker`                  |
| ASS `Name` -> SubRip, WebVTT, LRC                 | dropped (*measured*)  | (no ASS reader)                      | the same                                                                          |
| whisper-cli `-di` `speaker`, WhisperX's `speaker` | --                    | ignored                              | the same                                                                          |
| a speaker into SubRip, LRC, CSV, TSV, plain text  | --                    | --                                   | a text prefix, as WhisperX writes one (`[SPEAKER_00]: `), or dropped -- to decide |

## Identifiers, comments and titles

| Source -> target                           | ffmpeg (*measured*)                                                  | ffman reads                                | Candidate                                                  |
| ------------------------------------------ | -------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------------------------------- |
| WebVTT identifier (`intro`)                | dropped by every conversion (a stream copy keeps it)                 | dropped                                    | kept into WebVTT; elsewhere none holds it                  |
| WebVTT `NOTE`; ASS `Comment:`              | dropped                                                              | dropped                                    | each other's: a `NOTE` an ASS `Comment:`, and back         |
| WebVTT's title (`WEBVTT - The title`)      | dropped                                                              | dropped                                    | ASS `Title`, LRC `[ti:]`                                   |
| ASS `Title`                                | dropped                                                              | --                                         | WebVTT's title line, LRC `[ti:]`                           |
| LRC `[ti:]`, `[ar:]` and the other ID tags | read as metadata (`title`, `artist`), written into none (*measured*) | dropped                                    | `[ti:]` the title as above; the rest kept into LRC alone   |
| LRC `[offset:+500]`                        | applied, in microseconds (the `lrc` record)                          | **ignored** (*measured*: `one` at 1000 ms) | applied in ms, as the convention says -- to decide (6.8.1) |
| SubRip's index                             | renumbered                                                           | --                                         | renumbered                                                 |

## Word times

[`words.md`](words.md): how each holds them, what ffman reads back, how libass and Chromium draw
them, and what a by-word output is in each.
