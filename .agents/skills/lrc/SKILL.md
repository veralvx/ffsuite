---
name: lrc
description: LRC lyrics files (.lrc) as their readers take them, for there is no specification - ffmpeg's lrc demuxer and text decoder (so mpv and an ffmpeg burn), Navidrome, Jellyfin (LrcParser) and ffman - with line stamps [mm:ss.xx], ID tags, offset, repeated lines and Enhanced LRC's word stamps; where the readers disagree (a fraction's digits, minutes past 99, blanks before or between stamps, a line without a stamp, the last line's end, UTF-16, markup); what ffmpeg makes of it in SubRip, WebVTT and ASS; the writers (whisper.cpp -olrc, ffmpeg's muxer); and the rules for a file all of them read alike. Use this whenever reading, writing, validating, fixing or converting an .lrc file; burning lyrics into a video or muxing them into MKV, MP4 or WebM; explaining a line one player shows and another drops, a last line never shown, karaoke word times; or working on ffman's LRC handling (--burn-subs, --add-subs) - even when the request only names an .lrc file or synced lyrics.
---

# LRC

A text file of lyrics, each line opened by the time it is sung: `[01:02.50]text`. No
specification exists; its conventions -- line stamps, ID tags, `[offset:]`, Enhanced LRC's word
stamps -- are Wikipedia's ("LRC (file format)"), and its readers differ at the edges. Everything
here is read in their sources and measured -- ffmpeg n8.1.2 and ffman measured, mpv 0.41.0,
Navidrome 0.64.2, Jellyfin 12.2 (LrcParser 2025.623.0) and whisper.cpp v1.8.4 by source. The full
tables are in [references/format.md](references/format.md); [scripts/measure.py](scripts/measure.py)
re-measures ffmpeg and ffman and checks this file's example, time rule and commands, failing on a
difference (`python3 scripts/measure.py [FFMPEG [PYTHON]]`, `PYTHON` an interpreter that imports
ffman).

## The format

```
[ti:Title]
[ar:Artist]
[offset:+500]

[00:01.00]A line
[00:05.00][01:10.00]A chorus, sung twice
[00:12.00]<00:12.00>Enhanced <00:12.40>word <00:12.90>times
[00:15.00]
```

A line stamp `[mm:ss.xx]` -- minutes, seconds, hundredths -- opens each lyric line; several before
one text repeat it; a line lasts until the next starts, so an empty stamped line ends the one
before. ID tags, one a line: `[ti:]` title, `[ar:]` artist, `[al:]` album, `[au:]` author, `[by:]`
the file's maker, `[length:]` the song's, `[re:]` and `[ve:]` the program and its version;
`[offset:+500]` moves every time, in ms, `+` sooner. Enhanced LRC (A2) puts a word stamp
`<mm:ss.xx>` before each word. No styling, no position, no escape: the text is what is shown. The
rest: references/format.md.

## The readers

**ffmpeg** reads it with its `lrc` demuxer (`libavformat/lrcdec.c`) and passes each line's text
to ASS with its `text` decoder (`libavcodec/textdec.c`), escaping a backslash and a brace so
libass draws them as written; **mpv** reads it the same way (`demux/demux_lavf.c`,
`sub/sd_ass.c`) but for the last line. **Navidrome** reads a `.lrc` beside a track
(`model/lyrics_lrc.go`) and serves it to OpenSubsonic clients; **Jellyfin** reads a `.lrc` or
`.elrc` through LrcParser (`TimeTagUtils`, `LrcStartTimeUtils`). **ffman** reads it with subverter
(`readers/lrc.py`) and burns its own ASS.

| Where                                                                      | ffmpeg, mpv                                                                                    | Navidrome                                                                           | Jellyfin                                                       | ffman                                     |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------- |
| Recognised                                                                 | a `[` first, after a UTF-8 BOM and empty lines (a stamp or a known tag; mpv wants one of them) | a `.lrc` beside the track; synced when a line opens with a stamp                    | `.lrc`, `.elrc`                                                | `.lrc`                                    |
| A UTF-8 BOM; UTF-16 by its BOM                                             | the BOM kept in the first line, which is lost; UTF-16 no LRC                                   | skipped; recoded                                                                    | skipped; recoded                                               | skipped; recoded                          |
| Not UTF-8 (CP1252)                                                         | its bytes; the line dropped when decoded, but with `-sub_charenc`                              | each bad byte U+FFFD                                                                | replaced                                                       | refused by its line                       |
| Line ends                                                                  | LF, CRLF; CR alone: one line, each CR dropped                                                  | LF, CRLF; CR alone: one line                                                        | LF, CRLF, CR                                                   | LF, CRLF, CR                              |
| A stamp's fraction (`[00:01.5]`; `[00:01]`; `[00:01.234]`)                 | a decimal, any width: 1.5 s; 1 s; 1.234 s                                                      | one to three digits, a decimal: 1.5 s; 1 s; 1.234 s                                 | two or three digits alone: no line; no line; 1.234 s           | any width, a decimal: 1.5 s; 1 s; 1.234 s |
| Minutes past 99 (`[100:00.00]`)                                            | read                                                                                           | not a stamp: the line joined to the one before                                      | read                                                           | read                                      |
| Hours (`[1:02:03.00]`); seconds 60+ (`[00:60.50]`); a sign (`[-00:01.00]`) | 62 s, the hours lost; the line dropped; -1 s                                                   | 3723 s; 60.5 s; no stamp                                                            | no line; 60.5 s; no line                                       | no line; 60.5 s; no line                  |
| Several stamps (`[00:01.00][00:05.00]chorus`); a blank between them        | a line each; after a blank, the stamp dropped                                                  | a line each; blanks read                                                            | a line each; blanks read                                       | a line each; blanks read                  |
| A stamp after the text (`[00:01.00]a [00:05.00]b`)                         | text                                                                                           | text                                                                                | another start, taken off the text                              | text                                      |
| Blanks before a line's stamp                                               | the line dropped (`sscanf` given the blanks); its first line: no LRC                           | read                                                                                | read                                                           | the line dropped                          |
| A line without a stamp, after a lyric line                                 | dropped                                                                                        | joined to the line before, a line break between                                     | dropped                                                        | dropped                                   |
| Lines out of order                                                         | sorted                                                                                         | sorted only when a line held several stamps                                         | sorted                                                         | sorted                                    |
| An empty stamped line (`[00:08.00]`)                                       | the line before ends there; an empty event                                                     | the line before ends there; an empty line                                           | the line before ends there; an empty line                      | the line before ends there                |
| The last line's end                                                        | none: converted, a cue of no length; burned, never drawn; mpv, to the end                      | none: shown on                                                                      | none: shown on                                                 | 3 s on                                    |
| `[offset:+500]`                                                            | the lines after it, 0.5 ms sooner (µs)                                                         | passed to the client, ms, `+` sooner                                                | ignored                                                        | every line 500 ms sooner, noted           |
| ID tags (`[ti:]`, `[ar:]`...)                                              | metadata, any lower-case key                                                                   | `ti`, `ar`, `lang` read; any other skipped                                          | dropped                                                        | dropped                                   |
| Word stamps (`<00:12.40>word`)                                             | text, drawn                                                                                    | word times, taken off the text                                                      | word times, taken off the text -- on a line of one stamp alone | taken off the text                        |
| Tags, braces, backslashes (`<i>`, `{\an8}`, `a\nb`, `&amp;`)               | as written                                                                                     | HTML: UGCPolicy's elements kept (`<i>`), others off (`<v Bob>`); references decoded | as written                                                     | as written                                |
| Blanks round the text                                                      | the leading ones off                                                                           | trimmed                                                                             | trimmed                                                        | trimmed, runs squeezed                    |

## What ffmpeg makes of it

Converted to SubRip, WebVTT or ASS (`ffmpeg -i in.lrc out.srt`), each line becomes a cue to the next
start; the last line, which the demuxer gives no length, becomes a cue of no length -- shown by no
player -- unless an empty stamped line ends it, itself an empty cue of no length. The text goes
through the `text` decoder's escaping, kept by every writer: a backslash with a word joiner (U+2060)
after it, a `{` as `\{{}`; tags and word stamps pass as text, which a SubRip or WebVTT reader then
takes for tags. ID tags become the file's metadata, written into none of them. Burned (`-vf
subtitles=in.lrc`), the last line is never drawn unless an empty stamped line ends it. Muxed, `-c
copy` writes a SubRip track into Matroska; MP4 and WebM refuse a copy (`-c:s mov_text`, `-c:s
webvtt` convert it). Written as LRC (from SubRip), `[re:Lavf...]` and `[ve:...]` first (`-fflags
+bitexact` drops them; `-metadata title=T` writes `[ti:T]`), then a line a cue's line, hundredths by
default (`-precision 1..6`) -- a time ending in .995 s written `.100`, not carried.

## The writers in use

whisper.cpp's `-olrc` (v1.8.4, `output_lrc`): `[by:whisper.cpp]`, then a line a segment,
`[mm:ss.cc]` -- minutes past 59 not wrapped, three digits from 100 -- the speaker with `-di`, then
the text as written, its leading space too; a newline in it breaks the line. ffmpeg's muxer
(above). Navidrome writes none; Jellyfin saves a lyrics provider's file as it comes. ffman writes
no LRC (6.8.3's writer, last).

## Writing one all of them read alike

1. UTF-8 without a BOM (ffmpeg loses the first line after one); LF line ends (CRLF too; never CR
   alone: ffmpeg and Navidrome read one line).
2. ID tags first, lower case, one a line, nothing else on it; no `[offset:]` -- the readers apply
   it four ways: write the times already moved.
3. Each lyric line `[mm:ss.xx]` then its text: two-digit minutes, so under 100 minutes (Navidrome
   reads no third digit); two-digit seconds under 60; a `.` and two digits, hundredths (Jellyfin
   reads two or three, so none without a fraction); no hours, no sign. From milliseconds, round
   each start once to the hundredth, half up, then write it:

   ```python
   def lrc_time(ms: int) -> str:
       cs = (ms + 5) // 10  # to the hundredth, half up
       return f"[{cs // 6000:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}]"
   ```

4. The stamp first on its line, no blank before it (ffmpeg and ffman drop the line); several
   stamps for one text adjacent, no blank between (ffmpeg drops the one after it) -- or each line
   written out.
5. Lines in time order (Navidrome sorts only repeated lines).
6. Every line stamped: a line without one is dropped by three and joined to the line before by
   Navidrome.
7. An empty stamped line after the last lyric, at the time it ends: ffmpeg gives the last line no
   length -- converted or burned, it is never shown.
8. Plain text, trimmed: no `<`...`>` (Navidrome takes HTML off, ffmpeg's conversions make them
   tags), no backslash (ffmpeg's conversions write a word joiner after it), no leading blank.
   Word stamps only for a player that reads them: ffmpeg and mpv draw them as text.

## Reading one correctly

To lose no line a reader here shows: a UTF-8 BOM skipped, UTF-16 by its BOM recoded; lines ending at
an LF, a CRLF or a CR; a lower-case `[name:value]` line an ID tag; a lyric line's stamps at its
start, blanks before and between them read, each a start -- minutes and seconds of any digits, the
fraction a decimal, optional; its text the rest of the line, trimmed, word stamps taken off; every
line sorted by start, each ending where the next starts, the last a few seconds on; a line without a
stamp ignored. Where a reader differs (the table), say which the result is for.

## Converting, muxing and burning with ffmpeg

```sh
ffmpeg -i video.mp4 -vf subtitles=in.lrc -c:a copy out-burn.mp4          # the last line drawn only if ended
ffmpeg -i video.mkv -i in.lrc -map 0 -map 1 -c copy out.mkv               # a SubRip track
ffmpeg -i video.mp4 -i in.lrc -map 0 -map 1 -c copy -c:s mov_text out.mp4 # converted: MP4 takes no copy
ffmpeg -i in.lrc out.srt                                                  # the last line of no length
ffmpeg -i in.srt out.lrc                                                  # [re:] and [ve:], hundredths
```

ffman burns an LRC with `--burn-subs` and attaches one with `--add-subs` -- its own reading, each
line to the next start, the last 3 s on; Matroska, MP4 and WebM each take the text in their codec.

## Example

```lrc
[ti:Morning]
[ar:The Larks]
[00:01.00][00:05.00]Wake up, it's six
[00:03.50]Rise & shine
[00:08.00]
```

ffmpeg reads four events, sorted: 1 s for 2.5 s and 5 s for 3 s, `Wake up, it's six` each; 3.5 s for
1.5 s, `Rise & shine`; an empty one at 8 s, of no length, ending the last line -- without it, the
last line, at 5 s, would have none. Converted to SubRip: `Wake up, it's six`, `Rise & shine`, `Wake
up, it's six`, then the empty cue. ffman reads the three lines alike, the empty one ending the last
at 8 s; Navidrome and Jellyfin the same three, then the empty one. `Morning` and `The Larks` are the
title and artist to ffmpeg and Navidrome; to Jellyfin and ffman, nothing.

## Sources

FFmpeg n8.1.2 (`libavformat/lrcdec.c`, `lrcenc.c`, `lrc.c`, `subtitles.c`; `libavcodec/textdec.c`,
`ass.c`; `libavfilter/vf_subtitles.c`); mpv 0.41.0 (`demux/demux_lavf.c`, `sub/sd_ass.c`);
Navidrome 0.64.2 (`model/lyrics_lrc.go`, `lyrics_parse.go`, `core/lyrics/sources.go`,
`utils/ioutils/ioutils.go`, `utils/str/sanitize_strings.go`); Jellyfin 12.2
(`MediaBrowser.Providers/Lyric/LrcLyricParser.cs`, `LyricManager.cs`) and LrcParser 2025.623.0
(`LrcParser/Parser/LyricParser.cs`, `Lrc/LrcParser.cs`, `Lrc/Lines/LrcLyricParser.cs`,
`Lrc/Utils/LrcStartTimeUtils.cs`, `TimeTagUtils.cs`); whisper.cpp v1.8.4 (`examples/cli/cli.cpp`);
Wikipedia, "LRC (file format)"; ffman's subverter `readers/lrc.py`, `markup.py`.
Measurements: `scripts/measure.py`.
