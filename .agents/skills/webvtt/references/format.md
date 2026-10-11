# WebVTT: the format by its specification, measured in a browser

Researched from the W3C's "WebVTT: The Web Video Text Tracks Format", the Candidate
Recommendation Draft of 2026-05-20 (`https://www.w3.org/TR/2026/CRD-webvtt1-20260520/`), from its
source: the editor's draft, `w3c/webvtt` `index.bs` at commit `0648025` of the same day. Measured by
`../scripts/measure.py` in Chromium 141.0.7390.37 (Playwright's): its `<track>` parser
implements the specification's algorithm, its `VTTCue` the data model -- but not regions,
`lineAlign` or `positionAlign` (absent from its `VTTCue`), so those rows are the
specification's alone. ffmpeg's `webvtt` reader and writer are the next research box's; the
writers in use (whisper.cpp, OpenAI whisper, WhisperX) the `whisper-transcripts` skill's.

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
| tabs, runs of spaces, trailing spaces      | kept                                             |

A text holding `<` or `&` must write them `&lt;` and `&amp;`; `-->` cannot be held at all.

## What WebVTT holds

| Property    | WebVTT                                                                                                                                                                                           |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Times       | start and end, milliseconds (`.ttt`, exactly three digits)                                                                                                                                       |
| Text        | lines (no blank line, no `-->`), character references for `<` `&` and anything else                                                                                                              |
| Styling     | `b i u`; classes, styled by `STYLE` blocks of CSS (`::cue`, `::cue-region`) or by the default colour classes -- `white lime cyan red yellow magenta blue black` and their `bg_` background forms |
| Position    | per cue: `line`, `position`, `size`, `align`, `vertical`; regions (`REGION`)                                                                                                                     |
| Word timing | timestamp tags inside the text, each a word's (or syllable's) start; no word end but the next's start                                                                                            |
| Speakers    | `<v name>` spans                                                                                                                                                                                 |
| Other       | an identifier per cue; `NOTE` comments; the header line's free text; `lang` spans and ruby                                                                                                       |
