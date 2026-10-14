# ASS and SSA: the formats as libass reads them and Aegisub writes them

Advanced SubStation Alpha (ASS, `ScriptType: v4.00+`) and its predecessor SubStation Alpha v4 (SSA,
`v4.00`) have no maintained specification: the 1990s "Sub Station Alpha v4.00+ Script Format"
document is the origin, and practice is what libass (the renderer of mpv, ffmpeg's `subtitles` and
`ass` filters, and ffman's burn) reads and what Aegisub (the editor) writes. Researched at libass
0.17.4 (`libass/ass.c`, `ass_parse.c`, `ass_utils.c`, `ass_types.h`; nixpkgs' pin), Aegisub 3.4.2
(`src/subtitle_format_ass.cpp`, `ass_style.cpp`, `ass_dialogue.cpp`, `ass_parser.cpp`,
`libaegisub/ass/time.cpp`; nixpkgs' pin), libass's "ASS File Format Guide" (wiki) and Aegisub's "ASS
Override Tags" page; VLC 3.0.24 (`modules/demux/subtitle.c`, `modules/codec/libass.c`) and mpv
0.41.0 (`demux/demux_lavf.c`, `sub/sd_ass.c`) by source. Measured by `../scripts/measure.py` with
`../scripts/assdump.c` built against libass 0.17.4 (its output is the tables marked *measured*).
ffmpeg's `ass` reader and writer: their section below, measured by `../scripts/measure_ffmpeg.py`.

## The file

```
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,1,2,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:02.50,Default,Bob,0,0,0,,{\an8}Hello,\Nworld
```

| Rule (libass)                                                                                                                                                                                                                                      | Source                                       |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| Lines end at CR or LF; a UTF-8 BOM is skipped; leading spaces of a line ignored                                                                                                                                                                    | `process_text`, `process_line`               |
| A NUL ends the script: its line cut there, nothing after it read (measured below: an event after one not drawn)                                                                                                                                    | `process_text`                               |
| Bytes read as UTF-8 unless a codepage is given (iconv); ffmpeg's `ass` filter gives none, so a UTF-16 script ends at its first NUL byte: no track (measured below)                                                                                 | `read_file_recode`, `vf_subtitles.c`         |
| A byte not UTF-8 is its Latin-1 character (U+0080-U+00FF): CP1252's `é` drawn right, its quotes (0x91-0x94) and `€` controls (measured below)                                                                                                      | `ass_utf8_get_char`                          |
| Sections, by a case-insensitive prefix: `[Script Info]`, `[V4+ Styles]` (ASS), `[V4 Styles]` (SSA), `[Events]`, `[Fonts]`. Any other header -- `[V4++ Styles]`, `[Aegisub Project Garbage]`, `[Graphics]` -- leaves the previous section in force  | `process_line`                               |
| The type: the styles section's, else `ScriptType` (`4.00` with a trailing `+` is ASS, without SSA; `v4.00++` neither). No type, no track: the file is refused                                                                                      | `parse_script_type`, `parse_memory`          |
| `[Script Info]` keys are case-sensitive, `Key:` exactly; a repeated key warns, the last wins                                                                                                                                                       | `process_info_line`                          |
| `Format:` lines name the fields of the lines after them, in any order and number, names matched without case (`Actor` is `Name`); without one, the standard order of the file's type. A custom Format makes `ScaledBorderAndShadow` default to yes | `process_styles_line`, `process_events_line` |
| Fields split at commas, leading spaces skipped; the event's last field, `Text`, takes the rest of the line, trailing spaces, tabs and CRs removed                                                                                                  | `next_token`, `process_event_tail`           |
| `Dialogue:` lines are events; `Comment:` lines and anything else in `[Events]` are ignored                                                                                                                                                         | `process_events_line`                        |

## `[Script Info]` (what libass reads)

| Key                        | Value, default                                                                                                                           |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `ScriptType`               | `v4.00+` ASS, `v4.00` SSA                                                                                                                |
| `PlayResX`, `PlayResY`     | the script's coordinate space. Neither: 384x288; one: the other at 4:3, but X 1280 gives Y 1024, Y 1024 X 1280                           |
| `LayoutResX`, `LayoutResY` | the storage size the script was laid out for (libass 0.17+); default the video's                                                         |
| `WrapStyle`                | 0 smart (lines evened), 1 end of line, 2 none (`\N` and `\n` only); 3 VSFilter's smart with the lower line wider, 0 in libass. Default 0 |
| `ScaledBorderAndShadow`    | `yes`: borders and shadows scale with PlayRes; default no (yes for a custom Format line or a legacy ffmpeg file)                         |
| `Kerning`                  | `yes`/`no`, default no                                                                                                                   |
| `YCbCr Matrix`             | `None`, `TV.601`, `PC.601`, `TV.709`, `PC.709`, `TV.240M`, `PC.240M`, `TV.FCC`, `PC.FCC`                                                 |
| `Language`                 | its first two characters (`pt-BR` -> `pt`)                                                                                               |
| `Timer`                    | read, a speed in percent; no effect in libass                                                                                            |
| `Title` and the others     | ignored (Aegisub writes `Title`, `; Script generated by` comments)                                                                       |

## Styles

ASS fields, in the standard order: `Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,
OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle,
BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding`. SSA's: `Name,
Fontname, Fontsize, PrimaryColour, SecondaryColour, TertiaryColour, BackColour, Bold, Italic,
BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, AlphaLevel, Encoding`.

| Field                                                           | Value (libass)                                                                                                                                                |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| colours                                                         | `&HAABBGGRR` (alpha 00 opaque, FF clear), hex after `&H` or `0x`, else decimal; a trailing `&` ignored; fewer digits are the low bytes (`&HFF8040` is opaque) |
| `Bold`...`StrikeOut`                                            | integers, non-zero true (`-1` is Aegisub's true; a weight such as 700 is bold)                                                                                |
| `Fontsize`, `ScaleX/Y`, `Spacing`, `Angle`, `Outline`, `Shadow` | decimals; negative scales, spacing, outline and shadow become 0; scales are percent                                                                           |
| `BorderStyle`                                                   | 1 outline and shadow, 3 an opaque box in place of the outline, 4 (libass's) one box behind the whole event in `BackColour`, no shadow                         |
| `Alignment`                                                     | ASS: the numpad, 1-9 (7 top left, 5 middle, 2 bottom centre); SSA: legacy, 1-3 bottom, +4 top, +8 middle                                                      |
| `MarginL/R/V`                                                   | integers, pixels of PlayRes; negative kept                                                                                                                    |
| `Encoding`                                                      | a Windows charset number, 1 default; selects nothing in libass                                                                                                |
| SSA's `TertiaryColour`                                          | ignored: the outline takes `BackColour`'s colour; `AlphaLevel` the alpha of the fill, karaoke and outline colours, the shadow's always 0x80 (VSFilter's)      |

A style's name: leading `*` removed, trailing spaces kept (0.17.4; 0.17.1 -- Ubuntu 24.04's, which
the ffmpeg measured here links -- trims them). An event's style is found by exact, case-sensitive
name (`Default` without case), the last of equal names winning; an unknown name warns and takes the
file's last `Default` (else libass's own: Arial 18, white, outline 2, shadow 3, bold, margins 20).
Fields a custom Format omits are 0 -- black, size 0 -- not those defaults.

## Events

| Field                     | Value                                                                                                                                                                                                                                   |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Layer` (SSA: `Marked=0`) | an integer; higher layers are drawn over lower; collisions are resolved within a layer                                                                                                                                                  |
| `Start`, `End`            | `h:mm:ss.cc` -- hundredths of a second. libass: `%d:%d:%d.%d`, the fraction read as an integer of centiseconds whatever its digits; Aegisub: positional                                                                                 |
| `Style`                   | a style's name (above)                                                                                                                                                                                                                  |
| `Name` (`Actor`)          | free text, the speaker by convention; no effect                                                                                                                                                                                         |
| `MarginL/R/V`             | 0 means the style's                                                                                                                                                                                                                     |
| `Effect`                  | `Banner;delay[;lefttoright]`, `Scroll up;y1;y2;delay`, `Scroll down;y1;y2;delay`; anything else ignored                                                                                                                                 |
| `Text`                    | the text, with override blocks `{...}`; `\N` a forced break, `\n` a break only under WrapStyle 2 (a space otherwise), `\h` a non-breaking space; `\{` and `\}` a literal brace (`ass_get_next_char`), a `\` before anything else itself |

*Measured* (libass 0.17.4; times in ms):

| Line or file                                                                                                               | libass's reading                                                         |
| -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `0:00:01.23 --> 0:00:04.56`                                                                                                | 1230, duration 3330                                                      |
| `0:00:01.5`                                                                                                                | 1050: `.5` is 5 centiseconds (Aegisub, by its source: 1500)              |
| `0:00:01.500`                                                                                                              | 6000: 500 centiseconds (Aegisub, by its source: 1500)                    |
| `10:00:00.00`, `100:00:00.00`, `0:75:00.00`                                                                                | 36000000, 360000000, 4500000                                             |
| `0:00:01` (no fraction); `0:00:01,50` (comma)                                                                              | "Bad timestamp": 0; a comma also shifts every later field                |
| `-0:00:01.00`                                                                                                              | 1000: the sign lost                                                      |
| end before start                                                                                                           | a negative duration, kept                                                |
| `Text`: `  lead, mid,  trail   `                                                                                           | `  lead, mid,  trail`: commas and leading spaces kept, trailing removed  |
| override tags                                                                                                              | kept in `Text` as written (parsed when rendering)                        |
| margins `0012,-5,7`                                                                                                        | 12, -5, 7                                                                |
| `Effect` `Banner;20;1`                                                                                                     | kept                                                                     |
| a `Dialogue:` line with too few fields                                                                                     | dropped                                                                  |
| `Dialogue:0,...` (no space)                                                                                                | read                                                                     |
| style `Nope`; `default`; `*Default`                                                                                        | `Default` (a warning); `Default`; `Default`                              |
| two styles named `Default`                                                                                                 | the second                                                               |
| a style `My Style ` asked as `My Style`; as `My Style `                                                                    | 0.17.4: not found (a warning), the space the name's; found; 0.17.1: both |
| no styles section                                                                                                          | read: every event in libass's own style                                  |
| no Format lines                                                                                                            | read in the standard order                                               |
| `Format: Name, Fontsize, Fontname`                                                                                         | read in that order; the omitted fields 0                                 |
| `Format: Start, End, Text`                                                                                                 | read: no `Style` field, so libass's own style (not the file's `Default`) |
| `[script info]`, `[events]` (lower case)                                                                                   | read                                                                     |
| `playresx: 1920` (lower-case key)                                                                                          | ignored: 384x288                                                         |
| `PlayResX: 1920` alone; `1280` alone; `PlayResY: 1080` alone                                                               | 1920x1440; 1280x1024; 1440x1080 (warnings)                               |
| `WrapStyle: 2`, `ScaledBorderAndShadow: yes`, `Kerning: yes`, `YCbCr Matrix: TV.709`, `Language: pt-BR`, `Timer: 100.0000` | 2, 1, 1, TV.709, `pt`, 100                                               |
| `PlayResX: 640` under `[Aegisub Project Garbage]`                                                                          | applied: an unknown section is read as the one before                    |
| `ScriptType: v4.00++`, `[V4++ Styles]`                                                                                     | refused: no track                                                        |
| BOM and CRLF; CR only                                                                                                      | read                                                                     |
| SSA: decimal colours, `-1` bold, alignment `6`, `Marked=0`                                                                 | read: top centre; outline `&H808080` from `BackColour`                   |
| colours `&H80FF8040`; `&HFF8040`; `16777215`; `&h00ff8040&`                                                                | RGBA `4080FF80`; `4080FF00`; `FFFFFF00`; `4080FF00`                      |
| booleans `-1`, `1`, `700`                                                                                                  | true, true, true                                                         |
| `ScaleX -50`, `Outline -1`, `Shadow -1`, `Spacing -2`, `MarginL -10`                                                       | 0, 0, 0, 0, -10                                                          |

## Override tags

In `{...}` blocks within `Text`, each a backslash and a name; libass 0.17.4 knows `xbord ybord
xshad yshad fax fay iclip blur fscx fscy fsc fsp fs bord move frx fry frz fr fn alpha an a pos
fade fad org t clip c 1c 2c 3c 4c 1a 2a 3a 4a r be b i kt kf K ko k shad s u pbo p q fe`
(`ass_parse.c`); an unknown name is ignored.

| Group                 | Tags (Aegisub's page; units as libass reads them)                                                                                                                                                                                                                                                                                             |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Text style            | `\b1`/`\b0` or `\b<weight>`, `\i`, `\u`, `\s`; `\fn<name>`, `\fs<size>`, `\fscx`/`\fscy` (%), `\fsp` (pixels), `\fe`                                                                                                                                                                                                                          |
| Colour and alpha      | `\c` = `\1c&HBBGGRR&` fill, `\2c` karaoke's before-colour, `\3c` border, `\4c` shadow; `\alpha&HAA&`, `\1a`..`\4a`                                                                                                                                                                                                                            |
| Border, shadow, blur  | `\bord`, `\xbord`, `\ybord`; `\shad`, `\xshad`, `\yshad`; `\be`, `\blur`                                                                                                                                                                                                                                                                      |
| Geometry              | `\frx`, `\fry`, `\frz` (`\fr`) degrees; `\fax`, `\fay` shear; `\org(x,y)` the rotation's origin                                                                                                                                                                                                                                               |
| Position              | `\an1`..`\an9` (numpad), `\a` (legacy); `\pos(x,y)`; `\move(x1,y1,x2,y2[,t1,t2])` (t in ms from the event's start); `\q0`..`\q3` wrap style                                                                                                                                                                                                   |
| Clip, drawing         | `\clip(x1,y1,x2,y2)`, `\iclip`, or a drawing; `\p<n>` drawing mode, `\pbo`                                                                                                                                                                                                                                                                    |
| Time                  | `\fad(in,out)` ms; `\fade(a1,a2,a3,t1,t2,t3,t4)`; `\t([t1,t2,][accel,]tags)` animates tags (ms)                                                                                                                                                                                                                                               |
| Karaoke (word timing) | `\k<d>` (fill at once), `\kf<d>` = `\K<d>` (sweep), `\ko<d>` (border too): each the duration of the syllable after it, centiseconds -- libass reads decimals, truncated to the millisecond (`ass_parse.c`: `dtoi32(val * 10)`); no argument 100. `\kt<t>` (v4++, libass 0.17+) the next syllable's start, centiseconds from the event's start |
| Reset                 | `\r` to the event's style, `\r<style>` to another                                                                                                                                                                                                                                                                                             |

## ffmpeg's reading and writing

FFmpeg n8.1.2's `ass` demuxer and muxer (`libavformat/assdec.c`, `assenc.c`) and its `ass`
decoder and encoder (`libavcodec/assdec.c`, `assenc.c`): a script's events pass as they are;
everything else is the header, written back verbatim.

| Rule                                                                                                                                                                                                                                                                                                                                                              | Source                         |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| Detection: `[Script Info]`, its 13 bytes, in its case, after a UTF-8 BOM and CRs and LFs alone -- else not ASS: a space or a comment first, no reader; `[script info]`, the LRC one (measured)                                                                                                                                                                    | `ass_probe`                    |
| A UTF-16 BOM (LE or BE): the text recoded to UTF-8 as it is read; a lone surrogate read as a NUL, an odd last byte as a character                                                                                                                                                                                                                                 | `ff_text_r8` (`subtitles.c`)   |
| The decoder drops an event not UTF-8, its style's name included ("Invalid UTF-8 in decoded subtitles text"): a transcoding loses it, a stream copy keeps its bytes; the header passes as it is                                                                                                                                                                    | `utf8_check` (`decode.c`)      |
| An event: a line `Dialogue: <layer>,%d:%d:%d<any>%d,%d:%d:%d<any>%d,` -- the standard order whatever the `Format:` line, the fraction an integer of **centiseconds**, any width, after any one character; the packet `ReadOrder,Layer,` and the rest of the line. Every other line -- `Comment:`, a `Dialogue:` it cannot read, every section -- joins the header | `read_dialogue`                |
| Times in centiseconds (time base 1/100); sorted by start, a negative duration becomes the gap to the next start; duplicates kept                                                                                                                                                                                                                                  | `ff_subtitles_queue_finalize`  |
| The decoder and encoder pass each event's text through untouched: the header is the decoder's script, the encoder's too                                                                                                                                                                                                                                           | `ass_decode_frame`             |
| The muxer: the header up to the `[Events]` `Format:` line, then the events in their ReadOrder (the file's order), then the rest of the header; times `h:mm:ss.cc`, **9:59:59.99 at most**; SSA (no `[V4+ Styles]` line) gets `Marked=`                                                                                                                            | `write_packet`, `write_header` |

*Measured* -- read, then written back by a stream copy and by a transcoding (alike unless said):

| Script                                                        | ffmpeg's reading and writing                                                                                        |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `0:00:01.00` to `0:00:02.00`, `Hello\Nworld`                  | 100, 100 cs; written back as read                                                                                   |
| `0:00:01.5`; `0:00:01.500`                                    | 1.05 s; 6 s: centiseconds whatever the digits, as libass                                                            |
| a last event ending before it starts (`0:00:06.00` -> `2.00`) | copied as read; transcoded, its end `9:59:59.99`                                                                    |
| `10:00:00.00`                                                 | read; written `9:59:59.99` to `9:59:59.99`: no length, never shown (libass draws an event while start <= now < end) |
| layers 0 and 5; commas in the text                            | kept                                                                                                                |
| events out of order; overlapping; two identical               | written in the file's order; kept; both kept                                                                        |
| an event ending before it starts, another after               | its end the next one's start (`3.00 -> 5.00`)                                                                       |
| zero duration; empty text                                     | kept                                                                                                                |
| a `Comment:` between events                                   | moved after every `Dialogue:` (the header's rest)                                                                   |
| `[Fonts]` after the events                                    | kept, at the end                                                                                                    |
| `Dialogue: 0,0:00:01.00,0:00:02.00` (no more fields)          | no event: moved to the end, as header text                                                                          |
| `[Events]` without its `Format:` line                         | read; written without one                                                                                           |
| CRLF; a UTF-8 BOM; blank lines first                          | read alike; written LF                                                                                              |
| SSA v4 (`[V4 Styles]`, `Marked=0`)                            | read (`Marked=0` layer 0); written back as SSA, `Marked=0`                                                          |
| `v4.00++` (`[V4++ Styles]`)                                   | read; written with `Marked=0` under a `Layer` Format line: taken for SSA                                            |
| a NUL in a text (`fi` NUL `rst`, then `next`)                 | the event cut, `fi`; the rest, `rst`, a header line (written after the events); `next` kept                         |
| two NULs in a text (`fi` NUL NUL `rst`, then `next`)          | the event `fi`; the reading ends there: `next` lost                                                                 |
| a NUL first in a line (`first`, NUL `; x`, then `next`)       | `first` read; the reading ends at the NUL: `next` lost                                                              |
| UTF-16, LE or BE (its BOM), `café`                            | read as UTF-8; written UTF-8                                                                                        |
| UTF-16, a lone surrogate (`fi` U+D800 `rst`, then `next`)     | the surrogate and the unit after it a NUL: the event `fi`, `st` a header line; `next` kept                          |
| UTF-16, an odd byte (`x`) last                                | the events read; `x` a header line                                                                                  |
| CP1252, an event's text (`café ’x’`, then `next`)             | copied as read; transcoded, the event dropped, `next` kept                                                          |
| CP1252, a header's comment (`; é`)                            | kept as read, its bytes                                                                                             |
| `[script info]`, lower-cased                                  | no ASS: the LRC reader takes it (a `[` first), no event; an empty track                                             |
| `Format: Start, End, Style, Text` (another order)             | no event: each `Dialogue:` line a header line ("Output file is empty"): converted, no cue                           |
| a comma before a fraction (`0:00:01,00`)                      | read: 1.00 s, any one character before the fraction                                                                 |
| CR line ends alone                                            | no event: the script one line, the header ("Output file is empty"): converted, no cue                               |
| a comment, or spaces, before `[Script Info]`                  | no reader: "Invalid data found when processing input"                                                               |

*Measured* -- libass alone (ffmpeg's `ass` filter: `ass_read_file`; ffman's burn) against
libass given ffmpeg's reading (the `subtitles` filter: the demuxer's header to
`ass_process_codec_private`, each event to `ass_process_chunk`; mpv's path, `sub/sd_ass.c`):
what each draws at each time, `x` something, `.` nothing (libass 0.17.1 and 0.17.4 alike). The
header libass is given is read as a script, so a `Dialogue:` line the demuxer could not read is
still drawn when libass can read it. mpv, by source, passes the last event's negative length on
to libass (`sd_ass.c`, `filter_and_add`): that one never drawn:

| Script, its event at 1-2 s unless said               | `ass` (libass alone)                       | `subtitles` (ffmpeg, then libass)                              |
| ---------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------- |
| canonical (0.5, 1.5, 2.5 s)                          | `.x.`                                      | `.x.`                                                          |
| `[script info]`, lower-cased                         | `.x.`                                      | `...`: the LRC reader's, no event                              |
| a comment before `[Script Info]`                     | `.x.`                                      | failed: "Invalid data found when processing input"             |
| `Format: Start, End, Style, Text`                    | `.x.`                                      | `.x.`: no event read, libass reads the header's line           |
| a comma before the start's fraction                  | `...`: "Bad timestamp", the fields shifted | `.x.`                                                          |
| 3 s to 1 s, then 5 s to 6 s (2, 3.5, 4.5, 5.5 s)     | `...x`: never drawn                        | `.xxx`: drawn to the next start                                |
| 3 s to 1 s, the last (2, 3.5, 5.5 s)                 | `...`                                      | `.xx`: drawn to the end                                        |
| CR line ends alone                                   | `.x.`                                      | `.x.`: no event read, libass reads the header                  |
| no type (no `ScriptType`, no styles section)         | failed: "Could not create a libass track"  | `.x.`                                                          |
| `v4.00++`, `[V4++ Styles]`                           | failed: "Could not create a libass track"  | `.x.`                                                          |
| a NUL in a text, another event at 3-4 s (1.5, 3.5 s) | `x.`: the script ends at the NUL           | `xx`: the event cut at it                                      |
| UTF-16LE, its BOM                                    | failed: "Could not create a libass track"  | `.x`                                                           |
| CP1252, an event's text                              | `.x`: its Latin-1 characters               | failed: "Invalid UTF-8 in decoded subtitles text" -- no output |

The header -- `[Script Info]`, the styles -- is written back as it was read, ffmpeg's comment
not added. From SubRip, WebVTT or LRC, ffmpeg's default script instead (their records):
`PlayResX: 384`, `PlayResY: 288`, one `Default` style.

*Measured* -- converted to SubRip and to WebVTT: a style of every flag in ffmpeg's defaults (Arial
16, white, bottom centre) gives `<b><i><u>all</u></i></b>` in both, its strikeout dropped; one of
none, Times 20, red, top left, gives SubRip's
`<font face="Times" size="20" color="#ff0000">{\an7}other</font>` and WebVTT's `other`. The tags
`{\b1}b {\i1}i {\u1}u {\s1}s` give SubRip's `<b>b <i>i <u>u <s>s</s></u></i></b>`, WebVTT's the same
but `s`. `a\hb\nc\Nd \{x\}` gives both `a\hb`, `c` and `d \{x\}` as three lines; `e\N\Nf` an empty
line between; `g {\b1 h`, a block no `}` closes, both `g <b>`: cut there, where libass draws it as
written. A CP1252 script given `-sub_charenc CP1252` (the `subtitles` filter's `charenc`) has its
events recoded: `café ’x’`, drawn; not its header -- a style `Café` bold, its event `thé` converted
as `thé`, the style not found; recoded whole first, `<b>thé</b>`.

*Measured* -- libass through ffmpeg's `ass` filter (the frame's digest; that ffmpeg's libass
0.17.1, whose `ass_get_next_char` 0.17.4 keeps): `a{x}b` draws as `ab` (`{x}` an override
block); `a\{x\}b` draws otherwise -- its braces and `x` shown. `a` NUL `b`, an event after it,
draws as `a` alone: the script ends at the NUL. A UTF-16 script (its BOM, LE or BE) draws
nothing: "Could not create a libass track", the filter not initialized -- the job fails.
`café ’x’` in CP1252 draws as its Latin-1 reading, `café` and two U+0092s, not as UTF-8's. A
script of no type (no `ScriptType`, no styles section) draws nothing: "Could not create a libass
track".

## VLC 3's reading

VLC 3.0.24, by source: its own subtitle demuxer (`modules/demux/subtitle.c`) splits the script
into a header and events, and its libass decoder (`modules/codec/libass.c`, preferred over
`subsdec`) draws them -- the header by `ass_process_codec_private`, so libass reads a
`Dialogue:` line it could not read, as through ffmpeg; but VLC draws only while an event it read
is shown (`SubpictureValidate`, a subpicture a block): with none read, nothing.

| Rule                                                                                                                                                                                 | Source                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Recognised by a line, any case, among the first 256 of the first 4 KiB: `ScriptType: v4.00+` or `Dialogue:` ASS; `ScriptType: v4.00` or `Dialogue: Marked` SSA v4; 16 bytes at least | `Open`                        |
| A UTF-8 BOM skipped; UTF-16 by its BOM converted to UTF-8; other bytes passed unchanged (libass reads one not UTF-8 as its Latin-1 character)                                        | `Open`, `vlc_stream_ReadLine` |
| Lines end at an LF, or at a CR when the next 2 KiB hold none                                                                                                                         | `vlc_stream_ReadLine`         |
| An event: `Dialogue: %15[^,],%d:%d:%d.%d,%d:%d:%d.%d,` -- the standard order, a `.` before the fraction, read as centiseconds whatever its width; every other line the header        | `ParseSSA`                    |
| Events sorted by start; one ending before it starts given no length (0): never drawn                                                                                                 | `Fix`, `Demux`                |

## Aegisub's reading (3.4.2)

By source (`src/ass_parser.cpp`, `src/ass_dialogue.cpp`, `libaegisub/ass/time.cpp`): sections
by their whole name, any case, `[Aegisub Project Garbage]` its project's settings, an unknown one
skipped (libass reads its lines as the section's before); `ScriptType` other than `v4.00+` or
`v4.00` refused ("Unknown SSA file format version"); an event's fields split at its commas and
read by position, whatever the `Format:` line, its layer and margins as numbers -- so `Format:
Start, End, Style, Text` fails (the layer `0:00:01.00`), and so does `0:00:01,50` (its comma a
field's end: a margin not a number), the file not opened; a time's fraction a decimal:
`0:00:01.5` 1.5 s, three digits at most read (libass: 1.05 s); a time kept within 0 and
9:59:59.994.

## ffman's reading

ffman passes an ASS or SSA through, unread: its burn draws ffman's copy with the `ass` filter
(libass alone), `--add-subs` gives the copy to ffmpeg (its reading). The copy: UTF-8, a UTF-16
script (its BOM) recoded, each NUL U+FFFD, noted; refused unless `[Script Info]` is first (ffmpeg's
detection, though its attach names the demuxer) and the script has a type (libass's) --
`subs/ingest.py`. *Measured* (`../scripts/measure_ffmpeg.py` with a PYTHON), the scripts of the
table above:

| Script                                                | ffman                                                                                   |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------- |
| canonical                                             | burned; attached, 1 cue                                                                 |
| `[script info]`, lower-cased; a comment first         | refused: "not an ASS file: x.ass (its first line is not [Script Info])"                 |
| no type; `v4.00++`                                    | refused: "... (no [V4+ Styles] or [V4 Styles] section, nor ScriptType v4.00+ or v4.00)" |
| `Format: Start, End, Style, Text`; CR line ends alone | burned; attached, no cue -- unnoted                                                     |
| a comma before the start's fraction                   | not burned; attached, 1 cue -- unnoted                                                  |
| 3 s to 1 s, then 5 s to 6 s                           | burned, the second alone; attached, both (the first to the next start) -- unnoted       |
| a NUL in a text, another event                        | U+FFFD, noted; burned and attached, both                                                |
| UTF-16LE, its BOM                                     | recoded: burned; attached, 1 cue                                                        |
| CP1252, an event's text                               | refused: "not UTF-8: x.ass (line 12)"                                                   |

## Aegisub's writing (3.4.2)

| What         | How                                                                                                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Order        | `[Script Info]` (its comment `; Script generated by Aegisub <version>`, `; http://www.aegisub.org/`, then the keys), `[Aegisub Project Garbage]` (audio and video files, UI state), `[V4+ Styles]`, `[Fonts]`/`[Graphics]`, `[Events]`, `[Aegisub Extradata]` |
| A new file   | `Title: Default Aegisub file`, `ScriptType: v4.00+`, `WrapStyle: 0`, `ScaledBorderAndShadow: yes`, `YCbCr Matrix: None`, PlayRes when set                                                                                                                     |
| Format lines | the standard ones, always; Aegisub reads fields by position, ignoring any Format line                                                                                                                                                                         |
| Styles       | `Style: %s,%s,%g,&HAABBGGRR x4,-1/0 x4,%g x4,%d,%g,%g,%i,%i,%i,%i,%i`; a comma in a name or font becomes `;`                                                                                                                                                  |
| Events       | `Dialogue:`/`Comment:`; times `h:mm:ss.cc`, rounded to centiseconds half up (`(ms + 5)`), within 0 and 9:59:59.99; a comma in `Style`, `Name` or `Effect` becomes `;`; CR and LF removed from the text                                                        |
| SSA (`.ssa`) | read as v4: tertiary colour skipped, alignment converted, `Marked=` ignored                                                                                                                                                                                   |
| Line ends    | LF (CRLF on Windows)                                                                                                                                                                                                                                          |

## What ASS holds

| Property    | ASS (SSA)                                                                                                                                                  |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Times       | start and end, centiseconds; libass reads more digits as centiseconds too, so ms precision cannot be written                                               |
| Text        | one line per event, `\N` for breaks; `\{` and `\}` for literal braces (libass; a `{` before a `}` opens a block); no escape for `\` before `N`, `n` or `h` |
| Styling     | named styles (font, size, four colours with alpha, bold, italic, underline, strike, scale, spacing, angle, border, shadow) and per-span overrides          |
| Position    | alignment, margins, `\pos`, `\move`, `\org`, `\clip`, layers; PlayRes as the coordinate space                                                              |
| Word timing | `\k` family: syllable durations in centiseconds, from the event's start, consecutive; a gap an empty syllable, or `\kt` (libass: `effect_skip_timing`)     |
| Speakers    | `Name` (`Actor`), free text                                                                                                                                |
| Other       | `Comment:` events, `Effect`, embedded fonts and graphics, the script's header keys                                                                         |
