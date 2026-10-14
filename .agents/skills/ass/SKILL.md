---
name: ass
description: ASS and SSA subtitles (.ass, .ssa) as their readers take them, for no maintained specification exists - libass alone (ffmpeg's ass filter, ffman's burn), ffmpeg's demuxer then libass (mpv, the subtitles filter, conversions), VLC 3, Aegisub - with sections, styles, events, override tags, centisecond times and escapes; where the readers disagree (a lower-cased section, fields in another order, a comma or one digit in a time, CR line ends, an event ending before it starts, UTF-16 or a code page); what ffmpeg makes of it in SubRip and WebVTT; the writers; and the rules for a script all of them read alike. Use this whenever reading, writing, validating, fixing or converting an .ass or .ssa file; burning or muxing one into MKV, MP4 or WebM; explaining an event one player shows and another drops, a time a little off, a style or a brace shown wrong; or working on ffman's ASS handling (--burn-subs, --add-subs) - even when the request only names an .ass file or a karaoke script.
---

# ASS and SSA

A text script of styled, timed events: Advanced SubStation Alpha (ASS, `ScriptType: v4.00+`) and
its predecessor SubStation Alpha v4 (SSA, `v4.00`). The 1990s format document is all the
specification there is; practice is what libass draws -- every player's renderer here -- and what
Aegisub writes. Everything here is read in their sources and measured -- libass 0.17.4 (nixpkgs'
pin) and 0.17.1, ffmpeg n8.1.2 and ffman measured, VLC 3.0.24, mpv 0.41.0 and Aegisub 3.4.2 by
source. The full tables are in [references/format.md](references/format.md);
[scripts/measure.py](scripts/measure.py) re-measures libass through
[scripts/assdump.c](scripts/assdump.c) (`python3 scripts/measure.py ASSDUMP`, its build in
assdump.c), and [scripts/measure_ffmpeg.py](scripts/measure_ffmpeg.py) ffmpeg, libass through it,
and ffman, and checks this file's example, time rule and commands, failing on a difference
(`python3 scripts/measure_ffmpeg.py [FFMPEG [PYTHON]]`, `PYTHON` an interpreter that imports
ffman).

## The format

```
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.50,Default,Bob,0,0,0,,{\an8}Hello,\Nworld
```

Sections in brackets: `[Script Info]` (the type, `PlayResX`/`PlayResY` -- the coordinate space,
384x288 when absent -- `WrapStyle`, `ScaledBorderAndShadow`), the styles (`[V4+ Styles]`, SSA's
`[V4 Styles]`), `[Events]`, and `[Fonts]` or `[Graphics]` embedded. Each `Format:` line names the
fields of the lines after it; colours are `&HAABBGGRR`, alpha `00` opaque. An event, `Dialogue:`
(`Comment:` is not drawn): a layer (SSA: `Marked=0`), start and end as `h:mm:ss.cc` --
centiseconds -- a style's name, a speaker, margins (0: the style's), an effect, and the text, the
rest of the line, commas and all. In the text, override blocks `{\b1}`, `{\an8}`, `{\pos(x,y)}`,
`{\k25}` (karaoke, centiseconds) change what follows; `\N` is a line break, `\n` a space (a break
under `WrapStyle: 2`), `\h` a no-break space, `\{` and `\}` braces; a `{` with a `}` after it
opens a block. The tags and fields, all of them: references/format.md.

## The readers

**libass** reads a script whole (`ass_read_file`) in ffmpeg's `ass` filter and ffman's burn.
**ffmpeg** reads it with its `ass` demuxer and decoder (`assdec.c` in libavformat and libavcodec):
each `Dialogue:` line it can read an event, every other line the header, given back as written; its
`subtitles` filter hands that header and those events to libass, as **mpv** does (it demuxes with
libavformat, `demux/demux_lavf.c`, recoding a script not UTF-8 by its guess, then `sub/sd_ass.c`) --
and libass reads a `Dialogue:` line left in the header too. Every conversion and mux is ffmpeg's
reading. **VLC 3** splits the script itself (`modules/demux/subtitle.c`) and hands it to libass
(`modules/codec/libass.c`) the same way, but draws only while an event it read is shown.
**Aegisub**, the editor, reads it itself. **ffman** passes it through unread: its burn draws its
copy with the `ass` filter, `--add-subs` gives the copy to ffmpeg.

| Where                                                       | libass alone (`ass` filter)                                     | ffmpeg, mpv (`subtitles` filter, conversions)                                                | VLC 3                                                               | Aegisub                                        | ffman                                              |
| ----------------------------------------------------------- | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------- | -------------------------------------------------- |
| Recognised                                                  | a type: a styles section, else `ScriptType` `v4.00+` or `v4.00` | `[Script Info]` first, in its case, after a BOM and empty lines                              | `ScriptType: v4.00(+)` or `Dialogue:`, any case, in its first 4 KiB | by its extension; another `ScriptType` refused | both libass's and ffmpeg's, else refused, named    |
| `[script info]`; a comment before it                        | read                                                            | no event (ffmpeg's LRC reader; mpv loads none); no reader, an error                          | read                                                                | read                                           | refused                                            |
| No type; `v4.00++`, `[V4++ Styles]`                         | no track: the burn fails                                        | read                                                                                         | read; `v4.00++` as ASS                                              | the type by its extension; `v4.00++` refused   | refused                                            |
| Fields in another order (`Format: Start, End, Style, Text`) | read by the `Format:` line                                      | no event read, but drawn: libass reads the header's line; converted, no cue                  | no event: nothing drawn                                             | not opened: `0:00:01.00` read as the layer     | burned; attached, no cue -- unnoted                |
| A time's fraction (`0:00:01.5`; `0:00:01.500`)              | centiseconds, whatever its width: 1.05 s; 6 s                   | the same                                                                                     | the same                                                            | a decimal: 1.5 s; 1.5 s                        | as libass                                          |
| A comma before it (`0:00:01,50`)                            | "Bad timestamp": not drawn, the fields after it shifted         | read: 1.5 s                                                                                  | not read (a `.` wanted): not drawn                                  | not opened: the comma splits the fields        | not burned; attached -- unnoted                    |
| End before start                                            | never drawn                                                     | drawn to the next start; the last, to the end (mpv: never, by source)                        | never drawn                                                         | kept                                           | not burned; attached, to the next start -- unnoted |
| Line ends                                                   | LF, CRLF, CR                                                    | LF, CRLF; CR alone: no event read, drawn from the header; converted, no cue                  | LF, CRLF; CR alone in a file without LF                             | LF, CRLF; CR alone, one line                   | as libass; attached, CR alone no cue -- unnoted    |
| A section of its own (`[Aegisub Project Garbage]`)          | its lines read as the section's before                          | the header's, kept                                                                           | the header's, libass's reading                                      | its own: project settings; another skipped     | as libass                                          |
| Sections, `Format:` names, `Default`                        | any case; any case; any case                                    | the header's, libass's reading                                                               | libass's reading                                                    | sections any case; `Format:` lines ignored     | as libass                                          |
| Not UTF-8 (`café ’x’` in CP1252)                            | each byte its Latin-1 character: `’` a control                  | ffmpeg: the `subtitles` filter fails, a conversion drops the event; mpv recodes by its guess | passed to libass, as libass alone                                   | its guess (uchardet), else asked               | refused by its line                                |
| UTF-16, its BOM                                             | no track: the burn fails                                        | recoded, read                                                                                | recoded, read                                                       | read                                           | recoded: burned, attached                          |
| A NUL in a text                                             | the script ends there: every later event lost                   | the event cut there, the rest a header line; two, or one first in a line: the reading ends   | the line cut there (C strings)                                      | kept in the text                               | U+FFFD, noted                                      |

## What ffmpeg makes of it

Converted to SubRip, an event's style becomes markup: bold, italic and underline as `<b> <i> <u>`
(its strikeout dropped), its font, size and primary colour as `<font>` and its alignment as
`{\anN}`, each where not ffmpeg's own (Arial, 16, white, bottom centre); the blocks' own tags alike,
`\s1` as `<s>`; `\N` and `\n` line breaks; every other tag, position, motion, layer and effect
dropped; `\{`, `\}` and `\h` left as written. Converted to WebVTT, `<b> <i> <u>` alone, `\N` and
`\n` breaks, the other escapes as written -- a browser shows the backslashes. Into MP4 the text goes
as `mov_text`; Matroska keeps the script itself, its header the track's private data. Written back
as ASS -- a stream copy or a transcoding -- the header is kept as read, the events after it in the
file's order, `Comment:` lines and any line it could not read after them; times `h:mm:ss.cc`,
9:59:59.99 at most. From SubRip or WebVTT, ffmpeg's own script: `PlayResX: 384`, `PlayResY: 288`,
one `Default` style (Arial 16).

## The writers in use

Aegisub writes UTF-8 with a BOM: `[Script Info]` (its comment lines, `Title`, `ScriptType:
v4.00+`, `WrapStyle: 0`, `ScaledBorderAndShadow: yes`, `YCbCr Matrix: None`, PlayRes when set),
`[Aegisub Project Garbage]`, `[V4+ Styles]`, `[Fonts]`/`[Graphics]`, `[Events]` -- each
`Format:` line the standard one -- times rounded half up to the centisecond, within 0 and
9:59:59.99, a comma in a style's name, speaker or effect written `;`, line breaks dropped from a
text. ffmpeg writes its own script for a conversion from SubRip or WebVTT (above). ffman writes
an ASS for its burn alone, never as an output. whisper.cpp, OpenAI whisper and WhisperX write
none.

## Writing one all of them read alike

1. UTF-8, LF line ends (CRLF too; never CR alone: ffmpeg reads no event); a BOM, if any, first.
2. `[Script Info]` first, exactly so -- nothing before it but a BOM -- holding `ScriptType:
   v4.00+`, `PlayResX` and `PlayResY` (the video's size, or its shape: else 384x288, sizes scaled
   from it), `ScaledBorderAndShadow: yes` (borders and shadows scaled alike; libass's default
   no).
3. `[V4+ Styles]`, its standard `Format:` line, then each `Style:`: a name without commas,
   distinct, no `*` first and no space last (libass 0.17.4 keeps that space, 0.17.1 trims it);
   colours `&HAABBGGRR`.
4. `[Events]`, its standard `Format:` line -- `Layer, Start, End, Style, Name, MarginL, MarginR,
   MarginV, Effect, Text` -- and every event in that order: ffmpeg, VLC and Aegisub read no
   other.
5. Times `h:mm:ss.cc`, under 10 hours (ffmpeg's muxer writes each later one `9:59:59.99`,
   Aegisub stops there): a `.`, then exactly two digits -- libass and ffmpeg read the digits as
   centiseconds, Aegisub as a decimal -- each event's end after its start. From milliseconds,
   round each time once to the centisecond, half up, as Aegisub does, then write it:

   ```python
   def ass_time(ms: int) -> str:
       cs = (ms + 5) // 10  # to the centisecond, half up
       return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"
   ```

6. A text of one line, `\N` for a break; no NUL; `\{` and `\}` for a brace meant as text (a `{`
   with a `}` after it opens a block; the escapes reach SubRip and WebVTT as written); a `\`
   before `N`, `n`, `h`, `{` or `}` only as an escape.
7. An event's style by its exact name; `Comment:` for what must not be drawn.

## Reading one correctly

As libass does, every player's renderer: a UTF-8 BOM skipped, each byte not UTF-8 its Latin-1
character (better: ask, or guess as mpv does); lines ending at CR or LF, leading spaces skipped;
sections by a case-insensitive prefix, an unknown one reading on as the one before; the type from
the styles section, else `ScriptType`; each line's fields by its section's `Format:` line, the
standard order without one; the text the rest of the line, its trailing spaces off; a time
`%d:%d:%d.%d`, its fraction centiseconds whatever its width; a style by its name, an unknown one
`Default`'s; `Dialogue:` lines events, `Comment:` and anything else ignored. Where ffmpeg's
reading differs (the table), say which reader the result is for.

## Converting, muxing and burning with ffmpeg

```sh
ffmpeg -i video.mp4 -vf ass=in.ass -c:a copy out-burn.mp4                 # libass alone
ffmpeg -i video.mp4 -vf subtitles=in.ass -c:a copy out-sub.mp4            # ffmpeg's reading, then libass
ffmpeg -i video.mkv -i in.ass -map 0 -map 1 -c copy out.mkv               # the script kept whole
ffmpeg -i video.mp4 -i in.ass -map 0 -map 1 -c copy -c:s mov_text out.mp4 # its text alone
ffmpeg -i in.ass out.srt                                                  # b, i, u, \s1, font, colour
ffmpeg -i in.srt out.ass                                                  # PlayRes 384x288, one style
```

A burn draws with the fonts the system has, or a folder's (`ass=in.ass:fontsdir=fonts`); a script's
`[Fonts]` are used by both filters. A script not UTF-8 (CP1252, say): recode it whole first,
`iconv -f CP1252 -t UTF-8 in.ass > in-utf8.ass`; `-sub_charenc CP1252` before its `-i`
(`subtitles=in.ass:charenc=CP1252` for a burn) recodes its events alone, so a style's name not ASCII
then matches none; the `ass` filter has neither. ffman burns an ASS with `--burn-subs` (plain mode
alone, in its own styles: `--font` and the other look options refused) and attaches one with
`--add-subs` -- Matroska keeping it as ASS, MP4 and WebM converting it.

## Example

```ass
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,60,60,50,1
Style: Sign,Arial,48,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,8,60,60,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,Ana,0,0,0,,{\i1}Last stop{\i0}, the harbour\Nend of the line
Dialogue: 1,0:00:02.00,0:00:04.25,Sign,,0,0,0,,PLATFORM \{2\}
Comment: 0,0:00:04.00,0:00:05.00,Default,,0,0,0,,check the sign's font
Dialogue: 0,0:01:02.05,0:01:04.00,Default,,0,0,0,,Tea & toast, 2,50 €
```

libass and ffmpeg read three events, the `Comment:` none: 1 s for 2.5 s, the line in italic up to
`Last stop` and broken after `the harbour`; 2 s for 2.25 s, the sign in bold yellow at the top,
over the first (layer 1), `PLATFORM {2}`; 62.05 s for 1.95 s, the commas the text's. Converted to
SubRip, ffmpeg writes `<font size="64"><i>Last stop</i>, the harbour` and `end of the line</font>`;
`<font size="48" color="#ffff00"><b>{\an8}PLATFORM \{2\}</b></font>`; `<font size="64">Tea &
toast, 2,50 €</font>` -- the sign's escapes as written.

## Sources

libass 0.17.4 (`libass/ass.c`, `ass_parse.c`, `ass_utils.c`, `ass_render.c`); FFmpeg n8.1.2
(`libavformat/assdec.c`, `assenc.c`, `subtitles.c`; `libavcodec/assdec.c`, `assenc.c`,
`ass_split.c`, `srtenc.c`, `webvttenc.c`, `decode.c`; `libavfilter/vf_subtitles.c`); VLC 3.0.24
(`modules/demux/subtitle.c`, `modules/codec/libass.c`, `src/input/stream.c`); mpv 0.41.0
(`demux/demux_lavf.c`, `sub/sd_ass.c`); Aegisub 3.4.2 (`src/ass_parser.cpp`,
`src/ass_dialogue.cpp`, `src/subtitle_format_ass.cpp`, `src/text_file_writer.cpp`,
`libaegisub/ass/time.cpp`, `libaegisub/common/charset.cpp`); libass's "ASS File Format Guide" and
Aegisub's "ASS Override Tags"; ffman's `subs/ingest.py` and `jobs/convert/burn.py`.
Measurements: `scripts/measure.py`, `scripts/measure_ffmpeg.py`.
