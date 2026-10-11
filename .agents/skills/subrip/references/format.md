# SubRip: the format as ffmpeg reads and writes it, and ffman reads it

SubRip (`.srt`) has no specification: SubRip, the program that named it, published none. Its
definition here is ffmpeg's -- the `srt` demuxer and muxer, the `subrip` decoder and encoder --
because ffmpeg converts and muxes it, mpv reads it through ffmpeg, and libass draws ASS alone;
ffman's own reading closes the record (VLC's, by source: the skill). Researched at FFmpeg
n8.1.2: `libavformat/srtdec.c`, `srtenc.c`, `subtitles.c`; `libavcodec/srtdec.c`, `srtenc.c`,
`htmlsubtitles.c`, `ass_split.c`. Measured by `../scripts/measure.py` (its output is the tables
marked *measured*). The writers in use (whisper.cpp, OpenAI whisper, WhisperX): the
`whisper-transcripts` skill's record.

## The file

A cue: an index line, a timing line, one or more text lines, a blank line.

```
1
00:00:01,000 --> 00:00:02,500
Hello
world
```

| Rule                                                                                                                                                                                                                                                                                                                                         | Source                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Detection: the first non-blank line must parse as a number (anything may follow it), the next must hold `-->` (spaces around it) and two times. The demuxer declares no extension: a file failing this is not SubRip to ffmpeg unless `-f srt`                                                                                               | `srt_probe`                   |
| A timing line: `%d:%d:%d[,.]%d --> %d:%d:%d[,.]%d`, then optionally ` X1:%d X2:%d Y1:%d Y2:%d`. Each field a decimal integer: hours any width, minutes and seconds unbounded, the fraction an integer of **milliseconds** however many digits it has                                                                                         | `get_event_info` (sscanf)     |
| Start and duration in milliseconds (time base 1/1000); duration = end - start                                                                                                                                                                                                                                                                | `get_event_info`              |
| Text: every line after a timing line until the next timing line; blank lines are skipped, never a cue's end; a line that starts with a number is held back as the next cue's index: kept once another line follows it or at the file's end, dropped when a timing line follows it -- unless it is the cue's only text and more than a number | `srt_read_header`             |
| Lines end at LF, CRLF or a lone CR; a line is read at most 4095 bytes at a time                                                                                                                                                                                                                                                              | `ff_subtitles_read_line`      |
| A UTF-8 BOM is skipped; UTF-16 with a BOM is converted to UTF-8; other bytes pass unchanged (`-sub_charenc` recodes, in the decoder)                                                                                                                                                                                                         | `ff_text_init_avio`           |
| After reading: cues sorted by start (then file position); a negative duration becomes the gap to the next cue's start (the last keeps it); cues equal in start, duration and text are dropped but one                                                                                                                                        | `ff_subtitles_queue_finalize` |
| The muxer: an index from 1, `%02d:%02d:%02d,%03d` from whole milliseconds (hours past 99 in more digits), the coordinates when the packet has them, the text, a blank line. LF only, no BOM; a packet without a start or with a negative duration is dropped with a warning                                                                  | `srt_write_packet`            |

*Measured* -- the demuxer (start and duration in ms, the text):

| File                                                     | ffmpeg's reading                                                                 |
| -------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `00:00:01,000 --> 00:00:02,500`                          | 1000, 1500                                                                       |
| `00:00:01.000 --> 00:00:02.500` (periods)                | 1000, 1500: either separator                                                     |
| `00:00:01,5 --> 00:00:02,25`                             | 1005, 1020: the digits are milliseconds, not a fraction                          |
| `00:00:01,5000 --> 00:00:02,0000`                        | 6000, -4000: 5000 ms added; the muxer then drops the cue, a warning              |
| `00:01,000 --> 00:02,000` (no hours)                     | not SubRip: "Invalid data found"                                                 |
| `100:00:00,000`, `00:75:00,000`                          | 360000000, 4500000: written back `100:00:00,000`                                 |
| `-00:00:01,000 --> 00:00:02,000`                         | 1000: a sign on zero hours is lost                                               |
| `-01:00:00,000 --> 00:00:02,000`                         | -3600000; remuxed, every time shifted up by an hour (`avoid_negative_ts`)        |
| `00:00:01,000-->00:00:02,000` (no spaces)                | not detected; with `-f srt`, read                                                |
| `... X1:100 X2:300 Y1:400 Y2:450`                        | position side data; remuxed as `  X1:100 X2:300 Y1:400 Y2:450`                   |
| `... 00:00:02,000 garbage`                               | read; the trailing text ignored                                                  |
| `first`, blank line, `second`                            | one cue, `first\nsecond`: the blank line skipped                                 |
| a first cue without its index line                       | not detected                                                                     |
| last line `2024`, the next cue indexed                   | kept                                                                             |
| last line `2024` or `3 apples`, the next cue not indexed | dropped: taken for the next cue's index                                          |
| last line `2024` of the file's last cue                  | kept                                                                             |
| the only line `3 apples`, the next cue not indexed       | kept                                                                             |
| the only line `2024`, the next cue not indexed           | the cue lost: its one line taken for an index                                    |
| end before start (`00:00:03 --> 00:00:01`)               | 3000, 2000: the gap to the next start                                            |
| cues out of order; overlapping                           | sorted; overlaps kept                                                            |
| two identical cues                                       | one, a warning                                                                   |
| a timing line, no text                                   | no cue                                                                           |
| `00:00:01,000 --> 00:00:01,000`                          | 1000, 0: kept, written back                                                      |
| CRLF; CR only; UTF-8 BOM; UTF-16LE BOM                   | read alike, the text in UTF-8                                                    |
| `caf` and the byte E9 (Latin-1's é)                      | the byte passed unchanged: the text not UTF-8 (the decoder drops the cue: below) |
| a NUL byte in a cue's text                               | the reading stops: that cue and every later one lost                             |
| a 5000-byte line                                         | two lines, 4095 and 905 bytes                                                    |
| `  lead and trail  `                                     | kept by the demuxer (the decoder trims them)                                     |

## The text: the `subrip` decoder (into ASS)

ffmpeg converts a cue's text to ASS markup for every use but a stream copy (`htmlsubtitles.c`):
the policy is to drop unknown markup and keep the text. *Measured*:

| Cue text                                                     | ASS                                                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| `<b>b</b> <i>i</i> <u>u</u> <s>s</s>` (any case)             | `{\b1}b{\b0} {\i1}i{\i0} {\u1}u{\u0} {\s1}s{\s0}`                                           |
| `<font color="red">`, `color="#00ff80"`                      | `{\c&HFF&}`, `{\c&H80FF00&}` (BGR); `</font>` restores                                      |
| `<font size="30" face="Serif">`                              | `{\fs30}{\fnSerif}`; nested fonts kept on a 16-deep stack                                   |
| `one<br>two<br/>three`; a line break                         | `one\Ntwo\Nthree`                                                                           |
| `{\an8}top` (anywhere in the text)                           | `{\an8}top`: the one override kept                                                          |
| `{\b1}x{\pos(10,10)}`; `{y:i}` (MicroDVD)                    | removed, the text kept                                                                      |
| `<v Bob>`, `<c.yellow>` (WebVTT's)                           | `<v ...>` dropped with a warning; `<c.yellow>` kept as text                                 |
| `a < b and c > d`                                            | `a {\b1} d`: `< b and c >` read as a `<b>` tag, text lost                                   |
| `x<3 and y>2`; `heart <3`; `a ＜ b` (U+FF1C)                 | `x2`, a warning ("Unrecognized tag 3"): the span read as a tag; kept; kept                  |
| `<<quote>>`; `{not an override}`                             | kept                                                                                        |
| `A &amp; B`                                                  | kept: SubRip has no character references                                                    |
| `one\Ntwo` (typed in the text)                               | kept: `\N`, a break once rendered as ASS                                                    |
| `hard\hspace` (typed)                                        | kept: `\h`, a hard space once rendered as ASS                                               |
| leading and trailing spaces of a line                        | removed                                                                                     |
| `first`, a line of spaces, `second`                          | `first`: the rest of the cue dropped                                                        |
| `caf` and the byte E9, then a cue `next`                     | `next` alone: "Invalid UTF-8 in decoded subtitles text; maybe missing -sub_charenc option"  |
| `X1:100 X2:300 Y1:400 Y2:450`; `X1:100 X2:100 Y1:400 Y2:400` | `{\an5}{\pos(106,255)}`; `{\an1}{\pos(53,240)}`: scaled from 720x480 to the default 384x288 |

The decoder's script: `PlayResX: 384`, `PlayResY: 288`, `ScaledBorderAndShadow: yes`,
`YCbCr Matrix: None`, one style `Default` (Arial 16, white, outline 1, bottom centre, margins
10).

## Writing: the `subrip` encoder (from ASS)

*Measured*, an ASS event each, its SubRip text:

| ASS                                                                                          | SubRip                                                                                                                  |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `{\b1}b{\b0}`, `\i`, `\u`, `\s`                                                              | `<b>b</b>`, `<i>`, `<u>`, `<s>`                                                                                         |
| `{\c&H0000FF&}red{\c}`                                                                       | `<font color="#ff0000">red</font>`                                                                                      |
| `{\2c...}` (karaoke's colour), `\3c`, `\4c`, alpha                                           | dropped                                                                                                                 |
| `{\fnSerif\fs30}`                                                                            | `<font face="Serif"><font size="30">...</font></font>`                                                                  |
| `{\an8}`; legacy `{\a6}`                                                                     | `{\an8}`; `{\an8}` (converted)                                                                                          |
| `\pos`, `\move`, `\k`, `\fad`, any other override                                            | dropped                                                                                                                 |
| `\N`, `\n`                                                                                   | a line break each                                                                                                       |
| `\h`                                                                                         | `\h`, as text                                                                                                           |
| `{\b1 broken` (no closing brace)                                                             | `<b>`: the rest of the event lost                                                                                       |
| `{\r}`                                                                                       | open tags closed                                                                                                        |
| `a <b> c & d` (plain text)                                                                   | unchanged: nothing is escaped                                                                                           |
| a style other than ffmpeg's default (font, size, colour, bold, italic, underline, alignment) | its tags around the whole text: `<font face="Serif" size="24" color="#ff0000"><b><i><u>{\an8}styled</u></i></b></font>` |

Times from ASS centiseconds: `0:00:01.23` -> `00:00:01,230`. Overlapping events stay
overlapping cues. The `text` encoder (`-c:s text`) writes the text without markup.

## ffman's reading

subverter's cues, and the chunks ffman's burn draws (its `ingest`: sorted, cleaned, each cut at
the next start; a backslash drawn as `/`). *Measured*:

| File                                                        | subverter                            | ffman burns                    |
| ----------------------------------------------------------- | ------------------------------------ | ------------------------------ |
| `00:00:01,5 --> 00:00:02,25`                                | 1005, 2025: milliseconds, noted      | the same                       |
| `first`, a blank line, `second`                             | `first`; `second` no cue's           | the same                       |
| `first`, a line of spaces, `second`                         | `first`; `second` no cue's           | the same                       |
| last line `2024`, a blank line, the next cue not indexed    | `the year 2024`                      | the same                       |
| last line `2024`, the next cue's timing line right after it | `the year`, noted                    | the same                       |
| `first`, then `2` and a timing line, no blank line          | `first`, noted                       | the same                       |
| `a --> b`, `c`                                              | `a --> b c`                          | the same                       |
| end before start; zero duration                             | read as written                      | dropped                        |
| out of order; two identical                                 | as written; both                     | sorted; one                    |
| `<b>b</b> <font color="red">r</font> <v Bob>v</v>`          | as written                           | `b r v`                        |
| `x<3 and y>2`; `a < b and c > d`; `heart <3`                | as written                           | `x2`; `a d`; `heart <3`        |
| `{\an8}top`                                                 | as written                           | `top`                          |
| `one\Ntwo a\nb hard\hspace`                                 | as written                           | `one/Ntwo a b hard/hspace`     |
| `A &amp; B`                                                 | as written                           | the same                       |
| `  lead and trail  `                                        | as written                           | `lead and trail`               |
| `caf` and the byte E9                                       | refused: "not UTF-8: x.srt (line 3)" | the same                       |
| CRLF; a UTF-8 BOM                                           | read                                 | the same                       |
| CR only; UTF-16LE with a BOM                                | no cue                               | refused: "no timed text found" |

## What SubRip holds

| Property    | SubRip (through ffmpeg)                                                                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Times       | start and end, whole milliseconds                                                                                                                                                     |
| Text        | lines, UTF-8; no escape for any character -- a literal `<` can read as a tag; a blank line cannot be held                                                                             |
| Styling     | `<b> <i> <u> <s>`, `<font color size face>` per span                                                                                                                                  |
| Position    | `{\an1}`..`{\an9}` for the whole cue (ASS's numpad); `X1..Y2` pixel coordinates, assumed 720x480                                                                                      |
| Word timing | none. OpenAI whisper's and WhisperX's `--highlight_words` write one cue per word span with that word in `<u>` (see `whisper-transcripts`; read back: `subtitle-mappings`' `words.md`) |
| Other       | the index (renumbered on writing); no speakers, no comments, no header                                                                                                                |
