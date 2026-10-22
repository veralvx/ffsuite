# LRC: the format as its readers read it and its writers write it

LRC (`.lrc`, lyrics) has no specification. Its conventions -- `[mm:ss.xx]` line stamps, `[ti:]`
and the other ID tags, "Enhanced LRC"'s `<mm:ss.xx>` word stamps (A2 Media Player) -- are
described by Wikipedia's "LRC (file format)". Its readers here: ffmpeg's `lrc` demuxer, muxer and
`text` decoder (FFmpeg n8.1.2: `libavformat/lrcdec.c`, `lrcenc.c`, `lrc.c`;
`libavcodec/textdec.c`, `ass.c`), so mpv 0.41.0's (`demux/demux_lavf.c`, `sub/sd_ass.c`);
Navidrome 0.64.2's (`model/lyrics_lrc.go`, `lyrics_parse.go`, `core/lyrics/sources.go`,
`utils/ioutils/ioutils.go`); Jellyfin 12.2's (`MediaBrowser.Providers/Lyric/LrcLyricParser.cs`,
`LyricManager.cs`), through LrcParser 2025.623.0 (`LrcParser/Parser/LyricParser.cs`,
`Lrc/Lines/LrcLyricParser.cs`, `Lrc/Utils/LrcStartTimeUtils.cs`, `TimeTagUtils.cs`); ffman's
(subverter's `readers/lrc.py`). Its writer in use: whisper.cpp v1.8.4's `-olrc`
(`examples/cli/cli.cpp`, `output_lrc`). ffmpeg and ffman measured by `../scripts/measure.py`
(its output is the tables marked *measured*); the rest by source.

## The file

```
[ti:Title]
[ar:Artist]
[by:whisper.cpp]
[offset:+500]

[00:01.00]A line
[00:05.00][01:10.00]A chorus, sung twice
[00:12.00]<00:12.00>Enhanced <00:12.40>word <00:12.90>times
[00:15.00]
```

| Convention (Wikipedia)                                                                                                                                                                                 | ffmpeg (`lrcdec.c`, `lrcenc.c`)                                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[mm:ss.xx]` -- minutes, seconds, hundredths -- then the line's text; several tags before one text repeat it                                                                                           | `[` an optional `-`, `%u:%lf]`: minutes any integer, seconds a decimal 0-60 of any precision; each tag an event of that text                                                                                           |
| no end times: a line lasts until the next                                                                                                                                                              | each event lasts until the next start; the last has none (-1)                                                                                                                                                          |
| ID tags `[ti:]` title, `[ar:]` artist, `[al:]` album, `[au:]` author, `[lr:]` lyricist, `[length:]` mm:ss, `[by:]` the file's author, `[re:]`/`[tool:]` the program, `[ve:]` its version; `#` comments | a line `[` + a lower-case letter: a tag `key:value`, any key; `ti al ar au by re ve` read as `title album artist author creator encoder encoder_version`, the rest kept by their own names                             |
| `[offset:+/-ms]`: milliseconds, `+` shows the lyrics sooner                                                                                                                                            | subtracted from every time after it -- but as microseconds, not milliseconds                                                                                                                                           |
| Enhanced LRC: `<mm:ss.xx>` before each word                                                                                                                                                            | kept in the text, unread                                                                                                                                                                                               |
| The muxer                                                                                                                                                                                              | its tags (`[re:Lavf...]`, `[ve:...]` unless `-fflags +bitexact`; `[ti:]`, `[ar:]`... from `-metadata`), a blank line, then `[mm:ss.xx]` per text line -- `-precision 1..6` fraction digits, 2 by default; no end times |

## ffmpeg's reading and writing

The probe (`lrc_probe`) skips a UTF-8 BOM and CRs and LFs, then wants a `[`: 50 for a stamp with a
fraction, 40 for `offset:` or a tag it names (`ti`, `al`, `ar`, `au`, `by`, `re`, `ve`), 5 for any
other `[` (mpv takes 26 at least: not that one). Each line is read to an LF, every CR dropped
(`read_line`), its BOM kept; a line opening with `[` and a lower-case letter is a tag
(`find_header`), else each stamp at its start an event of the text after them (`count_ts`,
`read_ts`). `read_ts` skips blanks before a stamp, but hands `sscanf` the line from its start: a
stamp after a blank is no stamp. The `text` decoder passes a line's text to ASS
(`ff_ass_bprint_text_event`): a `{` as `\{{}`, a backslash with a word joiner (U+2060) after it, so
libass draws each as written; the trailing LF off.

*Measured* -- the demuxer (start and duration in microseconds, the text), and ffman (start and
end in ms, the text):

| File                                                                     | ffmpeg's reading                                                                          | ffman's reading                                                   |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `[00:01.00]one` `[00:02.50]two`                                          | 1000000 for 1500000, `one\n`; 2500000, no duration: each text keeps its `\n`              | 1000-2500 `one`, 2500-5500 `two`: the last 3 s on                 |
| `[00:01.234]`; `[00:01.5]`; `[00:01]`                                    | 1.234 s; 1.5 s; 1 s: the seconds a decimal                                                | the same                                                          |
| `[00:02,50]two`                                                          | 2 s, the text `,50]two`                                                                   | no line, noted                                                    |
| `[61:00.00]`; `[100:00.00]`                                              | 3660 s; 6000 s                                                                            | the same                                                          |
| `[1:02:03.00]` (hours)                                                   | 62 s: read as 1 minute 2 seconds, the hours lost                                          | no line, noted (alone: refused)                                   |
| `[00:60.50]`                                                             | the line dropped                                                                          | 60.5 s, noted                                                     |
| `[-00:01.00]`                                                            | -1 s                                                                                      | -1 s (shown from 0), noted                                        |
| `[00:01.00][00:05.00]chorus`                                             | two events of `chorus`, sorted among the others                                           | the same                                                          |
| `[00:01.00] [00:05.00]chorus`                                            | one event, at 1 s, the text `chorus`: a stamp after a blank dropped                       | two lines, at 1 and 5 s                                           |
| `[00:01.00]text [00:05.00]later`                                         | one event, the text `text [00:05.00]later`                                                | the same                                                          |
| ` \t[00:02.00]two`, after a first line                                   | dropped: `sscanf` given the blanks                                                        | read, noted                                                       |
| `more`, between two lines                                                | dropped                                                                                   | dropped, noted                                                    |
| lines out of order                                                       | sorted                                                                                    | sorted                                                            |
| a line twice at one time (`same`, `same`)                                | both, the first of no length                                                              | one, `same`: shown once                                           |
| two lines of one stamp (`line one`, `line two`)                          | `line one` for no time, `line two` to the next: the last alone shown                      | one, `line one line two`, noted                                   |
| `[00:03.00]` with no text                                                | an event of `\n`: the end of the line before it                                           | the end of the line before it, no line of its own                 |
| `[00:01.00] Hello`                                                       | `Hello`: blanks after a stamp skipped                                                     | `Hello`                                                           |
| `<00:01.00>one <00:01.50>two`                                            | the text as written                                                                       | `one two`: the word stamps off                                    |
| `x<3 and y>2 <i>i</i> a\nb {\an8}c &amp;`                                | the text as written                                                                       | the same                                                          |
| `[ti:Title] [ar:Artist] [al:] [au:] [by:] [re:] [ve:]`                   | `title`, `artist`, `album`, `author`, `creator`, `encoder`, `encoder_version`             | none read                                                         |
| `[length: 03:20]`, `[xx:unknown]`                                        | `length` = ` 03:20` (the space kept), `xx` = `unknown`                                    | none read                                                         |
| `[offset:+500]`; `[offset:-500]`                                         | every time 0.5 ms earlier; 0.5 ms later                                                   | every time 500 ms sooner; later -- noted                          |
| `[00:01.00]before`, `[offset:+500]`, `[00:02.00]after`                   | `before` at 1 s, `after` 0.5 ms earlier: the lines after the tag alone                    | both 500 ms sooner, noted                                         |
| `[TI:Upper]`                                                             | dropped: neither a tag nor a timed line                                                   | dropped                                                           |
| a first line without a tag; `  [00:01.00]` first                         | not LRC: "Invalid data found"                                                             | the line after it read; the stamp after blanks read -- each noted |
| CRLF                                                                     | CR removed                                                                                | the same                                                          |
| CR only                                                                  | one line: each CR dropped (`first[00:03.00]second`, at the first stamp; a NUL at its end) | two lines                                                         |
| a UTF-8 BOM                                                              | detected, but the first line lost: the BOM stays in it                                    | the BOM skipped                                                   |
| a NUL in a line (`fi` NUL `rst`)                                         | in the packet; the text cut there by the decoder; the next lines read                     | `fi` U+FFFD `rst`, noted                                          |
| UTF-16, LE or BE (its BOM)                                               | not LRC: "Invalid data found"; `-f lrc`, no line                                          | read as UTF-8's                                                   |
| CP1252 (`café ’x’`)                                                      | read as its bytes; converted, the line dropped ("Invalid UTF-8"), but with `-sub_charenc` | refused: "not UTF-8: x.lrc (line 1)"                              |
| whisper-cli's `[by:whisper.cpp]`, `[00:00.00] Hello world`, `[60:19.99]` | `creator` = `whisper.cpp`; `Hello world`; 3619.99 s                                       | `Hello world`; 3619.99 s                                          |

*Measured* -- converted into SubRip, WebVTT and ASS (`ffmpeg -i in.lrc out.srt`):

| File                                                 | ffmpeg's conversion                                                                                                          |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `[00:01.00]one` `[00:02.50]two`                      | `one` 1-2.5 s; `two` 2.5-2.5 s: the last line of no length, in all three                                                     |
| the same, then `[00:04.00]` (an empty stamped line)  | the last line to 4 s; an empty cue of no length after it                                                                     |
| `x<3 and y>2 <i>i</i> a\nb {\an8}c &amp;`            | in all three as written but for the decoder's escapes for libass: a word joiner (U+2060) after each backslash, `{` as `\{{}` |
| `<00:01.00>one <00:01.50>two`                        | the stamps as text: a WebVTT reader drops them as tags, a SubRip one shows them                                              |
| CP1252 (`café ’x’`)                                  | the line dropped: "Invalid UTF-8 in decoded subtitles text"; with `-sub_charenc CP1252`, `café ’x’`                          |
| the `subtitles` filter, `[00:01.00]x`, `[00:02.00]y` | `x` drawn at 1.5 s; `y` never (2.5, 5, 9.5 s): the last line drawn by no burn; with `[00:04.00]` after it, at 2.5 s          |

`-c copy` into Matroska writes the text as a SubRip track (`S_TEXT/UTF8`); MP4 and WebM refuse a
copy ("Could not find tag for codec text"; "... WebVTT subtitles are supported for WebM"): `-c:s
mov_text`, `-c:s webvtt` convert it.

*Measured* -- the muxer, from SubRip:

| SubRip                                                                | LRC                                                                                    |
| --------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| cues at 1 s and 2.5 s                                                 | `[re:Lavf62.12.102]`, `[ve:62.12.102]`, a blank line, `[00:01.00]one`, `[00:02.50]two` |
| a cue at 1.994 s                                                      | `[00:01.99]`                                                                           |
| a cue at 1.995 s                                                      | `[00:01.100]`: the hundredths rounded to 100 and not carried -- wrong                  |
| a cue at 1:01:01.5                                                    | `[61:01.50]`                                                                           |
| a cue of two lines                                                    | `[00:01.00]line one`, `[00:01.00]line two`                                             |
| a cue starting with `[`                                               | written, a warning                                                                     |
| `<i>italic</i> & more`                                                | as is: no markup removed                                                               |
| `-metadata title=T -metadata artist=A -fflags +bitexact -precision 3` | `[ti:T]`, `[ar:A]`, a blank line, `[00:01.000]one`                                     |

## mpv's reading (0.41.0)

ffmpeg's: it demuxes with libavformat (`demux_lavf.c`, LRC not among the formats it recodes) and
converts each line with the `text` decoder (`sd_ass.c`, `lavc_conv`). Two differences: a
packet of negative duration is of unknown length (`UNKNOWN_DURATION`), so the last line, which the
demuxer gives -1, is shown to the end; and its decoder checks no UTF-8 (`lavc_conv.c`:
`FF_SUB_CHARENC_MODE_IGNORE`, which `decode.c`'s `utf8_check` skips), so a line not UTF-8 is
libass's to draw, each bad byte its Latin-1 character -- ffmpeg drops it.

## Navidrome's reading (0.64.2)

A sidecar `.elrc` or `.lrc` beside a track, `.elrc` first (`sources.go`; `lyricspriority`'s
default), read through `ioutils.UTF8Reader`: a UTF-8 BOM skipped, UTF-16 by its BOM recoded
(`unicode.BOMOverride`), a byte not UTF-8 U+FFFD; its text then through bluemonday's UGCPolicy and
`html.UnescapeString` (`str.SanitizeText`). Served to OpenSubsonic clients as structured lyrics.

| Rule                                                                                                                                                                                                                                                                                                       | Source                                        |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Lines split at an LF alone, each trimmed: a CR-only file one line                                                                                                                                                                                                                                          | `parseLRC`                                    |
| Synced when a line opens with a stamp, blanks before it skipped; else every line plain text                                                                                                                                                                                                                | `syncRegex`                                   |
| A stamp `[h:]mm:ss[.f]`: hours optional, minutes and seconds of one or two digits, a fraction of one to three digits, a decimal (`.5` 500 ms); no sign                                                                                                                                                     | `timeRegexString`, `parseTime`                |
| A line's stamps at its start, blanks between them, each a line of its text; a stamp after the text is text                                                                                                                                                                                                 | `parseLRC`                                    |
| A line without a stamp at its start, after a timed one: joined to it, a line break before it (`[100:00.00]`, `[00:02,50]` alike)                                                                                                                                                                           | `parseLRC`                                    |
| `[ar:]`, `[ti:]`, `[lang:]`, `[offset:]` read wherever on a line they stand -- a lyric line holding one lost to it -- the offset passed on, OpenSubsonic's (ms, `+` sooner, the client's to apply); `[bg:...]` after a lyric line, a background vocal, joined to it; any other `[name:value]` line skipped | `lrcIdRegex`, `bgTagRegex`, `unknownTagRegex` |
| Enhanced LRC `<[h:]mm:ss[.f]>`: each a word's start, taken off the text, and the text before the first (`Every <00:07.56> night` is `night`)                                                                                                                                                               | `parseEnhancedLine`                           |
| HTML in the text: UGCPolicy's elements kept (`<b>`, `<i>`, `<u>`...), others off; references decoded (`&amp;` is `&`)                                                                                                                                                                                      | `str.SanitizeText`                            |
| Lines sorted when a line held several stamps; the last line no end                                                                                                                                                                                                                                         | `parseLRC`                                    |

## Jellyfin's reading (12.2, LrcParser 2025.623.0)

A `.lrc` or `.elrc` (`LrcLyricParser.cs`), read by `File.ReadAllTextAsync(path, Encoding.UTF8)`:
a BOM's encoding -- UTF-8, UTF-16 or UTF-32, either order -- detected (.NET's `File.ReadAllText`),
a byte not UTF-8 replaced (`Encoding.UTF8`'s replacement fallback).

| Rule                                                                                                                                                   | Source                                       |
| ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- |
| Lines split at a CRLF, a CR or an LF; blank lines dropped                                                                                              | `LyricParser.Decode`                         |
| A stamp `[m:ss.xx]`: minutes of any digits, seconds of exactly two, a fraction of two or three digits (hundredths or ms); no hours, no sign            | `TimeTagUtils.LINE_TIME_TAG_REGEX`           |
| Every stamp on the line, wherever it stands, a start of the line's text, the stamps taken off it, trimmed; a line without one dropped                  | `LrcStartTimeUtils.SplitLyricAndTimeTag`     |
| ID tags and `[offset:]` dropped, as lines without a stamp                                                                                              | `LrcLyricParser`                             |
| Enhanced LRC `<m:ss.xx>`: word starts, taken off the text -- on a line of one stamp alone; with several, kept as text                                  | `LrcLyricParser.Decode`, `LrcTimedTextUtils` |
| Lines sorted by start; the last line no end                                                                                                            | `LrcLyricParser.ParseLyrics` (Jellyfin's)    |
| A file of no line LrcParser reads: none, so the next parser's -- `TxtLyricParser` (`.lrc`, `.elrc`, `.txt`): the whole file plain text, stamps and all | `LyricManager` (parsers by `Priority`)       |

## ffman's reading

subverter's `readers/lrc.py` and ffman's `subs/markup.py`: UTF-8, or UTF-16 by its BOM, and its
lines, as a SubRip's (`subrip.file_lines`: a CR or an LF ends one, CR CR LF one end); a line's
stamps at its start, blanks before and between them, `[m:ss.f]` -- minutes and seconds of any
digits, the fraction optional, a decimal, a minus a time before 0, seconds past 60 of two digits;
each stamp a line of the text after them, sorted, those of one start one, their texts joined by a
line break (burned a space, nothing between two CJK characters), a text shown already once, each
ending at the next start, the last 3 s on; any other line but a tag (`[`, a letter or `#`, then `:`)
or an empty one dropped; the blanks, the minus, the seconds, the shared starts and the dropped lines
noted, each kind counted; the last `[offset:]` of whole ms moving every time, `+` sooner, noted,
each reason another is ignored counted; the text as written but for Enhanced LRC's word stamps,
taken off (`markup.unstamped`), its blanks squeezed and trimmed; a NUL U+FFFD, noted; a file of no
line read refused, `no timed text found`, after its notes. The measured table above holds its
column.

## The writers

whisper.cpp v1.8.4's `-olrc`: `[by:whisper.cpp]`, then a line a segment, `[mm:ss.cc]` (its
centiseconds, minutes past 59 not wrapped, three digits from 100), the speaker with `-di`
(`(speaker 0)`), then its text as written -- a leading space, any `<` or `[`, a tab; a newline in
the text breaks the line. ffmpeg's muxer: above.

## What LRC holds

| Property    | LRC                                                                                                   |
| ----------- | ----------------------------------------------------------------------------------------------------- |
| Times       | starts only, hundredths by convention (any decimal read by ffmpeg); a line ends where the next starts |
| Text        | one line per tag; a cue of several lines becomes several timed lines                                  |
| Styling     | none                                                                                                  |
| Position    | none                                                                                                  |
| Word timing | Enhanced LRC's `<mm:ss.xx>` word starts -- Navidrome and Jellyfin read them; ffmpeg and ffman do not  |
| Other       | ID tags (title, artist, album, author, lyricist, length, the file's author and tool); `offset`        |
