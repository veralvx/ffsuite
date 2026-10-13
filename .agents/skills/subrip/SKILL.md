---
name: subrip
description: SubRip subtitles (.srt) - the format as its readers take it, for there is no specification - ffmpeg's srt demuxer and subrip decoder (what mpv and an ffmpeg burn go through), VLC 3's own parser, and ffman's subverter - with the timing line, the text and its markup (b, i, u, s and font tags, {\an8}), where the readers disagree (a blank line, a number line, a less-than sign, a brace, a cue of no length), a short fraction read as milliseconds, what ffmpeg makes of it in ASS and back, the writers in use (whisper.cpp, OpenAI whisper, WhisperX), and the rules for a file all of them show alike. Use this whenever reading, writing, validating, fixing or converting an .srt file; muxing SubRip into MKV, MP4 or WebM; explaining a cue that vanished, a time a few milliseconds off, text lost as a tag or a tag shown as text, lines merged or split; or working on ffman's SubRip code (subverter's reader, --burn-subs, --add-subs) - even when the request only names an .srt file.
---

# SubRip

A text file of numbered cues, each a time span and the lines shown during it. SubRip, the
program that named it, published no specification: the format is what its readers accept, and
they disagree at the edges. Everything here is read in their sources and measured -- ffmpeg
n8.1.2 and ffman measured, VLC 3.0.24 and mpv 0.41.0 by source. ffmpeg's and ffman's full
tables are in [references/format.md](references/format.md);
[scripts/measure.py](scripts/measure.py) re-measures them and checks this file's example,
time rule and commands, failing on a difference (`python3 scripts/measure.py [FFMPEG [PYTHON]]`,
`PYTHON` an interpreter that imports subverter and ffman).

## The format

```
1
00:00:01,000 --> 00:00:02,500
Hello
world

2
00:00:03,000 --> 00:00:04,000
<i>Next</i>
```

A cue: an index line (from 1), a timing line, one or more text lines, a blank line. A timing
line is `HH:MM:SS,mmm --> HH:MM:SS,mmm`, start then end, `,` or `.` before the milliseconds;
SubRip's own pixel box may follow (`X1:100 X2:300 Y1:400 Y2:450`, read on a 720x480 frame). Text
is any UTF-8 but a blank line, with HTML-like tags -- `<b> <i> <u> <s>`,
`<font color="#rrggbb" size="30" face="Serif">` -- and ASS's alignment override
`{\an1}`..`{\an9}` (a numpad: 8 top centre). There is no escape for any character: no `&amp;`,
no `\<`.

## The readers

**ffmpeg** reads it with its `srt` demuxer and `subrip` decoder (`srtdec.c` in libavformat and
libavcodec, `htmlsubtitles.c`), turning each cue into ASS for every use but a stream copy.
**mpv** has no SubRip reader of its own: it demuxes with libavformat and converts with
libavcodec into ASS, which libass draws (`demux/demux_lavf.c`, `sub/lavc_conv.c`) -- ffmpeg's
reading, but for a file's character set, which mpv guesses itself. **VLC 3** parses it itself
(`modules/demux/subtitle.c`) and renders the markup itself (`modules/codec/subsdec.c`).
**ffman** reads it with subverter (`readers/subrip.py`, its cue blocks `readers/cues.py`) and
burns its own ASS.

| Where                                                         | ffmpeg, mpv                                                                                                                                                        | VLC 3                                                                                                                                               | ffman (subverter)                                                                                                                          |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Recognised                                                    | first non-blank line a number, the next a timing line with a space each side of `-->`; hours needed (`00:01,000` reads as no cue)                                  | a timing line in its first 256 lines and 4 KiB, the spaces not needed; hours needed                                                                 | by the name, `.srt`; `00:01,000` read too (bash's)                                                                                         |
| A short fraction (`00:00:01,5`)                               | the digits are milliseconds: 1.005 s; `,5000` adds 5 s                                                                                                             | the same: 1.005 s                                                                                                                                   | the same: 1.005 s, noted                                                                                                                   |
| A blank line inside a cue's text                              | an empty one skipped, the next line the same cue's; one of spaces ends the text, the rest of the cue dropped                                                       | an empty one ends the cue, what follows until a timing line lost; one of spaces is text                                                             | an empty one skipped, as ffmpeg's; one of spaces too, as MPC-HC's: the text after either noted                                             |
| A cue's last line starting with a number (`2024`, `3 apples`) | taken for the next cue's index -- dropped -- when the next cue has no index line (a cue's only line kept if more than a number)                                    | text                                                                                                                                                | text, but a number alone, only empty lines between it and a timing line: the next cue's index, dropped, noted when no blank line before it |
| No blank line before the next index                           | the index read as an index                                                                                                                                         | the index, the timing line and the next cue all the first cue's text                                                                                | the index read as an index, noted                                                                                                          |
| A text line holding `-->`                                     | text                                                                                                                                                               | text                                                                                                                                                | text                                                                                                                                       |
| End before start, or equal                                    | end before: the gap to the next start; equal: kept, of no length                                                                                                   | the cue skipped                                                                                                                                     | read as written; ffman drops it                                                                                                            |
| Cues out of order; two identical                              | sorted; the duplicate dropped                                                                                                                                      | as a video's subtitles, neither sorted nor merged (its sort skips a slave input)                                                                    | sorted; one shown, each cue cut at the next start                                                                                          |
| `<b> <i> <u> <s> <font>`, `<br>`                              | ASS's `\b1`... `\c&H..&`, `\fs`, `\fn`; `<br>` a break                                                                                                             | the same, by its own renderer                                                                                                                       | removed by ffman, `<br>` a break (its burn and `--add-subs`)                                                                               |
| An unknown tag (`<v Bob>`)                                    | dropped (`<c.yellow>` kept as text, its `</c>` dropped)                                                                                                            | dropped when its closing tag follows in the cue, else shown                                                                                         | as ffmpeg: `<v Bob>` dropped, `<c.yellow>` shown                                                                                           |
| A `<` as text                                                 | a tag when a name it knows (`b`) or likely one follows: `x<3 and y>2` shows `x2`, `a < b and c > d` turns bold; `1 < 2 and 3 > 2`, `heart <3` kept                 | a `<` before a letter opens a tag, the rest up to a `>` or the cue's end lost (`a < b and c > d`: `a d`, bold); else it is text                     | as ffmpeg (`x2`, `a d`; `1 < 2 and 3 > 2` kept)                                                                                            |
| Braces, a backslash (`a {b} c\x \{d\}`)                       | `{b}` an empty override block, hidden; `\{d\}` braces; `c\x` as written                                                                                            | `{b}` and `\{d\}` shown as written                                                                                                                  | `{b}` hidden, as libass, noted; `\{d\}` braces; drawn as written: `a c\x {d}`                                                              |
| `{\an8}`; other `{\...}`                                      | the first kept; the others dropped to the first `}`, a backslash before or not (`a \{\i1\} b`: `a \ b`), kept while one `{\anN}` alone is met (libass hides them)  | the first `{\anN}` honoured; others dropped                                                                                                         | as ffmpeg, then libass: hidden                                                                                                             |
| `\N`, `\n`, `\h` typed in the text                            | in ASS, `\N` a break, `\n` a space (libass: a break only with `WrapStyle: 2`), `\h` a hard space                                                                   | `\N` and `\n` a break, `\h` a hard space                                                                                                            | `\n` a space, `\N` a break (a space, ffman wrapping), `\h` a no-break space; `\t` as written                                               |
| `&amp;`                                                       | shown as written                                                                                                                                                   | shown as written                                                                                                                                    | shown as written                                                                                                                           |
| Spaces around a line                                          | removed                                                                                                                                                            | kept                                                                                                                                                | kept by subverter, trimmed by ffman                                                                                                        |
| Not UTF-8 (`caf\xe9`)                                         | ffmpeg drops the cue, an error, unless `-sub_charenc` names its set (a stream copy passes the bytes); mpv guesses the set (uchardet, else a stray byte as Latin-1) | UTF-8 while each cue is; from the first that is not, every cue read in the code page of VLC's interface language (CP1252 for Western European ones) | joined across lines if split, else refused by its line                                                                                     |
| A NUL in a text                                               | the reading stops there: that cue and every later one lost                                                                                                         | the line cut there (`strlen`)                                                                                                                       | U+FFFD, as the W3C reads one, noted                                                                                                        |
| Line ends; BOM                                                | LF, CRLF, CR; a UTF-8 BOM skipped, UTF-16 converted                                                                                                                | LF, CRLF (CR alone in a file without LF); UTF-8 and UTF-16 BOMs                                                                                     | LF, CRLF, CR (CR CR LF one end, as ffmpeg's); a UTF-8 BOM; UTF-16 converted, as ffmpeg's                                                   |

ffmpeg's ASS from a cue: `PlayResX: 384`, `PlayResY: 288`, one style, `Default` (Arial 16,
white, outline 1, bottom centre, margins 10); `X1..Y2` become `{\an5}{\pos(...)}` (a point,
`{\an1}`) scaled from 720x480. From ASS back to SubRip, ffmpeg keeps bold, italic, underline,
strikeout, the primary colour, font and size, `\an` (`\a` converted), `\N`; it drops `\pos`,
`\move`, `\k`, `\fad`, other colours and alpha, and escapes nothing (`a <b> c & d` written as it
is). `-c:s text` writes the text without markup. Through ASS, times become centiseconds, start
and duration rounded apart: the example's 62.005-64.000 s came back 62.010-64.010.

## The writers in use

whisper.cpp's `-osrt` writes the segment's text as it is -- its leading space, `<` and `-->`
unescaped, a newline in it raw (a new line, or a blank one) -- and with `-ml N` but not `-sow`
may split a character's bytes between two cues: not UTF-8 there. OpenAI whisper strips a segment
cue's text and writes `-->` in it as `->`; WhisperX writes its words joined, `[SPEAKER_00]: `
before them when diarized. Both, with `--highlight_words`, write a cue per word span, the word
in `<u>`. All write `HH:MM:SS,mmm`, no BOM, in text mode -- LF, but CRLF on Windows
(`open(path, "w")`, `std::ofstream`). Their details: the `whisper-transcripts` skill.

## Writing one all of them show alike

1. UTF-8 without a BOM, LF line ends.
2. Each cue: its index (`1`, then one more each), its timing line, its text, one blank line --
   the last cue too.
3. The timing line exactly `HH:MM:SS,mmm --> HH:MM:SS,mmm`: two-digit hours (more past 99),
   three-digit milliseconds, one space each side of `-->`, nothing after (but `X1..Y2`, which
   only ffmpeg and mpv read).
4. Times in whole milliseconds, each cue's end after its start, the cues in order of start. From
   seconds, round each time once to the millisecond, half up, then write it:

   ```python
   def srt_time(ms: int) -> str:
       return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
   ```

5. Text of at least one line, and no line of it empty or of spaces (readers end the cue there or
   join the next), last starting with a number (ffmpeg may take it for an index), or with spaces at
   either end (ffmpeg removes them); no NUL (ffmpeg stops reading there). A `<` only to open a
   tag: SubRip has no escape -- a word joiner (U+2060) after it keeps it text, or write `＜`
   (U+FF1C) or reword; never `&lt;`, shown as written. No `{\` but a leading `{\anN}`. A `\`
   meant as text before a word joiner (libass reads `\N` `\n` `\h` `\{` `\}`, VLC `\n` and `\h`
   in either case); a `{` with a `}` after it as `\{` and a joiner (libass's escape; VLC shows
   the backslash); a line that reads as a timing line led by one (ffmpeg starts a cue there).
6. Markup only `<b> <i> <u> <s>`, `<font color="#rrggbb">`, each closed, nested not crossed, and
   `{\anN}` first in the text. A WebVTT tag (`<v Bob>`, `<c.yellow>`) is not SubRip's.

## Reading one correctly

As the players do: a UTF-8 BOM skipped, a UTF-16 one read as UTF-16; LF, CRLF or CR; lines skipped
up to a timing line (an index is not needed); `,` or `.` before the fraction, its digits a count of
milliseconds (`,5` 5 ms, as ffmpeg and VLC); a timing line's text after the end time ignored; text
on to the next timing line, an empty line and a line of spaces skipped (MPC-HC, Subtitle Edit;
ffmpeg's demuxer skips the empty one, its decoder, so mpv, ending the text at the spaces; VLC ends
it at an empty line, Kodi at either), its last line, a number alone, the next cue's index (ffmpeg
drops any line starting with a number there); the markup above, a `<` a tag only before a name
ffmpeg's decoder knows or one likely a tag's, an unknown tag dropped. Sort by start. A file not
UTF-8 is a code page's: ask, or guess as VLC does, rather than pass its bytes on.

## Converting, muxing and burning with ffmpeg

```sh
ffmpeg -i in.srt out.ass                                         # styled ASS, PlayRes 384x288
ffmpeg -i in.ass out.srt                                         # bold, italic, colour, \an kept
ffmpeg -i video.mp4 -i in.srt -map 0 -map 1 -c copy -c:s mov_text out.mp4
ffmpeg -i video.mkv -i in.srt -map 0 -map 1 -c copy out.mkv     # SubRip kept as SubRip
ffmpeg -i video.mp4 -vf subtitles=in.srt -c:a copy out-burn.mp4  # burned: libass draws its ASS
```

MP4 and MOV hold text subtitles as `mov_text`, WebM as `webvtt`, MKV as SubRip itself. Converting
decodes the SRT into ASS and encodes that text raw but for `\N`, `\n` and `{\...}`: a typed `\N`
becomes a break, an unclosed `{\` cuts the cue (in SubRip and WebVTT its style runs on), WebVTT's
`&` and `<` go unescaped (references/format.md, "Muxed"). ffman attaches with `--add-subs` --
`subs/srt.py` writes each cue's index, `HH:MM:SS,mmm` times and one line of text cleaned of its
tags, LF, the text written for the track's codec so it holds it exactly -- and burns with
`--burn-subs` from its own ASS.

## Example

```srt
1
00:00:01,000 --> 00:00:03,500
<i>Previously:</i> the road
north, at night

2
00:00:04,000 --> 00:00:06,250
{\an8}<font color="#ffff00">CLOSED</font>

3
00:01:02,005 --> 00:01:04,000
Fish & chips, 1,99 €
```

ffmpeg reads three cues: 1 s for 2.5 s, `{\i1}Previously:{\i0} the road\Nnorth, at night`; 4 s
for 2.25 s, `{\an8}{\c&HFFFF&}CLOSED{\c}` (the colour in BGR); 62.005 s for 1.995 s, the text
as written -- `&` is a character, not a reference. subverter reads the same times, the texts
as written, its lines joined by a space (`<i>Previously:</i> the road north, at night`).

## Sources

FFmpeg n8.1.2 (`libavformat/srtdec.c`, `srtenc.c`, `subtitles.c`; `libavcodec/srtdec.c`,
`srtenc.c`, `htmlsubtitles.c`, `ass_split.c`, `movtextdec.c`, `webvttenc.c`); VLC 3.0.24
(`modules/demux/subtitle.c`, `modules/codec/subsdec.c`, `src/input/stream.c`); mpv 0.41.0
(`demux/demux.c`, `demux/demux_lavf.c`, `misc/charset_conv.c`, `sub/lavc_conv.c`, `sub/sd_ass.c`);
libass 0.17.1 (`ass_parse.c`); MPC-HC (`src/Subtitles/STS.cpp` at `48478c2`), Subtitle Edit
(`src/libse/SubtitleFormats/SubRip.cs` at `638ec76`), Kodi
(`xbmc/cores/VideoPlayer/DVDSubtitles/DVDSubtitleParserSubrip.cpp` at `a07b2bb`); whisper.cpp's,
OpenAI whisper's and WhisperX's writers (the `whisper-transcripts` skill); ffman's
`subverter/readers/subrip.py`, `subverter/readers/cues.py`, `subs/normalize.py`, `subs/markup.py`,
`subs/ass.py` and `subs/srt.py`.
Measurements: `scripts/measure.py`.
