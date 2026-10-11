# LRC: the format as ffmpeg reads and writes it, and whisper-cli writes it

LRC (`.lrc`, lyrics) has no specification. Its conventions -- `[mm:ss.xx]` line tags, `[ti:]`
and the other ID tags, "Enhanced LRC"'s `<mm:ss.xx>` word tags (A2 Media Player) -- are
described by Wikipedia's "LRC (file format)"; its readers here are ffmpeg's `lrc` demuxer and
muxer (FFmpeg n8.1.2: `libavformat/lrcdec.c`, `lrcenc.c`, `lrc.c`) and its writer in use
whisper.cpp's `-olrc` (the `whisper-transcripts` skill). Measured by `../scripts/measure.py` (its
output is the tables marked *measured*).

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
| `[offset:+/-ms]`: milliseconds, `+` shows the lyrics sooner                                                                                                                                            | subtracted from every time -- but as microseconds, not milliseconds                                                                                                                                                    |
| Enhanced LRC: `<mm:ss.xx>` before each word                                                                                                                                                            | kept in the text, unread                                                                                                                                                                                               |
| The muxer                                                                                                                                                                                              | its tags (`[re:Lavf...]`, `[ve:...]` unless `-fflags +bitexact`; `[ti:]`, `[ar:]`... from `-metadata`), a blank line, then `[mm:ss.xx]` per text line -- `-precision 1..6` fraction digits, 2 by default; no end times |

*Measured* -- the demuxer (start and duration in microseconds, the text):

| File                                                   | ffmpeg's reading                                                              |
| ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `[00:01.00]one` `[00:02.50]two`                        | 1000000 for 1500000, `one\n`; 2500000, no duration: each text keeps its `\n`  |
| `[00:01.234]`; `[00:01.5]`; `[00:01]`                  | 1.234 s; 1.5 s; 1 s: the seconds a decimal                                    |
| `[61:00.00]`                                           | 3660 s                                                                        |
| `[1:02:03.00]` (hours)                                 | 62 s: read as 1 minute 2 seconds, the hours lost                              |
| `[00:60.50]`                                           | the line dropped                                                              |
| `[-00:01.00]`                                          | -1 s                                                                          |
| `[00:01.00][00:05.00]chorus`                           | two events of `chorus`, sorted among the others                               |
| lines out of order                                     | sorted                                                                        |
| `[00:03.00]` with no text                              | an event of `\n`: the end of the line before it                               |
| `<00:01.00>one <00:01.50>two`                          | the text as written                                                           |
| `[ti:Title] [ar:Artist] [al:] [au:] [by:] [re:] [ve:]` | `title`, `artist`, `album`, `author`, `creator`, `encoder`, `encoder_version` |
| `[length: 03:20]`, `[xx:unknown]`                      | `length` = ` 03:20` (the space kept), `xx` = `unknown`                        |
| `[offset:+500]`; `[offset:-500]`                       | every time 0.5 ms earlier; 0.5 ms later                                       |
| `[TI:Upper]`                                           | dropped: neither a tag nor a timed line                                       |
| a first line without a tag; `  [00:01.00]` first       | not LRC: "Invalid data found"                                                 |
| a UTF-8 BOM                                            | detected, but the first line lost: the BOM stays in it                        |
| CRLF                                                   | CR removed                                                                    |
| whisper-cli's `[by:whisper.cpp]`, `[60:19.99]`         | `creator` = `whisper.cpp`; 3619.99 s                                          |

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

## What LRC holds

| Property    | LRC                                                                                                         |
| ----------- | ----------------------------------------------------------------------------------------------------------- |
| Times       | starts only, hundredths by convention (any decimal read by ffmpeg); a line ends where the next starts       |
| Text        | one line per tag; a cue of several lines becomes several timed lines                                        |
| Styling     | none                                                                                                        |
| Position    | none                                                                                                        |
| Word timing | Enhanced LRC's `<mm:ss.xx>` word starts -- no reader here interprets them (`subtitle-mappings`' `words.md`) |
| Other       | ID tags (title, artist, album, author, lyricist, length, the file's author and tool); `offset`              |
