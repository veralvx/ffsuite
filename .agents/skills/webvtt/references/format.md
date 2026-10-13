# WebVTT: the format by its specification, measured in a browser

Researched from the W3C's "WebVTT: The Web Video Text Tracks Format", the Candidate
Recommendation Draft of 2026-05-20 (`https://www.w3.org/TR/2026/CRD-webvtt1-20260520/`), from its
source: the editor's draft, `w3c/webvtt` `index.bs` at commit `0648025` of the same day. Measured by
`../scripts/measure.py` in Chromium 141.0.7390.37 (Playwright's): its `<track>` parser
implements the specification's algorithm, its `VTTCue` the data model -- but not regions,
`lineAlign` or `positionAlign` (absent from its `VTTCue`), so those rows are the
specification's alone. ffmpeg's `webvtt` reader and writer: their section below, measured by
`../scripts/measure_ffmpeg.py`, which with a Python importing ffman measures ffman's reading too,
closing the record (VLC's and mpv's, by source: the skill); the writers in use (whisper.cpp,
OpenAI whisper, WhisperX) the `whisper-transcripts` skill's.

## The file

```
WEBVTT - an optional title

NOTE a comment, ignored

STYLE
::cue(.yellow) { color: yellow }

REGION
id:fred width:40% lines:3 regionanchor:0%,100% viewportanchor:10%,90% scroll:up

intro
00:00:01.000 --> 00:00:02.500 align:start line:10% region:fred
<v Bob>Hello <c.yellow>there</c></v>
```

| Rule                                                                                                                                                                                                                                                | Source                                   |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| UTF-8 (`text/vtt`), an optional BOM; the signature `WEBVTT`, then a space, a tab or a line end -- else the file is refused whole                                                                                                                    | file structure; parser                   |
| Line ends: CRLF, LF or CR. NUL becomes U+FFFD                                                                                                                                                                                                       | parser                                   |
| Blocks separated by blank lines: `REGION` and `STYLE` blocks before the first cue only; `NOTE` comments anywhere; cues                                                                                                                              | file structure                           |
| A cue: an optional identifier line (no `-->`), the timing line, the payload; the payload ends at a blank line or at a line holding `-->`, and may hold neither                                                                                      | file structure; "collect a WebVTT block" |
| Timing: `start --> end`, separated by spaces or tabs (the parser takes none), then settings. A timestamp: `[hh:]mm:ss.ttt` -- hours two or more digits (required when non-zero), minutes and seconds two digits 0-59, exactly three fraction digits | "collect a WebVTT timestamp"             |
| Times in seconds, to the millisecond; the syntax wants start >= the previous cue's start and end > start, the parser checks neither                                                                                                                 | file structure; parser                   |
| A timing line the parser refuses drops its cue; an unknown or malformed setting is skipped alone                                                                                                                                                    | parser                                   |

*Measured* (Chromium):

| File                                                        | The parser's reading                                             |
| ----------------------------------------------------------- | ---------------------------------------------------------------- |
| `WEBVTT - a title` with header lines; `WEBVTT` + tab; a BOM | read                                                             |
| `webvtt`; `WEBVTTx`                                         | refused: no cues                                                 |
| no blank line after `WEBVTT`                                | read: the timing line still starts a cue                         |
| CRLF; CR                                                    | read alike                                                       |
| CR CR LF                                                    | two line ends: each cue of no text                               |
| a line of spaces or a tab in a cue                          | its text: an empty line alone ends a cue                         |
| a NUL in the text                                           | U+FFFD                                                           |
| `00:01.000` (no hours)                                      | 1 s                                                              |
| `1:00:00.000` (one-digit hour)                              | 3600 s: the parser takes it (the syntax wants two digits)        |
| `100:00:00.000`                                             | 360000 s                                                         |
| `60:00.000` (no hours); `00:60:00.000`                      | refused: the cue dropped                                         |
| `00:00:01,000` (comma); `.50` (two digits); `.5000` (four)  | refused: the cue dropped                                         |
| `00:00:01.000-->00:00:02.000`; tabs around `-->`            | read                                                             |
| end before start; end equal to start                        | kept as written (3 -> 1; 1 -> 1)                                 |
| cues out of order; overlapping                              | listed by start (the track's cue list is ordered); overlaps kept |
| a blank line inside the text                                | the cue ends there; the rest, without a timing line, dropped     |
| a text line holding `-->`                                   | the cue ends before it; that line and the rest dropped           |
| a timing line, then a blank line                            | a cue with empty text                                            |
| `my cue 1` before the timing line                           | the identifier `my cue 1`                                        |
| two lines before the timing line                            | no identifier: the block dropped, the cue read without it        |
| `NOTE ...` block                                            | ignored                                                          |
| `NOTE` directly over a timing line                          | a cue whose identifier is `NOTE`                                 |
| `STYLE` after a cue                                         | ignored                                                          |
| no blank line between two cues                              | two cues: the timing line ends the first                         |
| a comma time mid-file                                       | that cue dropped, the rest read                                  |
| two identical cues                                          | both kept                                                        |
| a byte not UTF-8 (`caf\xe9`)                                | U+FFFD                                                           |
| UTF-16LE with its BOM                                       | read: the BOM honoured (the syntax wants UTF-8)                  |

## Cue settings

Each `name:value`, separated by spaces or tabs, each at most once (the parser takes the last).

| Setting    | Values                                                                             | Default       | Chromium                                     |
| ---------- | ---------------------------------------------------------------------------------- | ------------- | -------------------------------------------- |
| `vertical` | `rl`, `lr`                                                                         | horizontal    | read                                         |
| `line`     | a line number (`-2`: from the end) or a percentage, then `,start`/`,center`/`,end` | `auto`, start | read without the alignment; with it, dropped |
| `position` | a percentage, then `,line-left`/`,center`/`,line-right`                            | `auto`        | read without the alignment; with it, dropped |
| `size`     | a percentage                                                                       | 100           | read                                         |
| `align`    | `start`, `center`, `end`, `left`, `right`                                          | `center`      | read                                         |
| `region`   | a region's id (dropped by `vertical`, `line` or a `size` other than 100)           | none          | not implemented                              |

*Measured*: `line:abc position:130% size:x align:middle foo:bar` -- each skipped, the cue kept;
`align:start align:end` -- `end`. A `REGION` block's settings: `id`, `width` (%), `lines`,
`regionanchor` and `viewportanchor` (`x%,y%`), `scroll:up`.

## Cue text

| Markup                                                                           | Means                                                                      | DOM (`getCueAsHTML`, measured) |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------ |
| `<b>`, `<i>`, `<u>`                                                              | bold, italic, underline                                                    | `<b>`, `<i>`, `<u>`            |
| `<c.yellow.big>`                                                                 | a span with classes (styled by `::cue(.yellow)`)                           | `<span class="yellow big">`    |
| `<b.loud>` -- any tag                                                            | classes on any span                                                        | `<b class="loud">`             |
| `<v Bob>`, `<v.first Esme Tiu>`                                                  | a voice: the speaker's name (the end tag may be omitted)                   | `<span title="Bob">`           |
| `<lang en-GB>`                                                                   | a language                                                                 | `<span lang="en-GB">`          |
| `<ruby>漢<rt>kan</rt></ruby>`                                                    | ruby                                                                       | `<ruby>`, `<rt>`               |
| `<00:00:01.500>`                                                                 | a timestamp: the text after it becomes current then (karaoke, word timing) | `<?timestamp 00:00:01.500>`    |
| `&amp;` `&lt;` `&gt;` `&nbsp;` `&lrm;` `&rlm;`, `&#169;`, `&#x263A;`, `&eacute;` | HTML's character references, every one                                     | decoded                        |

*Measured*, the parser's tolerance:

| Text                                       | DOM                                              |
| ------------------------------------------ | ------------------------------------------------ |
| `<v Bob>no end tag`                        | the voice span to the end                        |
| `<v>no name</v>`                           | `<span title="">`                                |
| `a <00:01.500>b` (no hours)                | a timestamp, written `00:00:01.500`              |
| `a <00:00:01,500>b`                        | ignored as an unknown tag                        |
| `<s>`, `<font color=red>`, `<span>`, `<B>` | ignored (names are lower case); text kept        |
| `<b>open` (unclosed)                       | bold to the end                                  |
| `a</b> b` (stray end tag)                  | ignored                                          |
| `<b>1<i>2</b>3</i>`                        | `</b>` ignored inside `<i>`: `<b>1<i>23</i></b>` |
| `&amp &lt; AT&T`                           | `& < AT&T`: HTML's legacy names need no `;`      |
| `&bogus; &;`                               | kept as text                                     |
| `a < b`                                    | `a `: `< b` read as a tag, the text lost         |
| `a<b`                                      | `a`, then an empty `<b>`                         |
| `a < b and c > d`                          | `a `, ` d`: `< b and c >` a tag                  |
| `before <b ends`                           | `before `, then an empty `<b>`                   |
| `{\an8}up {x} one\Ntwo \n`                 | as written                                       |
| tabs, runs of spaces, trailing spaces      | kept                                             |

A text holding `<` or `&` must write them `&lt;` and `&amp;`; `-->` cannot be held at all.

## ffmpeg's reading and writing

FFmpeg n8.1.2's `webvtt` demuxer and muxer (`libavformat/webvttdec.c`, `webvttenc.c`) and its
`webvtt` decoder and encoder (`libavcodec/webvttdec.c`, `webvttenc.c`, `ass_split.c`): not the
specification's parser. Every use but a stream copy decodes a cue into ASS and encodes it back.

| Rule                                                                                                                                                                                                                                                                                                           | Source                        |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Blocks are read between blank lines; one starting `WEBVTT`, `STYLE`, `REGION` or `NOTE` is skipped (its text unread) -- a cue whose identifier starts so, too                                                                                                                                                  | `webvtt_read_header`          |
| A cue: an identifier line when the first line holds no `-->`; the timing line, `%u:%u:%u.%u` or `%u:%u.%u` -- the fraction an integer of **milliseconds**, any width; the rest of the line the settings, unread                                                                                                | `read_ts`                     |
| A timing line it cannot read **ends the reading**: that cue and every later one lost                                                                                                                                                                                                                           | `webvtt_read_header`          |
| The identifier and the settings ride the packet as side data: a stream copy writes them back, a decoding drops them                                                                                                                                                                                            | `SET_SIDE_DATA`               |
| After reading: sorted by start; a negative duration becomes the gap to the next start; duplicates dropped but one (as SubRip's)                                                                                                                                                                                | `ff_subtitles_queue_finalize` |
| The decoder: `<b>`, `<i>`, `<u>` -- any tag whose name **starts** with `b`, `i` or `u` -- become `\b`, `\i`, `\u`; every other tag is dropped, its text kept; six references decoded (`&amp; &lt; &gt; &lrm; &rlm;`, `&nbsp;` as `\h`), others kept as written; `{` and `\` escaped for ASS; a line break `\N` | `webvtt_event_to_ass`         |
| The encoder: `\b`, `\i`, `\u` (a style's too) as `<b>`, `<i>`, `<u>`; every other override dropped; the text written as it is -- no `&` or `<` escaped                                                                                                                                                         | `webvtt_encode_frame`         |
| The muxer: `WEBVTT`, then each cue after a blank line: its identifier, `[hh:]mm:ss.ttt --> ...` (hours only when non-zero), its settings, its text. LF, no BOM                                                                                                                                                 | `webvtt_write_packet`         |

*Measured* -- the demuxer (start and duration in ms, the text):

| File                                                    | ffmpeg's reading                                                                  |
| ------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `00:01.000 --> 00:02.500`, `Hello`, `world`             | 1000, 1500, `Hello\nworld`                                                        |
| `01:00:01.000`; `75:00.000` (no hours)                  | 3601000; 4500000: minutes past 59 taken                                           |
| `00:01.5 --> 00:02.25`                                  | 1005, 1020: the digits are milliseconds                                           |
| `00:01.5000 --> 00:02.0000`                             | 6000, -4000                                                                       |
| a cue timed `00:01,000` (comma) mid-file                | the cues before it read; it and every later one lost                              |
| an identifier line holding `-->` (`a --> b`)            | the reading ends there: no cue                                                    |
| a cue whose identifier is `NOTE` or `WEBVTT-1`          | skipped whole, the next one read (Chromium reads a cue named `NOTE`)              |
| `intro-1`; settings `align:start line:0 position:10%`   | dropped by decoding; a stream copy writes both back                               |
| `NOTE`, `STYLE`, `REGION` blocks; a `NOTE` between cues | skipped                                                                           |
| `WEBVTT - a title`, `Kind: captions`                    | read; the header's text not kept (a stream copy writes `WEBVTT` alone)            |
| no blank line after `WEBVTT`                            | no cue: the block taken for the header (Chromium reads the cue)                   |
| a UTF-8 BOM; CRLF                                       | read; a CRLF's CR kept in the text, dropped by the decoder                        |
| a NUL in a cue's text                                   | the text cut there, every later cue lost (Chromium: U+FFFD)                       |
| CR only                                                 | the first cue lost, the rest read (Chromium reads every cue)                      |
| CR CR LF                                                | no cue (Chromium: each cue of no text)                                            |
| a first block neither a cue nor `WEBVTT`, `NOTE`...     | no cue: read as a cue, its timing fails, the reading ends                         |
| no blank line between two cues                          | one cue: the second's timing line and text its text (Chromium ends the cue there) |
| a timing line, no text                                  | a cue of empty text, which the decoder drops                                      |
| `00:01.000 --> 00:01.000`                               | 1000, 0: kept                                                                     |
| end before start (`00:03 --> 00:01`)                    | 3000, 2000: the gap to the next start (Chromium keeps 3 -> 1)                     |
| cues out of order; overlapping; two identical           | sorted; overlaps kept; one                                                        |
| `-->` without spaces, or with tabs                      | read                                                                              |
| an empty line in a cue's text                           | the cue ends; every later cue lost (Chromium: the text after it)                  |
| a line of spaces; a text line holding `-->`             | text, both (Chromium: the cue ends at the `-->`)                                  |
| no `WEBVTT`, a `.vtt` name                              | read, a low score (Chromium: refused)                                             |
| `webvtt` lower-cased                                    | no cue: the block taken for a cue, its timing fails                               |
| a byte not UTF-8 (`caf\xe9`)                            | read; the decoder drops that cue: "Invalid UTF-8"                                 |
| UTF-16LE with its BOM                                   | refused: "Invalid data found" (Chromium reads it)                                 |

*Measured* -- the decoder, a cue's text into an ASS event's:

| Cue text                                                     | ASS                                                             |
| ------------------------------------------------------------ | --------------------------------------------------------------- |
| `<b>b</b> <i>i</i> <u>u</u>`; `<b.loud>b</b>`                | `{\b1}b{\b0} {\i1}i{\i0} {\u1}u{\u0}`; `{\b1}b{\b0}`            |
| `<bogus>x</bogus> <image>y</image> <underline>z</underline>` | `{\b1}x{\b0} {\i1}y{\i0} {\u1}z{\u0}`: by first letter          |
| `<c.yellow>c</c> <v Bob>v</v> <lang en>l</lang>`             | `c v l`: classes, voices (speakers), languages lost             |
| `<ruby>kanji<rt>reading</rt></ruby>`                         | `kanjireading`                                                  |
| `one <00:00:01.500>two <00:00:01.800>three`                  | `one two three`: the word times lost                            |
| `&amp; &lt; &gt; &lrm;&rlm; &nbsp;`                          | `& < >`, U+200E U+200F, `\h`                                    |
| `&copy; &#38; &#x26; &bogus;`                                | kept as written                                                 |
| `a < b and c > d`                                            | `a  d`: `< b and c >` read as a tag                             |
| `before <b ends` (no `>`)                                    | `before `: the rest lost                                        |
| `{\an8}not an override {x}`; `one\Ntwo \h a\nb\tc`           | `\{{}\` + U+2060 `an8}...`; each `\` + U+2060: shown as written |
| two lines; leading and trailing spaces                       | `one\Ntwo`; kept                                                |

The decoder's script: ffmpeg's default -- `PlayResX: 384`, `PlayResY: 288`, one `Default`
style (Arial 16, white, bottom centre, margins 10), as SubRip's.

*Measured* -- the encoder and muxer, an ASS event into WebVTT:

| ASS                                                         | WebVTT                                                              |
| ----------------------------------------------------------- | ------------------------------------------------------------------- |
| `{\b1}b{\b0} {\i1}i{\i0} {\u1}u{\u0} {\s1}s{\s0}`           | `<b>b</b> <i>i</i> <u>u</u> s`: strike-through dropped              |
| `{\b1}bold to the end`                                      | `<b>bold to the end</b>`: closed                                    |
| colour, font, size; `\an8`, `\pos`, `\move`; `\k`           | dropped, the text kept: no class, setting or timestamp written      |
| `hard\Nbreak soft\nbreak hard\hspace`                       | line breaks for `\N` and `\n`; `\h` written as text                 |
| `a <b> c & d < e`                                           | as is: invalid WebVTT -- read back by the decoder, `a {\b1} c & d ` |
| `{\b1}bold{\r}plain`                                        | `<b>bold</b>plain`                                                  |
| an empty event                                              | a cue of empty text                                                 |
| a style bold, italic, underline, strike, red, Serif 24, top | `<b><i><u>styled</u></i></b>`: the rest dropped                     |
| `0:00:01.23`; `1:00:00.00`; `100:00:00.00`                  | `00:01.230`; `01:00:00.000`; `100:00:00.000`                        |
| overlapping events                                          | overlapping cues                                                    |

## ffman's reading

subverter's cues through ffman's `ingest` -- the chunks its burn draws and `--add-subs` writes:
sorted, cleaned of their tags, their references decoded, each cut at the next start. *Measured*
(`../scripts/measure_ffmpeg.py`, with its PYTHON):

| File                                                                       | ffman burns                                                                                                               |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| no `WEBVTT`; `webvtt` lower-cased; UTF-16 with its BOM                     | refused: "not a WebVTT file: in.vtt (its first line is not WEBVTT)"                                                       |
| no blank line after `WEBVTT`; `-->` without spaces, or with tabs           | read                                                                                                                      |
| `00:01.5`; `00:01.5000`; `00:01,000`; `75:00.000`                          | its cue dropped, noted: "1 cues dropped: a line holding --> that is no WebVTT timing line (W3C), the first ... on line N" |
| `one`, an empty line, `two`                                                | `one`; `two` dropped, noted: "1 text blocks dropped: after an empty line, in no cue (W3C), the first two on line N"       |
| `one`, a line of spaces, `two`                                             | `one two`                                                                                                                 |
| `one`, `Note: 1 --> 2`, `two`                                              | `one`, noted: the cue ends at the line                                                                                    |
| an identifier holding `-->` (`a --> b`)                                    | that line dropped, noted; the cue after it read                                                                           |
| no blank line between two cues                                             | two cues                                                                                                                  |
| `NOTE` or `WEBVTT-1` as a cue's identifier                                 | the cue read                                                                                                              |
| end before start; zero duration; a cue without text                        | dropped                                                                                                                   |
| out of order; two identical; overlapping                                   | sorted; one; each cut at the next start                                                                                   |
| `<b>b</b> <b.loud>`, `<bogus>x</bogus>`, `<c.yellow>`, `<v Bob>`, `<lang>` | the tags removed, their text kept                                                                                         |
| `<ruby>kanji<rt>reading</rt></ruby>`; timestamp tags                       | `kanjireading`; removed                                                                                                   |
| `&amp; &lt; &gt; &lrm;&rlm; &nbsp;`; `&copy; &#38; &#x26; &bogus;`         | decoded, HTML's: `& < >`, U+200E U+200F, U+00A0; `© & & &bogus;`                                                          |
| `a < b and c > d`; `before <b ends`                                        | `a d`; `before <b ends`: a `<` without a `>` after it kept                                                                |
| `{\an8}not an override {x}`; `one\Ntwo \h a\nb\tc`                         | as written                                                                                                                |
| two lines; CRLF; leading and trailing spaces                               | joined by a space; read; trimmed                                                                                          |
| a byte not UTF-8 (`caf\xe9`)                                               | refused: "not UTF-8: in.vtt (line 4)"                                                                                     |
| a NUL in a cue's text                                                      | U+FFFD there, noted                                                                                                       |
| CR only; CR CR LF                                                          | read; each cue of no text, so "no timed text found"                                                                       |
| an identifier; settings; `NOTE`, `STYLE`, `REGION`                         | ignored: ffman places its own                                                                                             |

## What WebVTT holds

| Property    | WebVTT                                                                                                                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Times       | start and end, milliseconds (`.ttt`, exactly three digits)                                                                                                                                       |
| Text        | lines (no blank line, no `-->`), character references for `<` `&` and anything else                                                                                                              |
| Styling     | `b i u`; classes, styled by `STYLE` blocks of CSS (`::cue`, `::cue-region`) or by the default colour classes -- `white lime cyan red yellow magenta blue black` and their `bg_` background forms |
| Position    | per cue: `line`, `position`, `size`, `align`, `vertical`; regions (`REGION`)                                                                                                                     |
| Word timing | timestamp tags inside the text, each a word's (or syllable's) start; no word end but the next's start (drawn by Chromium: `subtitle-mappings`' `words.md`)                                       |
| Speakers    | `<v name>` spans                                                                                                                                                                                 |
| Other       | an identifier per cue; `NOTE` comments; the header line's free text; `lang` spans and ruby                                                                                                       |
