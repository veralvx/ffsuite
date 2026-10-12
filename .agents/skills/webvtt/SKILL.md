---
name: webvtt
description: WebVTT subtitles (.vtt) - the W3C format as its readers take it - a browser's parser (Chromium), ffmpeg's demuxer and decoder (mpv's and an ffmpeg burn's too), VLC 3's own parser and ffman's subverter - its signature, timing lines, settings, tags, character references and blocks; where the readers disagree (a comma or a short fraction in a time, a blank line in a cue, no blank line after WEBVTT or between cues, an unescaped less-than sign); what ffmpeg makes of it in ASS and back; the writers in use (whisper.cpp, OpenAI whisper, WhisperX); and the rules for a file all of them show alike. Use this whenever reading, writing, validating, fixing or converting a .vtt file; muxing WebVTT into MKV, MP4 or WebM; explaining a cue one player shows and another drops, or cues or text lost after one bad line, less-than sign or ampersand; or working on ffman's WebVTT code (subverter's reader, --burn-subs, --add-subs) - even when the request only names a .vtt file or an HTML5 track.
---

# WebVTT

A text file of timed cues, the W3C's "WebVTT: The Web Video Text Tracks Format" (the Candidate
Recommendation Draft of 2026-05-20). Browsers implement its parser; the other readers have their
own, and they disagree at the edges. Everything here is read in their sources and measured --
Chromium 141, ffmpeg n8.1.2 and ffman measured, VLC 3.0.24 and mpv 0.41.0 by source. The full
tables -- the specification's rules, Chromium's, ffmpeg's and ffman's readings -- are in
[references/format.md](references/format.md); [scripts/measure.py](scripts/measure.py)
re-measures Chromium (`python3 scripts/measure.py`, Playwright's Chromium), and
[scripts/measure_ffmpeg.py](scripts/measure_ffmpeg.py) ffmpeg and ffman, and checks this file's
example, time rule and commands, failing on a difference
(`python3 scripts/measure_ffmpeg.py [FFMPEG [PYTHON]]`, `PYTHON` an interpreter that imports
subverter and ffman).

## The format

```
WEBVTT

intro
00:00:01.000 --> 00:00:02.500 align:start line:10%
<v Bob>Hello <c.yellow>there</c></v>
1 &lt; 2 &amp; more
```

The first line is the signature, `WEBVTT`, alone or before a space or a tab and free text. Blocks
are separated by blank lines: `NOTE` comments, and before the first cue `STYLE` (CSS for
`::cue`) and `REGION` blocks. A cue: an optional identifier line (no `-->` in it), the timing
line, then text lines up to a blank line. A timestamp is `[hh:]mm:ss.ttt` -- hours optional,
minutes and seconds two digits to 59, exactly three fraction digits; settings (`vertical`, `line`,
`position`, `size`, `align`, `region`) follow the end time. The text's tags: `<b> <i> <u>`,
`<c.class>`, `<v Name>` (a speaker), `<lang en>`, `<ruby>`/`<rt>`, `<00:00:01.500>` (a timestamp,
karaoke); HTML's character references, every one -- `&amp;` and `&lt;` are how a text holds `&`
and `<`. A text cannot hold `-->`, nor an empty line.

## The readers

**Chromium** (and any browser) runs the specification's parser for a `<track>`. **ffmpeg** reads
it with its `webvtt` demuxer and decoder (`webvttdec.c` in libavformat and libavcodec), turning
each cue into ASS for every use but a stream copy. **mpv** has no WebVTT reader of its own: it
demuxes with libavformat, guessing no character set for WebVTT (`demux/demux_lavf.c`), and
converts with libavcodec into ASS, which libass draws (`sub/lavc_conv.c`) -- ffmpeg's reading
whole. **VLC 3** parses it itself (`modules/demux/webvtt.c`, `modules/codec/webvtt/`) and renders
it itself. **ffman** reads it with subverter (`readers/webvtt.py`, its cue blocks
`readers/cues.py`) and burns its own ASS.

| Where                                               | Chromium (W3C)                                                       | ffmpeg, mpv                                                                           | VLC 3                                                                             | ffman (subverter)                                                  |
| --------------------------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Recognised                                          | `WEBVTT`, then a space, a tab or a line end                          | the same, or by the name `.vtt` (`webvtt` lower-cased: no cue)                        | the same, CRLF but not a CR alone after it, and 16 bytes at least                 | as Chromium; else refused, named                                   |
| No blank line after `WEBVTT`                        | the cue read                                                         | the first block taken for the header: that cue lost                                   | the cue read                                                                      | the cue read                                                       |
| A time's fraction not of three digits (`.5`)        | no time: the cue dropped                                             | the digits a count of ms: `.5` 5 ms, `.5000` 5000 ms                                  | a count of ms, three digits at most: `.5` 5 ms, `.5000` 500 ms                    | as Chromium, noted                                                 |
| A comma (`00:00:12,345`); minutes past 59           | no time: the cue dropped; past 59, dropped                           | the reading ends: that cue and every later one lost; past 59 read                     | that cue dropped; past 59 read                                                    | as Chromium, noted                                                 |
| `-->` without spaces, or with tabs                  | read                                                                 | read                                                                                  | no cue: it needs a space each side of `-->`                                       | read                                                               |
| An empty line in a cue's text                       | the cue ends; the text after it dropped                              | the cue ends; the reading ends too: every later cue lost                              | the cue ends; the text after it dropped                                           | as Chromium, unnoted                                               |
| A line of spaces in a cue's text                    | text                                                                 | text                                                                                  | text                                                                              | text                                                               |
| A text line holding `-->`                           | the cue ends before it; the rest dropped                             | text                                                                                  | text                                                                              | as Chromium, noted                                                 |
| No blank line between two cues                      | two cues                                                             | one: the second's timing line and text the first's text                               | one, as ffmpeg's                                                                  | two cues                                                           |
| End before start; equal                             | kept as written (3 -> 1); kept                                       | the gap to the next start; kept, of no length                                         | dropped; kept                                                                     | dropped; dropped                                                   |
| Cues out of order; two identical                    | listed by start; both                                                | sorted; one                                                                           | sorted; both                                                                      | sorted; one, each cut at the next start                            |
| `<b> <i> <u>`                                       | bold, italic, underline                                              | the same -- and any tag whose name starts with `b`, `i` or `u`                        | the same                                                                          | removed                                                            |
| `<c.yellow>`, `<v Bob>`, `<lang>`, `<ruby>`         | classes (CSS), a speaker, a language, ruby                           | dropped, their text kept (ruby's `<rt>` run on)                                       | the 8 colour classes and `bg_` ones; a voice coloured by its name; others ignored | removed, their text kept (ruby's run on)                           |
| `<00:00:01.500>` (a timestamp)                      | the text after it current then (`:past`, `:future`)                  | dropped                                                                               | read, drawn only through a `STYLE` rule                                           | removed                                                            |
| A `<` as text (`before <b ends`, `a < b and c > d`) | a tag: `before `, the rest of the cue lost; `a  d`                   | the same                                                                              | a tag only with a `>` after it: `before <b ends`; `a  d`                          | removed with what lies up to the next `>`: `before <b ends`; `a d` |
| References                                          | HTML's, every one; `&amp` without `;` too                            | six, by name amp, lt, gt, lrm, rlm and nbsp; others as written                        | 124 named ones (nbsp, not lrm or rlm), `;` needed, and numeric ones               | HTML's, every one                                                  |
| `{\an8}`, `\N` typed in the text                    | as written                                                           | as written                                                                            | as written                                                                        | `{\...}` removed, `\n` and `\t` a space, `\N` as written           |
| Identifier; settings; `STYLE`, `REGION`             | read; applied                                                        | a stream copy keeps identifier and settings, decoding drops them; blocks skipped      | read; settings applied; `STYLE` and `REGION` before the first cue                 | ignored: ffman places its own                                      |
| Not UTF-8 (`caf\xe9`)                               | U+FFFD                                                               | the cue dropped, an error (a stream copy passes the bytes)                            | passed as they are                                                                | refused by its line                                                |
| A NUL in a text                                     | U+FFFD                                                               | the text cut there, every later cue lost                                              | the line cut there                                                                | U+FFFD, noted                                                      |
| Line ends; BOM                                      | LF, CRLF, CR; a UTF-8 BOM, a UTF-16 one too (the syntax wants UTF-8) | LF, CRLF; CR alone: the first cue lost; CR CR LF: no cue; a UTF-8 BOM; UTF-16 refused | LF, CRLF; a file of CRs alone refused; a UTF-8 BOM; UTF-16 refused                | LF, CRLF, CR; a UTF-8 BOM; UTF-16 refused, named                   |

ffmpeg's ASS from a cue: `PlayResX: 384`, `PlayResY: 288`, one style, `Default` (Arial 16,
white, bottom centre, margins 10); `{` and `\` escaped, so shown as written; a line break `\N`.
From ASS back to WebVTT, ffmpeg writes `<b> <i> <u>` alone -- every other override, colour and
position dropped -- the times `MM:SS.mmm` (hours only when non-zero), and escapes nothing: `a <b>
c & d` comes out as it is, invalid WebVTT. Written as ASS, times become centiseconds, start and
duration rounded apart -- the example's 62.005-64.000 s became 62.01-64.01 s; into SubRip or
back to WebVTT they keep their milliseconds.

## The writers in use

whisper.cpp's `-ovtt` writes `WEBVTT`, a blank line, then `HH:MM:SS.mmm` cues without
identifiers, the text as it is -- `<`, `&` and `-->` unescaped, a newline raw -- and with `-di`
`<v Speaker0>` before it, never closed. OpenAI whisper writes `MM:SS.mmm` (hours only when
non-zero), no identifiers, a segment cue's text stripped and `-->` made `->`, `<` and `&` never
escaped; WhisperX the same, its words joined, `[SPEAKER_00]: ` before them when diarized. Both,
with `--highlight_words`, write a cue per word span, the word in `<u>`. Their details: the
`whisper-transcripts` skill.

## Writing one all of them show alike

1. UTF-8 without a BOM, LF line ends.
2. `WEBVTT` alone on the first line, then a blank line.
3. Each cue: an identifier only if it is wanted (never holding `-->`, never starting
   `WEBVTT`, `NOTE`, `STYLE` or `REGION`, which ffmpeg skips the cue for), its timing line,
   its text, one blank line -- the last cue too.
4. The timing line exactly `HH:MM:SS.mmm --> HH:MM:SS.mmm`: two-digit hours (more past 99),
   minutes and seconds to 59, three-digit milliseconds, one space each side of `-->` (VLC needs
   them), settings after one space only for the readers that use them.
5. Times in whole milliseconds, each cue's end after its start, the cues in order of start. From
   seconds, round each time once to the millisecond, half up, then write it:

   ```python
   def vtt_time(ms: int) -> str:
       return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000:03d}"
   ```

6. Text of at least one line, no line of it empty (every reader ends the cue there, ffmpeg the
   whole file) or holding `-->` (browsers end the cue there); no NUL. `&` as `&amp;`, `<` as
   `&lt;`, `>` as `&gt;`; no other reference but the no-break space's (ffmpeg shows the rest
   as written) -- write the character itself. No `{\` and no typed `\n` (ffman drops or
   breaks them).
7. Markup only `<b> <i> <u>`, each closed, nested not crossed. Classes, voices, `lang`, ruby,
   timestamps, settings, `STYLE` and `REGION` only for a browser (VLC honours some, the table
   says which); ffmpeg, mpv and ffman drop them all, a tag's text kept.

## Reading one correctly

As the specification's parser does: a UTF-8 BOM skipped; LF, CRLF or CR; the signature, else
no cue; blocks between blank lines; a line holding `-->` a timing line, or no cue if it is not
one -- the cue dropped, the reading going on; the text up to an empty line or a line holding
`-->`; every character reference decoded, each tag by its name. Sort by start. A file not UTF-8 is
not WebVTT: the specification decodes it as UTF-8, a byte not UTF-8 a U+FFFD.

## Converting, muxing and burning with ffmpeg

```sh
ffmpeg -i in.vtt out.srt                                          # b, i, u kept
ffmpeg -i in.srt out.vtt                                          # <, & unescaped: check them
ffmpeg -i video.mp4 -i in.vtt -map 0 -map 1 -c copy -c:s mov_text out.mp4
ffmpeg -i video.webm -i in.vtt -map 0 -map 1 -c copy out.webm    # WebVTT kept, settings too
ffmpeg -i video.mkv -i in.vtt -map 0 -map 1 -c copy out.mkv       # the same in Matroska
ffmpeg -i video.mp4 -vf subtitles=in.vtt -c:a copy out-burn.mp4   # burned: libass draws its ASS
```

MP4 and MOV hold text subtitles as `mov_text`, WebM and MKV as WebVTT itself (a stream copy
keeps each cue's identifier and settings). Converting decodes each cue into ASS (above) and
encodes that: classes, voices and timestamps are gone, and WebVTT from ASS escapes nothing -- the
example's third cue, into SubRip and back, is `Fish & chips < 2 €`, which a browser cuts at the
`<` (references/format.md, "ffmpeg's reading and writing"). ffman attaches with `--add-subs` --
`subs/srt.py` writing each cue's text cleaned of its tags, its references decoded, for the
track's codec, so `&` and `<` arrive escaped in WebVTT -- and burns with `--burn-subs` from its
own ASS.

## Example

```vtt
WEBVTT

intro
00:00:01.000 --> 00:00:03.500 align:start
<i>Previously:</i> the road
north, at night

00:00:04.000 --> 00:00:06.250 line:0
<v Ana><c.yellow>CLOSED</c></v>

00:01:02.005 --> 00:01:04.000
Fish &amp; chips &lt; 2 €
```

ffmpeg reads three cues: 1 s for 2.5 s, `{\i1}Previously:{\i0} the road\Nnorth, at night`, its
identifier and setting dropped; 4 s for 2.25 s, `CLOSED` -- the voice and the class lost;
62.005 s for 1.995 s, `Fish & chips < 2 €`. ffman reads the same times and burns `Previously: the
road north, at night`, `CLOSED` and `Fish & chips < 2 €`.

## Sources

The W3C's WebVTT, the Candidate Recommendation Draft of 2026-05-20 (`w3c/webvtt` `index.bs` at
`0648025`); Chromium 141.0.7390.37; FFmpeg n8.1.2 (`libavformat/webvttdec.c`, `webvttenc.c`,
`subtitles.c`; `libavcodec/webvttdec.c`, `webvttenc.c`, `ass_split.c`, `decode.c`); VLC 3.0.24
(`modules/demux/webvtt.c`, `modules/codec/webvtt/webvtt.c`, `subsvtt.c`, `src/input/stream.c`,
`src/text/strings.c`); mpv 0.41.0 (`demux/demux_lavf.c`, `sub/lavc_conv.c`); whisper.cpp's,
OpenAI whisper's and WhisperX's writers (the `whisper-transcripts` skill); ffman's
`subverter/readers/webvtt.py`, `subverter/readers/cues.py`, `subverter/markup.py`,
`subs/markup.py`, `subs/ass.py` and `subs/srt.py`. Measurements: `scripts/measure.py`,
`scripts/measure_ffmpeg.py`.
