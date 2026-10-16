# ffman, phase 6: stage B -- exact, idiomatic, researched

Phase 5 closed stage A: the Python ffman equals the bash one on every
invocation of its suites, then replaced it ([`ffman-python.md`](ffman-python.md)).
Stage A had to copy bash -- its arithmetic, its parsers' quirks, its order, its
shape. Phase 6 removes what was copied for equality alone, and improves on bash
where the improvement can be proven. This plan replaces the main plan's
phase-6 list (§6 carries its items). Reviewed once (findings applied: §8).

## 1. Principles

- **Every change to behaviour follows G4** (the main plan, §8): a
  `CHANGELOG.md` entry -- since 6.7.9 a `feat` or `fix` commit stating it,
  git-cliff writing the changelog at a release -- a test that fails on the old
  behaviour and passes on the new, a `07-tools.md` row. A change of form only (a move, a type, a
  split) changes no output, which the outcome report shows (6.0).
- **Proof without an oracle.** The bash comparison is gone; a change is proven
  against its stated rule, as phase 3's corrections were: the rule written
  down with its source; the old answer shown to break it, on a measured set;
  the new one never breaking it. Where an output changes, the **outcome
  report** says how much: the inputs that change, the size of each change (px,
  ms, a filter's parameter), and why the new value is the right one.
- **Pinned tests change with the behaviour.** Tests pin stage A's exact
  values: 5 files exact ASS (`\pos(960,981)`, `\fscx118`, event times), 9
  exact filter parameters, 3 import `fmt.py` themselves. A change updates
  the tests that pin what it changes, in the same commit: the updated test is
  G4's failing-then-passing test. A pinned test that changes when its box did
  not mean to change it is a regression.
- **Decide before doing.** Every refusal comes from the options and the probe,
  before any work: bash's order kept work ahead of refusals (§2, F6).
- **The contract moves with the code.** `ffman-spec.md` is the command line's
  contract (grammar, messages); `CHANGELOG.md` gains a "Stage B" section
  (closed at 6.7.9 in `docs/ffman-from-bash.md`; since, the commit says it); a
  box that changes either changes it in the same commit.
- **Effects are researched before they are changed** (§4).
- **One box at a time**, reviewed with the efficient-reason and
  efficient-code-review skills; nothing assumed, everything shown.

## 2. Findings (assessed at 6defa91; reviewed at a48dcb7)

### F1. awk's arithmetic, mirrored: 62 uses in 9 modules

`fmt.py` reproduces the bash ffman's number *text*: `calc` (a float printed
`%.6g`, six significant digits, each step reading the last one's text),
`round_int` (awk's `int(x + 0.5)` on that already rounded text: two roundings),
`awk_number` (a field's leading numeric prefix, else 0), `awk_print`,
`sort_n_key` (GNU `sort -n`'s key). Uses (names imported from `fmt`, counted
in each module's syntax tree): `effects/filters.py` 18, `subs/ass.py` 15,
`subs/ingest.py` 15, `subs/layout.py` 7, `camcorder.py` 2, `mosh.py` 2,
`geometry.py` 1 (`awk_print`, a message's text; its sizes are exact since
phase 3, with its own `round_int` on `Fraction`s), `jobs/convert_options.py`
1, `jobs/convert.py` 1. The tests import it too (`test_ingest.py`,
`suite/test_subtitles.py`, `test_geometry.py`).

| Area              | Where                                     | Now                                                                                                                                                                                                                                                         | The outcome at stake                                          |
| ----------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Placement         | `subs/ass.py`                             | canvas width, margin (px), outline and shadow through `calc`; `\pos` **truncated**: x is `int(px / 2)` (853 for a 1707-wide canvas: the centre is 853.5; libass renders a fractional `\pos` -- shown: half a pixel moved 257 of 382 lit pixels), y `int(y)` | text up to 1 px off; style sizes at 6 digits                  |
| Bar               | `subs/layout.py`                          | the bar's share and centre as `calc` text, compared as text-rounded floats; the 7 sample times as text                                                                                                                                                      | a bar at the threshold found or missed by rounding            |
| Sizes             | `camcorder.py`, `effects/filters.py` (CA) | the stamp's width, CA's scaled sizes: rounded twice                                                                                                                                                                                                         | ±1 px                                                         |
| Filter parameters | `effects/filters.py`                      | blur's SAR and sigma, CA's scale `k = px / w`, halation's sigma, VHS's four sigmas (`h / 906`, `/1811`, `/113.2`, `/452.8`), its drop, band and jump: text at 6 digits                                                                                      | a parameter at 6 significant digits; an integer rounded twice |
| Timing            | `subs/ingest.py`, `jobs/convert.py`       | times read from exact decimal text **through a float** (`seconds * 1000 + 0.5`); a gap's shares rounded on floats; the SRT clip **truncated** (bash's `printf "%d"`)                                                                                        | a millisecond at an exact half                                |
| Highlight         | `subs/ass.py`                             | the pop's peak `100 + int(45 / chars)`, truncated, where the rule is `1 + 0.45/chars` and `\fscx` takes decimals                                                                                                                                            | 7 letters peak at 106%, not 106.43%                           |

A gap's words are apportioned correctly: each start is the cumulative share,
rounded, so the spans sum to the gap by construction. ASS's 10 ms resolution
(`_cs10`, and the 10 ms base each untimed word gets) is the format's: kept.

### F2. Compensations: work done because the numbers were inexact

Read, not searched: `subs/ass.py`, `subs/layout.py`, `subs/ingest.py`'s
normalisers and placement, every commented literal and every floor in
`effects/filters.py`, `resize.py`, `gif.py`, `light.py`, `camcorder.py`,
`geometry.py`, `plan.py`, `encode.py`.

- **Datamosh's half-frame tolerance** (`mosh.py`): each heal time is `calc`
  text (a cut's time + seconds), kept by `noise=drop` within half a frame of
  `pts*tb`, a float comparison; the forced keyframes are times as text. Exact:
  each heal's frame index, `eq(n, N)`; keyframes forced by frame number.
- **CRT's gain times 1.01** (`effects/filters.py`, `_crt`): undocumented --
  no word in the code or `07-tools.md`. A margin against clipping, a
  compensation, or a choice: the CRT research decides.
- Rules, not compensations: the 400 ms hold that keeps a word up across a
  short gap; the 10 ms base; `height - 1 - lowest` (the rows below the
  picture); window clamps; the minimum sizes (`max(..., 1)`, `2`); x264's
  and Opus's limits; the bar blur's clamp.

### F3. Bash's way, written in Python

- **Ingest emulates jq and gawk** (`subs/ingest.py`, 604 lines): jq's `@tsv`
  escapes and `tonumber` grammar (`_jq_tsv`, `_jq_number`, `_tonumber`,
  `_jq_order`, `_jq_ge`, `_jq_lt`, `_jq_ms`), gawk's FPAT CSV split
  (`_csv_fields`), awk's records ("awk sees no record after the last
  newline"), awk's `split` (`ass._fields`). Python's `json` and `csv` read
  these formats with typed values.
- **A transcript's backslash is burned doubled** -- jq's `@tsv` escaped it and
  nothing undid it.
- **Numbers carried as text**: `Style.size`/`margin`/`bar_y`, `Bar.y`,
  `ConvertOptions.font_size` and `margin_bottom` ("a fraction as text, as the
  bash ffman carried it"), `Mosh.rate`, `plan`'s `fps` ("as bash printed it,
  %.6f"), every `probe` rate, duration and time base -- re-parsed where used.
  ffprobe's JSON gives strings: `probe.py` is where they become `Fraction`s.
- **Reading ffmpeg's log**: `layout.bar_height` finds the frame's height by
  scraping ffmpeg's human-readable log ("Output #0", a `Stream #0:0` line, a
  `WxH`) -- a height ffman's own plan already knows; cropdetect's rows can
  come as structured metadata -- shown: `metadata=print` gives `lavfi.cropdetect.y1`, `y2`, `h` -- not log text.
- **Bash's order**: `jobs/convert.py` runs "in the order its bash command ran"
  -- F6.
- **Shaped by bash's control flow**: `_place` (76 lines, four complexity
  rules suppressed: "bash's place(), rule for rule").
- **Grammar and messages** (in scope): the parser follows bash's grammar,
  including an optional value taken unless the next token starts with `-` and
  a letter ("`-1` is a value, and a bad one"); `checks.py` keeps bash's
  `is_uint`/`is_num` (no sign, no leading zero, no exponent); messages keep
  bash's text. Changed through the spec.
- **The camcorder's text** emulates gawk's `strftime` in the C locale: English
  names, fixed -- a choice to state, not an accident to copy.
- **Provenance as justification**: 182 lines in 24 modules cite bash ("as
  bash", "bash's ...") as the reason for code -- 44 comments, 138 docstrings,
  none in code (parsed). Stage B states each rule
  and its source instead; bash stays in the history (`CHANGELOG.md`, since
  6.7.9 `docs/ffman-from-bash.md`; `07-tools.md`).

### F4. Architecture

- `subs/ingest.py` (604): readers for seven formats (SRT, VTT, LRC, CSV, TSV,
  whisper-cli's and WhisperX's JSON) in six functions, jq's and gawk's
  emulations, two normalisers, the placement.
- `effects/filters.py` (432): every effect's filters in one module.
- `jobs/convert.py` (479): four flows, the passes and the render.
- `plan.py` (461): streams, outputs and their refusals, YouTube's video and
  sound.
- `subs/ass.py` wraps by an em estimate, not the font's metrics; `_plain`
  re-estimates libass's own wrap to count lines over the frame.
- Imports against the layers (today's graph, parsed): `plan` and `resize`
  import `jobs.convert_options` -- the planners' input lives in a job;
  `resize` (graph) imports `geometry` (plan) for the sizes it reads
  (`Displayed`, `Target`); `run` imports `options` for `PROG`, the program's
  name in messages.

### F5. DRY

- Rationals parsed in four modules, two notations: ffprobe's `N:D` SAR
  (`geometry._SAR`), and `N/D` (`effects/filters.py` the SAR, `mosh.py` its
  `_RATE` and two splits, `plan.fps_of`). Once, in `probe.py`.
- `f"file:{...}"` ten times (nine lines) in three modules: one helper.
- Constants in `07-tools.md` and inline in the code (VHS's 906 and 1811 as
  literals in a tuple): named constants with their source and row, as the
  main plan asks (§4, "constants carry provenance") -- per effect, §4.

### F6. Work before refusals (demonstrated)

`burn` decides an existing output, the output's kind and the loop checks
after the bar detection, the camcorder, the subtitles and -- for the kind --
the passes. `convert -i v.mp4 --burn-subs t.srt --vfx datamosh -o out.png`
ran 1 ffprobe and 9 ffmpeg (7 cropdetect samples, a scene detection over the
whole video, a full datamosh render) before "overlay output must be a video":
minutes of work on a long video, for an answer the command line held.
`attach` refuses an existing output after reading the transcript (cheap).
`resize` and `youtube` check first.

### F7. An option ignored where it is elsewhere refused (found by the outcome report)

`-b` and `--resize-mode` without a size are refused when burning subtitles
(`plan.select_flow`) and silently ignored when only effects run: `-b --vfx
invert` gives `--vfx invert`'s commands exactly (case `vfx/bblur-ignored`).
Bash's; one answer for every flow belongs to 6.10.

### F8. What each container holds (ffmpeg n8.1.2: source, measured)

A convert across container families drops every subtitle and attachment
(`plan/streams.py` `tracks`), and a container change alone is "nothing to do"
(`plan/flows.py`): `-i a.webm -o a.mp4` is refused, though copying works (VP9
and Opus into MP4: 1.46 MB of 1.45, nothing re-encoded).

| Muxer (extensions)          | Subtitles held as they are                        | Attachments      | Custom tags              | Cover art                |
| --------------------------- | ------------------------------------------------- | ---------------- | ------------------------ | ------------------------ |
| mp4 (`.mp4`)                | mov_text, dvd_subtitle, ttml (`movenc.c`)         | job fails        | with `use_metadata_tags` | kept                     |
| mov (`.mov`)                | mov_text, eia_608 (`isom.c`)                      | job fails        | with `use_metadata_tags` | dropped silently         |
| ipod (`.m4v` `.m4a` `.m4b`) | mov_text (`movenc.c`)                             | job fails        | with `use_metadata_tags` | kept                     |
| matroska (`.mkv` `.mka`)    | SRT, ASS, WebVTT, VobSub, DVB, PGS (`matroska.c`) | kept             | kept                     | written as a video track |
| webm (`.webm`)              | WebVTT (`matroskaenc.c`)                          | dropped silently | kept                     | job fails                |

Text subtitles convert into one another directly (decoders and encoders for
SRT, ASS, WebVTT, mov_text): WebVTT into MP4 needs no SRT step. Converting
loses what the target cannot say -- ASS's styles into mov_text or WebVTT,
WebVTT's cue settings into mov_text (kept when copied into Matroska or WebM).
Image subtitles never become text (no OCR). Chapters and stream languages
cross into all five; a cover into Matroska kept as a cover takes extracting
and attaching (`matroskaenc.c` has no attached-picture handling).

### F9. Metadata files (ffmpeg n8.1.2: source, measured)

ffmetadata is ffmpeg's text form of a file's tags and chapters (a demuxer and
a muxer), not a stream. Ogg (`.ogg` `.oga` `.opus` `.ogv` `.spx`) and FLAC
store tags as Vorbis comments (`oggenc.c`, `flacenc.c`); Matroska, only inside
a FLAC track's header. Chapters as Vorbis comments (`CHAPTERxxx`) are written
for Opus alone: FLAC's muxer passes none, Ogg's only to Opus headers -- into
Ogg Vorbis or FLAC they are lost (measured: 2 of 2 back from `.opus`, 0 from
`.ogg` and `.flac`). Read back, every Ogg stream's chapter comments are chapters,
and FLAC's embedded cue sheet is chapters too (`flacdec.c`). ffmpeg reads no
`.cue` file. So a cue sheet, an ffmetadata or a Vorbis text crosses containers
only as an attachment (Matroska) -- or converted, which nothing does yet.
Extensions: ffmpeg registers `.ffmeta` for ffmetadata (`ffmetaenc.c`; its
reader knows a file by its first line, `;FFMETADATA`, whatever its name);
Vorbis comments as text have none (`vorbiscomment(1)`'s example: `file.txt`;
`metaflac` takes any name); a cue sheet is `.cue`.

`metaflac` (FLAC's own metadata editor; 1.5.0, nixpkgs' at this pin, built from
its release and run): its tag files are `NAME=value` lines without escapes -- a
two-line value exported is refused by its own import (atomically). Its cue
import fills FLAC's `CUESHEET` block, which keeps positions only: ffmpeg reads
it as chapters, untitled (`TITLE`, `PERFORMER` dropped; 44.1 kHz and 48 kHz
alike) -- or titled with the track's ISRC, when it has one (6.6.1, cue). `CHAPTERxxx`/`CHAPTERxxxNAME` comments in FLAC ffmpeg reads as titled
chapters -- so ffmpeg's `-metadata` can carry them where its muxer writes none.
A whole cue sheet kept as a `CUESHEET` comment (`--set-tag-from-file`) is
text only to ffmpeg; mpv reads it as chapters (6.6.1, cue: source).
What crosses between the three, and what does not:
the [`metadata-mappings`](../.agents/skills/metadata-mappings/SKILL.md) skill. Pictures it imports are covers to ffmpeg.

## 3. Target architecture

```
src/ffman/
  cli.py  errors.py               errors.py: the one error, PROG
  options.py  values.py          the grammar; value checks (was checks.py)
  media/                          the only processes: ffprobe, ffmpeg, the tools
    probe.py                      JSON -> typed Media (Fractions)
    run.py                        Runner, signals, workdir
    paths.py                      file: URLs; output paths (was output.py)
  plan/                           pure decisions, every refusal (was plan.py)
    flows.py  outputs.py  streams.py  youtube.py  geometry.py  encode.py
    request.py                    ConvertOptions: what a job asks, checked
  graph/                          filtergraphs as data (__init__.py: the model)
    resize.py  light.py  gif.py  sizes.py (Displayed, Target)
  effects/                        __init__.py (the registry); one module an effect
    spec.py  frame.py  stages.py  the definition's types; the frame; the stages
    blur.py  pixelate.py  invert.py  chromatic_aberration.py  halation.py
    datamosh.py  camcorder.py  vhs.py  dither.py  crt.py
  subs/
    transcript.py                 Chunk, Word, Transcript, Row, Reading: the types
    ingest.py                     ingest(): the readers, then the normalisers
    readers/                      __init__.py (by format)  subrip.py (SRT, VTT)  lrc.py
                                  table.py  whisper.py
    normalize.py                  cues, words, their placement
    layout.py  ass.py  srt.py     placement; the writers
  meta/                           metadata files: ffmetadata, Vorbis comments, cue sheets
    model.py                      the one model: tags as written, exact times, a cue's disc
    ffmetadata.py                 ffmpeg's text form: read as ffmpeg reads it, written exactly
    vorbis.py                     Vorbis comments as text (vorbiscomment -e's form), chapters too
    cue.py                        cue sheets: read as the readers in use agree, written as all accept
    convert.py                    between the three: the mappings' rows, each loss noted
    files.py                      a file's format: by its extension, first line or --preset
    fields.py                     one field table: ffmetadata's key, Vorbis' name, a cue's command
    edit.py                       meta's edits: declarative, in the output's words
    chapters.py                   meta's chapter edits; in a cue, its tracks
    time.py                       meta's one time syntax: exact, never MM:SS:FF
  jobs/convert/                   __init__.py: the package's docstring alone
    dispatch.py  options.py       which flow; validate (the grammar's answer -> ConvertOptions)
    resize.py  burn.py  attach.py  youtube.py
    passes.py  render.py  output.py  the effects' passes; the render; writing, encoders
    metadata.py                   a metadata file, or a media file's, written as one (spec 3.9)
  jobs/meta/                      ffman meta (spec 8): options.py, run.py; io.py, convert's too
```

Dependencies point down: `cli` → `jobs` → `plan`, `effects`, `subs`, `meta` →
`graph` → `media`'s types, `values`, `errors`; the module graph has no cycle.
Only `media` runs processes, driven by `jobs`; `plan`, `graph`, `effects`,
`subs` and `meta` are pure -- no file, no OS, the architecture test holds it (the readers' file reads its listed exception, 6.3's to close). `ConvertOptions` -- the planners' input -- is `plan/request.py`,
which `jobs` validates from the grammar's answer; resize's own terms (its modes,
the bar blur) are `graph/resize.py`'s, and `head` takes them, not the options;
`PROG` is `errors.py`'s. An
architecture test (an AST walk of the imports) fails on an import against the
direction or a cycle. The names are the target; each move's box confirms them
against the code it moves.

## 4. The effects: research first

Ten effects (`ffman effects`): `blur`, `pixelate`, `invert`,
`chromatic-aberration`, `halation`, `datamosh`, `camcorder`, `vhs`, `dither`,
`crt`. For each, in turn, before any change to it:

1. **Research** what the effect is physically or digitally (VHS: the format's
   bandwidth, noise, head switching, chroma; CRT: the beam, the mask, the
   phosphors; halation: film's layers; ...), its specifications, and the best
   algorithm for its defaults -- from primary sources (standards, papers,
   manufacturers' data, ffmpeg's filter sources), each claim with its source.
2. **A skill**, `.agents/skills/vfx-<effect>/SKILL.md`: what the effect is,
   its parameters and their physical meaning, the default and why, how ffman
   builds it, how to measure it -- every figure sourced, every measurement a
   script beside it (`scripts/`), run. Its frontmatter passes skill-creator's
   `quick_validate.py` (only `name`, `description` and the allowed keys; the
   name kebab-case, at most 64 characters; the description at most 1024, no
   angle brackets); `package_skill.py` makes `vfx-<effect>.skill`, presented
   to the owner to save in Claude.
3. **Expand this plan**: the research's findings become the effect's code
   boxes.
4. **Then change the code**, under G4.

Already flagged, to fold into each effect's research:

| Effect                 | Flagged                                                                                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| all                    | resizing in gamma, not linear light (every resize, effects or none)                                                                                            |
| `blur`                 | its SAR and sigma through `calc` (F1)                                                                                                                          |
| `pixelate`             | ignores SAR (a review finding)                                                                                                                                 |
| `chromatic-aberration` | its scale `k = px / w` and sizes through `calc`; `px`'s auto `(shorter + 67) // 135`; prints `setsar=1` resized, `1/1` not (bash's text: `Frame.squared`, 6.0) |
| `halation`             | ignores SAR; its sigma through `calc`                                                                                                                          |
| `datamosh`             | the half-frame tolerance and time-text keyframes (F2)                                                                                                          |
| `camcorder`            | its width rounded twice; gawk's `strftime` (F3)                                                                                                                |
| `vhs`                  | four sigmas and three sizes through `calc`; constants inline, against their source                                                                             |
| `dither`               | auto 16 colours: the reason, against the source                                                                                                                |
| `crt`                  | decodes images with 2.4, not sRGB (a review finding); the gain's undocumented 1.01 (F2)                                                                        |

## 5. Skills

Skills live in `.agents/skills/<skill-name>/`;
[`.agents/skills/README.md`](../.agents/skills/README.md) states their format, sources
and packaging, and `AGENTS.md` routes there. Every skill is validated and
packaged as §4 says, and its `.skill` presented to the owner.

## 6. Carried from the main plan

- **D2, the default encode** -- a delivery default, `--lossless` explicit; it
  applies to burned subtitles too.
- **A transcript's backslash burned doubled** (F3).
- **Exact numbers**: `fmt.py`'s scaffolding replaced with exact arithmetic
  (F1) -- here by area.
- **Stage 4 in `convert`**: GIF, `--loop`/`--loop-reverse` from any input; any
  compatible output format.
- **The review findings**: resizing in linear light; SAR for pixelate and
  halation; CRT through `light.py` (§4).
- **`--attachment`, `--cover`, `--metadata`, `--title`.**
- **`-v/--verbose`**, held back in phase 4 until it has a meaning.
- *Done already*: fuzz.py's invariants as a Hypothesis property -- ported in
  phase 4 (S158, S159: `tools/ffman/tests/test_transcript_fuzz.py`).

## 7. Checklist

Each box: plan its change, show its outcome (or show none), review, commit.

**6.0 Foundations** (form only)

- [x] The outcome report, first: `python -m tests.outcome` (`tools/ffman/tests/outcome/`; `tools/ffman/AGENTS.md`, "The outcome report") runs a fixed corpus under `--dry-run` -- which runs ffman's read-only work too (the probe, bar detection, scene cuts), so one mode suffices -- and records each case's exit status, commands, notes and refusals, and work files (ASS, SRT); `compare REV` diffs a revision against this tree: identical, same graph (filtergraphs ffmpeg reads the same, by `tools/ffman/tests/support/filtergraph.py`), or changed. Every later box shows its diff (empty for form only). *Done: 341 cases (every flow, effect, transcript, hostile transcript and refusal; environments through `Case.env`), reaching 96% of `src` -- the rest real writes, signals, failing tools, invariants and the clock, each named in AGENTS.md. Shown: two reports identical (341); eight one-line mutations each caught on exactly its cases (a filter's parameter 4, the pop 6, the SRT 22, a note 1, a refusal 1, the status 118, an x264 option 167, the camcorder 3); a rename 341 identical; an escaping change 81 same graph, 0 changed; `compare HEAD` 341 identical; the tool's 21 tests catch five mutations of it. Found on the way and fixed: ten cases with no job (coverage showed them refused before their path); an installed ffman answering for the commit (cases run `python -S`: 9.9.9 from the commit's pyproject, not 2.0.0.dev0); HDR and BT.2020 sources untagged (`h264_metadata`, read back by ffprobe); escaped paths leaking (named however escaped); a refused graph crashing the diff; a src without its pyproject recording 341 crashes (refused); a revision read as an option (resolved first). And F7.*
- [x] Skills' home: `.agents/skills-map-project/` → `.agents/skills/map-project/`, every reference updated; `AGENTS.md` routes `.agents/skills/`; the doc map places it. *Done: moved by `git mv` (five renames, history kept); `.agents/skills/README.md` states the convention (skill-creator's format, its validator and packager, sources) and `AGENTS.md` routes to it; the doc map excludes `map-project/` (vendored -- shown: upstream through the repository's `dprint.json` is byte for byte this copy) and places `.agents/skills/` (the README, concept band); the Nix map's only changes the renamed paths in computed fields. Every old path gone but this plan's. Validated (skill-creator's `quick_validate.py`) before and after the move; packaged as `map-project.skill`. The files this box and the last wrote pass dprint (the plan and tools/ffman/AGENTS.md formatted, content shown unchanged).*
- [x] Typed numbers at the boundary: `probe.py` parses rates, time bases, durations and SARs into `Fraction`s; the four parsers (F5) use them; output text unchanged -- in the effect modules too, form only, no flagged item touched (§4). *Done: `probe.py` types ffprobe's numbers once, in the forms its source prints (fftools/textformat/avtextformat.c, n8.1.2: ratios `%d%c%d`, times `%f`; an optional field is absent from JSON, never "N/A"): a `Rational` for a ratio -- exact and unreduced, `0/0` kept, since its users tell `0/0` from other ratios, which a `Fraction` cannot hold -- a `Fraction` for a duration, an `int` for the sample rate; the SAR a `Fraction` past geometry (ffprobe reduces it: av_guess_sample_aspect_ratio). Gone: geometry's `_SAR`, the blur's partition, mosh's `_RATE` and splits, `fps_of`'s text, encode's `_TIME_BASE`. Shown: each pinned text table passes unchanged through `Rational.parse` (every consumer's old answers, row for row); text outside `%d` reads None (boundary tests); zero kept apart from absent (`"0.000000"` was true, `Fraction(0)` is not); CA's `setsar=1` resized, `1/1` not, kept by `Frame.squared` (bash's text, flagged in §4). `compare HEAD`: 343 identical -- two cases added, CA after a resize, the one text no case compared (a branch within one line: invisible to coverage). Suite 818 at 100%, matrix 761; ruff, basedpyright, vulture. Caught on the way: a `NameError` at import (a class's annotation naming itself: `Self`).*
- [x] One `file:` helper (F5). *Done: `output.file_url` (where §3 puts file URLs, beside the output paths); all ten uses in three modules call it. Its reason, from source (libavformat/avio.c url_find_protocol, file.c; n8.1.2): a name's leading `[A-Za-z0-9+-.]` run before a `:` is a protocol, and the file protocol takes one `file:` off -- shown against the pin: ffprobe refuses `a:b.png` ("Protocol not found") and opens `file:a:b.png` (a test). Outputs need none: the paths ffman makes are absolute (Python 3.13's mkstemp and mkdtemp, shown for a relative `a:b`), and a real run into `a:b/x.mp4` writes. `compare HEAD` 343 identical; suite 820 at 100%. Seen, left for a behaviour box: the mosh render is read once with `file:` and once without (`jobs/convert.py`, absolute either way).*

**6.1 Architecture** (form only)

- [x] The architecture test (§3's direction, no cycles), passing on today's tree but for its listed exceptions (`plan` and `resize` → `jobs.convert_options`; `resize` → `geometry`; `run` → `options`), which the moves below close. *Done: `tools/ffman/tests/test_architecture.py` reads the import graph from the source's syntax trees (every import, wherever it stands; a name that is a submodule counts as that module; a relative import fails, the package having none) and holds four rules: every module has a layer (§3's, numbered 0-5 on today's names); the upward imports are EXCEPTIONS exactly -- a new one fails, and so does one a move closed but did not strike; no cycle (one is reported as itself); only the media layer imports `subprocess` (§3's "only media runs processes": `run`, and `probe` for a type). The exceptions are four, not three: `resize` (graph) imports `geometry` (plan), which the plan's review missed -- added here, to F4 and to the moves' box. Shown: each rule broken in a scratch copy fails its test (a module unplaced, an import upward, a cycle within a layer, `subprocess` in `gif`, an exception stale).*
- [x] `media/`, `plan/`, `graph/`, `values.py`: the moves (§3); `ConvertOptions` below the planners; the sizes `resize` reads (`Displayed`, `Target`) below the graph; `PROG` to `errors.py`. *Done: `git mv` for the moves (`checks` → `values`; `probe`, `run`, `output` → `media/`; `graph.py` → `graph/__init__.py`, `from ffman.graph import` unchanged; `resize`, `light`, `gif` → `graph/`; `geometry`, `encode` → `plan/`). `plan.py` split by syntax-tree node into `plan/flows.py`, `outputs.py`, `streams.py`, `youtube.py` -- every node and character placed, one call across them (`youtube` → `outputs.is_image`), no cycle. `Displayed` and `Target` → `graph/sizes.py`; `ConvertOptions` and its literal types → `plan/request.py` (the planners' layer: it holds effect requests; `validate` stays in `jobs`); resize's own terms (`ResizeMode`, `RESIZE_MODES`, `BBLUR_MAX`, `bblur_on`) → `graph/resize.py`, and `head` takes `mode` and `bblur`; `PROG` → `errors.py`. Imports rewritten by a codemod from the syntax trees, name by name, each name's home read from the new modules' own definitions; the two imports inside a test's script string, which no syntax tree shows, by hand, and every string searched; the one comment inside an import the codemod dropped (a suppression), found by comparing every import's comments with HEAD's, restored. The architecture test: every module placed, EXCEPTIONS empty. `compare HEAD` 343 identical; docs' module paths followed (07-tools.md's 20 rows, AGENTS.md's layout by layer, a run-book, two comments).*
- [x] `effects/`: one module an effect -- first, so each effect's research reads one module. *Done: each of the ten in `effects/<effect>.py` -- its definition (`EFFECT`: name, stage, parameters and their checks, once in the registry's tuple), its builder (`build`, once `filters.py`'s private one), its helpers and constants; `mosh.py` and `camcorder.py` moved in by `git mv` (`datamosh.py`, `camcorder.py`). Shared, so no cycle: `spec.py` (`Stage`, `Param`, `Effect`, `Request`, `between`, `asked`), `frame.py` (`Frame`), `stages.py` (the stage sets, `Effects`, `apply`, `chain`; `PRE`/`POST` keyed by each module's own `EFFECT.name`); `__init__.py` the registry, in bash's order. The dither's `paletteuse` step, inline in `chain`, its own `dither.use_palette`. A duplicate found and removed: `_curves`, identical in `resize` and the effects, one `graph.light.curves`. Composed from syntax-tree segments, not retyped; basedpyright caught what merging two modules into one made of the camcorder -- `datetime` the class where it had been the module (every `camcorder:date=` would have raised `TypeError`), and two `_time`s (the check is `_is_time`) -- and ruff a definition used before its check was defined (`datamosh`, `camcorder`: a `NameError` at import). The codemod dropped the registry's own submodule import (taking the package's name for itself), restored. The architecture test: the effects' modules placed, no cycle. Docs: 07-tools.md's six rows, AGENTS.md's layout.*
- [x] `subs/`: transcript, readers, normalisation apart. *Done: `subs/ingest.py` (604 lines) split by syntax-tree node, every node placed once: `transcript.py` the types (`Chunk`, `Word`, `Transcript`, `Row`, and `Reading`, the readers' answer -- spelled out three times, now named); `readers/` one module a format (`subrip`, `lrc`, `table`, `whisper` -- the jq emulation whisper's alone, its only user) and `__init__.py` the dispatch; `normalize.py` (`cues`, `words`, their placement); `ingest.py` keeps `ingest()` and its history. §3 had `ingest()` in `transcript.py`: with the types it imports, the readers and normalisers would import it back -- a cycle -- so the types stand alone. Callers call through the module (`readers.read`, `normalize.words`); locals named like their module's function renamed (`found`, `placed_words`). The codemod's "defined here" rule took a package's own submodules for its names (6.1.3's registry, restored by hand then, dropped again now): fixed, and shown -- `effects/__init__.py` equals HEAD's after a rerun. 07-tools.md's ten rows cite where each behaviour now is; its "Hostile transcripts" row still tells of a jq path rule (`-` gets `./`) that no Python reader needs -- for 6.12's docs. The architecture test places the seven modules.*
- [x] `jobs/convert/`: one module a flow, the passes and the render shared. *Done: `jobs/convert.py` (479 lines) split by syntax-tree node, each segment cut from its predecessor's end (the source's spacing kept: the neighbour check finds none changed), every node placed once; `convert_options.py` → `convert/options.py` by `git mv`. Each flow a module with `run` (`resize`, `burn` -- its bar and subtitles with it --, `attach`, `youtube`); shared: `passes.py` (`frame_for`, `camcorder`, `effects`: the mosh and palette passes), `render.py` (`Render`, and `Passes`, the render's input -- in `passes` it made `render` and `passes` import each other), `output.py` (`write` through the partial file, `encoders`: attach writes but never renders, so not `render`'s). The dispatch is `dispatch.py`, not `__init__.py` as §3 had it: siblings import each other through the package (`from ffman.jobs.convert import output`), and basedpyright counts the package's `__init__` -- an `__init__` importing the flows is a cycle to it (shown in a scratch package; `import a.b as b` instead, ruff's PLR0402 refuses). Caught by checking what the renames did, before any test: two locals named `passes` the module's name (an `UnboundLocalError` in every resize and burn), and a keyword renamed with its function (`output.encoders=`, a syntax error). An orphan comment, `sub_codec_for`'s, whose constant (`SUBTITLE_CODECS`) phase 4's dead-code removal took (1ba4418), above `SAFE_PATH` (now `burn._SAFE_PATH`), removed. The test's `_frame` is `passes.frame_for`, public: its private-use suppression gone. Docs: 07-tools.md's five rows, AGENTS.md's layout.*
- [x] Numbers carried as text become typed (F3) where no effect is touched: `Style`, `Bar`, `ConvertOptions`, the YouTube plan (effects' own in their boxes). *Done: `ConvertOptions.font_size`, `margin_bottom` and `bblur` (`BBlur`: a sigma, or auto), `Style.size`, `margin`, `bar_y`, `Bar.y`, and the YouTube plan's `fps` (`fps_of`: the value bash's %.6f denoted, or None) are `Fraction`s, each exactly the number stage A's text denoted -- awk's rounding kept (6.4 makes it exact); the command line's text becomes them once, in `validate`, its refusals still quoting it. Read where `awk_number(text)` was: `float()`, the same double -- a property test over the grammar's decimals and `calc`'s outputs. `fps_of` is `round(x, 6)`: equal to %.6f read back on 210,004 rationals, 10,001 exact ties (half to even), and a property test. Printed by `values.decimal`, the shortest exact decimal (any other fraction refused, never rounded). One change, G4: a number in another spelling is written as its value -- `--font-size 057.50` is `57.5` in the ASS and its note, `--bblur 012.50` is `12.5` in gblur; libass rendered the three spellings to one frame (a control, 58, differed); CHANGELOG "Changed (phase 6)", its test failing on HEAD, 07-tools.md's Rendering and Blurred borders rows; four corpus cases show it (`*-spelled`): `compare HEAD` 344 identical, 3 changed -- each in the spelled number alone (the gblur case "changed", not "same graph": the report's same graph is the same parse, and `012.50` is not `12.5` as text; ffmpeg's reading them alike is the render's proof, a frame blurred with each, identical). The 57/64 defaults and the margin's default, each once now.*

**6.2 Decide before doing** (G4)

- [x] Every flow refuses before any work (F6): `burn`'s output, kind and loop checks before bar detection, the camcorder, the subtitles and the passes; `attach`'s output before the transcript. A test counts the processes run before each refusal: none. *Done (G4): each flow probes, decides, reads the transcript, works -- `burn` decides its output, kind, fonts and size after the probe; `attach` its output before writing the track; `resize` and `burn` their encoding (`render.encoding`: `GifEncoding`, `ImageEncoding`, `VideoEncoding` -- `Render` carries it, not a `kind` beside it) and the pixel format (`stages.check_restorable`; `chain`'s refusal an invariant) before the camcorder and the passes; what this ffmpeg encodes asked last, so a transcript's refusal starts nothing. Failures stay where they happen (ffmpeg's, an optimiser's, an empty output). Measured, every corpus case under an audit hook on process starts and files written, old and new: 121 refusals, every message and status the same (beyond the corpus: one message corrected, several faults heard in the new order -- 6.2's review); refused after work 5 (`burn/to-png`'s 9 ffmpeg and an ASS, `env/fonts-colon`'s 7 bar samples, three the reading found -- an output existing in `burn` and `attach`, a codec with effects -- now corpus cases), now none, none doing more. `compare HEAD`: 345 identical, 5 changed -- in work alone (files, a printed render, its note), no message. `test_convert_job`'s order test fails on the old code in all five. A `match` whose last arm fell through by coverage's count is `case _:`, the checker's narrowing holding the union (a fourth type refused, shown). The CHANGELOG's section is "Stage B", as §1 says (6.1.6 had named it otherwise). Carried to 6.10: the camcorder passes FFMAN_FONTS_DIR to its filter unchecked, `burn` refuses it -- one rule.*

**6.3 Idiomatic ingest** (G4 where outputs differ)

- [x] JSON through `json`, CSV/TSV through `csv`, typed values -- each difference in what is read listed and decided (the hostile transcripts and the property tests are the measure). From 6.1.4's review, for this rewrite: one text-cleaning rule (tags are stripped twice today, `readers/subrip._plain` and `normalize._clean`, each a different bash step); `readers/whisper.py` ordered by format, the jq emulation apart; `readers.read`'s `file` and `path`, one value. From 6.1's review: the readers read the transcript's file themselves (`readers/__init__.py`, `readers/whisper.py`: §3's planners are pure) -- a reader takes the bytes, the job reads the file; the architecture test's IMPURE then empty. *Done (G4): readers yield typed records (`transcript.Cue`, `Timing`, `Reading`: ms, None for no time), not TSV text; `json` and `csv` read the formats, jq's `@tsv`, `tonumber`, order and gawk's FPAT gone; one number grammar for a time read from text (`readers/fields.number`: a decimal, finite) in every format; one text rule (`subs/markup.py`, the subtitle readers' and the normalisers'); `readers/whisper.py` by format; `readers.read(fmt, data, name)`; `ingest(name, data)` pure, the job reading the file (`media.paths.read_file`, "no such file" kept), the architecture test's IO_CALLS now with the filesystem's queries (`ingest`'s `is_file` had passed) and IMPURE empty; `fmt.sort_n_key`, unused, gone. Each difference decided: a JSON text as written (a backslash single -- 6.3.2's -- a CR a break); a time not a number no time, in every format (awk: 0 ms); a value of the wrong kind no value, not the file's refusal; a DTW window not given in numbers unchecked (offsets used); a CSV header naming start and end in any order (bash's rule left a reordered one garbage, which a refusal would only have hidden); a quoted CSV field whole across lines; a `t_dtw` given as a decimal string read; WhisperX seconds past a double's range in ms no time (an `OverflowError` the rewrite first had, caught in review); cues sorted by value. Measured: `compare HEAD` 347 identical, 5 changed, each one of these; the hostile and property tests; `test_ingest.py`'s new cases each failing on the old code. CHANGELOG "Stage B"; 07-tools.md's "Transcript values" row, and three rows corrected (jq's clauses gone with jq).*
- [x] The doubled backslash fixed. *Done (G4; the fix landed with 6.3.1, no `@tsv` between): one backslash in every format, read once -- `test_ingest.py`'s `test_a_backslash_is_one_in_every_format`, each of SRT, VTT, LRC, CSV, TSV, whisper-cli JSON (and its words) and WhisperX JSON (and its words), read, burned and attached. Before 6.3.1, run on the same inputs: the two JSON formats doubled it -- in their cues and words, burned `//` where one `/` stands for it, and `\\` in an attached SRT track (counted: 2) -- the others never did. Researched, kept: `\` is burned as `/` and braces as parentheses -- libass's `ass_get_next_char` reads `\N`, `\n`, `\h`, `\{`, `\}` in text (0.17.1 and master the same), and ffman's override blocks follow words, so a word ending in `\` would open `\{`; showing them as written is a product choice, carried to 6.10. No product code changed.*
- [x] `_place` rewritten as Python, its rules stated, within the property tests' invariants. *Done (form only): `_place` is one sentence's words and its window, its six rules stated in its docstring and each a step -- `_within` (a start clamped, or none), `_anchors` (index and start of each time to trust), `_share` (10 ms each where there is room, the rest by characters) -- typed, its four complexity suppressions gone; `words` groups runs with `itertools.groupby`. Every `num(None)` the old code guarded was unreachable (only anchors' and tested values met it). Shown: the old and the new, run on 400,000 random sentence sets under eight seeds (about 1.6 million words: starts before, at and past the window, ties, out-of-order words, windows too small for 10 ms each, split runs, words of no sentence) -- not one word or count differs; the run reached every line and branch of the new code. The property tests' invariants hold (suite); `compare HEAD` all identical. 07-tools.md's two placement rows made exact ("at or past", "where the gap allows").*

**6.4 Exact arithmetic, outside the effects** (G4; outcome report each)

- [x] Timing: times from their decimal text to integer milliseconds, no float; shares rounded exactly; the SRT clip by a stated rule. *Done (G4): a time is read exactly from its decimal text (`readers/fields.exact`: a `Fraction`, in bounded work -- see 6.4.1's review; JSON through `json.loads(parse_float=fields.json_number)`, a number as text still printed as before, `default=float`) and is whole milliseconds, rounded half up -- `fields.ms`, one rule for every format (bash: SubRip and LRC half up through a float, WhisperX half away from zero, CSV, TSV and whisper-cli fractions kept and truncated); past a double's range none. Readers deliver integers; `normalize` is integer arithmetic (a share `(2·rest·done + total) // (2·total)`), shown identical to its float form on integer inputs (100,000 sentence sets, 200,000 cue lists); ASS centiseconds `(ms + 5) // 10`, the same for every integer. The SRT clip, a stated rule in `srt` (which now takes the duration): the media's duration in whole ms, floored -- no cue outlasts it: exact whenever the duration is whole ms (SRT's and Matroska's resolution), and, when it is not, the earlier neighbour, since a cue past the end lengthens the file (measured: an MP4 of 1.005500 s, a cue to 1006 ms, became 1.006000 s). Measured, float against exact: seconds to ms, 185 of 200,001 values on a 0.1 ms grid; the clip, 1,482 of 200,001 whole-ms durations (1.005 s was 1004). Shown: `test_ingest.py`'s tests (old: 500, 500, 500, 999, 999 and 1004); two corpus cases built to show it -- `burn/hostile/half-ms.srt` (0.50, 4.02 → 0.51, 4.03) and `attach/clip` (a 1.005 s source: `,004` → `,005`) -- `compare HEAD` 352 identical, those 2 changed. CHANGELOG; 07-tools.md's Transcript values and Attach rows.*
- [x] Placement and the bar: exact values; `\pos` exact (fractional where the centre is); the bar's threshold and centre exact; sample times exact. *Done (G4): the formats from libass's own reading (0.17.1, `ass_parse.c`, `ass.c`): `\pos`, size, outline, shadow are doubles (`argtod`, `FPVAL`), PlayResX and the margins integers (`INTVAL`, `parse_int_header`). So in `ass.py` every value exact -- the integers rounded half up once (`values.round_half_up`, which `geometry`, `fields.ms` and `ass` now share: one rule written three times before), the doubles written as their exact decimal or the double nearest it (`_number`; `values.terminates`) -- line positions exact (bash: truncated or rounded). Proved on this build: `\pos(853,985)` and `(853.0,985.0)` render alike, `(853.5,985.8)` moves 8,691 pixels. The bar (`layout.py`): the share, threshold and centre exact (a bar exactly a line tall, 19 of 288 rows at size 57, was missed by bash's six digits), the samples at their exact seconds. Decided here though wrapping is 6.5's: the wrap estimate exact -- 88% of 1920 px in 0.55 x 64 glyphs is 48, a float made it 47 (and 26 for 27 at 1080); the comparison with the old float put back held the same 32 cases to placement alone (7,007 `\pos` lines, 31 styles, nothing else), so the rest is the wrap's. Found on the way: four test parsers read `\pos` as integers -- one failed, three passed by skipping every fractional line (a line below the frame unchecked); one decimal `POS` (`tests/support/subtitles.py`), and every placed event must yield one (shown: lines pushed 400 px down now fail both fuzz properties and the suite's). Tests failing on the old code: the header, two positions, a half-pixel centre, the bar's threshold and centre, the sample times, a 48-character line.*
- [x] Bar detection without ffmpeg's log: the height from the plan, the rows from `metadata=print`. *Done (no outcome changed): the rows from `metadata=mode=print:file=-` after cropdetect -- stdout (`f_metadata.c`: "-" is pipe:1), a `frame:` line then `key=value`s; cropdetect sets `lavfi.cropdetect.y1`/`y2` from the very values it logs (`vf_cropdetect.c`, n8.1.2), shown frame for frame on this build (15 and 13 frames, a black start's y2 under its y1 included). `bar_rows` reads them, a value not a row skipped (never a crash); the detection runs at `-v error`. The height the plan's (`shown`, the frame the ASS is drawn for): instrumented first, the log's height equalled it in every detection the corpus, suite and matrix run (360, heights 90 to 720, resized and with effects). `bar_height`, its log patterns and `fmt.awk_number` gone; awk's prefix rule kept, pinned on `fields.prefix`. `compare HEAD` 354 identical -- every burn's bar as before.*
- [x] Highlight: the pop's peak exact (`1 + 0.45/chars`); whether its settle (150 ms past the peak) may outlive a short word -- a design question, decided with its source. *Done (G4), decided with its sources: libass draws no event past its end and counts `\t` from the start (`ass_parse.c`, 0.17.1); bash's help promised "colour + smooth scale" (`ffman.sh:1470`); the timing (90 ms rise, 150 ms settle) had no recorded reason, the peak its measured one (kept). Measured: bash's settle was cut on every word under 240 ms (visibly, at 24-30 fps, to ~270 ms) -- rendered, its last frame 106.9% of its size; simulated with libass's formula (agreeing with the renders to the pixel), 4.6-8.6% at 24-30 fps. Three rules weighed -- bash's; done by the word's end (halves it, up to 7.4% left); done a frame before (none) -- the last chosen (the user's call): the window is the word less a frame (`Video.frame_time`, the source's -- a burn keeps its frames; `youtube` now shares its rate rule), the rise half of it (90 ms at most: bash's own rule when the frame is unknown), the settle by its end, a word no longer than a frame gold at once (a `\t` ending at 0 runs the whole event: never written); plain's fade the same. Rendered at 24/25/30 fps, 27 cases: the last frame 100.0% of settled (bash: up to 108.0%). The peak exact (`_number`). `compare HEAD` 334 identical, 20 changed: 537 lines of timings and peaks, 9 of words no longer than a frame gold at once, nothing else. Tests failing on the old code: the popped word, done by its last frame, a word within a frame, plain's fade, the exact peak, the frame time.*
- [x] `geometry.py`'s message without `awk_print`. *Done (G4): the size's ratio reduced, as --aspect-ratio states one (`w / h`: the sizes are integers) -- "are 16:9", exact at any size, never ambiguous (a near miss reads `8889:5000`, where a rounding could read as the ratio it is not). bash's `calc | cut -c1-6`, shown on the real code: `1.7777:1` for 16:9, `123456:1` for 12345678:1, `1.2345:1` for 1234567.5:1. Tests failing on the old code: the 64:35 case and two at the extremes. CHANGELOG.*

**6.5 Subtitles, beyond arithmetic**

- [x] Line wrapping: the font's metrics against the em estimate -- research libass's wrapping and what the highlight layers need, then decide. *Done (G4), researched and decided with the user. libass (0.17.1 source): wraps by shaped glyphs at PlayResX less the margins (90% here), a font sized to usWinAscent + usWinDescent, kerning off unless the script says (a calloc'd track); nixpkgs' libass has no libunibreak, so it breaks only at spaces -- rendered, a Japanese plain line ran past the margins, unbroken. The highlight layers need ffman's breaks (alike on both). So ffman breaks every line in every mode (`WrapStyle: 2`, plain's with `\N`), at the BBC's width -- 68% of 16:9, 90% of 4:3: 1.2 heights -- inside libass's 90%; Netflix's 42 characters agree. Measured, the em estimate filled 49-76% of libass's width on ordinary text, 111% on wide glyphs. Widths from the shipped font's advances (`subs/metrics.py`, standard library, bounded against hostile fonts): equal to HarfBuzz's on every character of all 16 shipped fonts -- the dependency weighed and declined: kerning moves a line -3.9% to +0.14% (median -0.3%), ligatures never widen, and the fonts libass falls back to cannot be known by any library here. The shipped fonts proven: the release's NAR hash is nixpkgs' (fetchzip), the local copies identical. Unspaced text breaks between characters, a mark with its own; the estimate stays for another --font, a missing file, a character the font lacks. With it, as mpv sets its own text: `Kerning: yes` (rendered: 487 to 469 px) and `Encoding -1` (each text's direction, and whole-text layout). The local gates and the corpus now carry the shipped fonts (Nix's suite always did; HEAD passed under them first). Rendered with them: the Japanese line in 2 lines within its width, the wide text within its line. `compare HEAD`: 263 identical, 91 changed -- each, on its full script, the header and its lines' breaks and places only, every event group's words and highlight the same (3,708 groups; a planted word and a planted highlight both caught). Tests failing on the old code: the header, the estimated and measured widths, plain's breaks, unspaced text, a mark; the reader branch by branch on fonts built to order (fontTools reads each as asked).*
- [x] Line breaking for unspaced scripts by their rules: kinsoku (no line opening on `。`, `、`, a closing bracket), Thai by its words (a preposed vowel, `เ`, opens its syllable; Thai needs a dictionary) -- from 6.5.1, which breaks them between characters, never inside a cluster. *Done (G4), option A with the user (no dependency). The rules researched, not recalled: UAX #14's classes (Unicode 15.1's LineBreak.txt -- Python's unicodedata is 15.1 too), PropList's Logical_Order_Exception (Thai's, Lao's, New Tai Lue's, Tai Viet's preposed vowels); every Thai character is SA -- UAX #14 leaves it to a dictionary. Measured against ICU 74.2 (PyICU, researched aside): its strict breaker and ffman's agree on 339 of 339 break positions over 31 Japanese and Chinese texts, the corpus's own included -- the two first misses were rules (LB22's ellipsis, LB25's prefix and postfix), now in; on Thai, ffman keeps every ICU word break, none after a preposed vowel, 59% of its own inside a word -- the dictionary's cost (ICU 31 MB, PyICU 8 MB, no types) declined. `subs/breaks.py` takes the cluster rules from ass.py; its table generated by `tests/support/linebreak.py` (now `ucd.py`, into `subs/ucd.py`) and checked against the UCD where present; words carry their gap, glued where no break may part them (kinsoku between Whisper's timed words too: a lone 、 never opens a line); a run wider than a line starts its own, then breaks between its units (CSS's overflow-wrap -- the first form broke it on the line it began, two words' fragments on one line, which the corpus showed); a mark advances nothing, estimated or missing from the font. Also closed: 6.5.1 broke unspaced text only when a whole chunk had no space -- a Japanese run in spaced text stayed one 41-character line. Corpus: two transcripts on which the old code breaks wrongly (`の|、`, `ます|。`, `และเ|รา`; the first drafts did not, so did not show it). `compare HEAD`: 351 identical, 5 changed -- those two and the three huge-font cases (words wider than a line, now broken), each the breaks and places alone. Tests failing on the old code: the emergency, its own line, a run in spaced text, timed punctuation, a mark's width (both paths); the rule pair by pair and ICU's strict breaks recorded (new module).*
- [x] `--highlight-colorize COLOUR`: the highlighted word's colour, a hex `#RRGGBB` (gold stays the default) -- with `chunk-word` or `word-highlight` and a burn, refused elsewhere as `--highlight-mode` is; `subs/colorize.py` and its one seam, `_gold`. (Researched: gold is applied in one place; libass interpolates `\t`'s `\1c` linearly in RGB, rendered.) *Done (G4). `subs/colorize.py` (`Colour`, `GOLD`, `parse`; ASS's byte order from `parse_color_tag`, gold's string unchanged), `Style.colorize`, `_gold` become `_colour_in` -- the one seam; the option declared, validated in `_burn` with `--highlight-mode`'s overlay check made one loop over both, carried by `ConvertOptions` (layer 3, as `subs`) to `burn.py`'s `Style`. Tests: parsing and its refusals (`#FFF`, `##`, a name, a space), blue first, the default and a given colour, the four refusals (no highlighting overlay, a name, empty, no burn), the script's colour; rendered through the CLI, a green word with no gold (gold is 255 off in red: no false pass). Corpus: `burn/colorize` (on `wx.json`, which chunk-word accepts -- its first two forms, `words.srt` and the word-level `words.ojf.json`, showed refusals instead), its plain-mode and bad-value refusals (360 cases).*
- [x] Motions: `rainbow` (each letter its own hue, the spectrum across the word, a 2 s cycle), `lsd` (saturated, letters a third of the wheel apart, 1 s), `iridescent`/`iridescence` (a pastel sheen, 3 s) -- six keyframes a cycle, exact at any saturation (to 1e-16); at most 3 flashes a second (WCAG 2.3.1: a pair of opposing changes of 10% relative luminance, or any involving saturated red), counted in the tests. (Rendered: per-letter colour tags move no pixel.) *Done (G4). Established first: libass reads `\t`'s times as whole ms (`dtoi32(argtod(...))`) and mixes each tag from the colour before it (chains are paths); WCAG 2.2's red flash (R/(R+G+B) >= 0.8, linear; 0.2 in u'v'). `colorize.py`: `Motion`, the three (`iridescence` the same object), `type Colorize`, `parse` by name in any case, `keyframes` (the fade's colour, then each sixth to the first past the end -- no freeze); `ass.py`: `_in` (the fade-in, one rule, never negative), `_lit` (a colour's fade, byte-identical), `_letters` (each cluster its block, through `_colour_in`). Rendered: each letter within 3 levels of its predicted colour; a popped word's scale reaches every letter (179 px, gold and lsd). Flashes counted high per WCAG 2.2 on every letter of 1-8 letter words, 0.3-4 s: rainbow 2/1, lsd 3/2 -- at the limit, not over -- iridescent 1/0; a planted 300 ms turn, 7/4 (the counter discriminates). Tests: names, the wheel's six exact, the spread across a word, the pastel's floor, the flashes, per-letter blocks under a pop, a lit chunk's spaces, rendered through the CLI (hues apart; gold would show one). Corpus: rainbow (chunk-word pop), lsd (word-highlight), Iridescence (chunk-word) -- 363 cases.*
- [x] Colour names: `gold`, `red`, `amber`, `teal`, `violet`... in any case, beside `#RRGGBB`. *Done (G4), researched first: CSS's named colours are the standard, but dark against the black outline (indigo 1.62:1, purple 2.23, blue 2.44, green 4.09, teal 4.40) and without amber; Tailwind CSS's palette (v3.4.17, its source fetched) at shade 400 is the darkest at which all 22 hues keep 7:1 (WCAG AAA; indigo 7.04), its 500 losing 11, its 300 paler beside white words. Gold stays #FFD700 (bash's, CSS's); CSS's synonyms grey, magenta, aqua; no white, no black. The table generated from the source and checked entry by entry; a test holds every name to 7:1. Two tests used `green` and `gold` as values to refuse -- now names: changed (`glitter`), the corpus refusal too. Corpus: `burn/colorize-name` (Teal), 364 cases. Reviewed: the help had lost its default to fit a line -- now a constant joined by an explicit `+`, with ruff's ISC003 off (basedpyright refuses implicit concatenation, which ISC003 asks for; a decision recorded in pyproject).*
- [x] `--font-color` and `--outline-color` (`#RRGGBB` or a name, with any burn): the text's colours, white and black by default. No outline given: black or white, whichever contrasts more with the fill -- never under sqrt(21), 4.58:1 (WCAG AA), over every colour; the highlighted word its own (a gold word on a black font's white outline would be 1.4:1), and the highlight fades in from the font's colours, not white. `white` and `black` join the names; a highlight the font's colour is noted. (Researched: libass's `\3c` mixes as `\1c`; `--vfx invert` is ffmpeg's `negate` on pixels -- no colour code to share.) *Done (G4). `colorize.py`: `WHITE`, `BLACK` (names now), `luminance`, `contrast`, `outline_for` (a motion: the best worst over its six keyframes, exactly -- each segment moves one channel, one way), `Colour.code` beside `ass`. `ass.py`: `HIGHLIGHTING` once (the options' copy gone), `Style.text`, `.outline`, `.text_outline()`; the header's colours; `_fade` from the font's colours, `\3c` only where the lit word's outline differs (the default writes none) -- its outline the paint's, not each letter's start (a first form gave a motion's letters each their own). The fade's start now `&H00FFFFFF&` beside the old `&HFFFFFF&`: one colour (50 frames rendered, 0 px apart). Options: one helper for both. Tests: the outline's rule and floor, contrast's numbers, the header, the fade, the outline's three cases, the note, the options; rendered through the CLI, black text outlined white, red text set apart from the same burn in white (a first criterion, pure red, missed thin strokes at 4:2:0; the motions box found this note and two docstrings blaming testsrc2's red bar -- the suite's clip is run.sh's dark gradient, testsrc2 only in a reproduction of mine). Corpus: four (368). Reviewed: the outlines were computed per highlighted word (WCAG's `** 2.4` each time) -- 40% slower on 5,000 words (0.223 to 0.311 s); now once a script (0.216).*
- [x] Their motions: every visible letter its own chain (`\1c`, `\3c`), through one painter wherever text is written; the phase by absolute time, so colours flow across events; the motion budget bounds it. A motion's outline: the one with the best worst contrast over its turn -- never a black-white flip, which would flash (rainbow and lsd: black, 2.44:1 at blue; iridescent 10.81). *Done (G4). The places text is written mapped first (`_plain`, `_block`/`_line` on both layers, `_word`). `colorize.py`: `keyframes(..., start)` -- the phase by absolute time (a second event from 1000 ms continues one event's keyframes exactly) -- `colour_at`, `_lag` once. `ass.py`: `_paint` (unchanged text without a motion: every existing output byte-identical), `_chain`, `_budget` (an event's: a plain subtitle's lines decided once -- a first form budgeted each line, ten lines ten budgets, which its test caught); `_Lines.first`, `.letters` (a letter's place across its subtitle); `_letters` the lit word's from each letter's own colour; `_solid` for the style line. Caught by the tests: a shadowed local wrote the outline's colour as its width (the header tests); an outline chain ran on past a held run (`end if end else dur`, found by FURB110). Corrected: box 1's notes blamed testsrc2 -- the suite's clip is run.sh's dark gradient; the rainbow highlight test re-checked there (gold 1 hue, rainbow 4). Letters counted in every layout: 3-5% on 5,000 words, kept. Corpus: three (371); the font-colour refusal moved to glitter, rainbow being a colour now.*
- [x] `rectangle`, in reverse video: the box the font's colour, its text the outline's -- white and black by default. (Swapped against RGB-negated: teal's box teal with black text, 11.28:1, against white with red text, 5.05:1; reverse video keeps the colour chosen and the pair's contrast.) A second style, `BorderStyle=3`, for the lit word (libass boxes each glyph: the hidden neighbours' boxes hidden too). Never over a neighbour, in `plain` and `pop`: libass double-scales a box from each glyph's origin (rendered: up to 119 px over neighbours' outlines), so the box's padding pops, not the text -- from `pad` to `pad + R`, the room beside the word and between lines less the neighbour's outline; abutting words a 1 px box, no pop. (Rendered: 30 cases, 0 px covered.) *Done (G4). `colorize.py`: `Rectangle` (`RECTANGLE`), `type Highlight`, `parse_highlight` (the font's and the outline's stay `parse`'s: no rectangle there). `ass.py`: `_edges` once (the header's outline and the box's), a `Box` style only with it (the default's header unchanged), the box's padding and pop's rise once a script, `_box` (the padding's pop, never `\fscx`), reverse video in `_lit` and `_boxed_letters` (`_chain` with the roles swapped), the lit events in `Box`. Rendered, ffman's own scripts: 0 px of a neighbour's outline under a box over 30 cases (3 sizes, plain and a pop's peak, 1-9 letters, lines wrapped); the default seen, black on white. Tests: the value, the style, reverse video at 2.8 (computed by hand: room min(0.15 x 64 - 4, 80 - 64 - 4) = 5.6, half), the pop to 4.6 and back with no `\fscx`, abutting a unit and still, word-highlight's, motions on the box and the letters; through the CLI, a white box where gold was (1,194 px more, the test asking 500). Reviewed: `self.boxed` for the branch, `isinstance` kept where it narrows the type. No cost: 0.234 s on 5,000 words (HEAD 0.243). Corpus: four (375).*
- [x] The bar a resize makes, blurred: placement from the plan, detection its fallback. *Done (G4), asked by the user (apollo.webm, 320x240, fit 9:16 with `--bblur`: no bar found; without `--bblur`, 92 of 320). Established: detection reads black rows on the planned picture, and a blurred bar has none; ffmpeg's fit (`scale_eval.c`: tmp_h rounded to the nearest multiple, then floored) and its placement round in ways a model would have to copy -- so the plan is measured, not modelled: a white frame of the source's stored size, pixels and format through the render's own head with its blur filled black (`head(measure=True)`), into the same cropdetect. A first design padded black, set aside for a hand-built pad and overlay that rounded a row apart (1363 against 1364) -- unrepresentative, their formats not the render's: ffman's own padded and blurred fits agree (186, 556; found in the review); the head read as itself is exact by construction all the same. The real render, a band at the source's foot, settled it: 186 rows, the measurement's. `_bar`: a fit with blurred bars, the plan's (`_planned`; the message "a blurred bar"); else detected (`_detected`), as before -- its seven blurred samples spared. Shown: the user's command, its subtitles centred in the blurred bar. Tests: the measured head the render's but its blur (as text), the bar's word, the measurement's command; through the CLI, the note's rows the rendered frame's, 186 (failing on the old code). Corpus: `burn/bblur-bar` (16:9 into 9:16), 376 cases. (Superseded by the next box: read before what modifies it.)*
- [x] The bar read before what modifies it: the source through the resize alone, no effect. *Done (G4), asked by the user (the last box kept a source's own bars uncounted in a blurred fit: "shouldn't this be detected before source modification?"). Established: detection read the frame after the resize and after the effects before the text; no effect there moves the picture, each recolours or draws -- and they disguised the bar: `invert` hid it, `blur` took 6 rows of 92, chromatic aberration 1; the plan alone (the last box's white frame) missed a source's own (109 against 92). So one path: the real frames through the resize alone, its blur filled black (`head(measure=True)`) -- the source's bars and the resize's, as the render places them; the white frame, `_planned` and `planned_args`, gone. Shown on real frames first: apollo 92 and a letterboxed source 109, the black fit and the blurred alike. The real-render test's band now grey (black would be the source's own bar). Tests failing on the old code: a source's own bar in a blurred fit, invert, blur, chromatic aberration. S247 departed from, with the user: bash found no bar under an inverted letterbox (read after the effect, its bar white), its text at the margin -- on that same white bar; now the bar, 160 of 360, the text centred in it (rendered: legible by its outline, as at the margin). The note says black: the picture's bar before the effect. Corpus: `burn/bblur-boxed`, `burn/bar-invert` (378 cases). compare HEAD: 375 identical, 3 changed -- the two (126 of 320: bars.mp4's own 60 rows with the fit's; 60 of 240 inverted, none before) and `burn/resize-vfx`, unpredicted: its command's labels only (va2 to va; renamed, byte-identical) -- the old detection applied VHS through the render's own Effects, a read-only pass taking the render's labels: a coupling gone.*
- [x] The player as ffman burns: mpv's subtitles and `occivink.crop`. *Done, asked by the user. mpv.conf takes ffman's plain style at mpv's 720 lines (options.rst at v0.41.0: scaled pixels at a 720-line window): font, size 38, outline 1.65 (mpv's own defaults too -- ffman copied them), sub-margin-y 40 (60 at 1080, 5.573%), sub-margin-x 64 (5% of a 16:9 width; mpv's margin is a size, so other ratios differ), sub-pos 100 (was 105). `tests/test_mpv_conf.py` holds them to ffman's own style line, two thirds (failing on the old mpv.conf; skipped where the tree is ffman alone, as in Nix). `occivink.crop` removed with its bindings (c, Alt+c, C) and notes; blur-edges, built from its source, now fetches occivink/mpv-scripts itself at occivink.nix's commit and hash -- the NAR hash recomputed from GitHub's tarball: equal, one store path; packages.nix parses (tree-sitter-nix). The run-book's item 15 checks that fetch now, not crop.*

**6.6 Metadata and streams kept** (F8, F9; G4 each; research and skills before
any code -- §4's way; the spec first where the command line changes)

Three metadata formats, converted into one another; files of them read and
written by `convert` and a new `ffman meta`; and every convert keeping what
its target can hold, the converters carrying attached metadata where the
target holds it otherwise. In order:

*6.6.1 Research* (no code; each box's findings the next boxes' sources)

- [x] ffmetadata, all of it: ffmpeg's documentation (`doc/metadata.texi`) and
      `ffmetaenc.c`/`ffmetadec.c` at n8.1.2 -- the header, comments, escaping,
      line continuation, sections (global, `[STREAM]`, `[CHAPTER]` with
      `TIMEBASE`/`START`/`END`), what a reader refuses; ffmpeg's generic keys
      (`avformat.h`) and each container's mapping of them (the muxers' tables:
      MP4 atoms, Matroska tags, Vorbis comments). Measured: every key and a
      chapter round-tripped through each container ffman writes. *Done (research). `.agents/skills/ffmetadata/references/format.md`, measured by its `scripts/measure.py` (run). The source differs from the documentation: the probe checks `;FFMETADATA` alone (the version unread); sections are exact, case-sensitive lines -- a `[chapter]` makes its lines global tags; `TIMEBASE`, `START`, `END` in that order, a missing `START` logged and defaulted; a backslash makes any byte literal (`\n` is `n`); keys match without case, the last wins; a line without `=` and a comment's continued line are dropped. ffmpeg's writer escapes no carriage return, which its reader ends a line at: only an escaped one round-trips. Keys: avformat.h's 21 and two modifiers. Through twelve containers, of 23 (`encoder` always ffmpeg's): Matroska, Ogg, Opus, FLAC, MP3 keep all (Matroska upper-cased; Ogg's at the stream); MP4 12, MOV 9, WAV 10, AVI 9 (`album` back as `product`), MPEG-TS 2; chapters exact in Matroska, MP4, MOV, MP3, Opus (starts only), none in Ogg Vorbis, FLAC, WAV, AVI, TS. Three faults of the measurement found and fixed before recording: codec options before an `-i` (theirs), tags read at the global level only, a pipe cut short. Reviewed (owner's request): the record corrected in six places -- a negative `START` the reader keeps, `fftools`' `copy_chapters` clamping (not the reader); `[STREAM]` applied only by `-map_metadata:s:...`, a media file's stream tags exported only by `-map 0 -c copy` or `-map_metadata 0:s:0` (Ogg's are its stream's); MP4's whole `ilst` (six numeric atoms, `©too` defaulting to ffmpeg's name); AVI's `product` from `avidec.c`'s own table; MPEG-TS's service name from `title`; a chapter without `END` losing the line read in its place (the source's reading had missed it) -- each now measured by the script, with the empty key and value, `NUL`, an escaped CR and MP4 with `use_metadata_tags` (all 23).*
- [x] Vorbis comments, all of it: the Vorbis I specification §5 (vendor
      string, `NAME=value`, the name's characters and case), Xiph's field
      names, the chapter extension (`CHAPTERxxx`, `CHAPTERxxxNAME`,
      `CHAPTERxxxURL`), `METADATA_BLOCK_PICTURE`, keys in use (`ALBUMARTIST`,
      `TRACKNUMBER`, `DISCNUMBER`, `REPLAYGAIN_*`, `CUESHEET`), ffmpeg's
      mapping (`vorbiscomment.c`). Xiph's own format, not ffmetadata's: its
      specification defines the comments inside a stream only, so the text
      file `vorbiscomment` names (`NAME=value` a line) is the tools'
      convention -- vorbis-tools' `vorbiscomment -l`/`-c`, with its `-e`
      escapes, and FLAC's `metaflac --export-tags-to`/`--import-tags-from`,
      without multi-line values (F9): the form decided from them, with sources. *Done (research). `.agents/skills/vorbiscomment/references/format.md`, measured by its `scripts/measure.py` (its own Ogg and FLAC readers: every comment seen as bytes), with ffmpeg 8.1.2, `metaflac` 1.5.0 and `vorbiscomment` 1.4.3 (built from its tag against libogg 1.3.6 and libvorbis 1.3.7: nixpkgs' pins). Sources: the Vorbis I spec (libvorbis 1.3.7), RFC 7845 5.2, RFC 9639 8.6-8.8 with its errata, the Xiph wiki (VorbisComment, Chapter Extension), Picard's tag mapping (87 names in use). Found: the name ranges differ (FLAC's RFC allows `~`; the Vorbis spec, libFLAC and `vorbiscomment` refuse it); names may repeat -- ffmpeg joins them with `;`, indistinguishable from a `;` in a value, and drops empty values and names; ffmpeg writes keys unchecked (a name holding `=`); **ffmpeg's chapter writer (Opus) puts every start with a fraction of 0.5 s or more a second late** (`av_rescale` rounding; unchanged in master); its reader takes `01.5` as 1.005 s, drops chapters without a fraction or of 100 hours and more, and leaves a `NAME` before its time a plain tag. The text form: `vorbiscomment -e` escapes `\n` `\r` `\\` (skips bad lines, exit 0); `metaflac` escapes nothing, refuses blank and `#` lines atomically, and drops an unterminated last line silently; both write the same comments from single-line values. Decided: ffman's text form (UTF-8, LF on every line, `vorbiscomment -e`'s escapes, names 0x20-0x7D but `=`, no `NUL`, a malformed line refused with its number). Reviewed: Picard's count corrected (87 names, 85 tags), source-only claims marked, three cases measured. Reviewed again (owner's request): `CUESHEET` as a comment added (metaflac's convention; to ffmpeg a plain tag); the six Ogg codecs whose headers ffmpeg writes comments into, from source; the vendor (`Lavf...`, `ffmpeg` bitexact) measured, not exported on reading; `vorbiscomment` refuses Opus, `metaflac` FLAC-in-Ogg; order stated as the spec has it (none). And found: **ffmpeg reorders comments** -- `av_dict_set` moves the last entry into a replaced key's place (`libavutil/dict.c`), and `encoder` is replaced on every write: chapter comments by `-metadata` into FLAC came out `NAME` first, a title lost; Ogg kept the order. All measured by the script.*
- [x] Cue sheets, all of it: the CDRWIN format -- every command (`CATALOG`,
      `CDTEXTFILE`, `FILE`, `FLAGS`, `INDEX`, `ISRC`, `PERFORMER`, `POSTGAP`,
      `PREGAP`, `REM`, `SONGWRITER`, `TITLE`, `TRACK`), its values and limits
      (`MM:SS:FF` at 75 frames a second, 99 tracks, quoting, encodings), the
      `REM` conventions in use (`GENRE`, `DATE`, `DISCID`, `COMMENT`,
      `REPLAYGAIN_*`); sources: CDRWIN's guide, libcue's grammar, readers in
      use; FLAC's `CUESHEET` block and comment (`metaflac`'s import and export,
      F9). *Done: `.agents/skills/cue/references/format.md`, `scripts/measure.py` (33
      cases through libcue, metaflac at CD-DA and 48 kHz, ffmpeg), `scripts/cuedump.c`
      (libcue 2.3.0's public API; libcue built here with bison and flex from Ubuntu's
      archive). CDRWIN's guide is only on the Internet Archive, unreachable here: its
      rules come from GNU ccd2cue 0.5's free rendering and quotations of it -- and GNU's
      one slip (the first index "of the current TRACK"; CDRWIN: of a file) recorded.
      mpv 0.41.0 read in source only. Found: no reader agrees with another -- libcue
      checks almost nothing (times unchecked, numbers ignored, a bare number read as
      frames, an unquoted multi-word string lost, `REM` values cut to one word, a
      spurious "syntax error" for every sheet ending in a newline, no `CATALOG` getter);
      metaflac keeps no text, ignores `FILE` (a multi-file sheet refused at CD-DA, stored
      wrong otherwise), exports non-CD offsets as sample numbers, and silently drops a
      `CATALOG` behind a UTF-8 BOM; mpv refuses a whole sheet for one unknown command
      (libcue's own `COMPOSER` among them); ffmpeg reads no `.cue`, and of FLAC's block
      makes chapters from each track's first index point (`INDEX 00`: the pregap opens
      the chapter) titled with its ISRC. The form every measured reader accepts is
      recorded. Reviewed (owner's request): the block's rules from libFLAC's
      `format.h` and `format.c` ("at most 100 index points" was unproven: index
      numbers 0-99 are what is enforced); `flac --cuesheet` shares metaflac's parser;
      found -- ffmpeg drops a FLAC's block, copied or encoded, writing no chapters
      in its place; mpv reads a `CUESHEET` tag as chapters at `INDEX 01` when a file
      has none (`demux.c`); libcue keeps quoted `REM` values whole (only
      `REPLAYGAIN_*` cut); metaflac accepts offsets past the stream's end, which
      ffmpeg makes a chapter without length. All measured but mpv's.*
- [x] The mappings between the three, and what each loses: ffmetadata and
      Vorbis (keys, chapters as `CHAPTERxxx`, streams' sections; repeated names
      against unique keys -- ffmpeg's `;` join -- and `COMMENT`/`DESCRIPTION`,
      `ENCODEDBY`/`encoded_by` as tools write them); either and
      cue (chapters and tracks, `INDEX 01` and `START`, a chapter's `END` from
      the next index or the duration, `PERFORMER`/`TITLE`/`SONGWRITER` and
      their keys, `REM` and the rest, 1/75 s rounding). A table, each row
      sourced; what cannot cross stated, so a conversion notes it. *Done:
      [`ffman-mappings.md`](../.agents/skills/metadata-mappings/references/mappings.md)
      (two tables, each row sourced, its loss stated) and
      [`ffman-mappings.py`](../.agents/skills/metadata-mappings/scripts/measure.py) (parts A-E, run;
      the vorbiscomment skill's readers imported -- its script now takes its
      tools in `main()`, output unchanged). Sources: FFmpeg's converters both
      ways, mpv's and Kodi's cue mappings (source), cuetools' `cuetag.sh` (built,
      run), Picard's definitions where no reader maps a field (`CATALOG` is
      `BARCODE`, not `CATALOGNUMBER`; `SONGWRITER` nearest `WRITER`). Found:
      `COMMENT` with `DESCRIPTION` -- ffmpeg keeps the first in order; Ogg merges
      global tags into a stream's, the stream's winning, FLAC drops `[STREAM]`;
      chapters vanish from a stream copy with `-fflags +bitexact` and no tags
      (the writer's `if (m)`); `-map_metadata -1` drops chapter titles,
      `-map_metadata:g -1` does not; cue times cross into ffmetadata exactly
      (`TIMEBASE=1/75`), into Vorbis within 1/3 ms and back exactly, while 92.5%
      of milliseconds do not survive a cue; mpv and Kodi end a track at the next
      `INDEX 01`, libcue at `INDEX 00`. Refuted: chapters lost by encoding with
      `+bitexact` (the encoder's tag remains). Corrected in the cue record:
      mpv converts a `.cue`'s charset (uchardet). Reviewed (owner's request): every
      direction covered -- a table of the six (ffmetadata, Vorbis, cue: each into
      the others; the same format into itself is each skill's round trip); table 1
      completed at its edges (F: a key with `=` read back as another key, a
      non-ASCII key written and read by ffmpeg, empty values dropped back, CR
      breaking ffmetadata, a picture no tag, `CUESHEET` exact); table 2 completed
      (`FILE`, a track's `REM`, libcue's commands -- G: cuetag's `ARTIST` is the
      composer before the performer); table 3 new, into cue -- no tool writes one
      (`cueconvert`: cue and TOC only) -- its rows proven by building five sheets
      from them and reading each back (H: libcue, metaflac with ffmpeg, cuetag).
      Found in the review: Kodi reads `REM DATE "1991"` as no year
      (`ExtractNumericInfo`), so the cue skill's rule "REM values quoted when they
      hold spaces" was wrong for numbers and gains (`-7.03 dB`) -- corrected
      there and in its record, the skill re-checked and re-packaged; a cue-born
      first chapter after 0 comes back at 0 from FLAC's block (ffmpeg's `INDEX
      00` rule). Both since moved into the `metadata-mappings` skill (6.6.2).*

*6.6.2 Skills* (§5; validated, packaged, presented -- before any code)

- [x] `ffmetadata`: the specification, every key and value, examples, sources. *Done: `.agents/skills/ffmetadata/` -- `SKILL.md` (218 lines: the grammar and ffmpeg's reading of every edge, the rules for a writer whose files read back exactly, the 21 keys with meanings and values, chapters, streams, what each container keeps, examples, sources), `references/format.md`, `scripts/measure.py` (which reads and checks the skill's own example). `quick_validate.py`: valid; packaged (`ffmetadata.skill`: those three files). Three test prompts (`evals/evals.json`, not packaged) answered by the skill and run: an audiobook's file into `.m4b` (tags, three chapters exact, an escaped `;`), a custom tag kept into MP4 by `use_metadata_tags`, an Ogg's tags exported by `-map_metadata 0:s:0`.*
- [x] `vorbiscomment`: the same, its text form as decided. *Done: `.agents/skills/vorbiscomment/` -- `SKILL.md` (203 lines: the format by its specifications, names and values, the chapter extension with the rules to write it exactly and ffmpeg's two faults -- its seconds rounded, its order not kept --, what ffmpeg does with comments, the two tools' text forms and ffman's decided grammar, examples, sources), `references/format.md`, `scripts/measure.py` (its part F checks the skill from its own text: the example file read as described and equal through `vorbiscomment -e`, the metaflac and ffmpeg chapter commands). `quick_validate.py`: valid; packaged (three files, each identical to the committed one). Three test prompts (`evals/evals.json`) answered by the skill and run: FLAC chapter titles lost to ffmpeg's order (metaflac keeps it), multi-line lyrics into `.ogg`, a chapter at 1:30.5 into `.opus` (ffmpeg's own: 91.5 s; the comments: 90.5).*
- [x] `cue`: the same. *Done: `.agents/skills/cue/` -- `SKILL.md` (158 lines: the format with every command, practice, how the four readers disagree, FLAC's block and the `CUESHEET` tag, rules to write a sheet every reader accepts -- times by integer arithmetic to the nearest frame, at most 6.67 ms off -- and to read one correctly, examples, sources), `references/format.md`, `scripts/measure.py` (its last part checks the skill from its own text: the example through libcue, metaflac and ffmpeg -- chapters at 0, 255 and 542.987 s --, the three commands as written, the `CUESHEET` tag byte-equal, the time rule over every millisecond to an hour), `scripts/cuedump.c`. `quick_validate.py`: valid; packaged (four files, each identical to the committed one). Three test prompts (`evals/evals.json`) run: a FLAC's block lost through ffmpeg and carried by metaflac; a podcast's sheet with half-frame times (12:30.5 -> `12:30:38`); a chapter titled with its ISRC.*
- [x] `metadata-mappings` (the owner's, at 6.7.9): the mappings, a skill. *Done:
      `.agents/skills/metadata-mappings/` -- `SKILL.md` (the fields' table,
      ffmpeg's four renames, chapters, times, the losses each way, converting by
      ffmeta, ffman and ffmpeg, two examples, sources); `references/mappings.md`
      and `scripts/measure.py`, 6.6.1's record and script moved (`git mv`), its
      citations repointed. The script imported the vorbiscomment readers from no
      file (`parents[2]`, measured) -- fixed, its eight parts re-run and matching
      the record (ffmpeg 8.1.2, metaflac 1.5.0; vorbis-tools 1.4.3, cuetools
      1.4.1, libcue 2.3.0 built from their tags). `test_skills` holds the tables
      to `fields.py` and the examples to ffmeta's conversions, each note its loss.
      `quick_validate.py`: valid; packaged. Three test prompts
      (`evals/evals.json`) run: ffmpeg's Opus chapter a second late (258.693 s;
      ffman's 257.693), an ffmetadata into a cue (libcue's track 1 at 30 s, FLAC's
      block at 0), an EAC sheet's fields into Vorbis. Found: ffmpeg's rounded
      second (the vorbiscomment skill's) reaches `-map_chapters` into Opus, stated
      where the skill gives that command. Reviewed (an independent pass), each
      finding measured and fixed: `-map 0` fails into Opus on a FLAC with a cover
      (`-map 0:a`); `ffman meta` takes no media length (the last chapter's end
      noted, a cue over several files refused); a `"` lost only in a quoted cue
      value; ffmeta not yet on PyPI; an eval's ISRC unnamed in its prompt.
      Reviewed again end to end (the owner's: efficient-skill-review), to
      convergence in four passes -- two independent, one cold run of the evals
      from the skill alone. Found and fixed: the three evals were the skill's
      own examples (answer keys: new instances, each measured), and an example's
      ISRC and title the cue skill's eval keys; a Vorbis chapter holds a URL
      too, which ffmeta maps and ffmpeg reads as the file's tag; where ffmeta
      departs from ffmpeg (`COMMENT` with `DESCRIPTION` joined, chapter tags
      left out); ffmeta's time bases; both ffman commands refuse a multi-file
      cue; the real reason for `-map 0:a`; a final `\` lost into a cue; the
      description at 1024 characters after an edit (976 now), and given its
      negative scope. Found in ffmeta: a quoted `REM GENRE` ending in `\`
      written, libcue then unable to read the sheet -- fixed, tested.*

*6.6.3 The converters* (pure: no ffmpeg; from the skills)

- [x] The model: one metadata representation -- global tags, chapters at exact
      times, streams' tags, a cue's files and tracks -- and its notes of what
      a format cannot hold; refusals name the line. *Done:
      `src/ffman/meta/` (layer 3, pure; the architecture test failed on its two
      modules until they had their layer), `model.py`: `Tag`s as written (order,
      repeats, case: names compared without ASCII case only -- ffmpeg's
      `av_tolower` folds A-Z, Vorbis names are ASCII), `Chapter`s at exact
      `Fraction` seconds (an end optional: Vorbis and cue give none), streams'
      tags, a cue's `Disc` (files, tracks, each `Index` naming its file: EAC's
      track over two files fits), `Written` (a writer's text and its notes),
      `exact` and `nearest` (the mappings' rounding, a half up: `values.round_half_up`, the
      codebase's own).
      Invariants every format shares raise `ValueError` (the codebase's
      `__post_init__`). `errors.refuse_at`: `SOURCE:LINE: message`, lines from
      1 -- the GNU Coding Standards' form (4.4) after ffman's `ffman: error:`.
      26 tests (every frame to an hour through milliseconds and back; Hypothesis
      on the rounding); suite 1121 passed at 100% coverage, the corpus 378
      identical, the matrix 761 passed, ruff and basedpyright clean. No
      behaviour changes (no command reaches it yet): no CHANGELOG row. §3 and
      `AGENTS.md` name the package. Reviewed (owner's request): `nearest` now
      `values.round_half_up` (it had re-implemented it); `values` renamed
      `values_of` (the module `ffman.values` beside it); `Track.text` and
      `Disc.text` renamed `cdtext` (CD-Text's, as libcue names it, beside
      `cdtextfile`); the rising check one helper (`_rising`), its messages
      unchanged (the tests pin them); the citation style `section 3`. Proven:
      `cli.main` prints `refuse_at`'s refusal as `ffman: error: album.cue:12:
      ...`, exit 1; no product module imports `meta`.*
- [x] ffmetadata: reader and writer, round trip exact. *Done:
      `src/ffman/meta/ffmetadata.py`. The reader agrees with ffmpeg on every file
      it reads right, and refuses, naming the line, what it reads otherwise than
      written -- found in `ffmetadec.c` and measured: a line without `=`
      (dropped), `[chapter]` (global tags), a repeated key (the last kept), a
      line ending in an escaped `\\` (**the next line read into it**: no value
      can end in `\\` -- ffmpeg cannot read back its own export of one), a
      comment ending in `\\`, a comment with `=` ending the file (**read as a
      tag**), a CR alone (it ends a tag's line, not a chapter's), a NUL, and
      chapter times not plain integers (`START=12abc` read as 12, `TIMEBASE=1`
      as 1/10^9). The writer escapes the CR ffmpeg's forgets, writes exact
      times (1/1000 where it divides, else the least time base; past `%d`,
      nanoseconds, noted), fills a missing end from the next chapter or the
      duration, and notes and leaves out what ffmpeg cannot read back. 59
      tests: every refusal with its line; round trip 400 examples (read of
      write is the model, write of read the text); ffmpeg as oracle -- ffprobe
      reads ffman's files as ffman's model (40 examples), and shows each new
      refusal's reason. The skill gained the findings (rule 7, five reading
      rows, six measured edges; re-packaged). Gates: suite 1179 passed at 100%
      coverage (the example inlined -- the build has no skill; a test holds the
      copy equal where the repository is); matrix 761 passed; ruff and
      basedpyright clean. Reviewed (owner's request), four passes:
      **a crash** -- `START=` or `TIMEBASE=` of thousands of digits reached
      `int()`, which refuses 4300 (`sys.int_info`): now refused first, past 19
      significant digits; a line in a message one line, 60 characters at most
      (`_shown`: a joined line spanned several, a huge one was echoed whole);
      `_ends` quadratic, now by bisection (100,000 chapters: 0.74 s); the two
      escape loops replaced by two regexes beside the tokenizer's; the header's
      message ("must begin"); the docstring exact that the time lines' one form
      is stricter than `sscanf`; the oracle test's `end or start` explicit; the
      strategy `ffmetadata_models` (not the module's name). Each rewrite proven
      against the committed code, differentially (20,000 inputs each).*
- [x] Vorbis text: reader and writer, round trip exact. *Done:
      `src/ffman/meta/vorbis.py`, the skill's decided form (a comment a line,
      every line ending LF; names ASCII 0x20-0x7D but `=` and `~`; values with
      `\\` `\n` `\r` alone; anything else refused, the line named). Chapters are
      the Chapter Extension's (`CHAPTERxxx=HH:MM:SS.mmm`, `NAME`, `URL`); from
      `ogm_chapter`'s source, a name ffmpeg may read as a chapter's though not the
      extension's is refused (`CHAPTER01`; `CHAPTER1000NAME`, chapter 100's to its
      `sscanf`), a chapter's comment before its time or repeated too; every other
      name a tag (`CHAPTER000ARTIST`, ffmpeg's own writer's). The writer times by
      division (the skill's rule), and notes and leaves out what the form cannot
      hold (rounding, past 99 h or 1000 chapters, ends, chapter tags but `NAME`
      and `URL`, a name not Vorbis' or a chapter's, a NUL, streams, a disc).
      Proven: vorbiscomment 1.4.3 `-w -e` stores ffman's comments byte for byte
      and `-l -e` gives back ffman's text exactly (the form is its own); the
      skill's example written back byte for byte. 48 tests -- round trip 400
      examples; ffmpeg as oracle (ffman's text, unescaped independently, in a
      FLAC: ffprobe reads its tags and chapters as the model, 40 examples; and
      shows each chapter refusal's reason); found by it: an empty title is no
      comment to ffmpeg (`if (!tl || !vl)`). Reviewed: messages exact (a URL
      repeated is joined, not "kept last"), ffmpeg's lengths named, `shown` moved
      to `errors.py` and one ffprobe helper in `tests/support/media.py` (DRY).
      Gates: suite 1228 passed at 100% coverage; matrix 761 passed; ruff and
      basedpyright clean. Reviewed (owner's request), four passes:
      **a coverage illusion** -- the round trip's and the oracle's names could not
      spell "chapter" (letters a, b, z), so neither had tested a chapter-like tag:
      now drawn too (`CHAPTER1`, `CHAPTER1000`, `chapter000artist` ...), and ffmpeg
      confirms each a tag; the two dead filters gone. The two writers' notes one
      shape, `model.left_out` -- `{what}: {why}: left out` for all that is dropped,
      the readers' words for the same facts; `errors.shown` and `left_out` tested
      directly; `_a_chapters` named. Checked: RFC 9639's 8.1 and 8.6 (Xiph's map).*
- [x] Cue: reader and writer, round trip exact within its frames. *Done:
      `src/ffman/meta/cue.py`. Reader: the skill's reading -- commands without
      case, BOM, CR LF, quoted strings to the next quote, unquoted to the line's
      end, the disc's lines before its first TRACK, EAC's layout accepted;
      refused, the line named: an unknown command or line, one out of place or
      repeated, a malformed CATALOG/ISRC/flag/number/time, a track without INDEX
      01, a FILE no INDEX follows, a time going back in its file, an INDEX 02+
      in a new FILE, a NUL, a lone CR. Keywords stored upper case (the writer
      writes them so); libcue's CD-Text read. The model's Disc and Track now
      hold the cue structure (tracks and indexes one more each, an INDEX 01,
      files in turn, from 01 one file, never back). Writer: what every reader
      accepts; noted and left out -- a string with a quote, a break or a NUL,
      or ending in `\`; libcue's CD-Text; a bad CATALOG/ISRC/flag; EAC's INDEX
      00 in the file before; noted -- a REM's ends trimmed, over 80 characters,
      a FILE name a quote cannot hold (written as readers lose least).
      Proven: 500 discs (202 multi-file) written without notes and read back
      equal; libcue reads all 500 as the model (one-off); the skill's example
      read as stated and written back byte for byte. Found: the property test
      caught the reader refusing the standard multi-file layout (fixed); libcue
      -- a value ending in `\` swallows the lines after, an INDEX after 01 in a
      new FILE and every track after EAC's layout misplaced (all measured, in
      the cue skill, with `CDTEXTFILE` added to its rule 2). Reviewed: a REM's
      ends changed silently (now noted), a no-break-space line dropped silently
      (now refused), `_BREAKS` named. 74 tests. Gates: suite 1318 passed at
      100% coverage; matrix 761 passed; ruff and basedpyright clean. Reviewed (owner's request), to
      convergence: `LIBCUE_CDTEXT` checked against libcue's scanner (equal);
      the strategy reached every edge but track 99 (first track drawn to 95) --
      now to 99, 2000 discs round-tripped; a FILE name no quote holds is now
      always unquoted -- measured, a quoted one ending in `\` makes libcue fail
      the whole sheet -- its note as measured (mpv no name; libcue none with a
      space), a claim first written from assumption, caught against the
      measurement; the model's docstrings true to it (its invariants the
      format's; keywords upper case, text as written).*
- [x] Every conversion between the three through the model: property tests
      (exact where lossless; each loss noted), corpus cases. *Done:
      `src/ffman/meta/convert.py`, `convert(meta, source, target, media=,
      durations=)`: the mappings' rows as two field tables (the disc's, a
      track's: ffmetadata's key, Vorbis' name, the cue's command) and ffmpeg's
      four names, each direction reading them; each loss noted, the target
      writer's own left to it. ffmetadata/Vorbis: the four names and a
      chapter's title renamed, a repeated name joined with `;` (noted). Cue
      into either: a track a chapter at INDEX 01, exact (frames/75), placed
      past the files before it (their durations required), ends at the next
      start; what nothing maps noted once a kind. Into a cue: chapters sorted
      (noted), INDEX 01 at the nearest frame (noted), track 1 after 0 its INDEX
      00 at 0, gaps, overlaps, the last end and past 99 noted, REM quoted only
      for spaced text. Two rows kept where the mappings dropped them
      (`CATALOG` as `BARCODE`, a track's `ISRC`, into ffmetadata: its keys are
      free), marked in the record. The Vorbis writer now notes only ends a
      reader cannot recover (at the next start: none lost). Proven: every
      direction, 1000 models each, a change in meaning only with a note (found
      by it: no chapters made one track unnoted, now noted); the whole
      disc through ffmetadata and Vorbis exact, ffmetadata and Vorbis through
      each other the same in meaning, no notes. Cases, pinned text and notes
      (the outcome corpus gains them with the command line, 6.6.4): an EAC
      sheet into both and back; ffmpeg's export into Vorbis and cue; the Vorbis
      skill's example into both. Reviewed: `_cue_lines` one for the disc and a
      track, `Track.start_index`, positions and asserts gone. 29 tests. Gates:
      suite 1348 passed at 100% coverage; matrix 761 passed; ruff and
      basedpyright clean. Reviewed (owner's request), to
      convergence: the property "each loss noted" was near vacuous in four
      directions (995-1000 of 1000 models noted anyway) -- every direction now
      has its silent path tested, ffmetadata and Vorbis through a cue exact
      (models from whole discs); `_meaning` per format, a chapter's title
      alone unified, which unmasked a silent change: an ffmetadata chapter's
      own `name` key became a Vorbis title -- now noted, left out; the tables
      carry their holder (`_Table`), no identity test.*
- [x] Interoperable: `metaflac` the oracle (`pkgs.flac`, in the checks) --
      its exported tags and cue sheets read by ffman, ffman's read by it,
      where the formats meet (single-line values). *Done: `pkgs.flac` in the
      checks' inputs (not `ffmanRuntime`: ffman never runs it; nixpkgs' pin is
      FLAC 1.5.0, read at the locked revision), a `metaflac` fixture holding
      the pin. `tests/test_meta_metaflac.py`, on a CD-DA FLAC: tags set by
      metaflac and exported, read by ffman as the model; ffman's tag file
      imported and exported by metaflac byte for byte (single-line values
      without `\`; an escape past that, metaflac's literal text); random discs
      through FLAC's CUESHEET block exactly as it keeps them (no text, PRE
      alone, AUDIO or DATA, the lead-in and lead-out REM lines after the last
      track -- measured, added to the cue skill); metaflac's export of an EAC
      sheet pinned and read; its 48 kHz export (sample numbers) refused by
      ffman, the line named. Reviewed: the strategies reach every case (no
      coverage illusion); a full disk, found when the tests filled /tmp (a 7 MB
      FLAC copied per example, 3.3 GB): now silence (98 kB) and one working
      copy -- 216 kB at most, measured. Gates: suite 1357 passed at 100%
      coverage (the 6 run, metaflac on the gate's PATH as in the check);
      matrix 761 passed; ruff and basedpyright clean; the Nix expression
      parsed (tree-sitter, a broken copy refused). Reviewed (owner's request), to
      convergence: the test's own `run()` was `tests/support/media.tool()`
      (removed); its silent CD-DA FLAC now `conftest`'s `cd_flac`, which the
      Vorbis oracles use too instead of an ffmpeg run an example (`CD_SECONDS`
      in `tests/support/media.py`: no import from conftest); both fixtures'
      version checks through `tool` (two `noqa` gone). 35 lines fewer.*

*6.6.3 reviewed whole (owner's request), to convergence -- what only shows
across its boxes: a public name is one another module or a test uses
(`ffmetadata`'s `HEADER`, `VERSION`, `NANOSECONDS`, `cue`'s CD-Text tuples and
80, `convert`'s tables and `BARCODE` made private, by token; the model's
ranges stay its contract); no logic doubled across modules (nine names in two,
each its format's own); the readers on a BOM, CR LF, a lone CR and a NUL each
as their formats' readers do -- but the cause unseen: `errors.shown` now writes
what prints nothing (`\ufeff`, `\t`, `\x00`, `\xa0`), ffmetadata's refusal
quotes the line it found (or says the file is empty), and a Vorbis file with
CR line ends is refused for its CR, not its missing break. Gates: suite 1358
passed at 100% coverage; matrix 761 passed; ruff and basedpyright clean.*

*6.6.4 The command line* (`ffman-spec.md` first, then help; completion is 6.11's)

- [x] `convert` with metadata files: `.ffmeta` (ffmpeg's: ffmetadata, no
      `--preset`), `.txt` in (ffmetadata or vorbiscomment, told by its first
      line) and `.cue`, in and out; `--preset ffmetadata` (the default) or
      `vorbiscomment` for a `.txt` out, from a `.ffmeta`, `.txt` or `.cue`; a media file's tags and chapters out to either; what cannot be
      (a metadata file into a picture flow) refused. *Done: spec 3.9 first (and
      3.6's `--preset`, 3.8's order); `meta/files.py` (a file's format: its
      extension, a `.txt`'s first line, `--preset`), `jobs/convert/metadata.py`,
      `Flow.METADATA` first with every refusal. A media file's tags and
      chapters: probed first (every flow's refusals), ffmpeg's ffmetadata export
      with `+bitexact`, and the tags ffmpeg drops either way -- `encoder`
      (`mux.c`), `creation_time`, `company_name`, `product_name`,
      `product_version` (`ffmpeg_mux_init.c`), found when a corpus case lacked
      `creation_time` -- restored from the probe (`Media.tags`). Output as
      3.1; notes on stderr; an empty result refused; strict UTF-8, the byte
      named. `--normalize` needs `--preset youtube`. 23 tests; 15 corpus cases
      (393): against HEAD, 375 identical, 18 changed -- the 15, the help's
      line, the two messages. Reviewed: a missing or non-media input refused
      as every flow does (was a misread export), the spec's rule stated once,
      README examples; the previous commit's unformatted test line (`ruff
      format --check` now in every gate). Gates: suite 1381 passed at 100%
      coverage; matrix 761 passed; ruff (check, format) and basedpyright
      clean.*
- [x] `ffman meta`, its spec (8) and tags: a metadata file written or edited
      -- input any (a media file's exported), output any, as convert's;
      `--set`, `--add`, `--unset`, `--clear` in ffmpeg's generic keys
      (`avformat.h`), each format's spelling from one field table shared with
      the converter; declarative (a fixed order, contradictions refused). *Done: spec 8 first; `meta/fields.py`
      (the converter's tables moved, one source), `meta/edit.py`
      (`Edits`, `apply` in each format's model; a cue's disc fields one each),
      `jobs/meta/` (options, run; `io.py`, moved from convert's flow, which
      shares it), `media/paths.new_output`, `META` and its Tags group, the
      command. Found in building: removing after converting noted losses of
      what was removed -- now removals in the source's words, then the
      conversion, then additions. 49 tests (a property: a set key holds its
      one value, every other tag untouched); 7 corpus cases (400): against
      HEAD 392 identical -- convert's 15 metadata cases among them, the IO move
      proven -- 8 changed (the 7, the top help). Gates: suite 1415 passed at
      100% coverage; matrix 761 passed; ruff check and format, basedpyright
      clean. Reviewed (owner's request), to
      convergence: spec 8 named 3 of meta's 12 messages -- now every one, and
      the removal rule; `--unset` of what a cue cannot hold was refused where
      the tag formats find nothing to remove -- now nothing to remove in each;
      a cue made from a metadata file named that file as its media (`FILE
      "x.ffmeta"`, convert's too since its metadata box) -- now the input's
      stem, noted (`io.cue_media`, both flows; spec 3.9); `GENERIC` private.
      Against e0666f3: 398 identical, 2 changed (the two cues from ffmetadata:
      the note). Suite 1416 passed at 100% coverage; matrix 761 passed.*
- [x] `ffman meta` chapters, one exact time syntax (`62.5`, `1:02.5`,
      `1:01:02.5`, `4650f`; never `MM:SS:FF`, which reads as `H:M:S`):
      `--chapter`, `--retitle`, `--chapter-set`, `--drop-chapter`,
      `--clear-chapters`; in a cue, a track. *Done: spec 8 first;
      `meta/time.py` (four forms, digit runs bounded), `meta/chapters.py`
      (`ChapterEdits`; numbered edits in the input's words, before
      converting; `--chapter` after the last chapter starting no later; in a
      cue a track at the nearest frame, renumbered, unused files dropped,
      track 1 holding the time before it; refused inside another track or in
      a cue over several files); `key`, `spelled` to `fields.py`, `put` to
      the model, so `edit.py` and `chapters.py` share them without a cycle.
      Found in building: a new chapter at 0 left track 1 empty; a retitle
      twice named `--chapter-set`; a track's REM branch unreachable (no
      track field is quoted). Reviewed: `bisect` on Vorbis' unordered
      chapters (no defined place: now after the last no later); Vorbis'
      `NAME` set twice through `--retitle` and `--chapter-set` (a silent
      last-wins: now refused); two suppressions replaced by typed code. 51
      tests (properties: time order kept, a drop takes the input's Nth); 4
      corpus cases (404): against 0a21562, 399 identical, 5 changed. Gates:
      suite 1467 passed at 100% coverage; matrix 761 passed; ruff check and
      format, basedpyright clean. Reviewed again (owner's request),
      to convergence: the spec had drifted from the code in five messages
      (three reworded in review, two never listed) -- now the code's; the
      edit's and the chapters' "set where it stood, its spelling kept" one
      helper (`model.set_where`). Against 515cc91: 404 identical.*
- [x] `ffman meta`, a cue's own: `--catalog`, `--isrc`, `--flags`,
      `--pregap`, `--file`. *Done: spec 8 first. Decided:
      no `--catalog` or `--isrc` -- `--set barcode=` and `--chapter-set
      N:ISRC=` are those edits already (the field table's); a second flag
      each would say one thing two ways -- each now refused unless well formed,
      for a cue. `--flags N=` and `--pregap N=TIME` (`INDEX 00`, the pregap in
      the file; `PREGAP` is silence it has not): a cue's tracks, so its input a
      cue -- N its track N, applied before converting, as every edit of N (a
      conversion into a cue sorts chapters: N would move); `--file NAME`: the
      cue's one FILE, the stem's guess and its note replaced. `cue.py`'s
      `is_catalog`, `is_isrc`, `are_flags`, its reader's and writer's checks
      too; `ChapterText` (the parser's input; `parse_chapters` split into its
      checks). 21 tests; 3 corpus cases (407): against 7d798ef, 403
      identical, 4 changed (the 3, meta's help). Gates: suite 1484 passed at
      100% coverage; matrix 761 passed; ruff check and format, basedpyright
      clean. Reviewed (owner's request), to
      convergence: `--file` with a name no cue holds (a space or quote
      first, a line break, a NUL) reached the writer's guard -- a Python
      traceback, not a refusal (shown): now refused before any work
      (`cue.is_file_name`, the writer's guard too; spec 8). Tested: a pregap
      on EAC's layout lands in its INDEX 01's file. Every message checked in
      spec 8 (13, all there). Against b2d5e33: 407 identical.*
- [x] `ffman meta -o -`: the result to stdout (inspection, pipes). *Done:
      spec 8 first. Its format `-p`'s (`ffmetadata`, `vorbiscomment`, `cue` --
      `cue` stdout's alone: a `.txt` holds ffmetadata or Vorbis), else the
      input's if a metadata file (inspection shows it as read), else
      ffmetadata. No partial file, no path printed; notes on stderr, stdout
      the text alone; an empty result printed empty (a pipe takes it); a new
      cue's FILE `media`, noted. `run.py` one pipeline (`_edited`), two ends
      (`write_output`, `io.print_output`); `files.format_of`, `Preset`.
      Found: the help told nothing of `-` (usage, `-o`, `-p`: now said); a
      disc's TITLE is `ALBUM` (my test's expectation, not the code). 9 tests;
      2 corpus cases (409), run for real -- no file written -- so their
      stdout recorded: against d0eb79c, 406 identical, 3 changed. Gates:
      suite 1497 passed at 100% coverage; matrix 761 passed; ruff check and
      format, basedpyright clean. Reviewed (owner's request), to
      convergence: stdout in a non-UTF-8 locale's encoding (latin-1) met a
      Japanese title with a `UnicodeEncodeError` traceback (shown) -- now
      UTF-8 bytes to its buffer, whatever the locale (spec 8; a test with a
      latin-1 stdout). A closed pipe: `| true` exits 141, silent (spec 2);
      `| head -c 10` exited 0 with 18 MB written -- bare Python the same in
      this sandbox (its pipe took the whole write), not ffman. Against
      ebc0d39: 409 identical.*
- [x] A metadata file applied to a media convert (`--metadata FILE`): decided
      here, and 6.10's `--attachment`, `--cover`, `--metadata`, `--title` box
      narrowed to what remains. *Done: spec 3.10 first.
      ffmpeg's `copy_meta` (source): a global `-map_metadata N` leaves each
      stream's tags to the automatic copy, and two `-map_metadata` merge --
      so the file **replaces** the global tags and chapters, every stream's
      own kept, through one mapping (`plan/streams.kept_metadata`), never
      two. The file read in any format, converted to ffmetadata (a cue's last
      track ending with the media), its stream sections noted not applied
      (`jobs/meta/io.applied`); after the output's kind is checked, before
      any pass (F6). In every flow that keeps metadata (picture, tracks,
      YouTube); alone, a flow of its own (`Flow.TAGS`, `jobs/convert/tags.py`:
      streams copied, the container the input's -- across containers is
      6.6.5's). Refused: not a metadata file, a GIF or an image, a changed
      container alone, a cue over several files, in the metadata job. 6.10's
      box narrowed to `--attachment`, `--cover`, `--title`. Found: the
      architecture table's layer-4 block out of order since the meta box
      (sorted). 12 tests, real ffmpeg (the language kept, each); 3 corpus
      cases (412): against cede5e3, 408 identical, 4 changed. Gates: suite
      1510 passed at 100% coverage; matrix 761 passed; ruff check and format,
      basedpyright clean. Reviewed (owner's request), to
      convergence: `attach` and `youtube` read the file before their own
      refusals -- `--add-subs` onto an output that exists reported the
      file's syntax error, not the output (shown); the four flows' repeated
      line now one helper, `tags.metadata_file`, each calling it after its
      refusals (a test: an existing output first, in every flow). The name
      `prepared` was taken -- `resize` and `burn` hold a local of it (ruff's
      F823). Every message checked in spec 3.10 (6, all there). Against
      1f81b12: 412 identical.*

*6.6.4 reviewed whole (owner's request), to convergence -- what only shows
across its boxes.* Hostile values for every option it added, run in-process
(121 runs; an exception escaping `main` the defect): the time syntax (to
99,999 hours) outran what a cue's `MM:SS:FF` holds (999,999 minutes), so a
far `--chapter`, and a far chapter converted into a cue (6.6.3's, by
`convert` and by `meta`), met the writer's guard as a traceback (shown, three
routes). Now `cue.LAST_FRAME` and `LAST_TIME` state the range once: a
conversion leaves such chapters out, noted (as the 99-track cut); `--chapter`
refuses one; the writer's guard through them (spec 3.9, 8). Not defects:
a NUL in a path (no argv carries one), and the harness's own StringIO
stdout, which has no buffer. Swept: no stale names, no ghost `--catalog`
or `--isrc`, one plan number in source (`tags.py`'s docstring: now the
reason). Against cedc514: 412 identical. Suite 1515 passed at 100%
coverage; matrix 761 passed; ruff check and format, basedpyright clean.

*6.6.5 Streams kept* (one stream plan, every convert flow; F8)

- [x] A container change is a job: copied (a remux), `--video-codec`
      (lossless), `--audio-codec` and `--preset` re-encoding; the same family
      with nothing asked still nothing to do (M066). *Done: spec 3.11 first.
      `Flow.REMUX` (`jobs/convert/remux.py`, `tags.py` folded in): another
      extension, a codec, `--metadata`, with no size, effect or burn; each
      stream copied unless a codec is asked (3.3's lossless; `sound`); into
      its own container whole (covers, data -- as `-map 0` kept them), else
      the picture alone (`0:V`: covers are box 5's). What a container holds
      **asked of the pinned ffmpeg** (`output.holds`): the planned command
      with `-t 0` opens each encoder and writes the header, no frame
      (measured: H.264 encoded or copied into WebM fails, VP9 and Opus pass,
      FFV1 into MP4 passes -- against memory); a failure retried per kind
      names it (`output.check_held`, `Held`). The picture's flow asks too:
      a resize from H.264 into WebM failed after its work (found, fixed).
      Decided: the same extension with nothing asked is nothing to do (M066);
      `.mp4` to `.mov` a remux -- another muxer (F8: MOV drops covers);
      the owner confirmed. Found: the trial lacked the metadata input (index 1);
      it marked every job's record with a work directory (78 records) -- now
      a directory of its own, `ffman-trial.`, the codebase's convention;
      a same-container copy dropped covers and data -- whole again (a cover
      measured kept). 14 tests (real ffmpeg); 3 corpus cases (415): against
      26c8ec0, 405 identical, 10 changed, each expected. Gates: suite 1533
      passed at 100% coverage; matrix 761 passed; ruff check and format,
      basedpyright clean. Reviewed (owner's request), to
      convergence: `--lossless` alone counted as asking a codec, so a
      refusal named `--video-codec h264`, a flag never given (shown) -- now
      asked means `--video-codec`, in both flows; `--video-codec`'s help
      said "default: the source's", false for a remux (a copy) -- now says
      both; the picture's encode arguments one helper
      (`output.lossless_picture`, the remux's and the trial's). Proven fine:
      `--audio-codec none` leaves no sound (`-an` over the map), audio-only
      remuxes, MP3 into M4A refused by the trial. Against baca688: 414
      identical, 1 changed (the help).*
- [x] Subtitles: copied where held; text into the target's (mov_text; SRT,
      ASS as ASS, WebVTT in Matroska; WebVTT); images where held, else left
      with a note naming the track -- resize, effects and burn too. *Done: spec 3.12 first.
      Each subtitle stream decided alone (`jobs/convert/subtitles.py`), by
      the remux's trial: the copy, then `mov_text`, `webvtt`, `srt`, `ass` --
      the first held, no table. Measured with subtitle-only trials: SRT and
      ASS into MP4 and MOV take `mov_text`, into WebM `webvtt`, into
      Matroska a copy (ASS as ASS); AVI, FLV and Ogg hold none. An image
      subtitle passes the copy alone (F8, no OCR); no image source could be
      made here -- ffmpeg encodes no bitmap from text -- so that path rests on
      F8's measurement and the same code. Each conversion and each loss noted,
      the track named (language, title). In the remux and the picture's flow
      (resize, effects, burn). The probe reads each subtitle stream
      (`Subtitle`: codec, language, title) instead of a count; attachments
      named so (`attachments`, `attachment_args`), the family rule theirs
      until their box. Found: an AVI copy of H.264 refused -- ffmpeg itself
      fails it (shown), the trial right; a test's private import and its
      suppression -- now the public `kept()`; the spec's attachment note
      still pointed to `--add-subs` (the old combined note's). 12 tests
      (real ffmpeg; a real attachment through both flows); 1 corpus case
      (416): against 80825e2, 412 identical, 4 changed -- every one an input
      with subtitles. Gates: suite 1539 passed at 100% coverage; matrix 761
      passed; ruff check and format, basedpyright clean. Reviewed (owner's request), to
      convergence: 20 subtitle tracks cost 40 trials, each opening the input
      (0.83 s against 0.17 s, a tiny file: seconds on a disc rip) -- the trial
      sees only the codec, so one answer a codec a job (0.18 s, the same 20
      `mov_text`; an unknown codec never shared); a test counts the trials
      per track and the kept numbered in turn around one left out. Out of
      scope, found: `--preset youtube` drops subtitle tracks without a note
      -- carried as a box, the owner's call. Against c3e8f4f: 416
      identical.*
- [x] Tags and chapters: always; the MP4 family with `use_metadata_tags`;
      chapters into Ogg Vorbis, Theora, Speex, FLAC -- and Opus -- as `CHAPTERxxx`
      comments, in order (FLAC by `metaflac`: ffmpeg's `-metadata` can reorder them,
      a title lost; Ogg by `-metadata`, the order checked) (the converter; ffmpeg's muxers write none
      there, and its Opus one puts starts of a fraction of 0.5 s or more a
      second late; its readers take them as titled chapters, FLAC measured, F9). A
      FLAC `CUESHEET` block too, for players reading only that -- `metaflac`
      (`flac` may be a runtime dependency of ffman: the owner's decision) --
      decided here, measured against the comments. A source FLAC's block is
      carried by `metaflac` too: ffmpeg writes none and drops it, copied or
      encoded again (6.6.1, cue: measured). *Done in two steps, spec
      3.13 first. Owner's decisions: the MP4 family keeps iTunes' atoms
      (`use_metadata_tags` writes `mdta` alone, `movenc.c`) -- custom tags
      noted; the CUESHEET block carried from a source FLAC, never made --
      measured against the comments: a FLAC with both reads back in ffmpeg
      and mpv as untitled chapters (`flacdec.c` by track number,
      `avpriv_new_chapter` overwriting); `flac` in `ffmanRuntime`. Tags: the
      job's own trial read back (`output.trial`). Chapters into Ogg and FLAC
      as CHAPTERxxx by `-metadata`, ffmpeg's off: measured, Vorbis lost them,
      Opus put them a second late, and `-metadata` lost the last title in all
      three -- `dict.c` moves the last entry into a replaced one's slot,
      `mux.c` replaces `encoder`: so `encoder=` first (FLAC's comments then in
      exact order; FLAC needs no metaflac). Implied ends dropped before
      converting: only a gap noted. `output.write` finishes on the partial
      before the rename. Found: a path parsed from argv; two corpus cases
      exercising nothing; an unreachable branch (FLAC into FLAC keeps every
      sample: measured) removed; a dry run printing metaflac with no block.
      Not checked here: `pkgs/default.nix`'s syntax (no nix: the flake check).
      13 tests (real ffmpeg, metaflac); corpus 418: against 352cb84, 416
      identical, 2 changed (the new). Gates: suite 1552 passed at 100%
      coverage; matrix 761 passed; ruff check and format, basedpyright
      clean. Reviewed (owner's request), to
      convergence: `--add-subs` and `--preset youtube` dropped a custom tag
      without a note -- "every convert flow" kept by three of five (shown);
      both now tag too, YouTube's trial with its own mapping (its real one
      counts the normalised audio, absent from a trial and under
      --dry-run: an index would point elsewhere). `Given.applied` a Path:
      four flows build it alike. Against 077ccab: 418 identical. Reviewed a third time (owner's
      request), for what lies between the box's own parts: step 1 read a
      source's chapters through ffmpeg, and step 2 found ffmpeg misreads a
      FLAC holding a block -- so FLAC into FLAC wrote that misreading as the
      output's comments: titles Two and Three gone, times 1.7 s and 2.5 s
      written 0 and 1 (shown; data the box itself lost). A FLAC's chapters
      now from its own comments (`metaflac`, the CHAPTERxxx lines, the Vorbis
      reader, their format kept -- `NAME` read as ffmetadata would lose the
      titles again). And a false note: ffmpeg ends a comment's last chapter
      at the duration rounded to 1/1000 s (3.007 for 3.0065) -- the last end
      now implied within a millisecond, the others exactly. Against 5cd1cf4:
      419 identical. Reviewed a fourth time (owner's
      request), the skills reread and their failure modes countered
      (familiarity: values traced, not prose re-read; a fix widened around).
      Found: the third review's fix refused a whole job over a malformed
      chapter comment ffmpeg skips (shown) -- now read as ffmpeg reads it,
      noted; and every title with a backslash or a line break was altered
      into Ogg and FLAC, silently (shown: `a\b` written `a\\b`) -- the
      Vorbis writer's text form, escapes and all, went to `-metadata`, which
      takes values raw: `vorbis.comments` now gives the raw pairs, `write`
      escapes them (its output byte-identical: its tests and the metaflac
      oracle unchanged). Swept: no other `-metadata` takes file text. Against
      7bd9030: 419 identical. Reviewed a fifth time (owner's
      request): the skills and the depth techniques reread -- invariant
      hunting the one my reviews lacked, each fix checked one hop. The
      invariant, now written: a chapter title passes through ffman unchanged
      through any chain of conversions. Violated (shown): the fourth review
      wrote a line break raw, and the third read a FLAC's comments by
      metaflac's text export, where a value's line break cannot be told from
      two comments -- ffman's own FLAC lost the rest of the title at the next
      hop. Now `media/flac.py` reads the comment block byte-exact (each
      comment's length), `vorbis.text` the writer's escaping, the reader the
      same; a test each way a file is not one (11), and the invariant through
      two hops. Against 1adedbb: 419 identical. Reviewed a sixth time (owner's
      request), nix at hand (nix-portable 2.20.6: its git the system's,
      cache.nixos.org not reachable here, so evaluated, never built):
      `pkgs/default.nix` parses and evaluates; flac 1.5.0 in the runtime
      package's derivation and the checks'. Invariants proven through
      chains: chapter times and titles through MKA -> FLAC -> Ogg -> FLAC; a
      CUESHEET block through two FLACs, CD audio too; source metadata never
      fails a job. Omissions, by the project's own rule: a new runtime tool
      gets a job in `ffman-installed` -- none had (a wrapper without metaflac
      would pass every check); now one, its script as nix renders it run here,
      failing without metaflac. And `ffman-lint`'s vulture -- never in my
      gates -- had failed since 6.6.3: `values_of`, then `same_name`, dead
      product code tested by itself; removed, `folded` now tested in their
      place. Against 13b551c: 419 identical. Reviewed a seventh time, bounded
      by the stop rule (an independent angle, its end defined): spec 3.13 read
      bottom-up as prose -- it still said a FLAC's chapters were read by
      metaflac, the third review's mechanism the fifth replaced (a text export
      cannot tell a line break from two comments); now it says the block,
      byte-exact. No other document claimed it. The code unchanged this round:
      its gates at 013b43d stand.*
- [x] Attachments: kept into Matroska; elsewhere, metadata files among them
      (ffmetadata, Vorbis text, cue) converted into the target's tags and
      chapters (automatically, 6.6.3's converters); the rest left with a note
      (MP4 fails on them, WebM drops them silently). *Done: spec 3.14 first.
      Measured: ffprobe names each attachment (filename, mimetype);
      `-dump_attachment` extracts it byte-identical, then exits non-zero (no
      output given) -- so the file, not the status, is the answer. Into
      Matroska carried as they are (3.3's family rule, every flow's).
      Elsewhere the first attached metadata file that applies, by its
      filename, tried in order, goes through `applied()` as `--metadata`
      would (it replaces; `--metadata` wins) -- one entry point,
      `tagging.metadata_file` (moved there from `remux` in review), in all five flows; each refused one noted with
      its reason, never a refusal of the job; those after, noted left out.
      `Media.attachments` a tuple of `Attachment` (by filename: the mimetype
      measured, then dropped -- vulture: nothing read it). Found: a note
      claimed a readme.txt a metadata file, and order decided correctness
      (a refused first left the cue untried) -- now tried in order, no claim
      made; `runner.workdir` touched before any attachment, a scratch
      directory for every job (108 records) -- now only on a dump; an
      assertion of mine near-tautological -- exact. 6 tests (real ffmpeg);
      against d43047d: 419 identical. Gates: suite 1577 passed at 100%
      coverage; matrix 761 passed; ruff, vulture, basedpyright clean. Reviewed (owner's request), by
      invariants: an attached cue's chapters reach FLAC's comment path too
      (titled, the one note a true millisecond rounding); a `SET.CUE` is
      recognised (`ext_of` folds case). Structure: `metadata_file` and
      `_attached` lived in a flow, `remux`, and four flows imported it --
      moved to `tagging`, beside `Given`, their one concern (where a job's
      tags and chapters come from). Found stale since the remux box:
      07-tools named `jobs/convert/tags.py`, deleted then. Against c1685b7:
      419 identical.*
- [x] Cover art: kept where held; into Matroska extracted and attached; else
      left with a note (MOV drops it silently, WebM fails). *Done: spec 3.15 first.
      Measured: MP4, M4A, FLAC, MP3 keep a cover copied attached_pic; MOV
      drops it silently; Matroska writes it as a video track; WebM, Ogg,
      Opus fail on one; a header trial cannot read a cover back (-t 0 writes
      no packet), so its exit alone decides. Matroska's cover art from its
      specification: JPEG and PNG, `cover.(jpg|png)`, the cover first; ffmpeg
      reads the attachment back as a cover. `covers.kept` (`Job`: the input,
      the job's own trial, the streams before): into Matroska extracted
      byte-exact and attached; into MOV noted; elsewhere copied if the job's
      trial holds it. In the remux, the picture flows, YouTube; the remux's
      own container now `0:V?` plus the cover. `output.Kept` shared with
      subtitles. Found in building: a cover-only trial said FLAC and MP3
      hold none (an audio muxer refuses no sound) -- now the job's own;
      `cover` used before its definition in YouTube; probe edits lost by my
      script (asserted now); a YouTube cover-first bug suspected, not
      reproducible (the MP4 muxer reorders): a question, no change. Proven
      by chain: M4A -> MKA -> FLAC -> MP4, the cover byte-identical. 10
      tests; against 031429e: 417 identical, 2 changed (0:v? to 0:V?, no
      cover in either). Gates: suite 1586 passed at 100% coverage; matrix
      761 passed; ruff, vulture, basedpyright clean. Reviewed (owner's request), by
      the paths the box's tests had not run: a resize and a re-encoding remux
      keep a cover (shown); YouTube said `a .mp4 holds none` -- false, MP4
      holds one. Its video options were written for every video stream:
      `-vf` filtered the copied cover (an ffmpeg error), and `-profile:v
      high` reached the PNG's encoder, which cannot parse it (each isolated by
      elimination). Every option now `:v:0`, the picture's alone, and a test
      that every one is; YouTube's real encodes unchanged (the matrix).
      Against 688ffe2: 404 identical, 15 changed -- the YouTube cases, their
      option spellings alone (no status or note). Asked by the owner, whether a
      cover needs an aspect ratio: none -- every format keeps it as it is
      (shown, landscape and portrait). But Matroska names it by orientation,
      as its specification says (matroska.org, RFC 9559's Cover Art):
      `cover_land. Reviewed a third time (owner's
      request): spec 3.15 read against the code's notes -- it listed two of
      five; now one form,`the cover (CODEC): WHY: left out`, every WHY named.
      The JPEG path, never run end to end:`cover_land.jpg`,`image/jpeg`,
      byte-identical, back into M4A -- now a test. No source changed
      (shown): cc292ad's outcome and matrix stand.*` wider than tall (its example 960x600), `cover.*` square
      or portrait, case-sensitive. ffman named every one `cover` -- now
      `_named` follows it from the cover's size (the probe's `Cover` holds
      width and height; unknown, `cover`). Measured first: ffprobe sizes PNG
      and JPEG covers; ffmpeg reads `cover_land.png` back as a cover, so it
      round-trips. Found: 07-tools' cover row broken since 688ffe2 -- a `|`
      in `cover.(png|jpg)` split its cell; rewritten without one. Against
      4e136fc: 419 identical.*
- [x] `--preset youtube` drops an input's subtitle tracks without a note
      (found in 6.6.5's subtitles review; bash's preset did the same). *Done:
      the owner's call -- carried, as every flow (3.12): `mov_text` in its MP4,
      each conversion and loss noted; the first pass untouched. Reviewed again (owner's request):
      input 0 the source in its final pass (the subtitle maps right); an
      attachment dropped without a note by YouTube and `--add-subs` alike
      (shown) -- both now ask `attachments()`, the one policy every flow
      shares (a Matroska output from `--add-subs` measured keeping it); the
      YouTube tests' preset setup one fixture (three copies), the attached
      source one fixture (two). Against e197b3d: 419 identical.*
- [x] Proven: sources carrying every kind of stream, each container pair's
      outcome and notes measured; the corpus, README, 07-tools, CHANGELOG.
      *Step 1 (fixes the measurement found): one Matroska source with every
      kind (video, audio, SRT, a font and a cue attached, a cover, chapters,
      a custom tag) into twelve targets. Found: into FLAC the picture vanished
      without a note (`flacenc.c` drops it at warning level, shown) -- now not
      mapped, noted; a refused job (WebM, AVI, MP3, Ogg, Opus) said an
      attached cue was applied before refusing -- `metadata_file` now returns
      its notes (`tagging.Applied`), told after the refusals; the note now
      says the cue applies in place of the media's. Every kind, after:
      held, or noted. Against 4ad9632: 419 identical. Step 2: the measured table a matrix test
      (`tests/suite/test_streams_proven.py`, nine targets: status, every
      stream, every note). Step 3: the corpus builds `all.mkv` (EVERYTHING,
      last, its attachments METADATA's), five `proven/*` cases -- whose
      records showed the step-1 fix half done: `applied()` itself told the
      cue's conversion notes before the refusal; it now returns them too,
      `--metadata`'s alike (spec 3.10). Step 4: README (what a conversion
      keeps), 07-tools, CHANGELOG. Against 7bfd301: 420 identical, 4 changed
      -- the proven cases: three reordered, the refused one stripped of
      false notes. Gates: suite 1593 passed at 100% coverage; matrix 770
      passed; ruff, vulture, basedpyright clean. Reviewed (owner's request): a
      metadata note told exactly once in all five flows (shown); the FLAC
      rule ignored what was asked -- `--video-codec ffv1` into `.flac` wrote
      the file without its picture (shown): now refused before any work;
      `--lossless`, whose sound a FLAC holds, still noted. Against 9705dfd:
      424 identical.*

*6.6.6 Review*

- [x] The section reviewed whole: formats, converters, command line, streams.
      *In progress. Sweeps across the section, one concern each (the
      boxes had their own reviews): 07-tools' 52 references -- every one
      exists; the left-out notes -- one grammar (3.12's `--` its spec's);
      the flows' notes loops -- `--add-subs` alone never asked covers.kept,
      so into Matroska a cover became a plain video track, first in the file
      (shown): its maps now all but covers, the cover placed as every flow's
      (spec 3.15). Against 2d929da: 396 identical, 28 changed -- `attach/*`,
      their maps alone. Gates: suite 1595 passed at 100% coverage (287 s:
      past my gate's own 280 s cap, which had cut three runs off silently --
      uncapped now); matrix 770 passed; ruff, vulture, basedpyright clean. Sweep 5, error
      handling: three local catches of a refusal, each told or noted; one
      note printed at once, as F4's -- `_media_chapters`', not reproducible
      before a refusal (its flows check first), yet the one place left
      breaking the rule every job note follows: returned now, told with the
      job's others. Against 0ea5f42: 424 identical. Sweep 6, the spec's
      promise that every message is specified: 25 messages' fixed words
      searched in the spec -- 3 absent (an attached file's `ffmpeg dumped
      none`, which the cover said as `extracted`: one phrasing now; the
      CUESHEET's `metaflac failed`; `ffman meta`'s `nothing to write`):
      each specified. Sweep 4: no broad video map left (`0:v?`, `-map 0`).
      Against 6dfe189: 424 identical.*

**6.7 Its own workspace and repository** (the owner's: PyPI, MIT OR Apache-2.0,
Python >= 3.13, a flake building all; before 6.8, so `subverter` is born a package)

Decided, with the owner: a uv workspace (docs.astral.sh/uv, "Using workspaces":
one lockfile, members editable to each other; uv's own split, core apart from
CLI) of three packages -- `ffman` (the CLI and its jobs), `ffmeta` (`meta/`),
`subverter` (`subs/readers/`, the cue model; 6.8's converter); `ffman-core` not
split (no consumer but `ffman`); `media/`, `graph/`, `effects/`, the burn
pipeline stay in `ffman` (measured: each imports `media` or `graph`). Its own
repository, `veramachine/ffsuite` (the owner's: an organization for the NixOS
project's repositories; the repository named for the tools it holds, `ffsuite` -- `fftools`,
first chosen, is another's project on PyPI; first planned as `veralvx/ffman`), history kept -- its authorship one, unified before its first push
(the owner's decision: trees, dates and messages kept, the hashes messages cite
re-pointed; superseded: published fresh, 6.7.4); nixos-config takes it as a flake input -- not a submodule (a second pin beside `flake.lock`; Nix >= 2.27 needs
`inputs.self.submodules`). Nix builds it from source with nixpkgs' builders
(`pypa-install-hook`: `installer`, bytecode at levels 0 and 1, measured); uv is
the development tool; uv2nix only once a dependency is missing from nixpkgs.
Names free on PyPI (measured: `ffman`, `ffmeta`, `subverter`, 404).

*6.7.1 Research* (done before the section, its facts the boxes' ground)

- [x] Measured: the tools by call site -- `ffmpeg`, `ffprobe` (7 modules: all);
      `ffmpeg-normalize` (`youtube.py`: one feature; on PyPI); `metaflac`
      (`cuesheet.py`: one rare feature); `oxipng`, `jpegoptim`, `gifsicle`
      (`plan/encode.optimizer`). No check before use: a missing optimiser
      fails the job, nothing written (shown); a missing `metaflac` fails every
      FLAC to FLAC, a cue sheet or not. The font: `FFMAN_FONTS_DIR` alone (the
      Nix wrapper's), libass's `fontsdir` and ffman's measuring both; two files
      used, IBM Plex Sans Regular and Bold, 277 kB (OFL-1.1). Read: csan
      (`checks.yml` uv matrix, `publish.yml` Trusted Publishing, `release.yml`,
      `Justfile` groups), imi (dependency review, Dependabot automerge, audit,
      cocogitto -- monorepo package tags -- dprint, templates, CONTRIBUTING).

*6.7.2 The tools, by what each is* (in nixos-config first: the gates as ever)

- [x] `ffmpeg`, `ffprobe` required: looked up once (`shutil.which`) before any
      work; absent, refused: `ffprobe not found: install ffmpeg
      (https://ffmpeg.org)`. In the spec's opening (what ffman needs); a test on a
      `PATH` holding neither. *Done. Measured first: `meta` and
      `convert` on metadata files alone run with no ffmpeg at all -- a check at
      start would have refused them; so `dispatch` requires both for every
      flow but METADATA, after choosing it. The runner names any tool missing
      at launch (`missing`), the one place every launch passes, `shutil.which`
      deciding it is the tool and not another file (typeshed's `filename` is
      `Any`: no second boundary). Shown: ffprobe without ffmpeg refused before
      any work, no work directory left; `meta` on media refused naming
      ffprobe. 7 tests; 424 identical; suite 1602 at 100% coverage; matrix
      770; ruff, vulture, basedpyright clean. Reviewed (owner's request): its
      test's "no work directory" assertion was vacuous -- the fake input fails
      at the probe, before any directory, the check or not; a mutation (the
      check removed) showed it never ran. Now a spy on the runner's two
      launches: none, not even the probe -- the same mutation fails it, the
      probe's argv shown. `_PROVIDERS`' repeated provider one constant; the
      spec's `meta` sentence unambiguous. A tool present but not executable
      is `not found`, as `execvp` sees it: right, no usable one.*
- [x] `ffmpeg-normalize` left as it is used today (the owner's decision):
      `env XDG_CONFIG_HOME=$FFMAN_NORMALIZE_HOME ffmpeg-normalize ...`, the
      command on `PATH`, its presets through `FFMAN_NORMALIZE_HOME`; Nix's
      `ffmpeg-normalize.override { ffmpeg = ffmpeg-full; }` on the wrapper's
      `PATH`, the presets directory generated. No Python dependency (on 26.05,
      nixos-config's pin, nixpkgs has no such Python package -- measured: the
      build's runtime-deps check would fail). For pip users, documented:
      `--preset youtube` needs ffmpeg-normalize on `PATH` and
      `FFMAN_NORMALIZE_HOME`, refused otherwise as today. Re-assessed at NixOS
      26.11 (nixos-unstable has `python3Packages.ffmpeg-normalize`, measured):
      a Python dependency, run as `sys.executable -m ffmpeg_normalize` (it has a
      `__main__`), `FFMPEG_PATH` handed the ffmpeg ffman runs (it reads it
      first, measured: `get_ffmpeg_exe`), the presets bundled. *Done: no code changed (shown, 0
      lines under `src`). Measured first, the case a pip user meets most --
      ffmpeg-normalize not on `PATH`: the note, `env`'s own line naming it,
      `ffmpeg-normalize failed`, nothing written -- refused as today, and
      unpinned (test 515's stub exists and fails); now pinned. Spec 1 states
      when it runs (`youtube_sound`: the sound not AAC LC 48 kHz stereo, or
      `--normalize`), its refusals word for word, the 26.11 re-assessment.
      Test 515's hand-made presets the `youtube_home` fixture. Suite 1603 at
      100% coverage; the outcome report and the matrix stand (no source
      changed). Reviewed (owner's request), by
      mutation: the pinning test passed with ffmpeg-normalize present -- a
      present one failing for its own reason (empty presets: PCM into
      `.m4a`) gives ffman the same words, so ffman's line cannot tell missing
      from failing. Now its cause asserted, `env`'s line through `capfd`
      (the child's descriptor); the mutation fails it. And my refactor had
      cut test 515's `assert not out.exists()` (left on the new test, twice):
      restored, 515's assertions identical to its original (shown).*
- [x] `metaflac` optional: a FLAC's CUESHEET block found by `media/flac.py`
      (block type 5: `media/flac.py` taught to list the blocks), `metaflac` asked
      only when there is one; absent: `the
      source's CUESHEET block: metaflac not found: left out`, the job done. A
      FLAC without one never needs it (today it fails: fixed). *Done. Found reading the carry:
      it ran `metaflac --export-cuesheet-to` to learn whether a block was
      there, after ffmpeg wrote -- so a missing metaflac failed every FLAC
      to FLAC, its encode wasted. Type 5 confirmed by `metaflac --list`
      ("type: 5 (CUESHEET)"). `media/flac.py`: one block walk (`_read`), two
      clients -- `comments` as before, `has_cuesheet`. The finisher: no
      block, nothing asked; `--metadata`'s note; metaflac absent, noted
      (`missing`'s words), the job done; an export failing with a block
      there refused, no longer silent. Shown end to end: no block without
      metaflac written, no note; a block without it, written and noted; with
      it, carried identical. Mutation-proven (three): the no-block test
      first passed with its guard removed -- the which-check also stops
      before a launch -- and now asserts the false note's absence too.
      Spec 1 (its `metaflac not found` example, now untrue, generalised),
      3.13; 07-tools; CHANGELOG. 424 identical; suite 1610 at 100%
      coverage; matrix 770; ruff, vulture, basedpyright clean. Reviewed (owner's request), by
      mutation: two more survived -- the export's refusal removed (the import
      of nothing then refused with the same words) and the two checks
      swapped (no test held `--metadata` without metaflac). Now the export
      test asserts no import tried, and a test holds the replace note, not
      `metaflac not found`, without metaflac; both mutations fail them.
      `finisher`'s docstring had drifted: it now says what it does. The
      source's change docstring-only (syntax trees compared with HEAD's):
      the outcome report and the matrix stand; suite 1611.*
- [x] The optimisers optional: `optimizer` asks `shutil.which`; absent, warned
      once, `oxipng not found: the .png written unoptimised`, the output kept,
      exit 0. Each tool's case tested; corpus `env/` cases without them. *Done. In `output._produce`, the
      one place an optimiser runs: `shutil.which` first; absent, noted
      (`missing`'s words), the partial finished and renamed, exit 0; present
      and failing, refused as before (test_convert_job's, passing). Shown for
      each format with a `PATH` of ffmpeg and ffprobe alone; mutation-proven
      (the branch removed; noted then refused: both fail all three). Corpus:
      `no-optimisers/` built with ffmpeg and `which`'s ffprobe, three
      `env/no-*` cases; 427. Predicted before running, and so: 414
      identical, 13 changed -- the 10 `.png` cases (oxipng is not on the
      harness's PATH: its line now the note) and the three new; no status.
      Spec 3.7, CHANGELOG. Suite 1614 at 100% coverage; matrix 770 (its PATH
      has oxipng: the real path still run); ruff, vulture, basedpyright
      clean. Reviewed (owner's request): spec 1's
      cross-reference named 3.13 alone, not 3.7's optimisers; 07-tools' GIF
      and optimisers row said nothing of their being optional -- both now
      do. `_produce` tested `optimise is not None` twice: one guard, its two
      outcomes nested (427 identical: no behaviour changed). A wrapper over
      `shutil.which` for the two optional tools weighed and declined: one
      stdlib call, the notes rightly differ, the shared wording already
      `missing`'s.*
- [x] Spec 3.x and the README: each tool, what it serves, what works without. *Done.
      The inventory from the code, not from the boxes: eight programs --
      `env` (it launches ffmpeg-normalize) and `nproc` (the thread count,
      `cores`) beyond the boxes'. Each claim proven: `nproc` absent, one
      thread without a word (`OMP_NUM_THREADS=3` gives 3 with it, 1 without:
      the sandbox's single CPU no evidence alone); `FFMAN_FONTS_DIR` unset, a
      burn done with no `fontsdir` -- `font_metrics` None, "its lines
      estimated". Spec 1: a table, each tool's use and its absence; the
      environment table's `FFMAN_*` rows say what unset does, and
      `OMP_NUM_THREADS` added. README: "What it needs". Only documents
      changed (shown); suite 1614 (the README in the package's source set). Reviewed (owner's request), each
      cell re-proven: the normaliser's row said `ffmpeg-normalize failed` for
      both its tools -- without `env`, `env not found` (shown); the variables'
      row called `OMP_NUM_THREADS` a ceiling -- it is a minimum (3 on one
      CPU), `OMP_THREAD_LIMIT` the maximum (3 and 2 give 2), as GNU's manual
      says; "cgroup quotas" true from coreutils 9.8 alone (its NEWS; 9.4
      here) -- `cores`' docstring, its source, too; the README's metadata
      sentence read as `meta` needing nothing. Docstring-only in the source
      (syntax trees compared); suite 1614.*
- [x] Without `nproc`, Python's count (the owner's decision): `cores` falls
      back to `os.process_cpu_count` -- affinity, or `PYTHON_CPU_COUNT` -- and
      1 only if Python has none, noted (`nproc not found: N threads, as
      Python counts the processors`; `nproc gave no count` when it fails);
      it used one thread, silently (macOS ships no `nproc`). `Runner`
      counts on first use, so a job running no ffmpeg never asks, never
      notes (shown: `meta` on metadata files silent). *Done. Proven: 32 by
      `PYTHON_CPU_COUNT` reaches ffmpeg as `-threads 33` (its flag only past
      16, bash's `ffargs`); `PYTHON_CPU_COUNT` read at startup alone
      (measured), so the tests monkeypatch Python's count. Mutations fail
      their tests -- the CLI eager (its `nproc` note, not a NameError, shown),
      the fallback 1, the note removed. Tests needing `nproc` absent from
      their own subject -- the optimisers' and the corpus's `no-optimisers`
      PATH -- now hold it: 427 identical. Spec 1's two tables, README,
      CHANGELOG. Suite 1617 at 100% coverage; matrix 770; ruff, vulture,
      basedpyright clean. Found, older and apart: four signal tests leak a
      file under `-W error` (the same at HEAD). Reviewed (owner's request): its reason,
      as I gave it, was false -- "it used one thread, silently". Below 16
      ffman passes no thread flag (`ffmpeg_args`) and ffmpeg threads itself;
      the count sets FFV1's slices past four and the threads past 16 alone
      (shown: 1 and 4 processors give identical commands; 07-tools' Threads
      row had said so all along). The old fallback's cost: FFV1 at its four
      slices on a larger machine, ffmpeg's cap past 16. The note said
      "4 threads" for a processor count: now "4 processors, as Python
      counts them"; the spec's and README's rows, the CHANGELOG and `cores`'
      docstring say what the count serves; 07-tools gains the fallback.
      427 identical; suite 1617; matrix 770.*
- [x] The leaked pipe (the owner's: fix it): the signal test opened its job
      with `stdout=PIPE` and never closed it -- a test's leak, not ffman's.
      *Done: `subprocess.Popen` as a context manager (it closes and waits);
      its assertions identical, line for line. Proven both ways under `-W
      error`: four pass, and fail with the fix alone reverted. Why it hid:
      no warning failed the suite -- now `filterwarnings = ["error"]`, after
      the whole suite (1617) and the matrix (770) passed under `-W error`;
      the configuration alone, without `-W`, fails the leak and passes the
      fix (in the gate's environment: the ad-hoc one lacks pytest-timeout,
      whose `timeout` option it warns of). AGENTS: a warning fails the
      suite.*

*6.7.3 The font*

- [x] The two Plex files bundled, unmodified (the OFL's Reserved Font Name:
      no subsetting), with `OFL.txt`, as `src/ffman/fonts/`; found by
      `FFMAN_FONTS_DIR` if set, else the package's own, as a real directory
      (`importlib.resources.as_file`: libass takes a path) -- pip and Nix alike;
      the wrapper stops setting it. Neither readable: libass's fontconfig
      default and the width estimate (today's), noted once. *Done. The source proven, not
      assumed: nixpkgs pins IBM Plex 1.1.0 by `fetchzip` from IBM's release;
      nix, fetching and unpacking it itself, reproduces the pinned hash
      (`sha256-mK+8...`; my own unpacking had not -- zipfile drops the
      permission bits a tree hash counts), and its Regular, Bold and licence
      are byte-identical to the files bundled. One resolver,
      `jobs/convert/fonts.py`, for the two readers -- the burn checked the
      variable's path, the camcorder did not (now refused alike: a latent
      bug). The package's own folder as is where its path is safe (a Nix
      store path is; a venv under a spaced folder is not, measured), else
      copied into the work directory -- one mechanism for a spaced path and
      a zip, so not `as_file`, whose temporary lifetime a job outlives. A
      folder lacking the font noted once a job (weakly keyed by the runner).
      Nix: `FFMAN_FONTS_DIR` gone from `ffmanEnv` -- wrapper, tests, shell
      alike; evaluated, the derivation no longer holds `ibm-plex`. The wheel
      hatchling builds carries the three files, identical. `test_metrics`'
      shipped-font test now runs anywhere (it skipped unless the variable
      was set); the corpus copies ffman's own (its records now the same on
      every machine). Mutation-proven (four), the camcorder's among them.
      Gates without the variable, as Nix now: 427 identical; suite 1624 at
      100% coverage; matrix 770 (real burns: the rendering unchanged); ruff,
      vulture, basedpyright clean. Spec, README, 07-tools, CHANGELOG.*
- [x] Proven: the bundled files byte-identical to nixpkgs' `ibm-plex` ones
      (`cmp`); the burn and camcorder records differing only in the fonts
      directory's path (the outcome report); a burn from a pip-installed wheel. *Done. (1) The committed files
      `cmp`-equal nix's own fetched release; to the installed file, not the
      source alone: `installFonts` is `install -m644` (read), and each font
      exists once in the tree -- no collision chooses another. (2) Bundled
      against the old Nix path, the burn's and the camcorder's commands and
      notes identical but for that path (and the work directory's random
      name); the commands only point at the scripts, so the scripts
      themselves -- the burn's lines broken by the font's metrics -- kept
      and compared: identical. (3) A wheel built from HEAD, pip-installed in
      a clean venv: a real burn, its fonts in its own `site-packages`; from
      a venv under "My Venv", `WORKDIR/fonts` -- the copy route; both
      decoded frames pixel-identical to a burn with the old Nix fonts
      (lossless, `framemd5`). Controls: without Plex, and without captions,
      the frames differ -- the comparison sees the font. Pinned: a test
      that the bundled files are the release's three, by SHA-256 (one byte
      appended, a stray file added: it fails). No source changed; suite
      1625.
- [x] 6.7.3 reviewed whole (owner's request). *Found: the camcorder's stamp
      is drawn in IBM Plex Mono (its script's Style line), which ffman never
      carried -- nor did Nix (`families = [ "sans" ]`): it is fontconfig's,
      the host's (here none: DejaVu Sans Bold substituted, `fc-match`). So
      the CHANGELOG's and README's "the camcorder's stamp render alike" was
      false: both, and spec 3's row, now say so. The "not in" note fired for
      a job not drawing with Plex Sans (shown: `--font "DejaVu Sans"`, an
      empty folder) -- `fonts_dir` now takes the job's family, noting only
      ffman's own missing; the burn passes `--font`'s, the camcorder
      `STAMP_FONT` (a test holds it to the script's Style). `Frame`'s
      `camcorder`/`fonts`, a state now impossible (a stamp without fonts),
      one `Stamp(script, fonts)`. Stale: `camcorder`'s docstring, `frame`'s
      comment, AGENTS' corpus lines. Shown: another family renders alike
      with ffman's folder or none. Mutation-proven (two). 427 identical;
      suite 1629 at 100% coverage; matrix 770.*
- [x] Owner's decision: carry IBM Plex Mono Bold too, so the camcorder's
      stamp renders alike everywhere, as the captions now do? (One more
      file of the same 1.1.0 release, the `mono` family, OFL.) *Done: carried.
      Its need measured first: the stamp's one style is Plex Mono, bold, no
      inline override (8 dialogue lines) -- the Bold alone. Proven as the
      Sans: nix, fetching IBM's `mono` release itself, reproduces the pinned
      hash (`sha256-OwUm...`); the Bold exists once in the tree; its licence
      is the Sans' byte for byte -- one `OFL.txt`. `fonts.py`: one table of
      what ffman carries, each family's files and what a job gets without
      them; the note per family, once a job; the copy route copies all.
      `STAMP_FILE` beside `STAMP_FONT`. Shown: the camcorder's frames with
      the bundled Bold equal those with nix's own, and differ from the old
      substitute's (an empty folder). The corpus copies every carried font
      (427 identical); the copy test holds the Bold (mutation: three caught).
      Wheel: the four files, identical. Suite 1629 at 100% coverage; matrix
      770. The documents' caveats reversed: the stamp renders alike. Reviewed (owner's request): the note
      said "the system's default font" -- measured against a private
      fontconfig holding Plex Mono, libass takes the system's own when it has
      it (`fc-match` finds it; the frames leave the substitute's), though it
      renders a little apart from ffman's copy, the same file (fontconfig's
      settings, not isolated): now "the system's font in its place", both
      families; spec 3 says so. The camcorder's template takes `STAMP_FONT`
      (`{font}`, it was formatted already): the family written once. The
      told set made only for a family ffman carries. 427 identical; suite
      1629; matrix 770.*

*6.7.4 The repository*

- [x] Extracted with its history and its documents', on a fresh clone --
      nixos-config's own history never rewritten (the owner's): `git
      filter-repo` keeping `tools/ffman/` (to the root), the five
      `ffman-mappings.{md,py}`, `-phase6`, `-python`, `-spec` (to `docs/`),
      the bash origin `tools/ffman.sh` and `tools/ffman-tests/` (to `bash/`:
      history alone, removed at HEAD), and the skills `ffmetadata`,
      `vorbiscomment`, `cue` (as they are: the meta tests' oracles); 07-tools'
      ffman section copied into `docs/decisions.md` (a part of a shared file:
      its history stays in nixos-config). *Done. The plan's paths were short
      three ways, each measured: `ffman-mappings.py` beside its `.md`; the
      bash origin, gone at HEAD, its history ffman's; the three skills, which
      tests read at `parents[3]`. No file ever moved into these paths from
      outside them (every rename internal). nixos-config proven untouched --
      its HEAD, 956 commits, clean tree, history and refs hashed before and
      after: identical (the clone read it under a throwaway
      `GIT_CONFIG_GLOBAL`, git's real configuration neither read nor
      written). The history complete: 215 commits for 215 that touched the
      paths; the 240 files at HEAD each its original's blob; per-file
      history equal through renames. Made whole in one commit: every link
      and citation re-pointed (`decisions.md`, `docs/`); the harness's
      export, `src` and `pyproject.toml` -- one path built of segments,
      `"tools" / "ffman" / "src"`, missed by a search for the joined string,
      caught by its own run; `test_mpv_conf` left for nixos-config (6.7.8).
      Found: in nixos-config and in Nix's check, four tests had never run --
      the three oracles and `mpv.conf`'s, each skipped "not in this tree";
      the oracles' skips removed, a missing skill now fails (shown). ruff's
      scope kept (`.agents`, `docs`, `bash` excluded: 182 files, 183 less the
      moved test). 427 identical (the harness against this history); suite
      1632, no skip; matrix 770. From here ffman's work is in this
      repository; nixos-config's `tools/ffman` and its plan copies frozen
      until 6.7.8 removes them. Reviewed (owner's request), each of
      my own checks' blind spots searched: the docs I had called historical
      held four broken links (the living plan's one); the CHANGELOG two dead
      references; 23 citations in the short form `plans/ffman-...` (source,
      tests, spec, decisions) that no search for `.agents/` or `../../`
      could find -- all re-pointed, the code's changes comment-only (14
      files, syntax trees identical). README's and AGENTS' Nix instructions
      named nixos-config's flake as this one's: now qualified, 6.7.7 to
      rewrite them. My dprint run reformatted `ffman-python.md` whole and
      corrupted it (`>=` read as a quote, `> =`): restored, its one link
      alone; 6.7.9's `dprint.json` excludes it. The tag carried,
      `ffman-bash-final`, is ffman's own (its bash's last; no `src/`).
      Suite 1632.*
- [x] The layout (each entry built by the box named):

      ffsuite/
        pyproject.toml          the workspace's root, no project of its own
                                (uv's virtual root): [tool.uv.workspace]
                                members = ["packages/*"], the dev group, the
                                tools' configuration (6.7.5; virtual: below)
        uv.lock                 (6.7.5)
        justfile  cog.toml  cliff.toml  dprint.json
                                .pre-commit-config.yaml  CONTRIBUTING.md (6.7.9)
        flake.nix  flake.lock  nix/      (6.7.7)
        LICENSE-MIT  LICENSE-APACHE (6.7.5)
        README.md  AGENTS.md  .gitignore     the repository's (here)
        docs/                   the spec, the plans, decisions.md (here),
                                upgrading.md (6.7.8), ffman-from-bash.md
                                (ffman's curated changes, 6.7.9)
        .agents/skills/         cue, ffmetadata, vorbiscomment: ffmeta's
                                tests' oracles (here)
        packages/ffman/         pyproject.toml, README.md, CHANGELOG.md (each
                                package's, git-cliff's at its release: 6.7.9),
                                LICENSE-MIT, LICENSE-APACHE, src/ffman/ (cli,
                                jobs, plan, graph, effects, media, subs -- the
                                burn pipeline -- fonts/: Plex Sans, Plex Mono
                                Bold, OFL.txt), tests/ (suite/, outcome/,
                                support/, fixtures/, test_architecture.py,
                                test_workspace.py, the rest) (below)
        packages/ffmeta/        pyproject.toml, README.md, LICENSE-MIT,
                                LICENSE-APACHE, src/ffmeta/
                                (+ py.typed), tests/ (the test_meta_* files)
                                (6.7.5, 6.7.6)
        packages/subverter/     pyproject.toml, README.md, LICENSE-MIT,
                                LICENSE-APACHE,
                                src/subverter/
                                (+ py.typed), tests/ (the readers' tests)
                                (6.7.5, 6.7.6)
        .github/                workflows/, package-tag.sh, dependabot.yml,
                                ISSUE_TEMPLATE/, PULL_REQUEST_TEMPLATE.md (6.7.9)

      *Done: the design, checked; its files are its boxes'. uv's own
      documentation: "Every workspace needs a root, which is also a
      workspace member" -- a root project with accompanying libraries, its
      most common layout. Against the extraction: the tree lacked
      `.gitignore`, `.agents/skills/`, `docs/`'s contents and `bash/`, now
      named. Each entry's owner found by meaning (my literal search missed
      the flake's, whose box names it "Its flake"): two gaps, given to 6.7.5
      -- the packages' README files (each its PyPI page: a `readme` field,
      no box writing it) and the root's sdist, which hatchling fills with
      every tracked file (measured from HEAD: `.agents`, `docs`, `tests`
      too; `packages/` would follow). Reviewed with 6.7.4 whole: two more
      owners missing, found by reading each claim in context -- `uv.lock`,
      which my table gave 6.7.9 on a literal match (it only checks it), and
      the `LICENSE` files `license-files` names (no box wrote them): both
      6.7.5's now.*
- [x] ffman under `packages/`, beside its libraries (the owner's decision, before the first
      push; the repository then named `fftools`, now `ffsuite`: below). *Done: `git mv` of `src`,
      `tests`, `README.md`, `CHANGELOG.md` to `packages/ffman/` (192 renames, their history
      followed), its licence copies held to the root's like the libraries'; its own
      `pyproject.toml` (its project, its sdist and wheel, its pytest rules for its sdist); the
      root a virtual one -- the workspace, the dev group, the tools' configuration -- proven
      first in miniature on uv 0.11.32 and the pin's 0.11.21 (lock, sync, run, build). The
      lock: the dev group to the workspace's manifest, ffman's source `packages/ffman`, no
      version moved; both uv versions accept it. `test_workspace`: the root no project, its
      members exactly the three; each library's shared fields ffman's; every pytest option a
      package sets the root's but where its tests are -- each new rule failed by its mutation.
      The outcome harness reads both layouts (`git cat-file -e`: `ls-tree` given two paths
      lists the folder's contents, measured), its import path tested on each. Nix: ffman's
      root `packages/ffman`; the pytest checks build ffman from its own source and run from a
      writable copy of the workspace (`preCheck`). A new root README, the repository's; ffman's
      README links absolute (its PyPI page); AGENTS, decisions repointed. Proven: suite 1719
      at 100% (1714 and the five new tests, predicted); outcome report against the commit
      before the move, 427 identical; the three wheels' code and data unchanged, their
      METADATA alone differing -- each README's new text, ffman's changelog URL; `nix flake
      check --no-build`, the libraries' derivations differing by their source alone (the
      README); ruff, basedpyright, vulture clean. Reviewed: that record had said the libraries'
      wheels byte-identical and their derivations unchanged -- measured before their READMEs
      were edited, now corrected (both revisions built and evaluated). The outcome harness's
      docstring still sent it to the repository's root (refused there: no `tests`); its import
      path took a root-layout tree kept in a folder named `packages` for a member (a test
      failing on it, and one on a lone tree's neighbour); AGENTS lost the verdicts' names;
      ffman's README, its PyPI page, lacked the libraries' licence section; ruff's first-party
      roots named `tests`' folder, not its import root (no import moved). Suite 1721 (two new
      tests); outcome 427 identical against the commit before the move and against it; sdists
      375, 55, 1245.*
- [x] The repository renamed `veramachine/ffsuite` (the owner's decision, before the first
      push: `fftools` is another's project on PyPI, an unrelated one -- measured -- so the name
      would be read as it). No package of that name: a meta-package re-exporting the three was
      declined -- `pip install ffman` already installs all three, ffmeta's and subverter's
      top-level names collide (`Error`, `read`), its version would break with any of theirs
      (Azure's `azure` meta-package deprecated for that), and a placeholder is name squatting
      (PEP 541). The name checked free by PyPI's own similarity rule (warehouse's
      `ultranormalize_name`: separators dropped, `l`/`i` read `1`, `o` `0`) over its 906,870
      projects -- `ffkit` and `fftoolkit` taken that way; `ffman`, `ffmeta`, `subverter` free.
      *Done: every reference (URLs, README titles, the flake's `nix run` line, the plan's
      boxes, `origin`) -- ffmpeg's own `fftools/` paths kept.*
- [x] Published fresh (the owner's decision, the bash past): `veramachine/ffsuite` begins at
      one commit, its tree the one built above (measured: every file and mode equal). The
      history before -- ffman's own in nixos-config, kept there whole, never rewritten, its tag
      `ffman-bash-final` on `tools/ffman.sh` -- and the extraction's commits from 6.7.4 to the
      push stay unpublished. The docs' commit hashes are nixos-config's (71, each found there)
      but one, 6.7.6's base `7b8c433`, that history's record alone (the other hex in the docs:
      digests and numbers, each read). *Done: what pointed into the old history points to
      nixos-config's -- the spec's source and decisions' (its `tools/ffman.sh` at its tag); the
      layout's `bash/` gone, ruff's exclusion of it dropped (the files it checks the same, 211);
      ffman's README, its PyPI page, tells the bash ffman retired, no history named.*

*6.7.5 The packages and their pyproject.toml*

- [x] Root (`ffman`): `name`, `version`, `description`, `readme`, `license = "(MIT OR Apache-2.0) AND OFL-1.1"` (the owner's: MIT or Apache-2.0,
      the user's choice, in place of AGPL-3.0; the wheel carries the fonts: PEP
      639's expression is what is distributed. The parentheses are the meaning:
      SPDX applies AND before OR (3.0.1, Annex B), so without them it would
      read "MIT, or Apache-2.0 and OFL" -- and the PyPA's parser takes both
      spellings, measured), `license-files = ["LICENSE-MIT", "LICENSE-APACHE",
      "src/ffman/fonts/OFL.txt"]`, `requires-python = ">=3.13"`, `authors`,
      `keywords`, `classifiers` (csan's set, 3.13 and 3.14, `Typing :: Typed` -- but no
      `License ::` one: with a license expression PyPI MUST reject the upload,
      PEP 639; hatchling builds it regardless, measured),
      `[project.urls]`, `[project.scripts] ffman = "ffman.cli:main"`,
      `dependencies = ["ffmeta>=0.1,<0.2", "subverter>=0.1,<0.2"]` (each library's next breaking version kept out;
      first versions: `ffmeta`, `subverter` 0.1.0, `ffman` 2.0.0),
      `[tool.uv.sources]` the two `{ workspace = true }`, `[tool.uv.workspace]
      members = ["packages/*"]`, `[dependency-groups] dev` (pytest, pytest-cov,
      pytest-timeout, pytest-xdist, hypothesis, syrupy, numpy, ruff,
      basedpyright, ty, vulture -- floors at nixpkgs' versions then),
      `[build-system]` hatchling (proven in nixpkgs), the tool tables (ruff,
      basedpyright, pytest, coverage, vulture) shared. `LICENSE-MIT` and
      `LICENSE-APACHE` written -- MIT's text as SPDX lists it, its copyright
      line the owner's (the name asked here), and Apache-2.0's from
      apache.org, each hash recorded -- at the root and in each package, a
      copy: `license-files` is each `pyproject.toml`'s own
      folder's, and `"../LICENSE"` -- which hatchling takes -- writes an sdist
      member `pkg-0.1/../LICENSE`, which tar refuses as escaping the archive,
      and no wheel builds from it (all measured).
      Each wheel's `dist-info/licenses/` checked -- `LICENSE-MIT`,
      `LICENSE-APACHE`, and ffman's `OFL.txt` (hatchling carries all three
      and names each, measured): hatchling 1.32.4 builds without a listed file, silently
      (measured: exit 0, no warning, no file, the `License-File` line
      dropped). `uv.lock` generated and committed
      (no box made it; 6.7.9's CI only checks it): `uv lock --check`
      passing, `uv sync --locked` installing, pytest run from it. *Done. csan's conventions from
      its own `pyproject.toml` (fetched): authors and maintainers "VERA LVX",
      its URL keys, its classifier shape -- but `Operating System :: POSIX`,
      not its "OS Independent": ffman calls `os.killpg`, `SIGHUP`,
      `process_group` (`media/run.py`). 14 classifiers, each in PyPI's own
      list (`trove-classifiers`). `Typing :: Typed` was untrue -- no
      `py.typed`: added (basedpyright `all`, zero errors), in the wheel.
      `hatchling>=1.26.2`: its changelog's first release with
      `license-files` in PEP 639's final form; nixpkgs' 1.29.0 within (6.7.11: 1.27.0, the first
      writing core metadata 2.4, PEP 639's fields; 1.26.x wrote 2.3 without them, measured).
      `LICENSE-MIT`: SPDX's text, "Copyright (c) 2026 veralvx" (the owner's
      handle; ffman's history begins 2026-09-27), sha256 bb99fc5b...7872.
      `LICENSE-APACHE`: the ASF's, from its site's repository
      (`apache/www-site`; apache.org itself unreachable here), equal to
      SPDX's but for whitespace, sha256 cfc7749b...3d30. The wheel: all three
      licence files, each a `License-File`, the expression, no `License ::`;
      `twine check --strict` passes. It writes Metadata 2.5 -- PyPI
      accepts it (Warehouse's `SUPPORTED_METADATA_VERSIONS` on main holds
      "2.5"). The dev group is pinned to the nixpkgs pin's versions,
      exactly, not floored: floored, the lock took newer ones, and on the
      same code ruff 0.16 (its `ALL` grown: CPY001, PLR0917, 216) and
      basedpyright with numpy 2.5's stubs (24) disagreed with Nix's -- one
      verdict only when the versions are one. `uv lock` (uv 0.11.21, nixpkgs'),
      `uv lock --check` and `uv sync --locked`: exit 0; from that
      environment ruff, format, vulture, basedpyright clean, the suite
      1632 at 100%. Reviewed: of the lock's nine transitive packages, three
      differ from nixpkgs' -- `packaging`, `pygments` (no verdict) and
      `coverage` 7.16.2 against 7.14.1, the coverage floor's measurer: pinned
      too (the floor passes under it); numpy 2.4.4 has CPython 3.14 wheels
      (21, as for 3.13), so the CI matrix's 3.14 gets binaries.
      `dependencies` and `[tool.uv.sources]` for `ffmeta` and
      `subverter` move to the box that makes them (no workspace source
      resolves before its package exists), which re-locks.*
- [x] `ffmeta`, `subverter`: each its own `pyproject.toml` -- name, version,
      readme, `license = "MIT OR Apache-2.0"` (no fonts), `requires-python`, classifiers, no
      dependencies, hatchling, `py.typed`. *Done, from one template: `0.1.0.dev0`, the root's authors and
      hatchling floor, `MIT OR Apache-2.0` with `LICENSE-MIT` and
      `LICENSE-APACHE` copies (byte-equal to the root's), `Operating System
      :: OS Independent` -- neither imports anything platform-bound
      (measured), unlike ffman -- 12 classifiers each in PyPI's list; the
      names still free (404). Each package's frame: `src/<name>/__init__.py`
      (its purpose) and `py.typed` -- its code is the move's -- and a short
      README, true but brief: hatchling reads it to build, and the next box
      writes it whole. The branch renamed `main` (csan's, and every URL's;
      no commit changed). Proven: the lock's members ffman, ffmeta,
      subverter; `uv lock --check`, `uv sync --locked` (and
      `--all-packages`: all three import from their `src`); `uv build
      --package` each -- its wheel's two licences, `py.typed`, the
      expression, no `License ::`, no `Requires-Dist`; its sdist its own
      files; `twine check --strict` four times PASSED. Each sdist holds the
      repository's `.gitignore`: hatchling looks for it up to `.git` and
      force-includes it (its `config.py`, `sdist.py`, read) -- by design.
      Reviewed: "cannot drift" was false as written -- the template a
      one-off script -- now true: `tests/test_workspace.py` holds each
      package's licence files byte-equal to the root's, its authors,
      maintainers, `requires-python`, `[build-system]` and Python
      classifiers equal to the root's, and the root's expression exactly
      `(` + the packages' + `) AND OFL-1.1`; four kinds of drift, each
      failing it. Measured for the move: `ffmeta>=0.1,<0.2` resolves with
      the members at `0.1.0.dev0` (uv takes a workspace member as its
      source). The gate copies what git tracks (and untracked, not
      ignored): suite 1638. Reviewed again: a comment misplaced ("the
      standard library alone" above the classifiers: now beside
      `dependencies = []`, and the classifiers' says why OS Independent); the
      test parsed each file twice (now once) and never checked the box's "no
      dependencies" (now does: a dependency added fails it; the floor's
      mutation re-proven on the rewritten test).*
- [x] Each package's `README.md` written: its PyPI page (the `readme`
      field names it; nothing else writes it). The root's sdist scoped
      (`[tool.hatch.build.targets.sdist]`): ffman's own -- `src`, its
      `tests`, the README, CHANGELOG, LICENSE -- never `packages/` (hatchling
      takes every tracked file otherwise: measured). *Done. The READMEs:
      what each package is, its formats in a table (each claim checked
      against the code -- ffmeta keeps `[STREAM]` sections, its model a
      cue sheet's disc too; the readers' six formats their `FORMATS`),
      installing, the licence; every link absolute (a PyPI page has no
      repository beside it), each file it names present. No usage example
      yet: the public names are the move's `__all__` -- that box writes the
      example and a test that runs it. The sdist: unscoped it held
      `packages/` (12 files), `docs/`, `.agents/`, `uv.lock`. Scoped to
      `src`, `tests`, `CHANGELOG.md` (hatchling adds the README, licences,
      `pyproject.toml`), it was proven by its own tests, unpacked: 9 failed --
      `test_workspace` (it tests the repository: excluded) and the three
      oracle tests (they read `SKILL.md`: those three files included, while
      the tests are ffman's) -- then 1632 passed, none failed. `twine check
      --strict` on all six artefacts; the repository's suite 1638.
      Reviewed: the READMEs' strongest claims proven, not read. "No file
      opened": `meta/` holds no `open`, `Path`, `os` or file read or write.
      "Never dropped in silence": an ffmetadata of tags, a stream and a
      chapter -- to a cue sheet, `convert` notes all five losses (its
      tags, the stream's, the chapter's end); to Vorbis comments, `convert`
      none but `write` two (the stream's tags, the chapter's end): what a
      format's fields cannot take is noted converting, what its structure
      cannot, writing. Nothing changed.*
- [x] `meta/` to `ffmeta`, `subs/readers/` and the cue model
      (`transcript.py`, `markup.untagged`) to `subverter`; each its own error
      (`ffmeta.Error`, `subverter.Error`) in place of `ffman.errors`, and its
      own of `values`' helpers; `ffman` catches and words them as today.
      Imports rewritten; the public names declared (`__all__`). Each package's
      README gains its usage, from those names, and a test that runs it. *Done.
      Moved by `git mv` (17 renames: history follows). The dependencies
      measured first: the moving code needed ffman's `refuse`, `refuse_at`,
      `shown`, `round_half_up`, and `markup.untagged` -- which moved too,
      ffman's `clean` importing it back. Each package's `_errors` and
      `_values` hold what it uses (subverter's first held two unused copies:
      coverage caught them -- vulture could not, a name used elsewhere --
      removed); `test_copies` holds each copy to ffman's on any input (a
      mutation surviving -- halves rounded down -- until halves were drawn
      on purpose). Imports rewritten by rule (44 files); one form, `from
      ffman.subs import readers`, escaped rule and search, caught by its own
      import. `REFUSALS` in `ffman.errors`: the CLI catches all three, each
      inner site exactly what its block raises. `__all__` from each module's
      own definitions; the roots re-export the API (`Cue` found missing by
      using it), each `Error` named by its package. A cycle (`files` importing
      its package's root, which re-exports it): the aliased module import,
      ruff's PLR0402 silenced on those lines with the reason -- the one form
      basedpyright and ruff could both accept. `ffman` depends on both;
      coverage, basedpyright, vulture reach them (vulture told
      `__module__` is read). The READMEs' usage as doctests, run from their
      `pycon` fences alone (dprint drops the blank line a whole-file doctest
      needs: shown). ffman's sdist: its own tests from it alone, the
      libraries installed -- the repository's tooling excluded (the outcome
      harness runs each case under `-S`, its commit's sources only, so it
      needs `packages/`). Proven: 427 identical against HEAD; suite 1643
      at 100% for all three; matrix 770; ruff, basedpyright, vulture clean;
      the three wheels each its own code (none moved left in ffman's), its
      dependencies, its licences; `twine check --strict` x6; ffman's sdist
      1613 passed, none failed. Reviewed: my record said each inner
      site catches exactly what its block raises -- the attached file's
      caught `REFUSALS`, subverter's too, which its block cannot raise (its
      six modules reach subverter only by `errors` importing it): now
      `(FfmanError, ffmeta.Error)`, 427 identical, both its paths covered.
      ffman's 58 imports of the libraries all public (each name in its
      module's `__all__`, or a module); no `FfmanError` left outside
      `errors.py`. AGENTS names `REFUSALS`.*
- [x] 6.7.5 reviewed whole (owner's request). *Each box was proven from the
      working tree, whose gate copies untracked files too -- a file left
      uncommitted would pass here and fail a clone. So the section's proof
      is a fresh clone of the commits alone: its own `uv sync --locked` (22
      installed), all three packages imported from it, the suite 1643 at
      100% (5607 statements, all three), ruff, format, basedpyright and
      vulture clean under its own configuration, `uv lock --check` passing,
      all six artefacts built from it and `twine check --strict` PASSED x6.
      subverter's purity, its README's claim, proven as ffmeta's was: no file
      or OS operation in either library. Every inheritance 6.7.5 owed has
      landed; what it passes on is 6.7.6's.*
- [x] The two open choices, left to my recommendation (the owner's): the
      dev group stays pinned exactly to the nixpkgs pin's versions -- one
      verdict for CI and Nix (with floors, ruff 0.16 and numpy 2.5's stubs
      disagreed on the same code, measured); Development Status by each
      package's stage -- ffman, 2.0.0, a working tool's successor held by
      100% coverage, the matrix and the outcome corpus, "5 -
      Production/Stable"; ffmeta and subverter, 0.1.0, their API declared
      just now, 0.x promising no stability, "4 - Beta". *Done: valid in
      PyPI's list, in the wheel's metadata, `twine check --strict` passing.* basedpyright's
      `include` and vulture's `paths` widened to the packages' `src` and
      `tests` (today the root's only: moved code would go unchecked; ruff
      already reaches `packages/`).
- [x] All three at `0.1.0` (the owner's decision: young tools, none yet stable -- ffman's
      2.0.0, a successor's number, dropped). *Done: the three versions; ffman "4 - Beta", as
      its libraries; its dependencies `>=0.1,<0.2` -- the `.dev0` floor had served dev
      versions alone, and named a pre-release, it opened pre-releases to pip and uv (PEP 440;
      shown: `SpecifierSet(">=0.1.0.dev0,<0.2").prereleases` true, the new one unset); the
      lock relocked, nothing else moved; the README's image tag. Proven: the wheels installed
      by uv pip and by pip (`pip check` clean), `ffman --version` 0.1.0; suite 1728 at 100%;
      sdists 1251, 375, 55; outcome 426 identical, one changed -- `cli/version`; the flake's
      packages and image at 0.1.0 (`nix flake check --no-build --all-systems`); both uv
      versions accept the lock.*

*6.7.6 The tests*

- [x] Moved: `test_meta_*` to `packages/ffmeta/tests/`, the readers' to
      `packages/subverter/tests/`; ffman's stay. With them the helpers they use
      (measured: `tests.support.metadata`'s strategies, `media`'s `tool` and
      `metadata_seen`, `flac`'s `with_comments`; conftest's `ffmpeg` and
      `metaflac` fixtures) -- each package's own; ffmpeg and metaflac stay
      `ffmeta`'s test oracles, never its runtime. Three test trees: pytest's
      `--import-mode=importlib`, each helper package its own name (no two
      `tests`). pytest from the root over all three; coverage 100% per
      package. The moved meta tests read their oracles at the root's
      `.agents/skills/` (`parents[3]` from `packages/ffmeta/tests/`).
      Their sdists then: ffman's drops the three `SKILL.md` it holds for
      them; ffmeta's cannot reach `../../.agents` (an upward path breaks an
      sdist, 6.7.5) -- copies held equal by a test, or the oracle tests kept
      out of its sdist: decided there, each sdist's tests run from it. `test_readmes`
      and `test_copies` go with them: each package tests its own README,
      and the copies' test reads all three packages (the repository's). *Done. What moves
      decided by each file's imports, through its helpers, not its name:
      `test_meta_command` is ffman's (its `meta` command); of the other
      eight, three reached ffman only through `tests.support.media`, whose
      four helpers they use need it not -- ffmeta's copies them; `metadata`
      and `flac`, used by nothing that stays, moved. Measured: subverter's
      own tests were `test_fields` alone. 9 test files and 2 helpers by `git
      mv` (11 renames), dropping the `meta_` prefix. Each tree its helper
      package (`ffmeta_support`), `pythonpath` naming it (pytest's docs:
      importlib changes no `sys.path`) and basedpyright's `extraPaths` the
      same roots; no `__init__.py` in a library's tests (another `tests`):
      ruff's INP001 excepted there, with why. The examples, which the
      oracles and the format tests share, into `ffmeta_support.examples`
      (test modules import none of each other under importlib). The oracles:
      `test_skills.py`, left out of ffmeta's sdist -- no copies. Each
      package its README test and its pytest rules (held to the root's by
      `test_workspace`, as the oracles' pins: a pin moved alone, warnings
      loosened, each fails it). `test_copies` stays ffman's: it runs from
      ffman's sdist, the libraries installed. Proven: 1646, the count
      predicted -- none lost or doubled; 100% for each package over the run;
      the matrix 770 under importlib; each sdist its own tests from it alone
      -- ffman 1244, ffmeta 347 (350 less the oracles), subverter 21; no
      source changed. Reviewed: Hypothesis' settings are
      process-global -- in one run from the root the last conftest's
      profile governs all three trees, so each tree's must be one: now held
      by `test_workspace` (a profile randomised, one with fewer examples:
      each fails it, its message the three profiles side by side). No dead
      helper left (`Seen` types `metadata_seen`, still used), no stale name
      cited.*
- [x] Each library's own tests cover it alone, 100%: measured from its own
      tree, ffmeta 99% (`files.py` 67%, its `_errors` guard), subverter 54%
      (the readers 21-65%: ffman's ingest tests ran them). Published alone,
      a library's tests must test it: reader tests for subverter, `files`
      tests for ffmeta -- written, not moved. *Done. Every
      expectation worked by hand from a recorded rule -- decisions.md's
      rows, the readers' docstrings, the spec (3.13's formats, its preset
      refusals), ffman's test_ingest's refusal words -- never from a run:
      what a reader yields before ffman's normalising. Where a test and the
      code first disagreed, the test was wrong, each shown: a message's
      `(.` read as regex (escaped); "past a double" is past its range,
      ~1.8e308, not past 1e303 (`_LONGEST`, read; the test now straddles it).
      `test_readers.py` (subverter: every format, its refusals, the
      boundaries) and `test_files.py` (ffmeta: formats by name and first
      line, the presets, `refuse_at`'s guard). Mutation-proven: four across
      them, each failing (one first missed by its anchor -- retried).
      From its own tests: subverter 54% to 100% (53), ffmeta 99% to 100%
      (376); from its own sdist alone, 100% each (subverter 53, ffmeta 373:
      the oracles not needed for it). Suite 1705 -- my prediction's 1704
      had a stale base (the profiles' guard, added since): exact. No
      source changed. Reviewed: a test imported `Timing` from
      `subverter.transcript` -- the type of `read`'s words, yet not at the
      root, as `Cue` had not been. One rule decides now: a root exports every
      type its API takes or returns, directly or as a field. Derived from the
      annotations, it found ffmeta's `Tag`, `Chapter`, `Disc`, `File`,
      `Index`, `Track` (what `Metadata` is made of) and subverter's `Timing`
      missing: exported, and a `test_api.py` in each package holds the rule
      (`Timing` unexported again: fails, naming it). Its first form too
      complex and leaking `typing`'s `Any`: split in two, cast to shape.
      427 identical; suite 1707.*
- [x] `test_architecture.py`: `ffmeta` and `subverter` import nothing of
      `ffman` nor of each other (uv cannot ensure it: its docs say so). *Done -- not in
      `test_architecture`, which is ffman's and ships in its sdist without
      `packages/`: the boundary is each library's, so each carries
      `tests/test_imports.py`, run from its own sdist too. One rule, stronger
      than the box's: itself and the standard library alone
      (`sys.stdlib_module_names`) -- ffman, the other library and any third
      party alike, as `dependencies = []` declares; a relative or a dynamic
      import (`importlib`, `__import__`) refused, this reader not seeing where
      it leads. Eight forbidden imports, each inserted in turn, each failing
      it by file, line and module (one inside a function). The other way is
      ffman's, so in `test_architecture`: every name ffman takes from a
      library -- `from`, `import`, an attribute of a bound module -- public
      (no private part; in its module's `__all__`, or a public submodule): 62
      found. Mutations: a private module, either form; a private name; a name
      a module only imports (`Format` from `files`); `ffmeta._errors` as an
      attribute -- each failing it; a public submodule passing (control). One
      mutation of mine first broke ffman's import, not the rule: placed where
      the module is bound, caught. The three test files both libraries carry
      held identical but for the package's name (`test_workspace`; one copy
      edited alone fails it), `test_api`'s docstring made generic for it. The
      environment was reset before this box: rebuilt -- the lock's Python
      tools by `uv sync --locked`, FLAC 1.5.0 and FFmpeg 8.1.2 from their
      sources (cache.nixos.org refused by the session's network policy),
      oxipng from crates.io, jpegoptim 1.5.6 from its repository (Ubuntu's
      1.4.7 lacks `--auto-mode`), the presets folder by the local Nix from
      nixos-config's file, as `pkgs/default.nix` builds it; ffmpeg's version
      string from `RELEASE`, not `git describe` (`n8.1.2` would fail the pin's
      check). Before committing, my own review: two blind spots closed --
      `builtins.__import__` (an attribute) and a private part deep in a chain
      (`ffmeta.model._x`), each caught -- and a false positive found by its
      control: a dunder (`ffmeta.__name__`) is every module's protocol, now
      public. Proven: suite 1713 at 100%, the count predicted; 427 identical;
      matrix 770; each sdist its own tests -- ffman 1245, ffmeta 375,
      subverter 55, each library 100%; ruff, basedpyright, vulture, the lock
      clean; no source changed. Reviewed: the reader followed `import`'s
      names alone, and deeper only private parts -- `from ffmeta import
      vorbis`, then `vorbis._NAME`, `vorbis.re`; `ffmeta.cue.re`; a class's
      `Metadata._x`: each passed it (proven). Now every import binds its local
      name to a dotted path, an attribute chain extends it, and each module
      along it is read: in its `__all__`, or a public submodule; past the
      modules, no private part (scope not read: a collision fails, never
      passes). 66 found; thirteen mutations fail it (a star import too), nine
      controls pass. The copies' guard printed the packages' names, not the
      drift: now the lines that differ. `test_imports` says what it refuses:
      `importlib` whole, against the running Python's list (3.13, the floor;
      a later one may add names).*
- [x] 6.7.6 reviewed whole (owner's request). *Found, each proven before
      its fix and after: ffman's and ffmeta's trees carry the same oracle
      tools (four fixtures; `tool`, `Seen`, `metadata_seen`, `CD_SECONDS`),
      held by the pin's string alone -- now every definition both carry is
      held identical, comments aside (a pin, `cd_flac`, `metadata_seen` or
      an annotated `CD_SECONDS` changed in one tree fails it; it replaces the
      pin test). `test_api` skipped an exported type alias -- one naming an
      unexported class passed; now fails. The dispatcher's refusals matched
      unanchored -- a tail added passed; now whole. Three reader tests,
      appended for coverage, moved into their formats' sections. One ruff
      list for the three trees (`**/tests/**`: ruff applies every pattern a
      file matches, measured), `INP001` alone the libraries'. Stale: the meta
      tests' comments on their moved example copies, the skills README's
      `test_meta_*`. Proven from a fresh clone of the commits: its own `uv
      sync --locked`; suite 1714 at 100%, the count predicted; ruff,
      basedpyright, vulture, the lock clean; each sdist from it -- ffman
      1245, ffmeta 375 and subverter 55, each library 100% line and branch;
      the outcome report against the section's base (7b8c433) 427 identical:
      the section changed no behaviour.*

*6.7.7 Its flake*

- [x] `packages`: `ffmeta`, `subverter`, `ffman` (wrapped, its runtime:
      ffmpeg-full, flac, oxipng, jpegoptim, gifsicle, and ffmpeg-normalize on
      ffmpeg-full, as today; its presets directory as `FFMAN_NORMALIZE_HOME`).
      The presets in both, apart (the owner's decision): ffman's repository its
      own file (`nix/ffmpeg-normalize-presets.nix`: its youtube-aac, today's
      values, and the native twin derived), from which its flake builds the
      default `FFMAN_NORMALIZE_HOME` -- the variable still an override;
      nixos-config's home its own file, as today. No check that the two are
      equal: each its owner's. No
      `pythonRecompileBytecodeHook`: an opt-in repair for bytecode that is not
      reproducible (nixpkgs #81441; removed as a default in 2020), which would
      delete the installer's bytecode and write `-OO`'s alone -- ffman's is
      reproducible already (measured: two installs by `installer` on 3.13, 178
      `.pyc`, 89 plain and 89 `opt-1`, byte-identical), `default = ffman`; `apps.default`, so `nix run
      github:veramachine/ffsuite -- convert ...` works. *Done: `flake.nix`,
      `flake.lock` (nixpkgs at nixos-config's node, `nixos-26.05` 4c78701:
      Python 3.13.15, ffmpeg-full 8.1.2, FLAC 1.5.0, hatchling 1.29.0),
      `nix/packages.nix`, `nix/ffmpeg-normalize-presets.nix`; nixos-config's
      two systems. Each package from its own `pyproject.toml` (name,
      version, description, licences from its SPDX expression, homepage),
      its tests run apart; `PATH` set to `runtime`, the presets
      `--set-default` (nixpkgs' `make-wrapper.sh`, run: unset, the package's;
      set, the user's). Found: ffman's `ffmeta>=0.1,<0.2` excluded the
      libraries' own `0.1.0.dev0` (PEP 440) -- pip, uv pip and nixpkgs'
      runtime check each refused the wheels; now `>=0.1.0.dev0,<0.2`, all
      three accept (uv's lock unchanged: a workspace source keeps no
      specifier). Beyond the box: `overlays.default`, ffman on a consumer's
      own nixpkgs -- nixos-config's ffmpeg-full carries FDK, the flake's
      cannot (evaluated: the overlaid build's ffmpeg-full and normalize on
      `PATH`, stock's absent). Proven where nothing builds (cache.nixos.org
      refused): nixpkgs fetched at the rev by git, its NAR hash the lock's;
      `nix flake check --no-build --all-systems` passes; each wheel from the
      flake's sources identical to the repository's (84, 19, 17 files); the
      presets' JSON byte-identical to those ffman ran with; nixfmt 1.5.0
      (the pin's) clean; suite 1714 at 100%; outcome 427 identical. The
      owner's to run: `nix build`, `nix run . -- --version`. Reviewed: each
      package now refuses an interpreter below its `requires-python` at
      evaluation (`disabled`, the floor read from the file: 3.12 refused,
      each by name; 3.13 and 3.14 evaluate; a range not a bare floor fails,
      saying so) -- the overlay builds on a consumer's Python, which nothing
      checked; the derivations unchanged (`disabled` is the builder's own).
      Verified, not assumed: nixpkgs' ffmpeg-full is built
      `--disable-libfdk-aac` (the native twin's reason), its `ffmpeg` and
      `ffprobe` in the `bin` output `PATH` takes; `.gitignore` holds
      `result`.*
- [x] `checks`: each package's tests, the matrix, lint, types, vulture, the
      installed check (its `metaflac` job; a job without the optimisers; a job
      with `FFMAN_NORMALIZE_HOME` set, the user's folder used -- 6.7.7's
      `--set-default`, untested until here), nixfmt on the Nix files (a
      `formatter`, as nixos-config's), each
      on Python 3.13 and 3.14. The source fileset holds `.agents/skills` (the
      meta tests' oracles: without them they fail now, no longer skip),
      `packages/` and the licence files (`test_workspace` reads them); the
      checks run pytest from the root (its `testpaths`, `pythonpath`). README's
      and AGENTS' Nix instructions -- nixos-config's flake's until now
      (`nix develop .#ffman`, the checks' names) -- rewritten for this flake
      (AGENTS' runtime rule already, 6.7.7's first box). `devShells.default`: uv, Python, ruff,
      basedpyright, just, dprint, cocogitto, pre-commit.
      *Done: `nix/checks.nix` -- on 3.13 and 3.14 each: `tests` (pytest
      from the root over the installed packages, `pytestCheckHook`, 100%),
      `matrix`, `installed` (`nix/installed.sh`), `types`, `vulture`; `lint`
      once (ruff, nixfmt, shellcheck: no interpreter); `nix/shell.nix` (uv on
      nixpkgs' Python, its downloads off -- shown: an absent Python refused,
      not fetched -- the box's tools, nixfmt, shellcheck, the runtime and
      presets); `formatter` nixfmt-tree (below); AGENTS' checks, its layout's `nix/`,
      decisions' header rewritten. The installed check gained its two jobs:
      `FFMAN_NORMALIZE_HOME` set, the user's (empty) folder refused by name;
      a wrapper without the optimisers (`wrapperArgs`, one definition), each
      output written and noted. Found: basedpyright resolved none of the
      workspace in a clean environment -- 6.7.6's `extraPaths` hid `src`,
      the venv's editable installs hid it here -- now the three sources in
      `extraPaths` (0 errors, 3.13 and 3.14, the repo's venv too). The
      checks' source holds no Nix file: an edit there reruns lint alone
      (shown). Python 3.14 met first here: suite 1714 at 100%. Proven where
      nothing builds: `nix flake check --no-build`, 11 checks a system; each
      check's command run in its own conditions -- the suite against the
      installed wheels from the fileset alone, `env -i`, both Pythons (1714,
      100%); the matrix the same (770 and 770); `installed.sh` itself over
      wrappers by nixpkgs' `make-wrapper.sh` (both pass; the old `--set`
      wrapper, a lean wrapper with optimisers, a missing `$lean`, each
      failing it); lint, types, vulture in the checks' read-only source; the
      lean `PATH` the runtime less the three. `syrupy`, in the dev group, is
      used by no test: not in the checks (the group is 6.7.5's). Reviewed:
      the emulation's own gaps attacked -- nixpkgs' Python builds export
      `PYTHONHASHSEED=0` (its `setup-hook.sh`), which my runs had not: the
      suite and the matrix again with it, both Pythons, all passing; the
      installed ffman importable in pytest's phase by the install hook's
      `PYTHONPATH` export (`pypa-install-hook.sh`, traced); no test needs the
      network, git or `/usr/bin/env`. `installed.sh` piped metaflac into
      `grep -q`: under `pipefail` a match found still fails when the writer
      is cut off (shown: 141) -- now captured, then matched; a wrapper
      without metaflac fails it there. Decisions' header: `lint` once.*
- [x] 6.7.7 reviewed whole (owner's request). *Every name the section
      retired swept across the repository: decisions still said
      `ffmanRuntime` twice and that the wrapper sets the presets -- now
      `runtime` in `nix/packages.nix`, the presets a default (and a 6.7.3
      leftover there, a doubled parenthetical on the fonts' hashes, made
      one). `formatter` was `pkgs.nixfmt`, whose directory argument -- `nix
      fmt`'s -- nixfmt itself calls deprecated: now `nixfmt-tree`, treefmt
      over the same nixfmt 1.5.0 (its inputs read). `with pkgs;` and `with
      python3Packages;` made explicit references; `installed.sh`'s failures
      to stderr; three lines past 100 columns shortened (a fourth, a Nix
      string nixfmt keeps, left: rewriting it would change a derivation
      unbuildable here). Proven: of all 32 derivations, the six predicted
      changed (lint, the installed checks) and the rest identical;
      `installed.sh` again on both Pythons, its mutations failing it on
      stderr; `nix flake check --no-build`; nixfmt, shellcheck clean. Built
      by the owner, where cache.nixos.org answers: `nix build` and `nix flake
      check` clean.*
- [x] The presets in the wheel (the owner's decision: the packages go to PyPI too, where a
      Nix-built folder never reaches -- from PyPI, `--preset youtube` refused its normalising,
      `FFMAN_NORMALIZE_HOME is not set`). *Done: `ffman/normalize/` in the package, an
      `XDG_CONFIG_HOME` -- `ffmpeg-normalize/presets/youtube-aac.json` and its native twin,
      written from `nix eval` of the retired `nix/ffmpeg-normalize-presets.nix`, equal value for
      value (and to the presets the suite had run with); its comments now decisions' packaging
      paragraph. ffman's own when the variable is unset or empty, as its fonts -- one helper,
      `jobs/convert/carried.py`, hands both over: the package's folder, or a copy in the work
      directory where a zip holds it (fonts.py's copy loop now that helper's: OFL.txt copied
      with the fonts). The wrapper sets `PATH` alone; the checks and the dev shell set nothing.
      The outcome report names the commit's src `$SRC`. Proven: suite 1725 at 100% (1721, the
      three tests of `test_carried.py`, a naming case), every real normalisation -- the suite's
      and the matrix's M7 -- on the carried presets (the gate sets no variable); six mutations
      each failing a test (no default, a nested folder not copied, a zip read as a path, the
      twin drifting, a preset missing, the fonts' safe path dropped); ffmpeg-normalize 1.42 on
      each preset, no option skipped; the built wheel installed in a clean venv: a 44.1 kHz mono
      source normalised to AAC 48 kHz stereo, no variable set; ffman's sdist 1248 from
      extraction; outcome against HEAD 426 identical, one changed -- `env/no-normalize-home`,
      the refusal now the run; `nix flake check --no-build`, the presets in ffman's Nix source,
      the wrapper's arguments `PATH` alone.*
- [x] Platforms (the owner's decisions): Windows refused clearly, Apple silicon in the flake,
      a container image. *Done. Windows: `ffman/__main__.py`, the command's entry now
      (pyproject's scripts), checks the platform before importing the command line -- whose
      tool handling names SIGHUP, absent there: the import alone failed, a traceback (shown) --
      and refuses, pointing to WSL. The reasons, each from its source: process groups and
      `killpg` POSIX's, SIGHUP, SIGKILL, SIGPIPE Unix's (Python's documentation); `C:\` no
      filter-safe path; no `env`; ffmpeg-normalize's `%APPDATA%` (its `_presets.py`). macOS:
      `aarch64-darwin` in the flake's systems, every runtime tool available there (evaluated);
      Intel Macs left, nixpkgs 26.05 their last. Two tests read `/proc`, absent on macOS -- one
      would fail, the other pass on nothing -- now `ps` (`tests/support/processes.py`, nixpkgs'
      `unixtools.ps` in the checks), a zombie excluded as before (shown on procps); the signal
      test kills its tree when a check fails, which had waited out its 600 s sleeps (found by
      mutation). The image: `nix/image.nix`, `streamLayeredImage` -- ffman, its runtime, tini as
      PID 1, `/tmp` 1777, `HOME=/tmp` -- `packages.<linux>.image` on ffmpeg-full with FDK
      (`withUnfree`, the one package let through `allowUnfreePredicate`): built for the owner,
      never published (ffmpeg's configure: "nonfree and unredistributable"); `overlays.default`'s
      `ffman-image` on a consumer's ffmpeg-full. Proven: suite 1728 at 100% (1725, the two
      Windows tests -- in-process, and a fresh Python with SIGHUP, SIGKILL, SIGPIPE and `killpg`
      removed -- and the README's image tag held to the version), the matrix 770; mutations: the
      command line imported first, no check, a wrong tag -- each failing; the outcome report 427
      identical (the driver runs `python -m ffman`); the wheels installed in a clean venv, the
      script `ffman.__main__:main`; ffman's sdist 1251, ffmeta's 375, subverter's 55;
      `nix flake check --no-build --all-systems`: the three systems' checks, the image's closure
      one ffmpeg-full, `--enable-libfdk-aac --enable-nonfree`, with tini and ffman. Not here:
      building the image, and anything on a Mac -- the owner's, and 6.7.9's macOS jobs.
      Reviewed with the rename and the presets (owner's request): the flake's comment claimed
      the owner's whole tuning for the image (FDK alone is ffman's; the rest a system's, through
      `ffman-image`); the changelog measured the Windows refusal against a traceback, not the
      bash ffman; a test's comment sat on the wrong line; `ps`'s arguments a `Final` tuple; the
      Windows script's name told apart from the message's. Checked and sound: the image's
      closure follows its config (dockerTools' `closureRoots`: the base JSON), its `/tmp` mode
      kept (the layer tarred as built); a passing signal test's cleanup a no-op (`Popen.kill`
      polls first). Suite 1728 again at 100%; `nix flake check --no-build --all-systems`.*

*6.7.8 Into nixos-config*

- [x] `inputs.ffman` (`inputs.nixpkgs.follows = "nixpkgs"`), its package in
      the system's through `overlays.default` (the system's ffmpeg-full, FDK
      kept; 6.7.7); `tools/ffman`, ffman's part of `pkgs/default.nix`, its
      checks and its dev shell removed; nixos-config's own references to it
      (`AGENTS.md`, 07-tools' section, the doc map and review maps under
      `.agents/review/`) pointed at the new repository. Its home presets stay
      its own (`home/ffmpeg-normalize-presets.nix`, its values unchanged: the owner's
      decision, 6.7.7). `test_mpv_conf` re-homed here -- it holds
      `home/config/mpv.conf` to ffman's style -- reading ffman's package,
      `mpv.conf` in its fileset. ffman's skills -- `cue`, `ffmetadata`,
      `vorbiscomment` -- removed from nixos-config's `.agents/skills/` (they
      live in ffman's: the owner's decision; `map-project`, generic, stays),
      with its index's, `AGENTS.md`'s and the review checklist's references
      to them pointed at ffman's repository. Proven: the flake evaluates, the
      system's closure holds `ffman`. *Done, on nixos-config at its last delivered
      commit (253c5eb; its own history never rewritten). The input named for the repository,
      `ffsuite`, `nixpkgs` followed; locked by hand at the pushed commit (dd0e31a) -- its NAR
      hash computed from the commit's tree, as GitHub's tarball unpacks (shown on the eleven
      other GitHub inputs: each git tree's NAR hash equal to its lock's), and `nix flake lock
      --offline` leaves the file unchanged. `modules/tools.nix` applies `overlays.default` and
      selects `pkgs.ffman` (the media set). nixos-config's checks re-export ffsuite's on the
      system's Python (`-py` from `python3.pythonVersion`, refused if ffsuite has none):
      `ffman-tests`, `-matrix`, `-installed`, `-types`, `-vulture`, `-lint`. Removed:
      `tools/ffman`, ffman's part of `pkgs/default.nix` (now nixfmt-clean, the one construct
      that was not gone with it), its export and dev shell, the three skills (each file
      byte-identical here) and ffman's five plans (here: one identical, four edited since);
      the 07-tools section's 61 decision areas each found in `decisions.md`. `test_mpv_conf`
      re-homed as `tests/mpv/` with its check (`mpv-conf`): its imports were stale --
      `Transcript` and `Chunk` are subverter's now (shown: it failed to import against this
      ffman) -- and its skip gone (the file is always there). Found by its blast radius: the
      evaluation harness (`scripts/eval-report.sh`) clones and overrides every input and
      builds a wrapper flake that passes its own `inputs` to the modules -- without ffsuite
      there, every variant would fail; added. The ISO carries every lock node (13 now, 8
      direct; `ffsuite` among them, evaluated) -- its counts and the installer's and harness's
      comments follow. Run-book 11.49's ffman facts moved to `docs/upgrading.md` (blur-edges'
      fetch and mpv's defaults stay nixos-config's), the item put back in section 11 (it sat
      under 12) and 6.5 counting `ffsuite` among the inputs a channel moves. Proven, offline,
      each input admitted by its lock's NAR hash (nixpkgs' already in the store, the rest
      fetched by git): every check, package and dev shell evaluates on both systems; the five
      hosts' toplevels; on each media host and both generic ISOs, `ffman-0.1.0` on the
      system's own `ffmpeg-full` (the same derivation, `--enable-libfdk-aac`); the ISOs with
      their inputs as store paths (their `fetchTree` needs network here, and fails alike at
      253c5eb); harness cells (a tool, the hostname seed, three x86 variants) passing; the mpv
      test against this ffman, from a read-only copy of its check's fileset, and failing on a
      mutated `mpv.conf`; review maps regenerated (their selftest passing; at 253c5eb they had
      been current). `nix flake check` whole exceeds this sandbox's memory, at 253c5eb too:
      the owner's to run, with the build. Reviewed (owner's request): the checks' bindings
      named for what they hold (`ffsuiteChecks`, `pythonSuffix`), the guard shown refusing a
      Python ffsuite lacks; a blank line the removal left in `pkgs/default.nix` gone;
      `docs/upgrading.md` made a numbered list, its words unchanged (compared). Checked and
      sound: nothing else names `tools.ffman` or the input; the installer's lock rewrite takes
      every manifest node, `ffsuite` with them; no ignore file, formatter or task runner named
      ffman.*
- [x] 6.7.8 reviewed whole (owner's request). *Both repositories swept together, the record's
      counts and references re-proven, two corrected there: of ffman's five plans one is
      identical here and four edited since (hashed), and eleven inputs were compared by git
      tree -- nixpkgs' source was already in the store, admitted, as each, by its lock's NAR
      hash (its fixed-output path present). `decisions.md` now says the 07-tools section
      points here. Re-proven: the lock's 13 nodes, 8 direct; no tracked nixos-config file
      names `tools/ffman`, `ffmanEnv`, `ffmanRuntime`, `devShells.ffman` or the moved plans
      but the review maps' history; ffsuite's references into nixos-config (flake, packages,
      the skills' index, `docs/upgrading.md`) accurate; nixos-config's lock still at dd0e31a
      (ffsuite's later commits: docs, and ruff told to skip them; `nix flake update ffsuite`
      the owner's, after the push); the bundle reproduces nixos-config's tree on 253c5eb.*

*6.7.9 Its tooling* (adapted from csan and imi; each file its source)

- [x] Workflows: `checks.yml` (csan's: uv, `uv sync --locked`, ruff,
      basedpyright, ty, vulture, pytest; 3.13 and 3.14; `uv lock --check`),
      `nix.yml` (`nix flake check` on Linux and on macOS, Apple silicon: the
      ffmpeg-bound tests, the matrix, the
      outcome report -- they need the pinned ffmpeg 8.1.2, not a runner's
      `apt` one; `checks.yml` runs the rest), `dependency-review.yml` (imi's; paths
      `pyproject.toml`, `uv.lock`, workflows), `dependabot-automerge.yml`
      (imi's; guard `veramachine/ffsuite`), `security.yml` (imi's audit as
      pip-audit on `uv export`: daily, and on the lock),
      `style-check-cocogitto.yml`, `style-check-dprint.yml` (imi's),
      `release.yml` and `publish.yml` (a package's tag, `ffmeta-v1.2.0`:
      `uv build --package`, `uv publish`, Trusted Publishing).
      *Done: the nine, each headed by its source and what it changed, and
      `.github/package-tag.sh` -- a tag read as its package, its version checked against that
      package's `pyproject.toml` -- shared by `release.yml` and `publish.yml`. Every action
      pinned to a commit, its release in a comment (setup-uv's own README; setup-uv publishes
      no floating tag past `v7`, measured; Dependabot moves both, the next box). Changed from
      the box, each for a reason found: ty runs advisory, `continue-on-error`
      (`ffman-python.md` §6: never failing the build until 1.0 is in the pin; its two
      diagnostics, `fonts.py:44` and the outcome driver's `fsdecode`, left, `[tool.ty.src]`
      excluding `.agents` and `docs` as ruff does); `dependency-review.yml` watches the
      workflows alone (GitHub's dependency graph reads no `uv.lock`: its ecosystems list pip, pipenv
      and Poetry files; corrected after 6.7.11: Dependabot's graph jobs submit it since 2026-04-23,
      GitHub's changelog -- seen on `main` alone, a pull request's change unmeasured), the lock
      pip-audit's; cocogitto checks a push's whole history, not `--from-latest-tag` (no tag yet: cog
      7.0.0, the action's, stops "unable to get any tag", measured; every commit is conventional); a
      release's notes are the commits touching its package since its previous tag (`git log`; cog's
      changelogs are the third box's -- superseded there: the tag's changelog section); pip-audit
      pinned in an `audit` group (2.10.1, nixpkgs' 2.10.0 in the next box; the lock grew by it), run
      `--isolated`. Proven, `checks.yml`'s steps as written, on uv's
      3.13 and 3.14 with a `PATH` lacking ffmpeg and metaflac, as the runner's image (its
      software list): lock checked, ruff, basedpyright 0 errors, vulture, pytest 1411 passed,
      the same with an apt ffmpeg 6.1 on `PATH` instead. The outcome job's command (uv in
      place of the dev shell) against `HEAD`, with ffmpeg 8.1.2: 427 identical; again from an
      environment of the workspace's packages alone (`--no-dev`), against the commit before.
      `nix develop ../..` from `packages/ffman` resolves to the repository's flake; its checks
      evaluate on x86_64-linux and aarch64-darwin, 11 each. pip-audit over the exported lock
      (45 packages): no known vulnerabilities, `.venv` untouched. On test tags: a match prints
      the package, a version or a package not the tree's is refused; the notes start after the
      package's own previous tag; `uv build --package --no-sources` builds that package alone,
      twice byte for byte alike. actionlint 1.7.12 with ShellCheck: clean. Not reachable here:
      a run on GitHub (after the push); `style-check-dprint.yml` passes only with the third
      box's `dprint.json`; macOS's flake check is 6.7.10's. Reviewed (owner's request): `-m
      "not ffmpeg"` left 94 tests needing a pin -- taking the `ffmpeg` or `metaflac` fixture
      unmarked, they skipped only for want of a tool, and an apt ffmpeg 6.1 on `PATH` made 83
      of them errors; both conftests now mark `ffmpeg` every test taking either fixture,
      directly or through another (a hook, `tryfirst`, before `-m` deselects; ffmeta's and
      ffman's held identical by `test_workspace`; the marker's text names both pins, ffmeta's
      pyproject declaring it as the root's does) -- now 1087 deselected, 993 before; removing
      a hook brings the errors back (76 in ffman's own run); AGENTS.md names `-m "not ffmpeg"`
      for a host's own tools. `uv publish --trusted-publishing always`: a missing publisher
      fails as one. The outcome job syncs `--no-dev`. Dependabot moves a commit pin and its
      comment on the same line (its documentation). Amended (owner's request): a runner checks
      its own system alone (`nix flake check` says so: "Use '--all-systems' to check all"),
      and aarch64 Linux had none -- nixos-config's aarch64 ISO installs ffman.
      `ubuntu-24.04-arm` joins the flake check's matrix (16 GB, 4 CPUs for a public
      repository: GitHub's runner reference; install-nix-action's own tests run there), and a
      job evaluates every output of all three systems, building nothing: 13 s here; a break
      thrown on aarch64-linux alone passed the default check and failed this one (measured).*
- [x] `dependabot.yml`: `uv` and `github-actions` (imi's schedule, groups,
      cooldown, labels, `chore` prefix). Issue templates (bug, feature,
      documentation, `config.yml`) and the PR template, imi's, adapted.
      *Done, `github-actions` alone (the owner asked whether uv belongs): every pin in the
      dependency groups is the pinned nixpkgs' version (all thirteen evaluated equal;
      pip-audit moved to nixpkgs' 2.10.0 to join them), so uv's verdict is Nix's -- a
      Dependabot bump would break that, and `dependabot-automerge.yml` would merge it (since the
      owner's branch protection, the required flake check fails it at `pins`: 6.7.11). They
      move at a nixpkgs bump instead (`docs/upgrading.md`, a new 22), held there by a new
      check, `pins` (`nix/checks.nix`: each pin against `python3Packages`, or nixpkgs'
      application -- basedpyright, ruff, ty, pip-audit; a spec not `name==version` refused at
      evaluation): empty now on x86_64-linux and aarch64-darwin; three pins moved, three
      named; its script failing on any, passing on none. nixos-config re-exports it not (its
      filter: the system's Python and `lint`, evaluated), so its channel never fails on
      ffsuite's dev pins. `security.yml` still audits them daily. imi's schedule, group (minor
      and patch together, which the auto-merge takes -- fetch-metadata gives a group its
      highest update type -- a major alone), labels (the owner creates them: one undefined is ignored -- Dependabot's options reference), `chore(deps)`
      commits (conventional, scoped) and cooldown (`default-days` alone: GitHub Actions takes
      no semver keys). Templates from imi's, their fields ffsuite's: the package and version,
      the install, ffmpeg's version, `--dry-run`'s commands, ffprobe's view of the input; a
      feature against the spec; the pull request's checks by AGENTS.md's -- its contract
      (CHANGELOG, a failing test, a decision) and the outcome report. `dependabot.yml` and
      `config.yml` valid by SchemaStore's schemas (a wrong value refused); the three
      templates' front matter parsed. Asked too: whether CI could take apt's ffmpeg -- no: the
      tests hold ffmpeg 8.1 and FLAC 1.5, and Ubuntu has 6.1.1 and 1.4.3 (24.04,
      `ubuntu-latest`), 8.0.1 and 1.5.0 (26.04) (packages.ubuntu.com) -- nor its build
      (nixpkgs' `ffmpeg-full` is what the suite measures); nix.yml runs them on the pin. Found
      on the way: AGENTS.md's markers rule still said `ffmpeg` runs ffmpeg (the last box's
      hook) -- now the pinned tool, by hand or by fixture; and `package-tag.sh` joins `lint`'s
      shellcheck.*
- [x] `CONTRIBUTING.md` imi's, its tools ffman's (uv, just, Nix); `cog.toml`
      imi's with `[packages]` for the three (their own tags); `dprint.json`
      imi's, excluding `docs/ffman-python.md` (a finished record it cannot
      round-trip: a line's `>=` read as a quote, `> =`; measured); the
      `justfile` (csan's groups and aliases, imi's `checks`, `cog`,
      `dprint-check`, `audit`, `release`); `.pre-commit-config.yaml` (ruff,
      dprint, `uv lock --check`, cocogitto's commit-message check).
      *Done, on nixpkgs' tools (just 1.51.0, cocogitto 7.0.0, pre-commit 4.5.1, dprint 0.54.0,
      git-cliff 2.13.1). `dprint.json`: the plugins at their latest, markdown 0.26.0 and toml
      0.9.0 (the owner's, over imi's 0.22.1 and 0.7.0; 0.26.0 joins a line opening `--` or a list
      marker to the one before: three such lines broken earlier; `ffman-python.md` still
      excluded, `>=` still `> =`; `just dprint-update`), asterisk emphasis (the repository's),
      four-space TOML (uv's); the four pyproject files re-indented, their data equal; clean on
      dprint 0.54.0 and 0.60.1 (the action's); an exclusion holds for a path given
      (pre-commit's). `cog.toml`: cocogitto's tables are strict, so `[monorepo.packages]`
      (`[packages]` refused); `from_latest_tag` off (no tag: `cog check` stops); no global tag;
      cog's changelog off; bumps from `main`; the bump's hooks, run in the package's folder, their
      changes in its commit: `uv version --no-sync` (it re-locks), the changelog, and
      `test_workspace`. Found: uv locks a workspace member without ffman's specifier, so ffmeta
      bumped past ffman's `<0.2` locked (measured); `test_workspace` now holds ffman's range to
      each library's version (three mutations); a failing hook stashes its changes, nothing
      committed. `justfile`: csan's groups and aliases (its `lintr`, a typo, and `ruff` for
      `format` dropped), the workflows' commands under `uv run --locked`; `checks` as
      `checks.yml`, the matrix, dprint, cog, pip-audit; `nix` all systems evaluated, then this
      one's built; `release PACKAGE major|minor|patch` refuses, before the checks, off `main`,
      dirty, behind `origin`, or below the package's version (cog counts from 0.0.0: a first
      `patch` gave 0.0.1, measured), then bumps, tags annotated (`--follow-tags` skips
      lightweight tags) and pushes atomically; `changelog PACKAGE` previews the next section.
      `.pre-commit-config.yaml`: local hooks on tools pinned already (no second pin);
      `default_stages` (unset, every hook also ran at the message's stage); each hook failed by
      its mutation; a message from the editor, git's comments in it, verified; a merge's passed.
      `CONTRIBUTING.md` imi's sections with the release's rules; AGENTS.md's checks through
      `just`; the README links it. Changelogs, the owner's (review): generated by git-cliff,
      never written. `cliff.toml` (csan's grouping by type, imi's header): one per package,
      `just changelog` giving its paths and tags; breaking changes first (`!` or a
      `BREAKING CHANGE` footer, a mutation each), chores, CI, formatting and cog's ignored commits
      (merges, fixups) skipped, a scope kept, no case changed (`ffmeta's` stays). The file is
      regenerated whole at each bump: a function of the history. git-cliff is a `release` group's
      pin, nixpkgs' version (`pins`, a mutation).
      `release.yml`'s notes are the tag's own section of its `CHANGELOG.md`, refused if its
      heading is not the tag's version -- not git-cliff's `--current`, which fails on a tag once a
      later one exists, nor `git log`. ffman's curated CHANGELOG, the port's record, is
      `docs/ffman-from-bash.md`, finished; the contract's changelog line is now a `feat` or `fix`
      commit (AGENTS.md, the PR template, §1 here); `dprint.json` excludes the generated files;
      the libraries name their changelog. Proven on a clone with a bare remote: ffmeta's first
      `minor` 0.1.0, its `CHANGELOG.md` new in the bump's commit; `patch` 0.1.1, its section
      first, `chore(version)` and merges absent; ffman's 0.1.0, cog writing no changelog of its
      own; `minor` refused by `test_workspace`; each refusal before the checks. `just checks`:
      1730 and 770 passed, 100%; `nix flake check --no-build --all-systems` and actionlint clean.
      Reviewed, the section whole (the owner's): uv floated in the workflows (setup-uv's latest)
      while every other tool is nixpkgs' (but dprint's CLI, the action's latest: the plugins format) -- now `required-version = "==0.11.21"`, which setup-uv
      installs and `pins` holds (two mutations; another uv refuses, naming the one to install);
      a squash merge of two commits or more takes the pull request's title as its commit (GitHub's
      default), an unchecked changelog entry -- the title is now `cog verify`'d, on an edit too,
      through the environment (a `$(...)` title runs nothing, measured); git-cliff's call, a
      script no workflow ran, is the `changelog` recipe the hook calls; `release.yml` clones
      shallow, its notes no history's; the PR template names `just checks`. Proven again: the
      release flow on a clone, `just checks` (uv 0.11.21) as above. Against
      rust-template (the owner's): `CODE_OF_CONDUCT.md` as its own, rendered;
      `SECURITY.md` adapted (each package's latest tag, Python's and ffmpeg's
      versions in a report); each changelog heading links its compare view
      (`cliff.toml`'s `[remote.github]`, read offline), `release.yml`'s check
      following -- measured on a clone with two tags.*

- [x] The owner's, outside any file: the GitHub repository and its settings
      (auto-merge allowed, branch protection requiring the checks, a `pypi`
      environment, private vulnerability reporting -- `config.yml`'s link; squash merging's
      default message the pull request's title, checked conventional); on PyPI, a pending
      Trusted Publisher per project
      (`ffman`, `ffmeta`, `subverter`: repository, workflow, environment).
      *Corrected by 6.7.11 (GitHub's and PyPI's documentation): each package's 0.1.0 is on PyPI
      already, published by hand on 2026-10-07 -- a build at 89d5487 byte-identical to all six
      files (measured) -- so a Trusted Publisher in each project's own Publishing settings, not
      a pending one. In order, after the push: (1) each package's `<package>-v0.1.0`, annotated, at the last
      commit touching its folder before 89d5487 -- ffman 33b6f55, ffmeta 71688f8, subverter
      6827d02, each building PyPI's files byte for byte (measured): at 89d5487 itself, which
      touches none, git-cliff's `--include-path` lost the tag (no 0.1.0 section, 6827d02 listed
      under 0.2.0; measured) -- Release and Publish disabled meanwhile (no changelog then for
      release.yml; PyPI holds the files). cog counts from there, and `just release` now refuses a
      version not above the package's: a first `minor` gave 0.1.0 again; (2) Settings > General: squash
      merging alone, its default message "Pull request title"; auto-merge allowed; (3) the labels
      `dependencies` and `actions`; (4) Settings > Branches, a classic rule on `main`: a pull
      request, no approvals, and the checks once each has run -- `Checks (Python 3.13)`, `Checks
      (Python 3.14)`, `nix flake check (ubuntu-latest)`, `nix flake check (ubuntu-24.04-arm)`,
      `nix flake check --all-systems (evaluation)`, `Check Conventional Commits` (unrequired, a
      bad title merges, and fails every later push's whole-history check), and
      macOS's once green; bypass left allowed (`just release` pushes to `main`); (5) the `pypi`
      environment, its deployments the three tags' patterns; (6) Advanced Security > private
      vulnerability reporting; (7) on PyPI, each project's publisher: `veramachine`, `ffsuite`,
      `publish.yml`, `pypi`; (8) the releases (below); (9) nixos-config's `nix flake update
      ffsuite`. Not needed, contrary to `dependabot-automerge.yml`'s first header: Actions' write
      permissions and its "create and approve pull requests" -- the workflow's `permissions:`
      override the default, and it creates and approves nothing. The releases: ffmeta none
      (nothing since 0.1.0); subverter `minor` (72310dc, `feat`), ffman's range first widened to
      `<0.3`; then ffman's lower bound raised to `>=0.2` -- found by 6.7.11's review: HEAD's ffman
      imports `subverter.markup.decoded`, which 0.1.0 lacks, and `>=0.1` let pip install it
      (measured, an `ImportError`; CONTRIBUTING.md's new rule) -- and ffman `patch`.*
      *Progress (2026-10-09), as seen from here: `main` pushed (3d908be), every workflow run on it,
      macOS's flake check among them; the labels exist; private vulnerability reporting is on (the
      Security page's "Report a vulnerability"). The owner reports the settings, the environment and
      PyPI's publishers done -- not visible without signing in. Not yet: the 0.1.0 tags (none on
      the remote), so the releases (PyPI holds 0.1.0 alone), and nixos-config's update.*
      *Closed (the owner's decision): publishing through the workflows waits for the next release
      -- the tags, the release order and its proof are 6.7.12's box.*

*6.7.10 Proven*

- [ ] In `veramachine/ffsuite`: the suite at 100% per package, the matrix, ruff,
      basedpyright, vulture; the outcome report against nixos-config's last
      ffman commit -- identical but 6.7.2's and 6.7.3's changes, each listed;
      `nix flake check`, on Linux and on a Mac -- macOS claimed (READMEs,
      classifiers) only once its checks pass; each package built (`uv build`)
      and installed in a clean venv, `ffman` run with only ffmpeg on `PATH`;
      the image built and run (the owner's: `docker load`, a conversion).
      *Done here, at 0dbcd34 (x86_64 Linux): `just`'s recipes on 3.13 and 3.14 with the pins on
      `PATH` (ffmpeg 8.1.2, FLAC 1.5.0, ffmpeg-normalize 1.37.7, nixpkgs' versions) -- lock, ruff,
      basedpyright, vulture clean; 1768 passed at 100% line and branch (every file); the matrix,
      770; dprint, cog, pip-audit clean; `nix flake check --no-build --all-systems` passes. The
      outcome report against 253c5eb (nixos-config's last `tools/ffman`, which holds 6.7.2 and
      6.7.3 already -- the box's "but 6.7.2's and 6.7.3's" was wrong): 425 identical, 4 changed,
      each a recorded change -- `cli/version` 2.0.0.dev0 to 0.1.0 (6.7.5), `env/no-normalize-home`
      refused to run on the carried presets (6.7.7), `attach/references` and
      `burn/hostile/references.vtt` decoded (6.8.1's fix). Built (`uv build --all-packages
      --no-sources`), installed offline from the six files into a clean 3.14 venv, run with
      ffmpeg and ffprobe alone on `PATH`: `--version`, a burn of an SRT and of a VTT, a GIF (noted
      unoptimised), and the refusals README.md's tools table names (`env not found` for
      `--preset youtube`; with `env`, its own line naming ffmpeg-normalize, then the refusal).
      Left, the owner's: `nix flake check` built on Linux and on a Mac (nix.yml, after the push:
      no binary cache reachable here), and the image.*
      *The owner's (2026-10-09): `nix flake check` and `just checks` clean on their NixOS machine.
      Left: the Mac's -- nix.yml ran it on 3d908be, its result not visible here -- and the image.*
      *Again at 35c1760 (6.7.11's changes in), on 3.14 with the pins: lock, ruff, basedpyright,
      vulture clean; 1768 passed at 100%; the matrix, 770; dprint, cog and the evaluation of all
      three systems clean. macOS stays "not yet tested" in both READMEs until its result is seen.*
      *macOS (2026-10-10): nix.yml's `nix flake check (macos-latest)`, aarch64-darwin, the
      suite on 3.13 and 3.14, the matrix and the installed binary, passed at fbfb3fb, 8edd92e and
      55580ae (#8 to #10); at 6b6dbb0 (#11), with the same code, one case failed: a TERM'd tree
      not gone within 1 s, on a builder running the suite and the matrix at once. The test's
      bound is 2 s now: the KILL path takes at least 3 s, so it still tells the two apart. The
      READMEs drop "not yet tested". Left: the image, run (the owner's).*

*6.7.11 Review*

- [x] The section reviewed whole.
      *Done (three independent reviews -- 6.7.1-6.7.5, 6.7.6-6.7.8, 6.7.9 -- each claim against
      the repositories, findings re-verified, then fixed or recorded). Release: each package's
      0.1.0 published by hand left the release flow re-issuing 0.1.0 (the owner box, corrected
      above; `just release` refuses a version not above the package's, CONTRIBUTING.md's rules);
      ffman's `subverter>=0.1` admitted a release without `decoded` (measured: `ImportError`) --
      the owner's release order. Packaging: `hatchling>=1.27.0` in the three (1.26.x wrote
      metadata 2.3, no `License-Expression`: measured); subverter's summary names whisper-cli's
      and WhisperX's JSON. CI: `dependabot-automerge.yml`'s settings (two unneeded, approvals
      none, a merge by its token runs no workflow), the commits' check required, a run on `main`
      never cancelled (a pending one could still give way: the second note), dependency review in
      effect a licence check (commit-pinned actions get no advisories), dprint's CLI the action's
      latest -- each said where it lives.
      Tests: ffmeta's oracle tools held to ffman's by every name it carries (a rename now fails:
      mutation). Documents: `decisions.md`'s floor (100% measured, 95% the floor) and `pins`;
      AGENTS.md's library-tests row; `image.nix`'s comment (the overlay's `ffman-image` refused,
      no `.#image` off Linux); nixos-config's comment on `pins` not re-exported; this record --
      the intro's history (published fresh, 6.7.4), the fonts 277 kB, the coverage floor's
      wording, hatchling, Dependabot's labels (the owner's to create), the home presets (their
      values unchanged), three citations 6.7.4 that are 6.7.5's. Since, unrecorded until now:
      `syrupy` left the dev group (7987ee3); `types-py314` checked 3.13 until `--pythonversion`
      (56324b0, the image `buildLayeredImage` with `.#image.stream` there too). nixos-config still
      locks ffsuite at dd0e31a (6.7.8, by hand): its update is the owner's. Not changed: the
      GitHub release and PyPI each build their own files (hatchling floating; reproducible at one
      version, measured -- one build since: the second note), a library's own tree's coverage held
      by no check (100% measured).*
      *Reviewed again, to convergence: four independent reviews at 099dfc8 -- the fixes above;
      packaging and the release, simulated end to end on a clone with a bare remote; CI and
      Dependabot; Nix, tests and documents -- then two reviews of their fixes; each finding re-verified,
      then fixed or recorded. Release: `release.yml` merged into `publish.yml` -- the package built
      once, without a credential to write or to mint (PyPI's security model, "Limit the scope of
      your publishing job"), published by PyPA's action with its attestations, then its GitHub
      release of the same files, ffman's alone the latest. `just release` pushes `main` and its
      own tag alone (`--follow-tags` took the local 0.1.0 tags too, and more than three tags at
      once start no workflow: GitHub's push event), and refuses a package whose current version's
      tag is not on `origin` (untagged, a `major` gave 1.0.0) and, for ffman, a library whose
      source is not its latest release's or a floor below that release's minor -- each refusal
      measured on the clone; a bump rewrites the README's `ffman:<version>` (an ffman release
      failed `test_readme` on `main`, measured); `packaging` declared in the dev group, nixpkgs'
      26.1. CI: a pull request's runs one concurrency group, every other run its own (a pending run
      on `main` gave way to the newest, and fork branches of one name shared a group); comments
      made exact -- `github.actor`, a PAT or an App's token, the cooldown's default, Dependabot's
      uv (0.12.19 in its image) refused by `required-version`, a schedule disabled after 60 days
      without activity. Dependabot, the owner's question: GitHub Actions alone -- the packages
      need nothing at run time, and every dev pin is nixpkgs', which `pins` holds against any bump;
      Dependabot alerts recommended on (the owner's setting), its graph jobs reading `uv.lock`.
      Documents: `upgrading.md` -- the lock kept at nixos-config's node and moved with it, a 24th
      item (ffmpeg's and FLAC's versions in the tests, the documents and the skills'
      measurements); `decisions.md` -- the FDK sentence, nixos-config's mpv test; AGENTS.md's
      `markup.py` and `flac.py`; this record (6.7.9's superseded lines, 6.7.12's tags and
      `Changelog` links, §9.1's tag); nixos-config's `07-tools.md` (when its ffsuite pin moves)
      and run-book 11.49 (the six checks). The templates took the same CI corrections. Left, the
      owner's: nixos-config following ffsuite's `main` or, after 6.7.12, its tags (§9.1 asks it of
      imi); python-template's release and publish, still two builds. 6.7.10's open parts are the
      owner's results, reviewed when they come.*

*6.7.12 The first release through the workflows* (the owner's, at the next release: deferred
from 6.7.9)

- [ ] Each package's 0.1.0 tagged (annotated) at the last commit touching its folder before
      89d5487 -- ffman 33b6f55, ffmeta 71688f8, subverter 6827d02 -- and the three pushed with the
      workflows `Publish` and `Release` disabled (CONTRIBUTING.md); then subverter's release --
      HEAD's ffman imports `subverter.markup.decoded`, which 0.1.0 lacks -- ffman's floor raised to
      it, `just release ffman` refusing it left undone; then ffman's release; ffmeta has nothing
      new. Proven:
      `publish.yml`'s three jobs green, PyPI's files the tag's build with their attestations, the
      GitHub release the same files and its notes the changelog's section, and a clean venv's `pip
      install ffman` importing. Until each package's release, its `Changelog` link (PyPI's 0.1.0
      page, the README) finds no file: git-cliff writes it then -- ffmeta's at its first release.
      *Progress (2026-10-09): the three 0.1.0 tags on `origin` at those commits; `Publish` ran
      for none (disabled), `Release` -- gone from `main`, so not disabled -- ran for each and
      failed at its notes, as expected (no changelog at those commits): no GitHub release, PyPI
      unchanged (0.1.0 alone). Next: subverter's release, then ffman's.*
      *Progress (2026-10-10): subverter `patch` (the owner's: 0.1.1, 72310dc's `feat` in 0.x)
      tagged and pushed; `Publish` #1 built, then its PyPI job was refused -- "not allowed to
      deploy to pypi due to environment protection rules": the `pypi` environment's deployment
      rules must admit the tags, each rule's ref type Tag (`ffman-v*`, `ffmeta-v*`,
      `subverter-v*`); then "Re-run failed jobs". Found with it: `just release ffman` held ffman's
      floor to a library's minor, so `subverter>=0.1` passed while 0.1.0 lacks `decoded` -- the
      floor is now the library's release, patch included, and ffman's `>=0.1.1` (dc7e051). And
      the owner's: `just release` runs no tests (CI's verdict on origin's `main`, which it now
      requires HEAD to be); ffman's range checked before the bump, cog's test hook gone (c490655).
      Proven on a clone against a bare remote: a floor of 0.1, a subverter `minor` outside `<0.2`
      and an unpushed commit each refused before anything is written; at dc7e051, ffman 0.1.1
      released in 8 s, its changelog's section and tag pushed.*
      *And found: the release checked a library's tag, never PyPI -- with subverter-v0.1.1 tagged
      and its upload refused, ffman's would have published a wheel no pip can install. `just
      release ffman` now asks PyPI's Simple API (PEP 691's JSON) for each library's release, a
      file not yanked, and refuses a range that excludes it. Proven against a local index: a
      release published, missing, yanked alone, an sdist alone, an unknown project and a server
      error, and a range excluding the release or a floor below it, each as expected. The index
      is `RELEASE_INDEX_URL`'s (PyPI's by default), as python-template's workspace release asks
      it too.*
      *Progress (2026-10-10, the owner's): ffmeta 0.1.1 (8edd92e) and ffman 0.1.1 (6b6dbb0, its
      floors `ffmeta>=0.1.1`, `subverter>=0.1.1`) released after subverter's; `just release ffman`
      passing means subverter 0.1.1 was on PyPI by then. `Publish` #3 (ffman-v0.1.1): build, PyPI
      with its attestations, GitHub release, all green. Left: a clean venv's `pip install ffman`,
      and nixos-config's `nix flake update ffsuite`.*

*6.7.13 The image published* (the owner's proposal, 2026-10-10)

- [ ] `.#image-free` (Linux's): the flake's own `ffman`, nixpkgs' ffmpeg-full -- no FDK
      (`withUnfree ? false`, so `withFdkAac` off: `generic.nix` at 4c78701), its licences LGPL and
      GPL -- published by `image.yml` on ffman's tag to `ghcr.io/veramachine/ffman`, amd64 and
      arm64, `<version>` and `latest`; `.#image`, FDK's, stays its user's to build. The OCI labels
      (title, description, version, source: ffman's `Repository`); no licences label, ffman's
      would misstate ffmpeg's. Proven: the flake evaluated for all three systems (`nix flake
      check --no-build --all-systems`); the free image's labels in its derivation; its ffmpeg's
      licences `lgpl21Plus gpl2Plus lgpl3Plus gpl3Plus`; `image.yml` by actionlint. Left:
      `image.yml` run by hand on `main` (built and run on both architectures), then ffman's
      release publishing it, and the package made public (GHCR's default is private).
      *Found: FDK's library is still in the free image's build graph -- pipewire's and
      gst-plugins-bad's input (via openal-soft, SDL), never ffmpeg's; nixpkgs gives FDK-AAC free
      and redistributable, and cache.nixos.org holds it. Whether it is in the image's runtime
      closure needs a build.*
      *Progress (2026-10-10): `Image` #1 (ffman-v0.1.1) green, built and run on both
      architectures and joined as `ghcr.io/veramachine/ffman:0.1.1` and `latest`. Left: the
      package made public.*

**6.8 Subtitle formats** (each into each other; research and skills before code, as 6.6; G4 each)

Converted into one another, every direction: SubRip (`.srt`), WebVTT (`.vtt`),
ASS (`.ass`), whisper-cli's and WhisperX's JSON (`.json`: `-oj`'s
`transcription[]`, WhisperX's `segments[]`) and whisper-cli's full JSON
(`-ojf`: tokens and their DTW times) -- by chunk or, where the source times
them, by word. Today ffman reads all but ASS (`subs/readers`: chunks and
words, integer ms) and writes SRT (`subs/srt.py`) and its burn's styled ASS.

Decided too (the owner's, 2026-10-09; each tool's writer its source: whisper.cpp's
`examples/cli/cli.cpp`, WhisperX's and OpenAI whisper's `utils.py`):

- CSV, TSV and LRC, sources and targets. ffman reads all three already: whisper-cli writes
  `-ocsv` (ms) and `-olrc`; WhisperX and OpenAI whisper write TSV (ms). CSV and TSV writers
  round-trip a chunk exactly; LRC keeps no end time, so its writer comes last.
- Plain text, a target alone: whisper's `-otxt`, a transcript's words without times.
- OpenAI whisper's JSON: WhisperX's `segments[]` shape, read already -- named by the research.
- SSA (v4): read through the ASS reader, as ffmpeg's `ass` demuxer reads both; never written.
- Left out unless a need comes: TTML/DFXP, SCC, SAMI, SubViewer, MicroDVD, SBV, WhisperX's
  Audacity labels.

*6.8.1 Research* (no code; each box's findings the next boxes' sources)

- [x] Measured first, before choosing (the owner's question): ffmpeg 8.1.2
      against ffman's own readers, on SRT, VTT and ASS inputs built to probe
      timing, formatting, line breaks, `&` and `<`, styles, positions,
      speakers. ffmpeg converts all six ways among SRT, VTT, ASS, but: its
      VTT writer leaves `&` and `<` unescaped (invalid WebVTT; read back,
      `A & B < C` lost `< C`) -- unrepairable after, a literal `<` and a tag
      alike; into ASS, start and duration rounded apart (an end +-10 ms);
      down-conversion drops VTT speakers, classes, cue settings and ASS
      positions, colours without a word; it reads LRC, not JSON, CSV, TSV.
      ffman's readers (`subs/readers/`: SRT, VTT, LRC, CSV, TSV, JSON; no
      ASS; writers `ass.py` for burning, `srt.py` for `--add-subs`, no VTT)
      keep milliseconds and text exactly, join lines (made to re-wrap), and
      carry tags as raw text. *Recommended (owner to confirm): ffman's own
      converter on a cue model keeping line breaks, formatting, speakers --
      ffman must parse every input to note what is lost, its VTT writer
      must be its own, the transcripts need its readers; ffmpeg the oracle
      where it is right. Skills first: SRT, WebVTT, ASS.*
- [x] Found by that measurement, an older defect: a burned VTT shows its
      escapes -- `A &amp; B &lt; C` on screen (shown: the job's own ASS).
      ffman's VTT reader decodes no character reference, nor does anything
      after it. To fix first, its own box: proven by a burned frame's ASS.
      *Done: the W3C spec's tokenizer reads `&` as HTML's character reference
      (not a list; ffmpeg 8.1.2's decoder knows six), in the runs between
      tags. subverter's `Reading.has_references` (`.vtt` alone: SubRip has
      none, ffmpeg's subrip decoding none) and `decoded` (`html.unescape`,
      a decimal of more than 7 significant digits U+FFFD unread -- Python's
      int refuses past 4300 digits); ffman's `clean` decodes each run once the overrides are off: a
      decoded `<b>` text, a decoded break a space. Proven: the outcome report,
      427 identical, `burn/hostile/references.vtt` and `attach/references`
      changed -- the ASS and the SRT `A & B <b> C &bogus;`; a burned frame
      shows it; the tests, the decoding ones failing on the old code. Reviewed
      (independent): a 5000-digit reference crashed (bounded now), a decoded
      `&bsol;n` read as a break (now text), a reference a tag split glued (each
      run alone now). An SRT from it (`--add-subs`) holds the decoded text as it is
      (SubRip has no escape): 6.8's writers.*
- [x] Found by 6.8.1's review: LRM and RLM (`&lrm;`, `&rlm;`), absent from
      the fonts, are measured an em (`subs/metrics.py`'s unknown glyph) and
      rendered as none -- a decoded one breaks a line early; with the font
      unread, any format character is estimated at 0.55 em (`ass.py`).
      *Done: what libass skips -- its `is_harfbuzz_ignorable` (ass_shaper.c,
      0.17.1 and 0.17.4 alike: HarfBuzz's default ignorables, which HarfBuzz
      8.3.0 and 13.2.1 zero when shaped), 13 ranges -- is `SKIPPED` (`metrics.py`; `breaks.py` since the next box):
      measured nothing, mapped or not; with a mark, what does not count
      (`metrics.counts`), in the measure, the estimate and a pop's peak
      alike. Measured first: each rendered +0 px between two Ms; U+0600,
      U+FFF9 and U+180F, outside it, drawn. Proven: the outcome report, 429
      identical, `burn/hostile/format-characters.vtt` changed -- one line,
      not two, its frame byte for byte the one without its marks; the tests,
      failing on the old code, and five mutations of the set and the rule,
      each caught. Reviewed: the rule moved to `metrics.py` (one for the
      three), the set built by `breaks.points`; "marks do not advance"
      corrected (a spacing one does: the box after next). What else they
      touch: the next box.*
- [x] Found by the box before: the characters libass skips are not yet whole
      in `subs/breaks.py` and `subs/paint.py`. UAX #14 keeps them where its
      rules put them -- no break before a CM (LRM, RLM: LB9), none beside a
      WJ (word joiner: LB11), one after a ZW (zero-width space: LB8) -- yet
      `breakable` allows a break before an LRM and beside a word joiner
      between ideographs, and none after a zero-width space in Latin;
      `segments` makes each its own unit, so a painted word counts it a
      letter (a colour step on nothing). And U+180F, a Mongolian selector
      libass draws as tofu (+27 px), is measured nothing, as a mark.
      *Done: UAX #14's rules, read in LineBreak 15.1 (the table's version):
      what libass skips is LRM, RLM, bidirectional controls, tags and
      selectors (CM), a word joiner and U+FEFF (WJ), a zero-width space
      (ZW), CGJ and U+180E (GL), the soft hyphen (BA). `breaks.py` now holds
      `SKIPPED` (from `metrics.py`) and the generated `ATTACHED` (LB9's CM
      and ZWJ, SA's marks by LB1); WJ and GL join the classes never broken
      before or after (LB11, LB12; GL even after a hyphen, stricter than
      LB12a). `breakable` in UAX #14's order: never before a zero-width
      space (LB7), always after one (LB8), never after a zero-width joiner
      (LB8a), never before what LB9 holds, the character before it deciding
      a break after it -- a CGJ, a mark but GL, its own. `segments`: what
      libass skips joins the unit before it, or, opening a word, the one
      after -- no letter of its own, so `paint.py` is unchanged. U+180F
      kept: Noto Sans Mongolian's features turn it, after its letter, into
      an empty glyph (`fvs4.valid`, `fvs4.ignored`), a box only where
      invalid or in a font without Mongolian (Unifont here: its words 1.10
      of their measure, 0.96 without). Proven: the tests, 11 break rows, 5
      segmentations, a rainbow's letters and two wrapped lines failing on
      the old code, and six mutations of the rules, each caught; the outcome
      report, 430 identical, `burn/hostile/joiners.srt` changed -- the
      joined line broken before の, not after it, the words at a zero-width
      space, not inside one -- rendered, each line within its width.
      Reviewed: LB8a, missed (a timed word ending on a joiner broke after
      it), added with its test; a unit libass draws nothing of tracked as
      `segments` goes, not rescanned; a subject's `#14` would link an issue
      in a release's notes (`CONTRIBUTING.md` now says so).*
- [x] Found by the LRM box's review: a spacing mark (Mc: an Indic vowel
      sign) advances -- rendered at 60, Devanagari's AA +11 px, Tamil's +26
      -- yet counts nothing (`metrics.counts`). Measured, harmless: Plex
      maps neither it nor its script, so its base, a size, over-measures the
      cluster (Tamil, Hindi and Bengali lines rendered 0.82, 0.56 and 0.48
      of their measure). Estimated (the font unread), one Tamil line
      rendered 1.27 of it (Hindi 0.78, Bengali 0.72): to weigh on more text,
      by script.
      *Done, weighed: the UDHR in 12 languages of 11 scripts with spacing
      marks (Hindi, Marathi, Bengali, Tamil, Telugu, Kannada, Malayalam,
      Gujarati, Gurmukhi, Sinhala, Myanmar, Khmer; 10-22% of their
      characters Mc), 60 lines of 6 words each (unicode-org/udhr `588b3f4`;
      notofonts.github.io `578d18e`), rendered by libass at 60 with Noto
      Sans' fallbacks alone and with this host's (FreeFont's and Unifont,
      both in NixOS's `fonts.enableDefaultPackages`). Measured: at most 1.01
      of the measure (Malayalam with Noto, Khmer with Unifont), a median
      0.37-0.99; counting the marks drops the median to 0.27-0.81 -- so they
      count nothing, kept, the rule pinned by a test failing on the other. A
      pop's peak, over the same `counts`, never reaches a neighbour: ffman's
      chunk-word script, rendered at each word's peak (Noto), the lit word's
      ink 5 px from the nearest at the least, in 10 of the languages
      (English's 9); the marks counted, 6. Estimated, the marks are not the
      cause: counted at 0.55, Malayalam still renders 1.20 of the estimate
      with Noto, Khmer 1.56 with Unifont -- the next box.*
- [x] Found by the spacing-mark box: the estimate (the font unread: 0.55
      sizes a glyph, a wide one a size) under-measures Brahmic and Southeast
      Asian text -- the UDHR rendered up to 1.64 of it with Noto (Malayalam;
      Tamil 1.61, Sinhala 1.26) and 1.76 with FreeFont's and Unifont (Khmer;
      Myanmar 1.70, Telugu 1.65), against libass's width from 1.33 on a 16:9
      frame (1.0 on a 4:3) and the frame's edge from 1.48 (1.11): ffman's
      own script of a Malayalam paragraph, estimated (another `--font`'s
      case), rendered with Noto across 5-1919 px of a 1920 frame. To weigh
      other scripts (Arabic, Hebrew, Thai, Georgian, Armenian, Ethiopic)
      before a rule.
      *Done: weighed in 26 languages -- Latin, Greek, Cyrillic; Arabic,
      Hebrew, Thaana; Thai, Lao; Georgian, Armenian; Amharic, Tigrinya; 11
      Brahmic; Myanmar, Khmer; Chinese, Japanese, Korean -- 60 UDHR lines
      each, rendered with Noto's fallbacks alone and with this host's
      (DejaVu, FreeFont, Loma, Unifont, WenQuanYi). At 0.55 a glyph,
      Armenian, Gujarati, Gurmukhi and Kannada passed it too (to 1.10);
      another script's glyphs at a size -- a fallback's, as the measure
      takes one (`UNKNOWN`) -- render at most 0.99 of the estimate, the
      least factor that holds 0.99 (Khmer with Unifont): no slack, so a
      size. So `metrics.estimate` (from `ass._estimate`): 0.55 for Latin,
      Greek, Cyrillic and Common (Scripts 15.1's, `ucd.NARROW`), a size for
      a wide glyph or another script's; equal to the weighed rule on all of
      Unicode (1,112,064 code points). Its cost, measured's already: Arabic,
      Hebrew and Thai lines fill a median 0.21-0.42 (measured with Plex,
      0.23-0.45) -- estimated lines now break as measured ones (the corpus's
      Thai and Malayalam, alike). The tables now one generated module,
      `subs/ucd.py` (`tests/support/ucd.py`, from `linebreak.py`: LineBreak,
      PropList, Scripts), checked byte for byte; `breaks.py` its logic and
      `SKIPPED`. Proven: the tests, the estimate of 4 characters and a
      Malayalam wrap failing on the old code, a range of `ucd.py` changed
      caught; the outcome report, 434 identical,
      `burn/another-font/long-ml.srt` and `long-th.srt` changed -- each line
      rendered alone with Noto, the Malayalam's 3 of 1452-1743 px (all past
      the BBC's 1296, the first past libass's 1728) now 6 of 473-1071, the
      Thai's 2 (834, 575) now 4 (462, 427, 449, 61), as measured; ffman's
      script of the Malayalam paragraph, 5-1919 px of the frame before,
      407-1512 now. Reviewed: `breaks.is_wide` now shared with the estimate;
      a check that Python's Unicode is 15.1 dropped from the module's test
      -- it failed under Python 3.14 (Unicode 16.0), which the generator's
      output still equals: the next box.*
- [x] Found by the estimate box's review: Python 3.14's unicodedata is
      Unicode 16.0, `ucd.py`'s tables 15.1 -- checks runs both (checks.yml),
      so under 3.14 the categories (`is_mark`, `is_wide`, a virama's class)
      know 16.0's new characters (Garay, Todhri, Tulu-Tigalari and more) and
      the tables do not: such a mark held by no LB9 rule, such a letter
      estimated a size. The generator's output equal under both. To weigh:
      tables by the running Python's version, or 15.1 until 3.13 is dropped.
      *Done: 15.1 for every property, whatever the Python -- one text, one
      break; a later Unicode is the module regenerated. Diffed on every code
      point, 3.13's unicodedata against 3.14's: 5,185 new characters (36 Mn,
      15 Mc, 4 of them viramas; 10 wide), 188 existing ones N to W (the trigrams
      U+2630-2637 among them), U+1171E Mn to Mc, no combining class changed
      -- so the categories, not only the new characters, moved. The
      generator reads UnicodeData.txt and EastAsianWidth.txt (15.1, as the
      other three) for `MARKS`, `VIRAMAS` and `WIDE` (120 ranges, by
      bisect) and its quotes and SA marks; `breaks.py` asks no
      `unicodedata`. Proven: the tables equal 3.13's unicodedata on all
      1,114,112 code points (a test, run where Python's Unicode is 15.1);
      the new tests (a 16.0 mark and virama, a trigram) fail on the old
      code under 3.14, pass under both; the outcome report under 3.14, 436
      identical, `burn/hostile/unicode-16.srt` changed -- the trigrams broken
      as under 3.13; under 3.13, 437 identical. Breaking and estimating
      145,000 characters (English, Japanese, Malayalam): 0.23-0.27 s, as
      before, run for run; the module imports in 3-5 ms (2.5-3.3 before).*
- [x] Each format from its source: SubRip (no standard: as ffmpeg's
      `subrip` reads and writes it -- libass renders ASS alone, SubRip once
      converted), WebVTT (W3C), ASS (v4.00+, Aegisub and libass) and SSA (v4,
      as the ASS reader takes it), whisper.cpp's writers (`output_json` for
      `-oj`/`-ojf`, `output_csv`, `output_lrc`, `output_txt`), WhisperX's and
      OpenAI whisper's (`WriteJSON`, `WriteTSV`, `WriteTXT`), LRC (no standard:
      as ffmpeg's `lrc` and whisper-cli write it) -- every field, its times'
      precision, what styling, position and word timing each holds.
      *Done: five records, each `references/format.md` and its
      `scripts/measure.py` (run), in the directories 6.8.2's skills will fill:
      `subrip` (ffmpeg n8.1.2's demuxer, decoder, encoder, muxer), `webvtt` (the
      W3C draft at `0648025`; Chromium 141's parser -- without regions and the
      line and position alignments), `ass` (ASS and SSA: libass 0.17.4 through
      `scripts/assdump.c`; Aegisub 3.4.2's reader and writer), `lrc` (ffmpeg's
      demuxer and muxer; the conventions), `whisper-transcripts` (whisper.cpp
      v1.8.4's writers cut from `cli.cpp` and run against stubs; OpenAI whisper
      v20250625's and WhisperX v3.8.5's run) -- nixpkgs' pins. Precision: SubRip
      and WebVTT ms; ASS cs; LRC cs, starts only; whisper-cli 10 ms (its unit
      the cs), DTW in cs; OpenAI seconds as floats, words 0.01 s; WhisperX 0.001
      s where aligned. Styling: ASS's styles and overrides; WebVTT's `b i u`,
      classes and CSS; SubRip's `b i u s` and `font`; none in LRC and the
      tables. Position: ASS's alignment, margins, `\pos`, `\move`; WebVTT's cue
      settings and regions; SubRip's `{\an}` and `X1..Y2`. Word timing: ASS's
      `\k` (cs durations), WebVTT's timestamp tags, Enhanced LRC's `<mm:ss.xx>`
      (unread by ffmpeg), `-ojf`'s tokens, OpenAI's and WhisperX's words. Found,
      each measured: ffmpeg reads a SubRip fraction as an integer of ms (`,5` is
      5 ms), skips blank lines, drops a number-led last line before an unindexed
      cue, stops at a NUL, and decodes `a < b and c > d` as `a {\b1} d`; libass
      reads an ASS fraction as centiseconds whatever its digits (`.500` is 5 s,
      Aegisub's 0.5 s) and refuses v4.00++; the WebVTT parser drops a cue timed
      with a comma or two-digit ms and loses `a < b`'s `< b`; ffmpeg applies
      LRC's `offset` in microseconds, writes 1.995 s as `[00:01.100]`, and loses
      the first line after a BOM; whisper-cli escapes only `"` and `\` in JSON,
      writes `t_dtw` as a 6-digit float (rounded past 2 h 46 min) and tokens as
      raw bytes (the next box); WhisperX's SubRip and WebVTT cues are the
      aligned words joined -- a Japanese segment lost its unaligned part -- and
      its JSON may hold `NaN`. The skills: these five, `subrip` among them,
      which no skill covers and 6.8.2 did not list. Reviewed: the WebVTT
      source corrected (the TR is the Candidate Recommendation Draft of
      2026-05-20, not 2019's); the SubRip and LRC scripts now check each
      conversion (a failed run had read the case before's file) and print no
      temporary path; invisible BOMs in four scripts written as `\ufeff`;
      measured too -- a style name's trailing space is its own, a Latin-1 byte
      passes ffmpeg unchanged, the muxer warns on the cue it drops.*
- [x] Found by the formats' box: whisper-cli's `-ojf` writes each token's bytes
      raw (`whisper_token_to_str`), and whisper's vocabulary splits what it
      lacks into byte tokens (`multilingual.tiktoken`: 1,476 of 50,257 not UTF-8
      alone; `鬱` and `😀` no token), so a transcript holding such a character is
      not UTF-8 -- and ffman refuses it whole, "not valid JSON" (measured on the
      writer's output). Its JSON escapes `"` and `\` alone: a control character
      in a text is refused too. To read: tokens as bytes, a character joined
      across them; a control character as text or refused, decided.
      *Done: a file not UTF-8 is read as bytes, each character joined across
      the texts it spans -- tokens, and with `-ml` sentences -- and given to the
      one it starts in; a token that only continues one extends that word, or
      is dropped at a sentence's start. A control character is text, as its
      escape reads. What is still no UTF-8 is refused where it is, `not UTF-8:
      NAME (.transcription[0].tokens[3].text)` -- the text holding the byte, or
      the one an unfinished character starts in, by its jq path. Proved failing
      first: 13 subverter tests, ffman's `test_ingest`; `hostile/bytes.json` (鬱
      over two tokens, 心 over two sentences, a raw tab). The outcome report,
      3.13 and 3.14 alike: 437 identical; `burn/hostile/bytes.json` changed --
      burned, refused before.*
- [x] Found by the box before: a SubRip, WebVTT, LRC, CSV or TSV file not UTF-8
      -- a Latin-1 byte; whisper-cli's `-ml` cues, split between tokens
      (`whisper_wrap_segment`), so maybe inside a character -- is read with each
      undecodable byte a surrogate, "as the shell kept them", and ffman stops on
      a traceback writing the burn's ASS or `--add-subs`' SRT
      (`UnicodeEncodeError`, measured: `--burn-subs` and `--add-subs` of
      `caf\xe9` in each). To decide: refused by name, or read (joined across
      cues, as whisper JSON's; another encoding).
      *Done, the owner's choice of three (2026-10-10): each character joined
      across the cue lines it spans, as the file holds them (LRC's before its
      sort), into the line it starts in; what is still not UTF-8 refused by its
      line, `not UTF-8: NAME (line N)` -- a CSV record's first; only the texts
      read must be. A Latin-1 file is refused. Measured first: `-ml 1` splits
      `ё` and `😀` of " Это ёлка и 😀" in whisper's own tokens
      (`whisper_wrap_segment` cut and run, now in the `whisper-transcripts`
      record), `-sow` none; bash burned a byte not UTF-8 as libass reads it,
      its Latin-1 character (pixels equal), and ffmpeg 8.1.2 drops such a cue
      from a track. The joining is one module, `readers/utf8.py`, whisper
      JSON's too. ffman writes its ASS and SRT in UTF-8: in the C locale
      without UTF-8 mode they were ASCII, a traceback. Proved failing first: 17
      subverter tests, 2 of ffman's ingest, 2 of its writers; on valid UTF-8,
      20,000 random transcripts read alike before and after; mutated, every
      text UTF-8, no traceback but the next box's. The outcome report, 3.13 and 3.14 alike:
      438 identical; `burn/hostile/split.srt`, `attach/split` (joined) and
      `burn/hostile/latin-1.srt` (refused) changed, each a traceback before.*
- [x] Found by the box before's fuzzing: a CSV or TSV whose header puts `text`
      before `start` or `end` (`text,start,end`), then a record short of those
      (`hello`), stops ffman on a traceback -- `IndexError` in `table.rows`,
      which checks a record holds its text, not its times (measured at
      `81c63a2`, `--burn-subs`). To decide: the record dropped, as one short of
      its text, or its missing times none.
      *Done, the owner's choice of three (2026-10-11): a field past a record's
      last reads empty, as awk's `$n` -- its text "", its time none -- whatever
      the header's order; a blank line is no record. So the reader drops no
      cue, as its contract says and JSON's missing values do: `1,2` under
      `start,end,text` is now a cue of no text, dropped by ffman as before
      (its output the same whichever the choice: untimed and empty cues
      dropped). Proved failing first: 4 subverter tests, ffman's ingest of
      `hostile/columns.csv`. The outcome report, 3.13 and 3.14 alike: 441
      identical; `burn/hostile/columns.csv` changed -- burned, a traceback
      before.*
- [x] Found by the box before's review: a CSV or TSV whose header follows a
      blank line is not read as a header -- `table.rows` takes only its first
      record, and a blank line is one to `csv` -- so its records are read as
      start, end, text: `\ntext,start,end\nhello,0,1000` reads `hello` as a
      start, and its cue is dropped (measured with the box before's change; a
      BOM before it alike). To decide: the header the first record that is not blank, or the
      first line, as now.
      *Done, the owner's choice of two (2026-10-11): the header is the first
      record, a blank line none -- as pandas' `read_csv` reads one
      (`skip_blank_lines`, its default: "the first line of data rather than
      the first line of the file"); RFC 4180's header is the file's first
      line, but the reader already counts a blank line as no record. A line
      of spaces is still one. Proved failing first: 2 subverter tests,
      ffman's ingest of `hostile/late-header.csv`; on valid UTF-8, of 30,000
      random transcripts, the 263 read otherwise than before each a header
      after blank lines. The outcome report, 3.13 and 3.14 alike: 442
      identical; `burn/hostile/late-header.csv` changed -- burned, "no timed
      text found" before.*
- [x] What ffmpeg converts between them (its `subrip`, `webvtt`, `ass`, `lrc`
      demuxers, muxers, decoders, encoders), measured both ways -- text,
      markup, positions, overlaps, empty cues, word timing -- against what
      ffman's readers already do; JSON, CSV, TSV, plain text: none in ffmpeg,
      so ffman's.
      *Done, three records (the owner's layout, 2026-10-11): ffmpeg n8.1.2's
      `webvtt` and `ass` reading and writing in the `webvtt` and `ass` records
      (`scripts/measure_ffmpeg.py` each), and every direction among SubRip,
      WebVTT, ASS and LRC, against subverter's readings, in a new
      `subtitle-mappings` directory (`references/ffmpeg.md`,
      `scripts/ffmpeg.py`; the mappings box's record joins it). Every
      conversion decodes to ASS events and encodes again, a format into itself
      too: SubRip trims spaces and makes coordinates `{\an5}`, WebVTT drops
      identifiers and settings. ffmpeg's WebVTT reader is not the
      specification's: a timing line it cannot read (a comma) ends the
      reading, a missing blank line merges two cues, any tag led by `b`, `i`
      or `u` is bold, italic or underline, six references decoded; its writer
      escapes nothing. ASS: centiseconds whatever the digits, `Comment:` lines
      moved after the events, 10 h written as 9:59:59.99, `v4.00++` taken for
      SSA. Into ASS a start and a duration round apart (an end can pass the
      next start); into LRC, SubRip's markup as text and no ends. Lost by
      ffmpeg: WebVTT's settings, classes, speakers and timestamps; ASS's
      positions, colours and karaoke; SubRip's strike-through and colours into
      WebVTT. ffman's readers: milliseconds and text exact, WhisperX's
      highlights as words, every chunk plain text, no ASS. Found too, the ASS
      record corrected: libass reads `\{` and `\}` as braces (0.17.1 and
      0.17.4's `ass_get_next_char`; a frame drawn), not "no escape". Reviewed:
      measured too -- a cue whose identifier starts `NOTE` is skipped whole, a
      CRLF decoded as one break, the WebVTT writer's `a <b> c & d < e` read
      back `a {\b1} c & d `; an ASS event at 10 h has no length, never shown.*
- [x] Words and chunks: how each holds word times (`-ojf`'s tokens, WhisperX's
      `words`, WebVTT's inline `<hh:mm:ss.ttt>`, ASS's `\k`); a chunk's words
      from none (impossible: noted), chunks from words (by segment); what a
      by-word output is in each (a cue a word, or timed within the chunk).
      *Done, one record (the owner's layout, 2026-10-11): `subtitle-mappings`'
      `references/words.md`, measured by `scripts/words.py` -- ffman's reading
      of each by-word form, libass 0.17.1's karaoke a frame a millisecond,
      Chromium 141's timestamps by colour; its SubRip and WebVTT cues equal to
      OpenAI whisper's writers'. whisper-cli's token offsets and WhisperX's
      words hold a start and an end; highlighted cues a cue a word, a gap a cue;
      WebVTT timestamps, Enhanced LRC and `-dtw` starts alone (a gap lost); `\k`
      durations from the event's start (a gap its own syllable). A chunk's words
      from none: no form holds them, none invented. Chunks from words: each
      form's sentence (an entry, a segment, a run, a cue, an event, a line); a
      cue a word names none. ffman reads words back from the JSON forms and
      highlighted cues alone: WebVTT's timestamps, `\k` and Enhanced LRC's tags
      dropped. Found: libass truncates `\k` to the ms (`\k12.59`, 125 ms);
      Chromium styles a timestamp's words only in an element, takes the word
      being spoken as `:past` (its FIXME; the specification: neither), reads a
      file's `STYLE`, and with no CSS greys the words to come (its own
      `video::cue(:future)`); a WhisperX segment its aligner skipped is shown
      unhighlighted, unnoted -- the next box.*
- [x] Found by the words box: a sentence with no words at all -- WhisperX's
      segment its aligner could not align (`"words": []`, `alignment.py`) --
      is shown without highlighting and unnoted: "N sentences had no word
      timings" counts only sentences that have words, none timed
      (`normalize.words`; bash's `place()` alike). To decide: counted in the
      note, or left.
      *Done, the owner's choice of three (2026-10-11): counted, one note for
      both -- every sentence no word is placed in is bare, as the decisions
      row already said ("Counts are reported"). Shown first: a whisper-cli
      `-ojf` segment of special tokens alone and a highlighted run without
      `<u>` alike. `normalize.words` counts the sentences shown without a
      word, not the word runs without an anchor. Proved failing first: 3
      ingest tests, one a source. The outcome report, 3.13 and 3.14 alike:
      440 identical; `burn/hostile/texts.json`, `windows.json` and
      `anchors.json` changed -- each a segment without words, now noted, its
      ASS the same.*
- [x] The mappings, every direction (a record as `metadata-mappings`'): what
      crosses, what is lost, ffmpeg's or ffman's -- measured, each row sourced.
      *Done, the owner's layout (2026-10-11: by element; positions, colours and
      whitespace measured; ffman's side as candidates for 6.8.3):
      `subtitle-mappings`' `references/mappings.md`, measured by
      `scripts/mappings.py` -- what each of the eight formats holds, a table an
      element (times, ends and empty cues, text and escapes, breaks and spaces,
      bold to strike, colour and font, position, speakers, identifiers and
      titles; words: `words.md`), each row ffmpeg's, ffman's reading and a
      candidate. The three scripts now share `frames.py` (drawing, read by
      colour), `files.py` (the writers by ms) and `readers.py` (ffmpeg's
      conversion, ffman's reading): `ffmpeg.py`'s and `words.py`'s outputs byte
      for byte the same. Measured: into ASS ffmpeg rounds start and duration
      apart, so an end equal to the next start passes it (`2.004` becomes `2.01`
      and `2.00`); it writes no plain text; ASS's `Name`, `Title` and
      `Comment:`, WebVTT's title, identifier, `NOTE` and voice, LRC's ID tags
      all lost. libass's `\an1-9` is Chromium's `line:0`, `line:50%` or no line
      with `align:left`, none or `align:right`; Chromium has no margin, draws a
      `STYLE` class's colour, size, font and line-through, but **none of
      WebVTT's default colour classes**, and keeps every space and tab
      (`pre-wrap`; the specification's `pre-line` collapses them) -- libass
      keeps inner runs and lays out without a line's leading and trailing
      spaces. Found: the next two boxes.*
- [x] Found by the mappings box: a SubRip or WebVTT text line holding `-->` is
      taken for a timing line -- subverter's `rows`, as bash's `subs_srt_vtt`,
      opens a cue at any line holding it -- so the cue's text is lost (measured:
      `a --> b` over `c`, the cue gone). ffmpeg reads it as text, SubRip's
      definition here; WebVTT's specification ends the cue there. whisper-cli
      and OpenAI's word cues write `-->` as it is. To decide: a SubRip timing
      line as ffmpeg reads one, WebVTT's as the specification.
      *Done, the owner's choice of three (2026-10-11): each format's own. A
      timing line has a time either side of its arrow -- one to three decimals
      joined by `:`, bash's lenient forms kept (`5 --> 7`, `00:01 --> 00:02`,
      either fraction mark); any other line holding `-->` is SubRip's text, and
      in WebVTT ends the cue, the lines after it up to a blank line or a timing
      line no cue's (`subrip._timing`, `rows(webvtt=)`; `fields.is_decimal` for
      awk's `prefix`, gone). Shown first: `Note: 1 --> 2` in a cue's text was a
      cue from 1 s to 2 minutes, `a --> b` first a file refused. Proved failing
      first: 6 subverter tests (5 SubRip lines, a WebVTT block), ffman's ingest
      of `hostile/arrows.srt` and `.vtt`; bash's lenient forms read as before (a
      test). The outcome report, 3.13 and 3.14 alike: 443 identical; the two new
      cases changed -- the SubRip's text kept, each a cue from 1 s to 2:00 gone.
      Its review: a decimal's pattern has one way to match (`fields.NUMBER`) --
      `[0-9]+\.?[0-9]*` tried each split of a run of digits, 17 s for a side of
      20000, as for a CSV, TSV or JSON time; an end glued to what follows
      (`00:00:02,000X1:5`, `00:02.000align:left`) is its time, as ffmpeg 8.1
      reads it and the W3C's "remainder" -- bash read 0 and 2 minutes. Suite
      1908, coverage 100%; the matrix, 770; the outcome report, 445 identical.*
- [x] Found by the mappings box: LRC's `[offset:+500]` is ignored -- subverter
      reads no ID tag, as bash did not -- where the convention moves every time
      by it, in ms (`+` sooner), and ffmpeg applies it in microseconds. To
      decide: applied, or ignored and noted.
      *Done, the owner's choices (2026-10-11): applied, noted; one not whole
      ignored, noted; `lrc.read` gives the Reading. Every time moves by the last
      offset of whole ms, `+` sooner, wherever it stands (Wikipedia; OpenSubsonic,
      as Navidrome serves it); ffmpeg 8.1.2 moves only the lines after it, by µs,
      pylrc the other way, Jellyfin and Quod Libet none. Proved failing first: 3
      subverter tests (sooner, later, the last whole one) and ffman's ingest of
      `hostile/offset.lrc`. The outcome report, 3.13 and 3.14 alike: 445
      identical; the new case changed -- `one` at 0.10 s, not 0.60, two notes.
      mappings.py rerun: only the offset's reading changed; subverter's README
      says so. Its review: the tag is ffmpeg's (measured) -- first on its line,
      the rest of it ignored, where a blank before it was taken and text after it
      refused; the offset an int. Without a tag the reading is the box's before,
      and with one every time that minus it (40000 random files). Suite 1916,
      coverage 100%; the matrix, 770. Found: the next box.*
- [x] Found by the offset box: an LRC line of several stamps
      (`[00:05.00][00:09.00]chorus`, the convention's repeated line) is read at
      its first time alone, the rest its text (`[00:09.00]chorus`, *measured*);
      ffmpeg reads an event a stamp, as the convention. To decide: each stamp a
      line, as ffmpeg, or as now.
      *Done, the owner's choices (2026-10-11): a line each, blanks between
      stamps read (Navidrome's; ffmpeg 8.1.2 drops a stamp after a blank,
      measured: a new row of the `lrc` record, the offset's scope another).
      The line's text read once (`utf8.by_line`), then given to each stamp.
      Proved failing first: 4
      subverter tests (repeated, blanks between, one past a double, joined once)
      and ffman's ingest of `hostile/chorus.lrc`. Without a second stamp the
      reading is the box's before, and with them the file's split a stamp a
      line (60000 random files). The outcome report, 3.13 and 3.14 alike: 446
      identical; the new case changed -- its four lines, each stamp's, where
      two showed a stamp as text. mappings.py's new case: ffman reads all five,
      ffmpeg four. Suite 1923, coverage 100%; the matrix, 770.*

*6.8.2 Skills* (validated, packaged, presented -- before any code)

Skills for the formats the research finds no skill covers (ASS and SSA; WebVTT; whisper
JSON; the tables -- CSV, TSV -- LRC and plain text, one skill or apart, as the research
finds), as 6.6.2's. *Found by 6.8.1: `subrip`, `webvtt`, `ass`, `lrc`,
`whisper-transcripts` (JSON, CSV, TSV, plain text, WhisperX's labels) -- their records in
`.agents/skills/`. The owner's (2026-10-11): a box a skill; `subtitle-mappings` a skill too,
as `metadata-mappings`; each reviewed by efficient-skill-review to convergence; the oracle
tests with 6.8.3's converters.*

- [x] `subrip`: the format by its readers and writers, rules to write a file every reader
      reads, examples, sources; three evals run; validated, packaged.
      *Done: `.agents/skills/subrip/` -- `SKILL.md` (163 lines: the format; its readers --
      ffmpeg's demuxer and decoder, which mpv goes through but for the character set, VLC
      3's own parser, ffman's subverter and burn -- side by side, 17 rows; what ffmpeg makes
      of it in ASS and back; the writers in use; the rules for a file every reader shows
      alike, the time rule as code; reading one; converting and muxing; an example;
      sources); `references/format.md` gains ffman's measured reading and ffmpeg's decoder
      dropping a cue not UTF-8 or after a line of spaces; `scripts/measure.py` gains ffman's
      cases and checks the skill from its own text -- the example's readings by ffmpeg,
      its ASS and subverter, the prose stating them, the time rule against ffmpeg's muxer
      over 7231 times to 100 h, the four commands' streams -- exiting 1 on a difference
      (each dosed mutation caught alone). VLC 3.0.24 and mpv 0.41.0 by source.
      `quick_validate.py`: valid (description 944 of 1024); packaged, three files
      byte-identical. Three evals (`evals/evals.json`, new instances, measured) answered
      cold from the skill alone: a merged file's `1999` lost to ffmpeg's index rule, a
      two-digit fraction read as milliseconds, `n<10 ... m>5` taken for a tag. Reviewed by
      efficient-skill-review to convergence, three independent passes: an MP4 command
      dropping the audio, the encoding row wrong for ffmpeg (it drops the cue) and mpv
      (it guesses the set), VLC's `X1..Y2` (it reads none), a line of spaces, `\n` in
      libass, the writers' UTF-8 (whisper.cpp's `-ml` splits a character), a script
      asserting nothing, an eval echoing the example -- each fixed and re-measured. Its
      review: ffmpeg drops `<v Bob>` but keeps `<c.yellow>` as text; ffman's tag cells hold
      for `--add-subs` too (its chunks are cleaned); the installed copy byte-identical.
      Reviewed again by efficient-skill-review: "every reader" narrowed to the four here
      (description, heading); hours needed by ffmpeg and VLC (`00:01,000`: no cue,
      measured; ffman reads it); a burn command, its streams checked. Found: the next
      three boxes.*
- [x] Found by the `subrip` box: subverter reads a short fraction (`00:00:01,5`) as a
      decimal, 1.5 s -- bash's reading -- where ffmpeg (so mpv) and VLC read its digits as
      milliseconds, 1.005 s. To decide: as the players, or as now. *Done: the owner's --
      SubRip as the players, noted; WebVTT the standard, noted; the layout, `subrip.read`
      giving the Reading as `lrc.read` does (the dispatcher's srt and vtt branch, the
      highlighting with it, moved in; `rows`, `is_highlighted`, `highlighted` private;
      `fields.DECIMAL` public for its groups). A seconds fraction not of three digits, no
      exponent: SubRip's a count of ms (`_seconds`: `,5` 1.005 s, `,5000` 6 s; bounded,
      `exact` on its digits), counted, the first named ("2 times had a fraction not of
      three digits, read as milliseconds as ffmpeg and VLC read them: the first, 00:00:01,5
      on line 2, as 1.005 s"); in WebVTT no timing line, its block dropped ("2 cues dropped:
      a time with a fraction not of three digits (W3C WebVTT), the first 00:01.5 on line
      3"). Three digits read alike either way; an empty fraction, an exponent, a fraction of
      minutes or hours and minutes alone decimals still. Measured: ffmpeg 8.1.2's srt and
      webvtt demuxers 1005 ms, `,5000` +5 s; VLC 3's `subtitle.c` ms by source; Chromium
      141 drops the cue; the W3C's "collect a WebVTT timestamp" by its text. Tests first:
      `test_readers.py`'s 18 new cases -- the 12 of a changed reading failing on the old
      code, the 6 of an unchanged one passing -- and ffman's `fraction.srt`, `fraction.vtt`
      (HOSTILE; an ingest test, failing on the old code). `half-ms.srt` became `half-ms.lrc`
      (SubRip's fraction no longer a decimal; its burn unchanged, 0.51-4.03) and
      `test_ingest`'s SubRip row of half-ms rounding went (LRC's and WhisperX's 0.5005 kept).
      Suite 1943, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 447
      identical, the 2 new cases changed as decided. `decisions.md` "Short fractions";
      from-bash; subverter's README; the `subrip` skill's rows and eval (measured again: 1005, 2025);
      `subtitle-mappings`' crossing rows (ffmpeg into SubRip, WebVTT, ASS measured); the
      next box found. Reviewed to convergence: `_rows`' WebVTT drop made explicit (its timing
      `None`); the tests name a first odd time that is an end, settings after it, and a line
      of two odd times -- 13 planted mutations, each caught; subverter's starts equal
      ffmpeg's for 400 random fractions of 1-6 digits; the skill's description no longer
      lists the short fraction among the readers' disagreements (all three agree now),
      revalidated (963 of 1024), eval 2 answered cold from it.*
- [x] Found by the `subrip` box: with no blank line before the next cue's index, subverter
      reads the index as the cue's text (`first 2`), where ffmpeg reads it as the index
      (VLC takes the whole next cue for text). To decide: an index line before a timing
      line dropped, as ffmpeg, or as now. *Done: the owner's -- a number
      alone dropped, noted, in `subrip._rows`. In SubRip, a cue's line of ASCII digits
      alone (blanks around) right before a timing line is the next cue's index: taken back
      from the cue's text, counted, the first named ("2 lines of a number alone before a
      timing line read as the next cue's index, as ffmpeg reads them: the first, 2 on line
      4"); a cue of that line alone is empty, dropped, as ffmpeg's. Other lines stay text
      (`3 apples`, `2.`, `+2`, which ffmpeg drops after a cue's text; `-2`, which it keeps),
      and a number with a blank line or no timing line after it. WebVTT unchanged: the
      W3C's "collect a WebVTT block" keeps the lines before a later `-->` line as the cue's
      text, Chromium 141 alike (`first\n2`, measured). Measured: ffmpeg 8.1.2 drops `2`,
      `02`, `\t7`, `2\t`, `+2`, `2.`, `3 apples`, keeps `-2` and a fullwidth digit; VLC 3
      by source (text to an empty line). Tests first: `test_readers.py`'s 13 new cases, the
      4 of a dropped index failing on the old code, and ffman's `index.srt` (HOSTILE; an
      ingest test, failing on the old code). Shown against ffmpeg: 30 random files of 40
      cues (an index with a blank line, without one, or none; texts of words and numbers
      alone), subverter's texts equal to ffmpeg's -- the old reader's differ in the first.
      10 planted mutations, each caught. Suite 1958, coverage 100%; matrix 770; `compare
      HEAD` on 3.13 and 3.14: 448 identical, 2 changed -- `index.srt` new, and
      `no-newline.srt`, whose `2` before `5 --> 7` is now that cue's index (`short times`,
      noted). `decisions.md` "Index lines"; from-bash; subverter's README; the `subrip`
      skill's rows (measured again: `first`). Reviewed to convergence: the skill measures
      the case its number-line row now claims (`the year`, `2024`, the timing line right
      after it: `the year`), its table telling it from the blank line's (`the year 2024`).*
- [x] Found by the `subrip` box: ffman burns a typed `\N` and `\h` as `/N` and `/h` (a
      backslash drawn as `/`, so no text makes an override), where ffmpeg, mpv and VLC
      show a break and a hard space (VLC breaks at `\n` too; ffman makes it a space). To
      decide: as the players, or as now. *Done: the owner's -- as the players, in
      ffman's wrap; SubRip alone; silent; the layout researched and chosen as WebVTT's
      references are: the reader states what its text holds (`Reading.has_ass_escapes`, a
      field with a default, subverter's API unbroken), `subverter.markup.unescaped` reads it
      (`\N` a line break, `\h` U+00A0, a backslash before either a character, as libass's
      `ass_get_next_char`, 0.17.1), and ffman's `clean` applies it, through `normalize`. `\N`
      is then a space, ffman wrapping (every break in a cue is, bash's rule); `\h` a no-break
      space: ffman's wrap never breaks there (UAX #14's GL), Plex's advance is a space's (236
      units), and libass draws it as one (a frame rendered identical). WebVTT's, LRC's and
      the rest's stay as written: ffmpeg's webvtt and text decoders escape a backslash. Found
      and fixed here (the owner's): `clean` removed overrides after turning `\t` and `\n`
      into spaces (bash's order), so `{\t(0,100,\fs20)}hi` was shown, burned `(
      (0,100,/fs20))hi`; now overrides go first, in every format (`hi`, as ffmpeg's subrip
      decoder and VLC). Tests first: subverter's 11 (`unescaped`, the flag by format) and
      ffman's 3 ingest tests (a highlighted SubRip's words too), each failing on the old
      code; `escapes.srt` (HOSTILE). 10 planted mutations, each caught. Suite 1973, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 450 identical, 1
      changed, `escapes.srt` new -- the reordering changed no other case (the override commit
      alone too, reported and diffed). `decisions.md`
      "ASS escapes", "Override order", and "WebVTT references" pointed at `subrip.py`, where
      the 6.8.2 short-fraction box moved its flag; from-bash; subverter's README; the `subrip`
      skill's rows (measured again: `one two a b hard\u00a0space`); the next box found.*
- [x] Found by the `\N` and `\h` box: libass also reads `\{` and `\}` as braces, which ffman
      burns as `/(` and `/)`; and ffman draws every `{`, `}` and backslash as `(`, `)` and
      `/` (`_esc`), where libass can draw each as written (`\{`, `\}`, a backslash before
      no escape letter). To decide: drawn as written, or as now. *Done: the owner's -- as written; a
      SubRip's `\{` and `\}` braces. The burn writes libass's own escapes: `\{`, `\}`, and a
      backslash before a word joiner, U+2060 -- ffmpeg's (`libavcodec/ass.c`), libass drawing
      it as nothing -- so neither a text nor a backslash before ffman's tag blocks makes an
      escape or an override. `paint.drawn` escapes each letter where it is written (each
      painted letter, a whole word, `_line`'s layers); lines are laid out and measured on the
      text as written (`ass._esc` gone). `subverter.unescaped` reads `\{` and `\}` too, as
      libass's `ass_get_next_char`. Measured, libass through ffmpeg 8.1.2: `\{b\}` rendered
      identical to ffmpeg's WebVTT `{b}`; a backslash before U+2060 identical to one alone; a
      SubRip's `a{text}b` as `ab` -- an empty block, hidden (VLC shows it: a box below). Tests
      first: a property test reading every burn back as libass does (its blocks, escapes and
      word joiners: `tests.support.subtitles.libass_reads`) -- each plain burn's text the
      transcript's, every block ffman's, 300 examples, the alphabet now with `N` and `h`; the
      painted letters' (a font, a highlight in motion); `braces.srt` (HOSTILE, an ingest test);
      `unescaped`'s braces; the fuzz test's invariant restated (its blocks ffman's, a backslash
      an escape ffman writes). 10 planted mutations, each caught, one -- the painted letters
      unescaped -- after its test was added. Suite 1980, coverage 100%; matrix 770;
      `compare HEAD` on 3.13 and 3.14: 449 identical, 3 changed -- `braces.srt` new,
      `settings.vtt`'s `\N` drawn `\N` (was `/N`), `texts.json`'s backslash itself (was
      `/`). `decisions.md` "Text drawn as written", "ASS escapes", "Rendering"; from-bash;
      subverter's README; the `subrip` skill: a row for braces (ffmpeg hides `{b}`, VLC shows
      `\{d\}`), its description, ffman's table and probe (measured again: `a {b} c\x {d}`).
      Found: the next two boxes.*
- [x] Found by the drawing box: a SubRip's `{text}` with no backslash is an empty override
      block to libass -- ffmpeg and mpv hide it (`a{text}b` renders `ab`; ASS's comment
      form) -- where VLC shows it and ffman keeps it as text. To decide: hidden, as libass,
      or text, as now. *Done: the owner's -- hidden, as
      libass; noted; one libass reader. `subverter.unescaped` reads a SubRip text in libass
      0.17.1's one pass -- a `{` with a `}` after it opens a block, to the first `}` (its
      `ass_render.c`), else a character; `\N`, `\h`, `\{`, `\}` (`ass_get_next_char`) -- and
      returns the blocks (`Unescaped`); past the last `}` the escapes alone, so it is bounded
      (200,000 unclosed `{`, under a second). ffman's `clean` reads a SubRip through it (other
      formats keep bash's `{\...}` rule); `ingest` notes the blocks that hold text ("2 braced
      runs hidden, ASS's override blocks, as ffmpeg and mpv hide them: the first, {note}"),
      not tags alone, `{}` or MicroDVD's `{y:i}` (ffmpeg's decoder drops those). A correction
      on the way: the layout question claimed regexes misread `\\{x}`; libass reads it as a
      backslash and a brace, as the chain did, and a lookbehind block regex is equivalent
      (proved) -- the one reader chosen again for cohesion. Measured: libass hides `a{text}b`
      (`ab`); ffmpeg's ASS-to-SubRip keeps an ASS comment as `{text}`; VLC shows it (by
      source). Tests first: `unescaped`'s 15 cases and a property test against a
      character-by-character libass (`{}\Nhnx `), bounded work; ffman's 4 (`{note}` hidden and
      noted, tags alone not, escaped braces text, WebVTT's text), each failing on the old
      code; 10 planted mutations, each caught. `decisions.md` "Braced runs", "ASS escapes";
      from-bash; subverter's README; the `subrip` skill's braces rows (measured again: `a c\x
      {d}`). Reviewed (the owner's request): libass alone was read, but ffmpeg's subrip decoder
      drops ASS's tags and MicroDVD's style first, to the first `}`, a backslash before the `{`
      or not, and keeps the tags while one `{\anN}` alone has been met (`handle_open_brace`) --
      so `a \{\i1\} b` is `a \ b`, not `a {\i1} b` (a test had asserted it), and `{a{\i1}b}c`
      `c`. Against ffmpeg 8.1.2 itself, then libass: 300 of 3,000 hostile texts differed; now
      `unescaped` reads ffmpeg's pass first (`_passed`, each `{` once) -- none of 9,000 differ,
      drawn or noted; the pass, as read, equal to ffmpeg on 12,000. ffman's MicroDVD filter,
      dead since, removed. Tests first: 9 cases and the property test against a
      character-by-character ffmpeg, then libass (8 failing on the old code), 2 bounded cases,
      ffman's 2 (tags inside a block, a backslash before tags; both failing); 12 planted
      mutations, each caught -- the one survivor first, `{\an8\i1}` counted an alignment, made a
      case. Not followed: a tag inside a block (ffmpeg makes `<i>` a block that ends the outer
      one; hand-written only), recorded. The skill measures the pass (4 decoder cases, 1 of
      ffman's). AGENTS.md's layout names `unescaped`. Suite 2004, coverage 100%; matrix 770;
      `compare HEAD~1` on 3.13 and 3.14: 451 identical, 1 changed -- `braces.srt`'s `{d}`
      hidden, noted.*
- [x] Found by the drawing box: `--add-subs` writes each chunk's text into the SRT as it is,
      where SubRip has no escape: a `{text}` from any source hidden by ffmpeg and mpv, a
      WebVTT's or a JSON's literal `\N` a break. To decide: a look-alike character, dropped,
      or as now. *Done -- the box widened to: the attached track holds the text exactly. The
      owner's: exact per container, of four; the faults research found, here; `srt()` takes
      the codec; silent. Research: ffmpeg converts ffman's SRT into every track -- its subrip
      decoder into ASS, then the track's encoder (`srt` in Matroska too, `mov_text`,
      `webvtt`), which writes that text raw but for `\N`, `\n` and `{\...}` (`ass_split.c`,
      n8.1.2). Measured through ffman's attach: a `{text}` hidden by mpv in MKV and MP4, a typed
      `\N` a break, a WebVTT's `&lt;b&gt;` bold, WebM's `1 < 2` cut and `&amp;` read `&`
      (ffmpeg's webvtt encoder escapes nothing), an unclosed `{\` cutting its cue and its
      italic running into the next, a timing-line text a lost cue. `subs/srt.py` writes each
      text for its codec: a word joiner after each `\`, `{` and `<`; in Matroska a `{` with a
      `}` after it `\{` and a joiner (libass's escape); in WebM `&amp;` `&lt;` `&gt;`; a joiner
      first where `-->` stands. Proved: 2,700 random hostile texts through the real ffmpeg,
      none differ (Matroska drawn through lavc and libass, MP4's samples, WebM's cues as the
      W3C reads them); Chromium 141 renders WebM's hostile cues pixel for pixel as without the
      joiners; VLC 3 by source (`subsdec.c`). Left: ffmpeg's `mov_text` decoder hands its text
      to libass unescaped, so mpv still hides an MP4's `{text}` (the stored text is exact).
      Tests first: `test_srt.py`'s 14 cases (13 failing on the old writing, a plain text the
      control), a Matroska round-trip property through subverter's reader and `unescaped`, an
      attach into .mka, .m4a and .webm read back from each track (failing); 14 planted mutations, each caught. The
      corpus: `hostile/attached.vtt`, burned and attached into each container (456 cases).
      Suite 2023, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 452 identical, 4
      changed -- `attach/references`' `<b>` joined, the three attached cases. `decisions.md`
      "Attached text" ("WebVTT references" corrected); from-bash; the `subrip` skill's writing
      rule, its muxing paragraph, and a "Muxed" section measured by `measure.py`, what mpv's
      libass receives with it. Reviewed: a table's name (`_JOINS`), the docstring's `\n`, the
      skill's VLC escapes (either case), its sources, mpv's MP4 reading measured. Reviewed
      again (the owner's request): the 13 failing cases proved against the old writing; the
      style's run into the next cue stated for SubRip and WebVTT alone (MP4 cuts only); a
      property for WebM's text, read as the W3C reads a cue -- its oracle made faithful when two
      planted mutants survived `untagged` (a `<` with no `>`, a `-->`), each WebVTT escape then
      caught; `measure.py` reading a track's stored text and libass's in one function;
      `ATTACHED`'s comment. Suite 2024.*
- [x] Found by the short-fraction box: WebVTT's timestamps wholly the W3C's ("collect a
      WebVTT timestamp"), where subverter still takes bash's lenient forms -- a bare
      number as minutes (`5 --> 7`), a sign, minutes or seconds not of two digits or past
      59, a first field of other digits or past 59 with no field after the seconds
      (`100:00.000`: hours needed), no fraction or an empty one, an exponent, `,` for `.`.
      To decide, each: the standard (no timing line, its block dropped, noted), or as now. *Done:
      the owner's, each group: the standard -- the forms every player refuses (a bare number,
      no fraction or an empty one, `,`), those ffmpeg, mpv and VLC read (a sign, one digit, past
      59, `75:00.000` as minutes), the exponent; the layout assessed and chosen: `readers/cues.py`
      the cue blocks SubRip and WebVTT share, each grammar a `Dialect` -- `subrip.py`,
      `webvtt.py` (one module a format, as AGENTS.md says; WebVTT's writer and skill next).
      `webvtt._timing` is the W3C's "collect WebVTT cue timings and settings" and "collect a
      WebVTT timestamp" (a regex, its 59s checked); every other line holding `-->` drops its
      block, noted once ("3 cues dropped: a line holding --> that is no WebVTT timing line
      (W3C), the first 5 --> 7 on line 6") -- the short fraction's note folded in, a cue's
      text line holding `-->` and other scripts' digits noted where they were silent. Measured:
      Chromium 141 on 31 forms; ffmpeg 8.1.2's demuxer (`webvttdec.c`) reads the lenient ones
      and, at a line it cannot read, loses every cue after it (`break`); VLC 3's `webvtt_scan_time` (run as written) reads most of them, not a sign or
      `100:00.000`, and needs `-->` spaced; bash read `00:01.0e1` as 10 s. A correction on
      the way: my first reading of the spec missed its line 3318 (minutes and seconds to 59),
      corrected before building. Tests first: Chromium's 30 forms in a table (21 failing on the
      old code), a property test against the W3C's steps transcribed (the oracle equal to
      Chromium on 31 forms and 1,200 random lines), hours past a double's range no time;
      ffman's `timestamps.vtt` (burned: 457 cases), `arrows.vtt` and `fraction.vtt` notes. 22
      planted mutations, each caught -- two survivors first (a form feed, a minute's weight),
      each made a Chromium-measured case. Bounded: 400,000 digits read in 4 ms. Suite 2058,
      coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 454 identical, 3 changed --
      `timestamps.vtt`'s lenient cues dropped, noted; `arrows.vtt` noted; `fraction.vtt`'s note
      reworded. `decisions.md` "WebVTT timing lines" (Timing lines, Short fractions, Index
      lines, WebVTT references, Transcripts not UTF-8 pointed at the modules); from-bash;
      subverter's README; AGENTS.md's layout; the `subrip` skill's and the mappings record's
      pointers. Reviewed (the owner's request): VLC 3's scanner run as written (glibc's
      `sscanf`) -- it refuses a sign and `100:00.000` and needs `-->` spaced, which the decision
      row, the test table and this note had overstated; each lenient mark in the table proven
      against ffmpeg and VLC (20 forms); ten block structures (a header without its blank line,
      identifiers, NOTE, STYLE, an arrow in a cue's text) equal to Chromium's; `Found` a
      documented dataclass; the commit in both packages' changelogs.*
- [x] Found by the timestamps box: a WebVTT not opening with its `WEBVTT` line (`WEBVTTX`,
      none, `webvtt`): the W3C's parser reads no cue (Chromium 141 none), ffmpeg 8.1.2's
      demuxer reads them all but for `webvtt`, ffman all. To decide: the standard (refused:
      no timed text), or as now.
      *Done: the standard (the owner's choice) -- refused, named: `not a WebVTT file: FILE
      (its first line is not WEBVTT)`, an empty file too; the burn and `--add-subs` alike.
      Each format a `read` (`subrip.read`, `webvtt.read`; their `Dialect` private), the
      signature WebVTT's alone. Measured on 20 heads: Chromium 141 reads the cues exactly when
      the W3C's signature holds; ffmpeg 8.1.2 reads a file whose first block opens `WEBVTT`,
      `NOTE`, `STYLE` or `REGION`, or is a cue -- any other none, every cue lost at it
      (`webvttdec.c`'s `break`: 6 of the 12 refused heads); VLC 3's `ProbeWEBVTT` (read)
      refuses each unless forced.
      Tests first: 19 heads, an empty file, a signed file of no cue (14 of 24 failing on the
      old code); ffman's `unsigned.vtt` refused. Reviewed: an arrow on the signature's line
      was noted as a dropped cue -- the W3C skips that line whole (Chromium reads the cue
      after it), so it is read blank, its numbering kept; a test first, 13 planted mutations
      caught. Suite 2086, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 457
      identical, 1 changed (`unsigned.vtt` refused). Spec 3.4; `decisions.md` "WebVTT
      signature"; subverter's README; AGENTS.md's count; the mappings record. Reviewed again
      (the owner's request): ffmpeg's and VLC's readings had been "most" -- each now its
      source's rule, measured again (the docstring, the test, this note, the mappings record);
      `ffman-from-bash.md`, closed at 6.7.9, had grown a bullet a box since (15, this one's
      among them): restored as closed (the owner's choice), each change its commit's subject
      and its `decisions.md` row.*
- [x] Found by the signature box: a WebVTT whose lines end in a CR alone -- a line end to
      the W3C (Chromium 141 reads its cues); ffmpeg 8.1.2's demuxer and subverter read none
      (`readers._lines` splits at LF). To decide: the standard (CR a line end), or as now;
      SubRip's to measure alike.
      *Done: a line ends at an LF, a CRLF or a CR alone -- WebVTT's the W3C's, each CRLF, CR
      and LF one end (the owner's); SubRip's, assessed (the owner's call), `\r*\n|\r`: the
      CRs before an LF part of its end, as `ff_subtitles_read_line` takes them, so CR CR LF, a
      CRLF file written again in text mode, reads as written -- of three rules, the one
      reading every measured form but an LF then a CR as ffmpeg does (VLC's loses a mixed
      file's cue, the W3C's a CR CR LF cue's later lines); LRC's as SubRip's (the owner's).
      Each module its `split_lines` (the owner chose a pattern a module; measured, SubRip's
      pattern `\r*\n|\r` is quadratic on a run of CRs -- 20,000 in 0.17 s -- so its split is
      at the LFs, then the CRs, held equal to the pattern by a property test; 200,000 CRs read
      in 0.04 s). Measured: ffmpeg's SubRip
      demuxer reads CR-only and CR CR LF files, its WebVTT one loses a CR-only file's first cue
      and reads no cue of a CR CR LF one, its LRC one ends a line at an LF alone, dropping each
      CR; Chromium reads the W3C's (CR CR LF: cues of no text); VLC 3 an LF, else a CR (by
      source); CSV and TSV already read each. Known: an LF then a CR is two ends (each cue of
      no text; ffmpeg reads its texts), and a CR in an LRC line ends it (ffmpeg drops the CR).
      Tests first: Chromium's and ffmpeg's tables, any mix of a format's ends read as LF (17
      failing on the old code), the splits' oracles, the bound, LRC's line count; ffman's five
      hostile cases (`cr.*`, `crcrlf.*`; 5 failing). 10 planted mutations, 8 caught; the two
      survivors equivalent -- `_AFTER`'s CR, `_lines`' last-line pop -- each dead, removed.
      Suite 2121, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 458 identical, 5
      changed (the new cases). Spec 3.4; `decisions.md` "Line ends" (and "WebVTT signature":
      its ffmpeg reading, missed by the last review, corrected); subverter's README; AGENTS.md's
      count; the mappings record. Reviewed (the owner's request): `split_lines`' claim
      narrowed -- its lines holding text ffmpeg's, its blank lines kept, which ffmpeg's reader
      skips (proven on the 88,573 texts of up to 10 CRs, LFs and letters; that reader
      transcribed, a property test); the `subrip` skill's ffman row, stale (a CR-only file no
      longer refused), and the `webvtt` and `lrc` records' measured rows; VLC 3's parser traced
      (a mixed file's first cue skipped); the bound's 18 s measured.*
- [x] Found by the line-ends box: a SubRip text line after its cue's blank line -- ffmpeg
      8.1.2 keeps it in that cue (`srtdec.c` reads no blank line), subverter drops it,
      silently. To decide: ffmpeg's, or as now, noted.
      *Done: ffmpeg's, noted (the owner's): a SubRip cue reads on past an empty line to the
      next timing line, the last cue to the file's end ("2 cues held text after an empty line,
      read as theirs, as ffmpeg reads them: the first, kept on line 5"); a line of spaces
      alone ends its text, as ffmpeg's decoder ends it (`htmlsubtitles.c`); a line holding a
      tab is text; the index, the last line before a timing line with only empty lines
      between, noted when no empty line stands before it. WebVTT's in the same box (the
      owner's): an empty line alone ends a cue, a line of spaces or tabs its text, as the W3C
      and Chromium read it (subverter had ended it there). The layout (the owner's):
      `cues.Dialect.ends`, any other empty line skipped; `_rows` split for its complexity
      (`_take_index`, `_joined`). Measured or read: ffmpeg 8.1.2 on 13 forms (its demuxer and
      decoder each), MPC-HC (`STS.cpp`) and Subtitle Edit (`SubRip.cs`) read on, VLC 3
      (`subtitle.c`) and Kodi (`DVDSubtitleParserSubrip.cpp`) stop at an empty line; Chromium
      141 and ffmpeg keep a WebVTT whitespace line. The line-ends box's one difference from
      ffmpeg, an LF then a CR, gone: its texts read, noted. Tests first: SubRip's 11 forms, the
      last cue's credits, WebVTT's 4 lines (11 failing on the old code), a cue of no text
      taking no index (measured); ffman's `continued.srt` and `whitespace.vtt` (2 failing). 13
      planted mutations, 11 caught; the 2 survivors equivalent -- the empty line's `is_open`
      and a reset after each text line -- each dead, removed (`emptied`). Suite 2142,
      coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 463 identical, 2 changed
      (the new cases). `decisions.md` "Cue ends" (and "Index lines", "Line ends", "Timing
      lines"); spec 3.4; subverter's README; AGENTS.md's count; the `subrip` skill's reading
      and its ffman rows (its `measure.py` run again: each row its output, its own checks
      passing), the `webvtt` record, the mappings record. Reviewed (the owner's request): a
      cue whose timing line ffmpeg cannot read (`->`) now the cue before's text, as ffmpeg's
      -- measured, tested, in "Cue ends" and the record; the `subrip` skill's ffman column,
      stale (its empty-line and index cells), corrected; its `measure.py` given the CR CR LF,
      LF-CR, last-cue and unread-timing cases and the notes' presence, its rows each its
      output again.*
- [x] Found by the line-ends box: a NUL in a SubRip's or WebVTT's text -- the W3C makes it
      U+FFFD (Chromium 141 shows it); subverter keeps it, into the ASS. What libass and ffmpeg
      draw, to measure; then to decide.
      *Done: U+FFFD, as the W3C reads one, noted (the owner's), in every format ("1 NULs read
      as U+FFFD, as the W3C reads them: the first in line 3"; a JSON's by its path). Measured:
      kept, the NUL broke both of ffman's outputs -- libass 0.17.1 ends its script there (the
      burn drew `fi`, and nothing of any later cue) and ffmpeg 8.1.2's SubRip demuxer stops
      (`--add-subs`' track empty from that cue on: 0 packets); every reader kept it. ffmpeg's
      WebVTT cuts the text and loses every later cue, its LRC cuts the line; VLC 3 cuts the line
      (`strlen`, by source); Subtitle Edit makes it a space; ffman's three fonts draw U+FFFD.
      The layout (the owner's): `utf8.joined`, the one place every reader's texts pass,
      returns `Joined` -- the texts and their `Nuls`, a count and the first's place -- and
      each reader notes them (`nul_notes`); `_tokens` given its sentences, so `_sentences`
      returns their NULs. Tests first: each of the 7 readers, the count, the place (9 failing
      on the old code), a later text's place and a segment's and its word's; ffman's `nul.srt`
      (failing). End to end,
      burned and attached, old against new: cue 2 drawn (55 pixels, before 0), 2 packets
      attached (before 0). 13 planted mutations, each caught. Suite 2154, coverage 100%;
      matrix 770; `compare HEAD` on 3.13 and 3.14: 465 identical, 1 changed (the new case).
      `decisions.md` "NUL"; spec 3.4; subverter's README; AGENTS.md's count; the `subrip`
      skill (a reader row, a writing rule, its ffman row, `measure.py`'s case), the `webvtt`,
      `lrc` and mappings records. Reviewed (the owner's request): ffmpeg's WebVTT, measured
      on four cues, loses every cue after the NUL, not the next alone -- corrected in
      `decisions.md`, this note and the records (the mappings record's SubRip cell too: its
      cue lost, not cut); `Joined` kept a place a NUL -- 10 million NULs, 162 MiB and 1.9 s
      -- now `Nuls`, a count and the first place (29 MiB, 0.04 s); 13 mutations again,
      each caught.*
- [x] Found by the NUL box: an ASS transcript holding a NUL -- burned as it is (copied), libass
      ends its script there, every later event lost (measured). To decide: U+FFFD, as the
      others' texts, noted; or as now.
      *Done: U+FFFD, noted, as the others' (the owner's): "1 NULs read as U+FFFD, as the W3C
      reads them: the first in line 12", an editor's line. ffman's copy for every ASS and SSA,
      burned or attached (the owner's: `--add-subs` gave ffmpeg the user's file, whose reader
      cuts the event's line at a NUL, its rest a header line -- measured); a UTF-16 one (its
      BOM) copied as it is. `ingest.passed` gives the copy's bytes and notes; the burn and the
      attach each write it (`test_architecture`: `subs` touches no file). Tests first:
      `passed`'s cases, the ingest note, burned and attached end to end (9 failing on the old
      code: the second event drawn in every frame, before 0 pixels; `fi\ufffdrst` attached,
      before `fi`). 10 planted mutations, each caught. Suite 2164, coverage 100%; matrix 770;
      `compare HEAD` on 3.13 and 3.14: 465 identical, 3 changed (`burn/hostile/nul.ass` and
      `attach/nul-ass` new; `attach/t.ass` given ffman's copy). `decisions.md` "ASS NUL";
      spec 3.4; AGENTS.md's count; the `ass` record (libass's `process_text`, ffmpeg's
      reading, `measure_ffmpeg.py`'s cases) and the mappings record. Reviewed (the owner's
      request): `("ass", "ssa")`, written in five places, named once -- `PASSED_THROUGH`
      (a refactor commit; `compare` against the fix: 468 identical); `passed`'s docstring
      says what ffmpeg does with the rest of the line; a UTF-16 ASS's U+0000, measured kept
      and cut when attached, added to its box; an SSA tested at last -- a mutant dropping it
      survived the whole suite; the spec's bullet one rule, its comments one word.*
- [x] Found by the ASS NUL box: a UTF-16 ASS (its BOM) cannot be burned -- ffmpeg's `ass`
      filter gives libass no codepage, whose script ends at the first NUL: "Could not create
      a libass track", the job failed; attached, ffmpeg's reader decodes it -- a U+0000 in it
      kept, its line cut, unnoted (measured). To decide: recoded to UTF-8 in ffman's copy,
      its NULs then U+FFFD; refused, named; or as now.
      *Done: recoded to UTF-8 in ffman's copy, burned and attached alike, not noted; a unit
      not UTF-16 refused by its line, `not UTF-16: FILE (line N)` (the owner's, each). In
      `passed`, now given the file's name: `_utf8` first, so a U+0000 is a NUL then, U+FFFD,
      noted. Researched: `vf_subtitles.c` calls `ass_read_file(..., NULL)`, libass recodes
      only given a codepage (`read_file_recode`); ffmpeg's reader recodes a BOM's UTF-16
      (`ff_text_init_avio`) and takes a unit not UTF-16 for a NUL (`ff_text_r8`) -- measured,
      a lone surrogate cut its line and took the next unit, an odd last byte a header line.
      Tests first: the recode (LE, BE), its U+0000 noted, four invalid files refused by
      line, ffman's hostile pair, and the NUL end-to-end tests run on UTF-16 too (10 failing
      on the old code: the burn failed, `fi` attached). End to end, LE and BE burned as
      UTF-8's (303 and 483 pixels, alike). 12 planted mutations, each caught. Suite 2178,
      coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 468 identical, 3 changed
      (`burn/hostile/utf-16.ass`, `burn/hostile/utf-16-bad.ass`, `attach/utf-16-ass`, new).
      `decisions.md` "ASS UTF-16" (and "ASS NUL" brought up to date); spec 3.4; AGENTS.md's
      count; the `ass` record (libass's and ffmpeg's rules, ffmpeg's readings, the UTF-16
      burn, `measure_ffmpeg.py`'s cases) and the mappings record. Reviewed (the owner's
      request): two properties added -- any UTF-16 text passed as its UTF-8 is (LE and BE,
      a U+0000 and an inner BOM alike), any bytes after a BOM passed whole or refused by a
      line -- each failing on a planted bug the examples alone also catch; 400,000 fuzzed
      files, none raising but a refusal; `measure_ffmpeg.py`'s failure line without its
      temporary path; the burn's and attach's name to `passed` cannot be refused there,
      ingest refusing first (an equivalent mutant, kept: one signature).*
- [x] Found by the ASS NUL box: a CP1252 ASS attached loses each event not UTF-8 -- ffmpeg's
      ASS decoder drops it ("Invalid data found"); burned, libass draws it (measured). To
      decide: refused by its line, as the other formats' bytes; recoded; or as now.
      *Done: refused by its line, `not UTF-8: FILE (line N)`, the whole file -- header,
      styles, comments -- in `_utf8` (the owner's, each): without a UTF-16 BOM, UTF-8 or
      refused, no encoding guessed. Researched: libass draws a byte not UTF-8 as its Latin-1
      character (`ass_utf8_get_char`) -- `é` right, CP1252's quotes and `€` controls
      (measured: the frame Latin-1's, not UTF-8's); ffmpeg's decoder drops an event not UTF-8
      (`utf8_check`), its style's name included, while a stream copy keeps its bytes and the
      header passes as it is (measured). Tests first: refusals by line (a header's byte, CR
      lines, a cut character, a lone continuation, a surrogate), a UTF-8 file copied as it
      is, its BOM kept, the property now over any bytes with or without a BOM, ffman's
      `cp1252.ass`, burned and attached (9 failing on the old code). End to end: refused,
      burned or attached; a UTF-8 file burned as before. 14 planted mutations, each caught.
      Suite 2190, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 471
      identical, 1 changed (`burn/hostile/cp1252.ass`, new). `decisions.md` "ASS not UTF-8"
      (and "ASS UTF-16" brought up to date); spec 3.4; AGENTS.md's count; the `ass` record
      (libass's and ffmpeg's rules, the readings, the drawing, `measure_ffmpeg.py`'s cases)
      and the mappings record. Reviewed (the owner's request): a UTF-8 file is now returned
      as it is, not decoded and encoded again -- on 54 MB, 0.157 s to 0.088 s, its peak
      255 MB to 162 MB, `compare HEAD` 472 identical; `PASSED_THROUGH`'s comment says
      ffman parses none of them, now it reads each; 15 mutations, each caught.*
- [x] Found by the CP1252 box: an .ass or .ssa that is no script -- empty, or text without
      `[Script Info]` -- fails in ffmpeg, burned ("Error initializing filters") or attached
      ("Invalid data found"), as `ffmpeg failed`, the message naming ffman's work copy
      (measured). To decide: refused, named, before any work, as a WebVTT without its
      signature; or as now.
      *Done: refused, named, before any work, burned or attached alike (the owner's, each;
      `_script` in `ingest`): `[Script Info]` first, as ffmpeg's reader (`ass_probe`: its 13
      bytes, in its case, after a UTF-8 BOM and blank lines), else `not an ASS file: FILE (its
      first line is not [Script Info])`; and a type, as libass (`process_line`,
      `parse_script_type`: a styles section, by any case, or `[Script Info]`'s `ScriptType` of
      `4.00+` or `4.00`), else `(no [V4+ Styles] or [V4 Styles] section, nor ScriptType
      v4.00+ or v4.00)`; `an SSA` for one. Found: `[script info]` -- which libass burns --
      ffmpeg reads as an LRC, so `--add-subs` wrote an empty track, unnoted (measured, exit
      0, 0 events). Tests first: 12 refusals, 8 scripts passed (a BOM, blank lines, any case,
      SSA's `4.00`, an unknown section, a BOM before `ScriptType`, UTF-16), burned and
      attached (14 failing on the old code). 800 generated scripts, ffman's verdict each as
      ffmpeg's probe and libass's burn (0 apart). 19 planted mutations, each caught -- one,
      after a case added (`[Script Info` without its `]`, which ffmpeg too reads as an LRC).
      Suite 2214, coverage 100%; matrix 770; `compare HEAD` on 3.13 and 3.14: 472
      identical, 3 changed (`burn/hostile/no-script.ass`, `burn/hostile/lower.ass`,
      `attach/lower-ass`, new). `decisions.md` "ASS script"; spec 3.4; AGENTS.md's count; the
      `ass` record (ffmpeg's detection, its readings, libass's untyped script,
      `measure_ffmpeg.py`'s cases, its failures without their temporary paths) and the
      mappings record. Reviewed (the owner's request): converged, nothing changed --
      `_script` on 52 MB, typed in its first lines 0.001 s, typed last or untyped (refused)
      1.2-1.4 s, a line at a time; each entry git-cliff's, no changelog written by hand.*
- [x] `webvtt`: the same.
      *Done: `.agents/skills/webvtt/` -- `SKILL.md` (180 lines: the format; its readers --
      Chromium, the W3C's parser; ffmpeg's demuxer and decoder, which mpv goes through whole,
      guessing no character set for WebVTT; VLC 3's own parser; ffman's subverter -- side by
      side, 21 rows; ffmpeg's ASS and back; the writers in use; the rules for a file every
      reader shows alike, the time rule as code; reading one; converting, muxing and burning;
      an example; sources); `references/format.md` gains Chromium's and ffmpeg's new rows and
      ffman's measured reading; `scripts/measure.py` new Chromium cases (a comma mid-file, no
      blank line between cues, a byte not UTF-8, UTF-16, duplicates, a `<` as text);
      `scripts/measure_ffmpeg.py` ffmpeg's new cases, ffman's reading with a PYTHON, and the
      skill checked from its own text -- the example's readings by ffmpeg, its ASS and its
      times, by ffman, the prose stating them, the time rule over 7231 times to 100 h read by
      ffmpeg and ffman, the six commands' streams and the copies' settings -- exiting 1 on a
      difference (four dosed mutations, each caught alone). VLC 3.0.24 and mpv 0.41.0 by
      source. `quick_validate.py`: valid (description 982 of 1024); packaged, four files
      byte-identical. Three evals (`evals/evals.json`, new instances, measured) answered cold
      from the skill alone: a comma in a time losing every later cue to ffmpeg, `<3` taken
      for a tag by Chromium and ffmpeg but not VLC, no blank line after `WEBVTT` losing the
      first cue to ffmpeg. Reviewed by efficient-skill-review to convergence: the
      description's colon, a YAML mapping, and its length (1071, then 982); two eval
      instances in the skill's own text (`00:00:05,000`, `&lt;3`), replaced; rule 7 claiming
      VLC honours settings alone; ASS's centiseconds told for every conversion (SubRip and
      WebVTT keep milliseconds: measured, now checked); VLC's spaced arrow lost to formatting;
      `.5000` read as 5 s, now 5000 ms. Measured anew: Chromium reads a UTF-16 file by its
      BOM, against the specification's UTF-8. Found: the next three boxes. Reviewed (the
      owner's request): ffmpeg's UTF-16 row, filed in Chromium's table, moved; rule 3 lacking
      `WEBVTT`, an identifier ffmpeg skips the cue for too (measured, `WEBVTT-1`); measured
      and recorded anew: ffman's note on `75:00.000`, its typed `\n` and `\t` read as
      spaces, Chromium's CR CR LF; the conversions' milliseconds now checked (18 checks);
      VLC's entities counted, 124; the lrm, rlm and nbsp references named, as the saved
      skill had lost them, and the package handed over with it -- the card carries
      `SKILL.md` alone.*
- [x] Found by the `webvtt` box: a WebVTT cue's text after an empty line is dropped unnoted
      -- as the W3C, Chromium and VLC drop it, ffmpeg losing every later cue -- where a
      SubRip's is read on and noted (measured). To decide: noted, as the cues dropped for
      their timing line are; or as now.
      *Done (the owner's: noted): a block of text after an empty line holding no `-->` is no
      cue's, dropped, noted past the first block holding one -- counted by block, the first
      named (`2 text blocks dropped: after an empty line, in no cue (W3C), the first lost on
      line 6`); not a line alone before a line holding `-->` (the next cue's identifier, the
      W3C's line count 2), a comment, style sheet or region block as the syntax writes them,
      nor blanks alone; nor text before any cue (a header's or a title's). `cues.py` records
      the runs (`Found.strays`), `webvtt.py` words them. Tests: 14 reader cases, 7 failing
      first, the rest guards, and ffman's `stray.vtt`, failing first; nine mutations, each
      caught (one, the first `-->` a dropped cue's, by a case added for it). Differential:
      60000 generated files, the W3C's block algorithm transcribed from `index.bs` -- 0
      mismatches in the note and the cue count; HEAD's code mismatched on all 2492 of the
      first 20000 holding stray text; that transcription's cue counts Chromium 141's on 1500
      more. 200000 strays in 7 MB read in 4.3 s (HEAD 3.8
      s). Suite 2230, 100%; matrix 770; outcome report: 475 identical, `stray.vtt` new, on
      3.13 and 3.14; the `webvtt` skill's ffman column and record re-measured. Found: the
      next box.*
- [x] Found by the stray-text box: a SubRip cue's text after a line of spaces is dropped
      unnoted -- as ffmpeg's decoder drops it, the lines after one to the next timing line
      no cue's (measured: `first`, then `   `, then `lost` -- ffmpeg 8.1.2 and ffman draw
      `first` alone). To decide: noted, as WebVTT's text in no cue now is; or as now.
      *Done (the owner's, after the readers' sources: read on, noted): a line of spaces is
      skipped as an empty line is, the cue going on to the next timing line, its text after
      one noted by cue (`2 cues held text after a line of spaces, read as theirs, as MPC-HC
      and Subtitle Edit read them (ffmpeg's decoder drops it): the first, lost on line 5`).
      Read: ffmpeg's decoder ends the text at one (`htmlsubtitles.c`, since n1.0, its own
      comment meaning to drop no text) and Kodi trims it to an empty line, which ends its
      text -- both drop what follows; ffmpeg's demuxer keeps it (a stream copy into MKV too,
      measured), VLC 3 as text, and MPC-HC (`STS.cpp`), Subtitle Edit (`SubRip.cs`),
      mkvmerge (its 2011 source; the current one, on GitLab and Codeberg, unreachable here), srt
      and pysubs2 read on. A number alone stays the next cue's index only with
      empty lines alone before the timing line, as ffmpeg's demuxer reads it; a line of
      spaces before an index is no missing blank line, unnoted. `Dialect.blank` (SubRip's
      ` *`, `ends` none), `Found.spaced`, the open cue's blanks in `cues._Blanks`. Tests: 7
      cases (6 readers', ffman's `spaced.srt`) failing first, 2 guards; nine mutations, each
      caught. Differential, 60000 generated files: the 19062 without a line of spaces read
      exactly as HEAD reads them, cues and notes; the rest as an independent reading of the
      rule reads them, 0 mismatches (HEAD's on 9797 of the first 20000). Suite 2237, 100%;
      matrix 770; outcome report: 476 identical, `spaced.srt` new, on 3.13 and 3.14; the
      `subrip` skill's ffman column, reading and record re-measured, its sources pinned
      (MPC-HC, Subtitle Edit, Kodi).*
- [x] Found by the `webvtt` box: in a WebVTT text ffman removes `{\...}` override blocks and
      reads a typed `\n` or `\t` as a space -- SubRip's reading -- where Chromium, ffmpeg and
      VLC show them as written (measured; VLC by source). To decide: as written in WebVTT;
      or as now.
      *Done (as written, the owner's standing rule: better by proof, so not asked): its
      override blocks and typed escapes are text, as every reader shows them, unnoted --
      nothing lost. The proof: SubRip's reading broke a WebVTT's backslash -- `C:\new
      \table` burned `C: ew able` -- and glued a reference across an override, `&am{\b1}p;`
      read `&`; Chromium 141 shows both as written (measured). `subs/markup.py`: WebVTT's
      `clean` takes its tags alone, its written breaks spaces once decoded with the
      references' (`_VTT_BREAK`, `_MARKED_OVERRIDE` gone); burned as written through
      libass's escapes (Text drawn as written), attached exactly (Attached text: MKV and WebM
      decoded back as written; MP4's `{...}` hidden by its decoder, as before). Tests: 8
      failing first (4 earlier ones changed: the WebVTT `{\an8}`, two decoded runs, the
      override order), 2 guards; four mutations, each caught. Differential: 9000 generated WebVTT texts of
      braces, backslashes, tags and references read as Chromium 141 renders them
      (`getCueAsHTML`'s text), 0 differ -- HEAD's code, 1520 of the first 3000. Suite 2243,
      100%; outcome report: 476 identical, `burn/hostile/settings.vtt` changed (`{\an8}`
      drawn), `typed.vtt` and `attach/typed-vtt` new, on 3.13 and 3.14; matrix 770; the
      `webvtt` skill's ffman column, rule 6 and record re-measured.*
- [x] Found by the `webvtt` box: a WebVTT text's `<` with no `>` after it is kept by ffman
      (`before <b ends`), where Chromium and ffmpeg lose the rest of the cue and VLC keeps it
      (measured; VLC by source). To decide: as the W3C, the rest dropped, noted; or as now.
      *Done (as the W3C, the owner's standing rule: better by proof, so not asked): a `<` no
      `>` closes opens a tag to the text's end, as Chromium 141 and ffmpeg 8.1.2 show it, the
      rest dropped, noted: `1 texts cut at a < with no > after it, a tag to their end (W3C):
      the first, <3 you`. The proof: a `<` before a `>` was already a tag and one with none
      text -- VLC's rule alone, one character read two ways; Chromium and ffmpeg (so mpv) lose
      the rest. A SubRip's stays text, as ffmpeg's subrip decoder shows it (measured).
      whisper.cpp, OpenAI whisper and WhisperX escape no `<`: their `I <3 you` is now cut,
      noted, as a browser cuts it. `subverter/markup.py`: `untagged(..., webvtt=True)` and
      `unclosed`; `clean` reads WebVTT's tags so, `ingest` notes the cut.
      Tests: 9 failing first, 2 guards; eleven mutations, each caught (the note's trim once
      survived: `unclosed.vtt`'s first cue now ends in blanks). Differentials, 9000 generated
      texts each against Chromium 141 (`getCueAsHTML`) and ffmpeg 8.1.2's decoder: 0 differ --
      HEAD's code, 1305 of the first 3000 against Chromium. Suite 2255, 100%; matrix 770;
      outcome report: 479 identical, `unclosed.vtt` new, on 3.13 and 3.14; the `webvtt`
      skill's ffman column, reading rule and record re-measured; a `subtitle-mappings` row.
      Its review found `untagged` seeking a tag from each `<` past the last `>`, squared steps
      -- 35 s at 200,000 of them: a SubRip of that one cue ingested in 104 s, a WebVTT in 34 s
      (WhisperX's test), now 0.01 s -- fixed apart: none sought there, equal to its regexes (a
      property test), bounded (3 cases, 2 failing first); five mutations, each caught. Its
      second review found `clean`'s overrides alike, in LRC, CSV, TSV and JSON -- an LRC line of
      200,000 `{\` read in 34 s, now 0.01 s -- fixed apart: none sought past the last `}`, equal
      to its regexes (a property test), bounded in every format (6 cases, 4 failing first); four
      mutations, each caught. The same probe found SubRip's timing line split by `[ \t]*-->`,
      scanning a run of blanks again from each -- 200,000 before an arrow, 36 s -- now split at
      its first arrow by `str.partition`: read as HEAD reads 60000 generated files, 0 differ;
      bounded (2 cases failing first), its tabs and first arrow pinned (2 guards); four
      mutations, three caught, the fourth (`lstrip()`) caught by the next fix: a VT or FF after
      the arrow, text before, now a blank, as ffmpeg's `sscanf` skips it (`srtdec.c`, measured;
      a no-break space none): 1 case failing first, 1 guard; five mutations, each caught.*
- [x] Found by the `<` box: a note quotes its text whole -- a cut rest, a stray block's first
      line, a dropped line -- so a 400,000-character line is that much on stderr. To decide:
      cut at a length, marked; or as now.
      *Done (cut, marked -- the owner's standing rule: better by proof, so not asked): a note
      names a text whole up to 85 characters -- a cue at its longest by Netflix's Timed Text
      Style Guide (English (USA), II.3 and II.13), two lines of 42 and the space joining them,
      so no note a conforming file makes changes -- else by its first 85, then `... (N more
      characters)` (`subverter.excerpt`, `notes.py`); ffmpeg bounds a log message too, at 64
      KiB (`libavutil/log.c`). Every note quoting a transcript's text, eight: WebVTT's dropped
      and stray lines; SubRip's odd time, index, and text after an empty line or a line of
      spaces; ffman's braced run and cut rest. Tests: 15 failing first (4 `excerpt`'s, 6 the
      readers', 3 ffman's, `quoted.srt` one, and the huge and long fractions, changed), 1 guard;
      thirteen mutations, each caught. Suite 2287, 100%; matrix 770; outcome report: 480
      identical, `quoted.srt` new, on 3.13 and 3.14. Its review counted the failing tests
      again on the code before it (15, not 13) and gave the fractions' test literal quotes, no
      longer `excerpt`'s own. Replaced by the next box: `shown`, the suite's rule already.*
- [x] Found by the note-quote box: a note or a refusal prints a transcript's control
      characters raw -- an ESC in a stray line reached stderr as it was, an OSC setting the
      terminal's title, an SGR its colour (measured); a file name's alike, in a refusal (`not
      UTF-8: x<ESC>[31m.vtt (line 4)`). ffmpeg's log writes `?` for each C0 control but BS to CR
      (`libavutil/log.c`, `sanitize`). To decide: shown escaped (as Python's `repr`, or `?` as
      ffmpeg's); or as now.
      *Done (escaped, as Python writes them -- the owner's standing rule: better by proof, so
      not asked): its research found `shown` (`errors.py`), the suite's rule for input in a
      message since 6.6.3 -- one line, each character visible, 60 characters at most -- ffmeta's
      copy held equal (`tests/test_copies.py`); the note-quote box's `excerpt` had missed it.
      So: a note quoting a transcript's text quotes it by `shown`, subverter's own copy, held
      equal too (`excerpt` and `notes.py` gone, never released); and every line on stderr --
      `note`, a refusal, an environment's error -- writes each control character, Unicode's Cc
      (C0, DEL, C1), as Python does (`errors.escaped`), uncut: a file's name stays whole.
      Python's escape names the character, where ffmpeg's `?` loses it. Tests: 20 failing first
      (5 `escaped`'s, 7 the readers' notes, 2 the fractions', 4 ffman's notes, the outlets'
      one, the copies' one), 1 guard; seventeen mutations, sixteen caught -- the one left
      the tab's own escape in `_ESCAPED`, which Python's `repr` writes alike (dead in each
      copy: the next commit). Suite 2292, 100%; matrix 770; outcome report: 480 identical,
      `quoted.srt` changed (its first 57 and `...`), `controls.vtt` new, on 3.13 and 3.14. It
      found a box: standard output, as written. Its review: a refusal's line written by `note`
      too, one writer escaping (`cli.main` had its own two); the decision's and `AGENTS.md`'s
      cells kept within their tables' widths (172 lines realigned, back to 2).*
- [x] Found by the control-character box: standard output writes its control characters as
      they are -- the output's path, `--dry-run`'s commands (`shlex.join` quotes, not escapes),
      `meta -o -`'s file. Data a script reads: `ls` escapes only to a terminal (GNU coreutils 9.4,
      measured: `'x'$'\033''[31m.vtt'` there, the bytes in a pipe). To decide: escaped to a
      terminal alone; or as now.
      *Done (escaped to a terminal alone -- the owner's standing rule: better by proof, so not
      asked): the output's path and `--dry-run`'s commands written by `put` (`media/run.py`):
      to a terminal, each control character as `note` writes one; to a pipe or a file, exactly,
      as `ls` -- the outcome report, its stdout a pipe, unchanged. `meta -o -`'s file stays as
      it is: content, as `cat` writes it, its line breaks text. Weighed: `$'...'` quoting, which
      would paste (POSIX.1-2024, 2.2.4: its octal escapes bytes), but dash 0.5.12 -- Ubuntu's
      `sh` -- reads it as text (measured: `$a\033b`), so a command shown escaped is shown, not
      pasted. Tests: 3 failing first (the commands', the convert path's, `meta`'s path), 1
      guard (the pipe's); five mutations, each caught. Suite 2296, 100%; matrix 770; outcome
      report: 482 identical, on 3.13 and 3.14. Its review found a terminal shown a name's byte
      not UTF-8 raw (`os.fsdecode`'s lone surrogate, written back by stdout: 0x9B, an 8-bit
      terminal's CSI) where stderr wrote `\udc9b`: `escaped` takes lone surrogates too, so both
      write them alike (measured on a pseudo-terminal), stderr's bytes unchanged; and the spec
      marks the printed path's escaping new, not the path.*
- [x] Found by the note-quote box: ffmeta's notes quote names and values whole -- a tag's
      name, a CATALOG or ISRC value, a FILE's name (eleven notes, not by `shown`) -- unbounded,
      as the transcripts' were; their control characters now escaped on stderr. To decide: by
      `shown`, as its refusals; or as now.
      *Done (by `shown`, as its refusals -- the owner's standing rule: better by proof, so not
      asked): every ffmeta note and refusal quoting a name or a value its format has not
      checked as its own quotes it by `shown`: a tag's name (Vorbis' writer, a chapter's, the
      joined ones, ffmetadata's NUL and repeated key, the cue writer's no field), a CATALOG, an
      ISRC, FLAGS, a FILE, a REM's word, and `--set`'s and `--chapter`'s names and titles --
      eighteen sites; the new chapter's two notes by the refusals' own `what` (DRY). Left as
      they are, checked first: a field's own name in its case (`genre`, `NAME`, `ISRC`), a
      `--pregap`'s `N=TIME`, a chapter comment's `CHAPTERxxxNAME`, a cue's keywords and
      numbers. Tests: 18 failing first (12 notes, 6 refusals: `tests/test_quoted.py`, a name
      of an ESC and 100 more); twenty mutations, each caught. Suite 2316, 100%; matrix 770;
      outcome report: 482 identical, `meta/quoted-name` new, on 3.13 and 3.14. Its review named
      two locals by what they hold (`name`, `unset_name`; `given`), and the decision's list the
      options whose names are quoted.*
- [x] The owner's review (2026-10-13): SubRip and WebVTT end to end -- the approach, the layout, the
      architecture, DRY, the standards, researched again (the W3C's WebVTT still at `0648025`;
      ffmpeg 8.1.3's readers and decoders as 8.1.2's).
      *Done (the owner's standing rule: better by proof, so not asked). Proven as they were:
      WebVTT's cues as a fresh transcription of the W3C's parser reads them, 0 of 50000 generated
      files differ (the transcription Chromium 141's on 1500); its cue texts as Chromium's, 0 of
      3000; SubRip's cues as ffmpeg's demuxer, 0 of 6000 but for the recorded readings (Index
      lines). Found and fixed: a SubRip's `<` read as any `<...>` -- `1 < 2 and 3 > 2` burned `1 2`,
      `one<br>two` `onetwo` -- now as ffmpeg's decoder reads a tag, `<br>` a line break (SubRip
      tags); a typed `\t` a space, bash's rule for jq's @tsv, now text, as libass and VLC draw it
      (ASS escapes); a UTF-16 SubRip refused as no timed text, now read as ffmpeg recodes it, and a
      UTF-16 WebVTT's refusal so named (Transcripts in UTF-16); a STYLE or REGION block before a
      form feed noted as dropped text. Layout: each text reader reads its file's bytes, its encoding
      its own as its line ends (`utf8.file_text` shared); SubRip's and WebVTT's tests in
      `test_cues.py`, as `readers/cues.py`; the whole-file readings property tests, the W3C's parser
      and ffmpeg's demuxer transcribed -- before, differentials run once. Tests: 31 failing first
      (11 the UTF-16's, 19 the tags' and escapes', the form feed's); 23 mutations of the tags'
      reading, each caught; 9 of the readers against the new properties, 8 caught, the last
      equivalent there (a split character's empty part). Measured: 5000 generated SubRip texts of
      tags through ffmpeg 8.1.2's decoder, then libass, 0 differ (before, 3350); with braces and
      backslashes, 199, each a tag beside the text's own `{` or `\` (Braced runs). Suite 2363, 100%;
      matrix 770; outcome report: 483 identical, `markup.srt`, `utf-16.srt`, `utf-16-bad.srt` and
      `utf-16.vtt` new, on 3.13 and 3.14. Weighed, left: SubRip's lenient timing lines (the owner's,
      Timing lines); a cue whose only line is a number with a blank after it (ffmpeg keeps it, here
      an index); `Dialect.blank` for WebVTT, its `ends` read first; `Reading`'s two booleans;
      `unescaped`'s name, its docstring stating its reach.*
- [x] The owner's assessment (2026-10-13): the review's open points weighed again, each end to
      end -- the 199 texts, and each left one.
      *Done. Changed: SubRip's times are the players' (Timing lines) -- bash's bare number, its
      minutes alone and a decimal in a part made `2024 --> 2025` in a cue's text a timing line,
      its text lost; now ffmpeg's `sscanf`, the fraction optional (VLC 3's, by source).
      `unescaped` is `drawn` (unreleased: 0.1.1 has neither). Tests: 14 failing first; 12
      mutations of the grammar, each caught. Measured: 15492 generated lines read as ffmpeg
      8.1.2's demuxer reads them, but 338 without a fraction (VLC's) and 154 past 2^31 ms
      (ffmpeg's `int` wraps). Before, on those lines, 12876 read alike: 2377 text lines taken for
      timing lines, 33 timing lines for text, 196 other times; after, 14990, the rest those two
      and 10 of no length (ffprobe prints no duration; alike). Whole files, 6000: the same 280
      differences before and after (Index lines). A blank run's failed match given back blank by
      blank, 14 times the old cost -- possessive now, at or under it. Outcome report: 486
      identical, `no-newline.srt` refused, `years.srt` new, on 3.13 and 3.14. Left: the 199
      texts, each a tag beside the text's own `{` or `\` (ffmpeg's exact b/i/s/u blocks leave
      41, each a font's -- the owner's, not taken); a cue's
      only line `2 ` (ffmpeg's two-case rule, rare); `Dialect.blank`; `Reading`'s two booleans,
      one value with the ASS reader (6.8.3, the model).*
- [x] The owner's review (2026-10-13), the second: SubRip end to end, fresh -- every recorded
      decision weighed again against ffmpeg's sources (n8.1.2: `srtdec.c`, `subtitles.c`,
      `htmlsubtitles.c`, read again) and VLC 3.0.x's (`subtitle.c`).
      *Done (the owner's standing rule: better by proof, so not asked). Kept, each optimal by its
      evidence: the timing grammar (15492 lines read as ffmpeg reads them, but the two recorded),
      short fractions, line ends, cue ends, index lines (ffmpeg's `strtol` cache read again: a
      number alone the index, a negative one text), UTF-16 and UTF-8, the NUL, the tags, braces and
      escapes (`drawn`), the attached text. Found and fixed: a time without a fraction read unnoted
      -- the one SubRip reading where the players disagree that went unsaid -- now noted
      (Timing lines); a cue ending before it begins, or beginning with the next, dropped
      unnoted though a player shows its text (an ffmpeg burn draws a reversed one to the next
      start, the last to the end, measured) -- now noted, one of no length, before 0 or a
      duplicate of the text kept silent (Dropped cues); ffman's `paint.drawn` named as
      subverter's `drawn`, its inverse -- now `literal`; the timing grammar's differential run
      once -- now a property test, ffmpeg's sscanf transcribed (9 of the grammar's 12 mutations
      caught by it, the rest by the parametrized tests); ffmpeg's index rule worded loosely
      ("a line starting with a number": not a negative one). Tests: 3 and 2 failing first; 10
      mutations of the notes, each caught. Suite 2380, 100%; matrix 770; outcome report: 488
      identical, `bare.srt` and `dropped.srt` new, on 3.13 and 3.14. Left: an untimed cue
      dropped unnoted (the owner's, Transcript values); ffmpeg's 4095-byte line split (its
      buffer's; ffman reads the line whole).*
- [x] `ass`: the same, SSA (v4) through it.
      Found by the SubRip and WebVTT review: ffman's UTF-16 reading of an ASS (`subs/ingest.py`,
      `_utf8`) and subverter's of a SubRip (`subrip._text`, `utf8.UTF16_BOMS`), one.
      *Done: `.agents/skills/ass/` -- `SKILL.md` (the format; its readers -- libass alone,
      ffmpeg's demuxer then libass (mpv, the `subtitles` filter, every conversion), VLC 3,
      Aegisub, ffman -- side by side, 13 rows; what ffmpeg makes of it in SubRip and WebVTT; the
      writers; the rules for a script all of them read alike, the time rule as code; reading
      one; converting, muxing and burning; an example; sources); `references/format.md` gains
      libass alone against ffmpeg's reading then libass (the `ass` and `subtitles` filters, 13
      scripts drawn), the demuxer's field order and separator, VLC 3's and Aegisub's readings
      (by source) and ffman's (measured); `scripts/measure_ffmpeg.py` those cases, ffman's with a
      PYTHON, and the skill checked from its own text -- the example's events, its drawing by
      libass alone, its SubRip, the prose stating them, the time rule over 7233 times to 100 h as
      ffmpeg reads them, the six commands' streams -- exiting 1 on a difference (five dosed
      mutations, each caught alone; one underdosed first, `.05` to `.5` reading alike, then
      `.50`).
      libass 0.17.4, nixpkgs' pin, built from its tag: `measure.py`'s and the drawings alike to
      0.17.1's. VLC 3.0.24, mpv 0.41.0 and Aegisub 3.4.2 by source. `quick_validate.py`: valid
      (description 983 of 1024). Three evals (`evals/evals.json`, new instances, measured)
      answered cold from the skill alone: a comma before a fraction drawn by the `subtitles`
      filter, not the `ass` one; fields in another order, no cue converted; one fraction digit
      7.03 s in mpv, 7.3 s in Aegisub -- each right; the third read `.500` as 5 s, the row's
      example ambiguous, now `0:00:01.500`. The UTF-16 reading one: `utf8.utf16`, SubRip's and
      ffman's ASS copy's, each counting its lines as its reader splits them (`b98da2a`). Its
      review, then an independent reviewer's, two rounds, each claim checked against the sources
      and binaries: a `{` opens a block only before a `}`; VLC draws no event it did not read, nor
      reads a time with a comma; Aegisub opens none; SubRip drops a style's strikeout, and both
      formats break at `\n`; two NULs, or one first in a line, end ffmpeg's reading; ffmpeg reads
      a lone surrogate as a NUL, an odd last byte as a character (decisions, mappings);
      `-sub_charenc` recodes the events alone; mpv never draws the last event ending before it
      starts (by source). Each measured where it could be, now in `measure_ffmpeg.py`
      (`f5ae8fa`..`2520e71`). The evals untouched by them, not rerun.*
- [ ] Found by the `ass` box: ffman passes an ASS through unread, so where libass alone (its burn)
      and ffmpeg's reading (`--add-subs`) differ, the two differ, unnoted -- measured: fields in
      another order or CR line ends alone, burned, attached with no cue; a comma before a fraction
      or an event ending before it starts, attached, not burned. And its conversion to MP4 and WebM,
      unnoted (the ASS and LRC review, measured): a block no `}` closes (`a {\b1 b`), drawn as
      written by a burn, cuts the attached text there (MP4 `a `, WebM `a <b>`); a comment block
      (`a {x}b`), hidden by a burn, attached as written; a script of no styles section, a type by
      `ScriptType` alone, its MP4 text of size 0, black and transparent: nothing drawn. To decide
      with 6.8.3's ASS reader: refuse, write the copy as both read it, or note.
- [x] `lrc`: the same.
      Found by the SubRip and WebVTT review: an LRC in UTF-16, which ffmpeg's reader recodes as a
      SubRip's; its typed `\t` and `\n` spaces and every `<...>` a tag (bash's rules, for jq's
      @tsv); its tests in their own file, out of `test_readers.py`.
      *Done: `.agents/skills/lrc/` -- `SKILL.md` (the format; its readers -- ffmpeg's demuxer and
      `text` decoder, so mpv but for the last line, Navidrome 0.64.2, Jellyfin 12.2 through
      LrcParser 2025.623.0, ffman -- side by side, 19 rows; what ffmpeg makes of it; the writers;
      the rules for a file all of them read alike, the time rule as code; reading one;
      converting, muxing and burning; an example; sources); `references/format.md` rewritten from
      the sources and `scripts/measure.py`, which now measures ffman's reading beside ffmpeg's, the
      conversions' text and last line, a burn's last line, the copies into MKV, MP4 and WebM, and
      checks the skill from its own text -- the example's events, its SubRip and ffman's reading,
      the prose stating them, the time rule over 6029 times to 100 minutes as ffmpeg reads them
      and each stamp Navidrome's and LrcParser's grammar, the five commands' streams -- exiting 1
      on a difference. Measured: the last line, given no duration by ffmpeg's demuxer, never
      burned and a cue of no length converted, unless an empty stamped line ends it (mpv shows it
      to the end, by source). `quick_validate.py`: valid (description 972 of 1024). Three evals
      (`evals/evals.json`, new instances, measured) answered cold from the skill alone: the last
      line lost by a burn, Jellyfin's two-digit fraction, Navidrome's two-digit minutes past
      whisper.cpp's 99 -- each right.
      The found items: the box's first was wrong -- ffmpeg 8.1.2's LRC reader reads raw bytes
      (`read_line`), so a UTF-16 LRC is no LRC to it (measured), the "Transcripts in UTF-16" row
      corrected; Navidrome and Jellyfin read it, now ffman too, a unit not UTF-16 refused by its
      line (`eb867c8`; `subrip.file_lines` shared). Its text: as ffmpeg and Jellyfin show it, its
      Enhanced LRC word stamps off as Navidrome and Jellyfin take them -- `x<3 and y>2` no longer
      burned `x2` (`0ad33d8`, `cf9ac7b`; "LRC texts"), the markup one value in ffman, `Markup`
      (`07d90e3`, `4388c8d`). Its tests: `test_lrc.py`, the same 15 (`06b5891`). Tests: 5 and 2
      failing first (UTF-16), 13 and 3 (the text); suite 2405, coverage 100%; the outcome report,
      `burn/hostile/utf-16.lrc`, `utf-16-bad.lrc` and `markup.lrc` new, the rest identical.
      Reviewed by an independent reviewer, two rounds, every claim against the sources and
      binaries: Navidrome drops the text before a line's first word stamp; a SubRip reader shows
      word stamps, a WebVTT one drops them; mpv takes a first stamp with a fraction alone; a file
      for every reader holds no `{` (`e92e17f`). The owner's review: ingest names the markup
      `markup`; 11 planted mutations of the box's code, each caught by its tests (`54ad39b`).
      Found: the next box.*
- [x] Found by the `lrc` box: an LRC line ffman drops is unnoted -- one with blanks before its
      stamp (` [00:02.00]two`), which Navidrome and Jellyfin read and ffmpeg 8.1.2 drops only
      because `read_ts` skips the blanks but hands `sscanf` the line from its start; one of hours
      (`[1:02:03.00]`), which Navidrome reads; a sign, a comma before the fraction. To decide: read
      the first (and the second?), note the rest; or as now.
      *Done, better by proof (the owner's standing rule): blanks (a space or a tab, ffmpeg's)
      before a stamp read, as Navidrome and Jellyfin read them; a minus a time before 0, as
      ffmpeg's `lrcenc` writes it and its `lrcdec` reads it (measured: `-itsoffset -2` writes
      `[-00:01.00]`); every other line but a tag or an empty one dropped -- each kind noted,
      counted, the first named (`be92d5b`; "LRC lines"). Hours not read: no writer found writes
      them (ffmpeg's `lrcenc`, whisper.cpp's `-olrc`, LrcParser's encoder count minutes past 59),
      and the readers disagree -- `[1:02:03.00]` 62 s to ffmpeg, 3723 s to Navidrome, no line to
      Jellyfin; `[a:b:c]` m:s, h:m:s, or ModernLrc 2.0's mm:ss:ff. A plus, a comma, a colon
      fraction: ffmpeg's text garbled or its fraction lost -- dropped. Kept: `[offset:]` first on
      its line (the LRC offset row); a CP1252 byte in a line opened by blanks now refused by its
      line, as in any line read. The skill's ffman column, its reading prose and rule 4
      re-measured (`c2b5170`). Tests: 5 failing first, then 1 (a minus of 0); 19 planted
      mutations, each caught (two survivors first, pinned: the blank set, the named line
      trimmed); suite 2412, coverage 100%; the matrix 770; the outcome report on 3.13 and 3.14,
      `burn/hostile/lines.lrc` new, the rest identical. Reviewed by an independent reviewer, two
      rounds, every claim against the sources and binaries: a minus of 0 no longer noted;
      Navidrome reads the colon form as h:m:s; the README's empty line; a test comment; a
      docstring. Found: the next box.*
- [x] Found by the LRC lines box: a refusal for no timed text (`subs/ingest.py`) drops the
      reading's notes -- an LRC of hours alone is refused `no timed text found in: x.lrc`, without
      why; every format alike (a WebVTT whose every cue is dropped). To decide: the notes printed
      before the refusal, or named in it; or as now.
      *Done, better by proof (the owner's standing rule): the notes before the refusal, each its
      own `ffman: NOTE` line, its words unchanged (10 tests') -- the order ffman already tells a
      transcript's notes and a later refusal in (`burn._check_timings`); folded into the message,
      several notes one long line. A refusal carries the notes that led to it (`FfmanError.notes`,
      `refuse(message, notes)`, typed a tuple), `cli.main` telling them first; ingest refuses after
      building every note -- the normaliser's (cues ending before they begin) and the markup's
      (braced runs hidden) were built after it (`1a371fa`; "No timed text"). A cue of no text or
      of no length stays unnoted, as no player shows it (Dropped cues). The `lrc` skill's script
      records a refusal's notes, its reading refused after them (`b6f3cbe`); the `webvtt` skill's
      row stays true (refused), its script left; `subtitle-mappings`' for its box. Tests: 7
      failing first; 8 planted mutations, each caught (one survivor first, pinned: two notes, in
      order); suite 2420, coverage 100%; the matrix 770; the outcome report on 3.13 and 3.14,
      `burn/hostile/no-line.lrc` new, `crcrlf.vtt` and `reversed.srt` each its note before the
      refusal, the rest identical. Reviewed by an independent reviewer, two rounds: the spec
      narrowed to the notes ffman gives, the tests' count, the notes typed a tuple (a bare string
      had split into characters), the decision's maker, a row's pointer.*
- [x] The owner's review (2026-10-14): `ass` and `lrc` end to end -- code, docs and skills, each
      claim against the sources and binaries.
      *Done (the owner's standing rule: better by proof, so not asked). Found and fixed. LRC
      (`d6b46ed`; "LRC repeated lines", "LRC lines", "LRC offset"): lines sharing a stamp, as
      ffmpeg's lrcenc writes a cue of two lines, each but the last dropped unnoted -- now one cue,
      their texts joined, noted, a text its start shows already once (as ffmpeg shows it, the
      earlier of no length), each line counted once; seconds past 60 now read, as Navidrome and
      Jellyfin read them, noted, of more digits (no reader's) dropped, noted; each `[offset:]`
      ignored noted by its reason, counted -- after blanks, not whole, past a double's range,
      another after it. ASS (`d78807f`; "Attach", "ASS styles", "ASS script", "ASS NUL"): attached
      through its named demuxer (`-f ass`) -- a script after a MiB of blank lines, past ffmpeg's
      probe, an empty track before; a burn's look (`--font`, `--font-size`, `--font-color`,
      `--outline-color`, `--margin-bottom`) refused with one, burned in its own styles -- ignored
      before; refused as no script after its NUL notes; ffman's font no longer noted missing with
      one, which names its own (`a545937`). The `[Script Info]`-first rule kept, its reason
      restated: ffmpeg's detection, so the file is one `ffmpeg -i` takes for ASS -- the attach names
      the demuxer, and libass seeks no signature. Skills (`07504d0`): mpv draws an LRC line not
      UTF-8 as Latin-1 (`lavc_conv.c`); LRC lines of one stamp; seconds past 60; Navidrome's `.elrc`
      first, `[bg:]` joined, a mid-line tag losing its lyric; Jellyfin's plain-text fallback; ASS
      times under 10 hours (`assenc.c` writes past them `9:59:59.99`); a style name's trailing space
      kept by libass 0.17.4, trimmed by 0.17.1; `\k` read to the millisecond (`ass_parse.c`); the
      `ass` self-check seeing a one-digit fraction; SubRip keeping strikeout as a tag alone; a block
      no `}` closes cut there by ffmpeg's conversions, drawn as written by libass (measured, now in
      `measure_ffmpeg.py`). Tests: 27 failing first on `c6066e6`'s code, then 2 (the squared steps,
      the blanks); 10 planted mutations of the last two rounds, each caught; the skills' 6 dosed
      mutations, each caught alone. Suite 2448, coverage 100%; the matrix 770; the outcome report
      against `c6066e6` on 3.13 and 3.14: 493 identical, 10 changed -- `attach/` `ass-mp4`,
      `ass-webm`, `nul-ass`, `t.ass`, `t.ssa`, `utf-16-ass` (`-f ass`), `burn/ass-font-size`
      (refused), `burn/hostile/` `offset.lrc`, `shared.lrc`, `twice.lrc`. Reviewed by three
      independent reviewers (LRC, ASS, the skills), three rounds each: a line of many equal stamps
      read in squared steps, its text read once a stamp -- now once a line, its blanks squeezed as
      shown; an MP4's header lengthened too; a script of no styles transparent in MP4. Left,
      weighed: one builder for the counted notes (each reader's wording its own); a dropped line's
      byte not UTF-8 shown `\udcXX` in its note (it need not be UTF-8); `_script`'s scan (linear); a
      stamp past a double's range beside others (no line, the rest kept, unnoted); an offset within
      the latest stamp's time of a double's range (every time pushed past it); the `webvtt` skill's
      script notes; a highlight option with an ASS refused by the highlight rule first (bash's
      order, M5's); CI for the skills' self-checks (the owner's). Found: the next three boxes.*
- [ ] Found by the ASS and LRC review: a text holding U+FFFE, a noncharacter but valid UTF-8,
      read by ffman; ffmpeg's decoders refuse it (`utf8_check`), so the cue is dropped from an
      attached track with a log line alone, unnoted (measured: a SubRip's second cue, `a` U+FFFE
      `b`, lost) -- every format alike. To decide: note, replace it, or as now.
- [ ] Found by the ASS and LRC review: an attached ASS is not clipped, as the other formats are
      (Attach) -- an event ending past the media's end lengthens the output to that event's end
      (measured: 3 s to 30 s -- Matroska, WebM, an MP4 in its header, `mvhd`, though ffprobe shows
      the media's past about a second). To decide with 6.8.3's ASS reader: clip the copy, note, or
      as now.
- [ ] Found by the ASS and LRC review: an ASS of no event is burned and attached, unnoted --
      any other format of no timed text is refused (No timed text). To decide with 6.8.3's ASS
      reader: refuse it alike, note, or as now.
- [x] `whisper-transcripts`: the same -- whisper-cli's and WhisperX's JSON, CSV, TSV and plain text.
      Found by the SubRip and WebVTT review: CSV's, TSV's and JSON's typed `\t` and `\n` spaces and
      every `<...>` a tag (bash's rules, for jq's @tsv), and their encodings; their tests in their
      own files.
      *Done: `.agents/skills/whisper-transcripts/` -- `SKILL.md` (the formats: whisper-cli's `-oj`,
      `-ojf`, `-ocsv`, `-otxt`, ffmpeg's `whisper` filter's, OpenAI whisper's and WhisperX's; their
      readers -- Python's json and csv, pandas 3.0.5, jq 1.7, ffmpeg 8.1.2, ffman -- side by side,
      13 rows; what each holds; the rules for a transcript all of them read alike, the time rule as
      code, `transcript` and `to_ms`; reading one; converting; an example; sources);
      `references/format.md` gains the filter, the readers and WhisperX's releases;
      `scripts/measure.py` takes the four source trees, cuts the filter's writer from `af_whisper.c`
      (against libavutil), reads every writer's file by each reader, a BOM and UTF-16 too, and
      checks the skill from its own text -- the example as Python, jq and ffman read it, the time
      rule at 12 edges by hand (two negative), through `transcript`, and over 4025 times as ffman
      reads them and against `round(1000 * t)` (202 differ: 1.0005 s, 1000 against 1001), a text no
      JSON number or one past 10^±400 refused, the prose stating them -- exiting 1 on a difference,
      a reader absent said skipped. Measured: the filter's `json` one object a line, its text not
      escaped (a `"` breaks it), `srt` numbered from 0, `[BLANK_AUDIO]` removed in any case; jq
      takes each lone byte of a split character as U+FFFD and NaN as `null`; pandas reads an OpenAI
      TSV row a newline broke as a row of its own; `csv` and pandas read a TSV text opening with `"`
      as quoted, rows merged (`quoting=csv.QUOTE_NONE` reads it), and pandas a text `NA` as NaN, a
      rule-3 CSV's too (`keep_default_na=False` keeps it); `json.load` of a file with a BOM refused;
      ffmpeg opens a `.txt` whose first line opens with `[` as an LRC, no cue. Read by tag: WhisperX
      writes a word it cannot time alone in 3.1.0 to 3.3.2 and the patch releases of 2026-03-10
      (3.8.2 among them); 3.8.3 and every release since interpolate it. `quick_validate.py`: valid
      (description 980 of 1024); 4 evals. The found items: CSV's, TSV's and JSON's texts plain -- no
      writer marks one up -- so a tag, a brace, a backslash and a typed `\n` burned and attached as
      written, a tab or a line break a space (`a90b821`; "Plain texts"); a CSV or TSV in UTF-16 read
      by its BOM, as a SubRip and an LRC (`4fbf0eb`); their tests in `test_table.py` and
      `test_whisper.py`, the same 45 (`eab74ac`); the table reader its own `read`, one `bom_text`
      for a file's text by its BOM (`be5f12c`; the outcome report against its parent: 510
      identical). Tests: 5 failing first for the plain texts, 3 and 7 for UTF-16 (ffman's,
      subverter's); the skill's 11 dosed mutations, each caught, its 2 controls clean; suite 2467,
      coverage 100%; the outcome report against `dde58ad` on 3.13 and 3.14: 503 identical,
      `burn/hostile/` `markup.csv`, `markup.tsv`, `markup.json`, `utf-16.csv`, `utf-16.tsv`,
      `utf-16-bad.tsv` and `attach/markup-csv` new. Reviewed by two independent reviewers (the code,
      the skill): the decisions' rows pointing at "Plain texts", the skill's BOM, quoted-TSV,
      float-time and WhisperX-release claims corrected, its self-check made to hold without ffman
      (the rule's edges by hand). Then an end-to-end review, with a third independent reviewer and a
      cold run of the four evals: the attached track named and recorded (`attach/markup-csv`, the
      fixtures' rows inside its 0.4 s media); `to_ms` exact and half up toward +infinity, as ffman
      (a `Fraction`: `Decimal`'s `ROUND_HALF_UP` took a negative tie away from 0), a text no JSON
      number refused (`Fraction` read `1/2`, `1_0`, a bool), and one past 10^±400 (`1e999999999`
      built a billion-digit integer, as ffman's bound says); the tests' expectations stated whole;
      the filter's `json` salvaged and a broken TSV row joined back, stated; the "Braced runs" row
      and `words.py`'s docstring corrected; `measure.py`'s one JSON verdict. Left, weighed:
      whisper-cli's `-di` with `-tdrz` (the CLI refuses the pair); a UTF-16 unit refused by its
      physical line; a UTF-16 JSON's lone surrogate refused `not UTF-8` (its message); a UTF-32 LE
      file read as UTF-16 by its first bytes, then refused for no timed text (no writer of one;
      before, as garbled); the bounded-work test's plain cases, kept as guards;
      `untagged(..., webvtt=False)`, public, its last caller gone. Found: the next four boxes.*
- [x] Found by the `whisper-transcripts` box: OpenAI whisper's and WhisperX's TSV keep a newline in
      a text (`WriteTSV`: tabs alone made spaces), so the rest of that text is a line of its own,
      one field -- ffman reads it as a record of no time, dropped, the text cut unnoted (measured:
      `past an hour\nnewline`, `newline` lost). Their writers make every tab a space, so a line
      without one after a record is that record's text. To decide: join it to the record before,
      note it, or as now.
      *Done: in a TSV whose text is its last column, a line of no tab after a record ending at it is
      that record's text, a line break in it -- burned and attached a space -- noted
      (`1 TSV lines of no tab read as the text of the record before ...`); each run of line ends one
      break, a blank line no line of it; a byte not UTF-8 or a NUL on a later line told at its
      record's first, as a quoted CSV field's; a CSV unchanged; the lines joined once, in bounded
      work (400,000: 0.13 s; one by one, 5.7 s) (`937fecc`; decisions' "TSV line breaks"; the
      skill's cells and eval 2, `3fe6344`). The owner's standing rule, better by proof: both
      writers' `WriteTSV` (openai-whisper v20250625, WhisperX 3.8.5, byte-identical outputs) write a
      record's first line with two tabs, so a line of none is only a text's rest. Tests: 5 failing
      first (subverter's), 1 (ffman's); 8 mutants of the join's condition, each caught; a property
      test of `WriteTSV`'s rule, written then read back; suite 2481, coverage 100%; the matrix 770;
      the outcome report against `9f24545` on 3.13 and 3.14: 510 identical,
      `burn/hostile/newline.tsv` new. Reviewed: its own review made the join linear (it had copied
      the text at each line); an independent reviewer's, the writers run on 19 hostile texts, stated
      and tested the line a refusal or a NUL's note names, and made "whole" "into its record" (a
      blank line in a text is dropped). Left, weighed: a later line's bad byte named by its record's
      first line (as CSV's); the note quoting the line as written, a NUL raw. Your review, end to
      end, then an independent reviewer's: a record past its header's columns (or `start`, `end`,
      `text` without one) had taken the next line, though its text was a field before -- `WriteTSV`
      writes none -- now a record ending at its text alone, its 6 mutants each caught (`b45384c`);
      the counted note written once, `counted`, for SubRip's, LRC's and TSV's -- the outcome report
      511 identical, 3,000 random LRCs' readings identical (`0e47500`); an LRC's and a TSV's note
      tested shown, a TSV of no header's join tested (`4a226b3`, `eaf6450`); the rows it qualifies
      named, `WriteTSV` checked at a nixpkgs bump (`7d687d6`); the skill's rule 3 and reading
      sentence, a quote opening a text's later line, its writer's JSON (`f7d37d9`). Left, weighed: a
      record of no text taking the next line (kept, noted -- else a record of no time, lost
      unnoted); the bounded-work test's 1 s (7 times its 0.13 s). It found a box: a cue of no time
      dropped unnoted.*
- [ ] Found by the TSV line breaks box's review: a transcript's cue of no time -- a CSV or TSV
      record whose `start` or `end` is no number, a JSON segment's `NaN`, `null` or text -- is
      dropped by ffman unnoted, its text lost (measured: a CSV's `abc,900,lost words`, WhisperX's
      `NaN` start, whisper-cli's `"x"` offset), against the owner's rule, silent only when nothing
      is lost (decisions' "Dropped cues"). To decide: note it, counted, the first named, or as now.
- [x] Found by the `whisper-transcripts` box: ffmpeg's `whisper` filter (FFmpeg 8, nixpkgs'
      `ffmpeg-full`, ffman's runtime) writes `format=json` one object a line,
      `{"start":ms,"end":ms,"text":"..."}`, its text not escaped -- ffman refuses it,
      `not valid JSON`, without saying why. To decide: read it (each line, a broken one noted),
      refuse it named (`format=srt` advised), or as now.
      *Done: read as the filter writes it (`readers/whisper_filter.py`): a `.json` opening
      `{"start":` (after a BOM or none) is the filter's -- no whisper-cli, OpenAI or WhisperX JSON
      opens so -- its records each a line opening `{"start":`, a line that does not continuing the
      one before, each fullmatched against the writer's one `av_asprintf` (`S` and `E` by `PRId64`),
      its text as written: a `"`, a `\` and a line break its own (`C:\new` no line break), blank
      lines after its `"}` in no text, its lines ending as csv's (a re-saved file's CR LFs or CRs).
      A record not of that form -- a file cut mid-write -- dropped, noted (`counted`); UTF-8, or
      UTF-16 by its BOM; a character `max_len` split joined (`table.timed`, with
      `table.split_lines`, shared, `6dcb9b3`) (`2fffc3b`; decisions' "whisper filter JSON"; the
      skill's cells, paragraph and eval 3, `d65c522`). The owner's standing rule, better by proof:
      the format is one `av_asprintf` at n8.1.2 and master (2026-10-15), so read exactly -- refused,
      a transcription is run again; read as JSON, line by line, `C:\new` becomes a line break.
      Tests: 21 failing first (subverter's), 1 (ffman's); 14 mutants of the reader caught, the lazy
      text group equivalent; suite 2521, coverage 100%; the matrix 770; the outcome report against
      `2b9f05d` on 3.13 and 3.14: 511 identical, `burn/hostile/filter.json` new (refused, now
      burned). Reviewed: its own review tested a negative time and the notes' order; an independent
      reviewer's, two rounds, the filter's loop cut and run: a file of CR line ends had been one
      record unnoted, blank lines at the end had dropped the last record -- now lines end as csv's
      and blank lines after a record are in no text -- three tests added (a stray line, the UTF-16
      refusal's line, a negative end), the docs exact (`PRId64`, both Python errors, the earlier
      refusal of one record), the stale lists of JSON writers named. Left, weighed: a JSON document
      whose first key is `start` read as the filter's (no writer of one); a text's own CR a line
      break (no reader tells it from a re-save's). Your review, end to end, then a fresh independent
      reviewer's: the bounded-work figure re-measured (0.08 s), the signature test made to pin each
      outcome, a JSON writer's list and the package's description named, the line rule of a refusal
      stated, a check at a nixpkgs bump (`upgrading.md` 25), eval 3 advising `--add-subs` (an mp3
      burns nothing), four mutants killed by tests (a brace opening a text's line, an empty time,
      other digits, a dropped record's name). Left, weighed: JSON lines of the filter's form another
      tool writes, read as the filter's (no form tells them apart); the shared helpers kept in
      `table.py`, as LRC takes SubRip's `file_lines`.*
- [x] Found by the `whisper-transcripts` box: OpenAI whisper's JSON is read as WhisperX's
      (`.segments`) and named so -- `WhisperX JSON has none` in a word mode's refusal, the JSON
      refusal naming whisper-cli and WhisperX alone, the `.txt` refusal suggesting their outputs
      alone. To decide: name each by its keys (OpenAI's `text` and `segments[].id`) or one name for
      both, `whisper JSON (.segments)`.
      *Done: named by the key that proves the writer (`readers/whisper.py`): a `.segments` JSON with
      a top-level `text` string is OpenAI whisper's (`OpenAI whisper JSON`), any other WhisperX's --
      openai-whisper v20250625's `transcribe()` returns `dict(text, segments, language)`,
      `WriteJSON` dumping it whole; no WhisperX JSON writes one (`asr.py`, `alignment.py`,
      `diarize.py`, `transcribe.py` at 3.0.0, 3.0.2, 3.1.0, 3.3.2, 3.4.2, 3.8.5 and 3.8.6). Probing
      found the same defect in highlighted cues: OpenAI whisper's own `--highlight_words` SubRip and
      WebVTT, read as words, were named WhisperX's -- one writer's in both tools, undistinguishable,
      now `OpenAI whisper or WhisperX --highlight_words .srt`. The JSON and `.txt` refusals name
      OpenAI whisper's outputs; the word modes' name `OpenAI whisper --word_timestamps True JSON`
      and either's `--highlight_words` among the sources of word timings (`c998000`, `ca416e7`;
      decisions' "Whisper names"; `upgrading.md` 26). The owner's standing rule, better by proof:
      exact for both writers at every tag checked, where one generic name would drop what the key
      proves. Tests: OpenAI's JSON with and without words, its empty `text`, a `text` no string,
      OpenAI's own highlighted SubRip, the word modes' messages whole, failing first; the naming
      rule's mutants caught; suite 2529, coverage 100%; the matrix 770; the outcome report against
      `d783f05` on 3.13 and 3.14: 493 identical, 21 refusals reworded, `openai.json` (OpenAI
      whisper's own `WriteJSON`) new -- its chunk-word refusal `OpenAI whisper JSON has none`,
      before `WhisperX JSON has none`. Reviewed: its own review renamed `_whisperx` `_segments`; an
      independent reviewer's, two rounds: the word modes' hint without `JSON`
      (`--word_timestamps True` times words in the JSON alone), the refusals' count, the WhisperX
      key claim made exact (its keys by tag: `language` on an aligned result from 3.2.0,
      `speaker_embeddings` from 3.4.2; `text` at none, 3.1.1 to 3.3.1 checked too), the ffman
      README, `text` `""` tested, "byte-identical" bounded (wrapped lines, `ja` and `zh`). Left,
      weighed: one name for highlighted cues (nothing marks OpenAI whisper's); the
      `subtitle-mappings` skill's WhisperX-only rows, its own box's. It found a box: highlighted
      cues not read as such. Your review, end to end, then an independent reviewer's: the word
      modes' remedies each tool's options as it parses them -- `--highlight_words True`, OpenAI
      whisper's with `--word_timestamps True` (`str2bool`: a bare flag refused by argparse; OpenAI
      whisper's `--highlight_words` by its parser without `--word_timestamps True`), one phrase for
      both tools (`bf64f87`); a third writer weighed: whisper-ctranslate2 0.5.8 writes OpenAI
      whisper's result and takes its options, named so, the name its JSON's form (decisions);
      `openai.json` held by the word modes' test, a `text` with no other key tested (the mutant
      `and "language" in doc` caught); `upgrading.md` names OpenAI whisper's outputs, 26 how to
      write `openai.json` again; this record's hashes and its WhisperX key claim corrected, the open
      `verbose_json` box's naming brought up to date. Outcome against `24817d1` on 3.13 and 3.14:
      495 identical, 20 refusals changed in their remedies alone (17 chunk-word, 3 word modes);
      suite 2530, coverage 100%; the matrix 770. Left, weighed: WhisperX's `--task translate`,
      unaligned from 3.1.1 -- no words for any remedy; two test lines past 100 columns (the tests'
      E501 exemption).*
- [x] Found by the Whisper names box's review: a highlighted SubRip or WebVTT not read as
      highlighted, its words lost -- one underlined word a cue (OpenAI whisper
      `--word_timestamps True --highlight_words True --max_words_per_line 1`: no gap cues), or
      WhisperX's in `ja` or `zh` (`utils.py` joins a gap's cue by nothing, a highlighted one by
      spaces: neighbours of no one text). Read as plain cues; a chunk-word burn refused
      `.srt has none`, its remedy the `--highlight_words` it was written with. To decide: read each
      as words (by `<u>` alone where each cue is one word; by `<u>` and the text without spaces),
      refuse it named, or as now.
      *Done: read each as words (`readers/cues.py`), by the writers' own `utils.py` -- OpenAI
      whisper v20250625's and WhisperX's at 3.1.1, 3.2.0, 3.3.2, 3.4.2, 3.7.6, 3.7.7, 3.7.9, 3.8.0
      and 3.8.6, run on results in `en`, `ja`, `zh`, diarized, wrapped and a word a cue. Neighbours
      compared without the underline, WhisperX's `[SPEAKER]: ` and spaces: its `ja` and `zh` join a
      gap's cue by nothing and a highlighted one by spaces (3.2.0 on), its 3.1 writes a gap's cue
      without the speaker -- found by the probe, English too. Where a gap's cue shows the spaces
      WhisperX's, a sentence is without them, its speaker kept: its JSON's; a file of no such cue is
      read as written, nothing telling WhisperX's spaces from OpenAI whisper's `ja` own. Every cue
      wholly underlined (OpenAI whisper's `--max_words_per_line 1`, a word `- I` among them;
      WhisperX's from 3.7.7): a sentence a word. A sentence's text its first highlighted cue's
      (3.1's gap cue first had dropped its speaker). Proof: the writer matrix, 350 cases against the
      same result's JSON as ffman ingests it -- 122 better, none worse; every case probed from
      OpenAI whisper and WhisperX 3.7.7 its JSON's words; the fixtures `wx-ja-highlight.srt` and
      `openai-words.{srt,json}`, each tool's writers' (`a115b8e`; decisions' "Highlighted cues";
      `upgrading.md` 26, 27). Tests failing first, the rules' mutants caught; suite 2549, coverage
      100% (2548 passed, the LRC timing test its third found box's); the matrix 770; the outcome
      report against `b99bb16` on 3.13 and 3.14: 521 identical, the new fixtures' 3 changed --
      `wx-ja-highlight.srt` burned as its JSON, unspaced, and chunk-word refusing `openai-words.srt`
      as word-level, before `.srt has none`. Reviewed: an independent reviewer's, three rounds -- a
      word with a space (`- I`), the 3.1 sentence's speaker, WhisperX's version bounds, the helpers,
      the pre-3.7.7 `ja` and `zh` one-word reading documented (3.2.0's on before, 3.1's now: its gap
      cues each a word's, overlapping); a bare one-word cue (WhisperX 3.7.7 and 3.8.0 writing a word
      it could not align, at its segment's times) weighed and left as cues: read as words, its span
      hid its neighbours' in ffman. Left, weighed: cues underlined by hand read as words alike
      (their plain burn the same); naming a `ja` or `zh` file WhisperX's by its gap cues, one name
      kept for both; the word-level refusal's `e.g.`, whisper-cli's. It found two boxes: a CJK cue's
      line break read as a space; a highlighted sentence's speaker in chunk-word; and a third, the
      suite's: an LRC timing test near its bound.*
- [ ] Found by the highlighted cues box: a SubRip or WebVTT cue's line break is read as a space, in
      a script written without spaces too -- WhisperX 3.8.6's `ja`
      `--max_line_width 4 --max_line_count 2` burned `今日は良 い天気で` (measured), its JSON `今日は良い天気です`.
      To decide: join a line break by nothing between two characters of a script without spaces (UAX
      #14's), or as now.
- [ ] Found by the highlighted cues box: a highlighted sentence keeps WhisperX's `[SPEAKER]: `, so
      its chunk-word line, drawn from its words, shows no speaker, and in `ja` or `zh` spaces its
      characters (`subs/ass.py`: a text with a space, its words spaced) -- measured
      `今 日 は 良 い 天 気 で す`, its JSON's line `今日は良い天気です`. To decide: the speaker kept out of the
      sentence (a field of its own, as the JSON's `speaker`), drawn before its words, or as now.
- [ ] Found by the highlighted cues box's runs: `test_lrc.py`'s bounded-work test of 20 000 equal
      stamps takes 0.90 s of its 1 s under coverage alone (0.28 s without), so a parallel run on two
      cores fails it now and then. To decide: a bound measured against the reading's own scale (a
      quadratic reading takes minutes), its input halved, or as now.
- [ ] Found by the `whisper-transcripts` review: the OpenAI API's `verbose_json` (its
      `segments`, and with word timestamps its top-level `words`) is read by its segments alone,
      its words ignored, unnoted -- a word mode has none to show (measured: two words, `0` read, no
      note), its JSON named `OpenAI whisper JSON` by its `text` (Whisper names); one of words alone
      is refused, as no whisper-cli, OpenAI whisper or WhisperX JSON. To decide: read its `words`
      into their segments, note them ignored, or as now.
- [ ] `subtitle-mappings`: the mappings, a skill -- its three references and scripts.

*6.8.3 The converters* (pure, from the skills)

- [ ] The model: `Transcript` kept or grown (ASS's styles and positions?) --
      decided from the research.
      Found by the SubRip and WebVTT review: `Reading.has_references` and `has_ass_escapes`, one
      question -- how a format's texts mark up -- in two booleans, a third with ASS's; one value
      then. `has_references` released (0.1.1), `has_ass_escapes` not, and it gates a SubRip's tags
      too.
- [ ] Readers and writers each format lacks (an ASS reader, SSA through it; WebVTT, plain
      ASS, `-oj`, `-ojf`, WhisperX, CSV, TSV and plain-text writers): round trip exact where
      the formats meet, each loss noted; ffmpeg where it measured equal or better.
- [ ] The LRC writer, last: no end times -- each line's start, the loss noted.
- [ ] By word or by chunk: an output that holds either takes the choice (its
      flag decided in the spec), refused where the input times no words.
      Found by the SubRip and WebVTT review: ffmpeg's master, after 8.1, reads a WebVTT cue's
      timestamp tags as ASS karaoke (`\kf`) and writes them back (`webvttdec.c`, `webvttenc.c`):
      word timings a WebVTT holds, which ffman removes.
      Found by the `lrc` box: Enhanced LRC's word stamps (`<mm:ss.xx>`), word starts Navidrome
      and Jellyfin read, which ffman takes off its text (`unstamped`).
- [ ] Every conversion between the sources and targets above: property tests, corpus
      cases.

*6.8.4 The command line* (`ffman-spec.md` first)

- [ ] `convert -i talk.json -o talk.vtt` -- or a command of its own, decided
      in the spec -- its help, its corpus cases.

*6.8.5 Review*

- [ ] The section reviewed whole.

**6.9 The effects** (§4; each box is research and skill, its code boxes added after)

- [ ] `blur`
- [ ] `pixelate`
- [ ] `invert`
- [ ] `chromatic-aberration`
- [ ] `halation`
- [ ] `datamosh`
- [ ] `camcorder`
- [ ] `vhs`
- [ ] `dither`
- [ ] `crt`
- [ ] Resizing in linear light (every resize): researched as the effects are, after those sharing its light handling.

**6.10 Product** (G4 each; the spec first where the command line changes)

- [ ] Grammar: the optional-value rule, `values.py`'s number grammar -- reviewed against the spec, changed through it. From 6.4.1's review: `is_num` accepts any length, and a value past 4300 digits (`--font-size 999...`, 5000 nines) is a traceback -- `Fraction`'s `int` conversion; the command line's numbers want the bounded reading the transcripts got (`fields.exact`), or a length. From 6.4.2's review: a font size past a double (400 digits) is an `OverflowError` -- older too (stage A's floats failed at 310 digits; the exact code at 400).
- [ ] Messages: the spec's text reviewed for the user, not for bash. From 6.2: `FFMAN_FONTS_DIR` is refused by `burn` where ffmpeg's filter syntax splits it, yet passed unchecked to the camcorder's filter, which ffman's graph escapes -- one rule for both. From 6.3.2: a transcript's `\` and braces are burned as `/` and parentheses -- shown as written, braces would take libass's `\{`, `\}`, and a `\` before `N`, `n`, `h` or ffman's own block an invisible separator, its rendering to prove (font, HarfBuzz).
- [ ] `-b` and `--resize-mode` without a size: one answer in every flow -- refused, or applied (F7).
- [ ] D2, the default encode.
- [ ] Stage 4: GIF and `--loop`/`--loop-reverse` from any input; any compatible output.
- [ ] `--attachment`, `--cover`, `--title` (`--metadata FILE`: done in 6.6.4, spec 3.10;
      `--title` beside it: a convert's one tag, or `--metadata` enough).
- [ ] `-v/--verbose`, its meaning defined in the spec first.

**6.11 Completion and manual** (the last work before the close: every command and option settled)

- [ ] Assessed, then done: shell completion (bash, zsh, fish; generated
      from the option table, so it cannot drift), installed by
      `installShellCompletion`; a man page (written, or generated from the same
      table and the spec), installed by `installManPage` -- both nixpkgs'
      `installShellFiles` hooks; or both. What each gives (each shell's needs,
      `man ffman`, `--help` beside it), decided with the owner; each tested in
      the checks.

**6.12 Close**

- [ ] No stage-A scaffolding: `fmt.py` and its tests' imports gone; no comment justifies code by bash alone (a check: each "bash" in `src/` is history beside a stated rule); every effect has its skill, packaged; the spec and `CHANGELOG.md` current; `nix flake check` green. 07-tools.md's rows describe the Python, not bash's tools ("Hostile transcripts": bash's `fuzz.py`, retired in phase 5, as its finder; its jq path rule went with jq, in 6.3). From 6.4.5: `options._margin` reads `N%` through `awk_print` -- a value, not a message: `12.3456789%` is kept as 123457/1000000, and `150%` refused as `1.5`, not as typed. From 6.5's review: the tests hold ~40 trailing-comment wraps (`)  # ...`, the formatter's shape around a long assertion) -- comments above, as `src` has since 6.4.

## 8. Review (at a48dcb7)

The first draft, reviewed end to end. Applied: refusals after work found and
demonstrated (F6, 6.2); the compensation reading done here, not deferred (F2);
a false claim withdrawn (that a gap's shares might not sum to it: they are
cumulative); the outcome report first; the typing and the ingest rewrite
before exact arithmetic; the camcorder's width into its effect; pinned tests'
policy; the skills' home, format and delivery; the target tree; rationals in
four modules, not three; readers counted; the import graph checked against the target (two layer breaks); `\pos` fractions and cropdetect's metadata shown; grammar, messages and provenance
comments planned; each effect box research and skill first.

Section 6.0, reviewed end to end (at e4ef39b; three iterations, to none found).
Fixed: the outcome driver let a failed capture read as ffman's own error (ffman
catches the OSError) -- now kept from ffman and refused by the report (status
125, shown both ways by a test); `Frame` allowed `squared` with a SAR other than
1 and nine places built the squared frame by hand -- `__post_init__` refuses
it, `Frame.resized` builds it; `Rational.parse` took any separator, crashing on
an empty one -- `Literal["/", ":"]`; `Rational.value` and `text`'s separator
were dead (vulture matched them by name to `parsed.value`) -- removed; the
duration and sample-rate grammars untested -- tested; the driver crashed on
bad arguments or no TMPDIR -- refused; two docstrings stale from 6.0.3, one
test comment misplaced, AGENTS.md silent on the report's refusals.

Box 6.1.4, reviewed end to end (at a5a630a; two iterations, to none found).
Fixed: constants written together came apart -- the 6.1.3 and 6.1.4 splitters
joined every definition with blank lines (6.1.2's kept the source's spacing):
eight groups, two here, six in `effects/`, rejoined, a neighbour-spacing check
showing none left (the check's own off-by-one found because it disagreed with
the text); `ingest.py`'s docstring repeated what `readers/` and `normalize.py`
now say -- each fact once, with its code (the times' unit, milliseconds,
said only there, now with the types); a docstring's bash command line,
not in this tree to check, now what the code shows. Shown sound: the import
graph one-way, every public name used outside its module, every `subs` and
`effects` module importable first and alone. Carried to 6.3: tag stripping
twice, `whisper.py`'s order, `read`'s file and path.

Section 6.1, reviewed end to end (3171ca3..4c333be; two iterations, to none
found), aimed at what box-by-box reviews could not see. Fixed: 6.1.2 left
`graph.py` named in three places its sweep did not search (07-tools.md's
Filtergraph text row, `graph/light.py`'s docstring, a test's comment); §3's
"planners are pure" was not so -- two readers read the transcript's file -- and
nothing held it: the architecture test now does (no file, no OS in layers 2-3,
shown failing three ways), the readers its listed exception, 6.3's box to
close; its docstring named two of its rules, now all four; `test_output.py`,
named for a module 6.1.2 renamed, is `test_paths.py`. Shown sound: every path
the current docs cite exists, but other projects' sources; no public name dead
(each of 51 without product use outside its module used within it); one pair
of functions shaped alike (`probe._seconds`, `_count`), two grammars, kept;
every module importable first and alone; the four splits' spacing as written.
Carried: 07-tools.md's "Hostile transcripts" row cites bash's `fuzz.py`, to
6.10 with that row's jq rule.

Section 6.2, reviewed end to end (55137be..d565f3b; three iterations, to none
found), testing what the corpus could not: commands where two checks contend,
run on the old code and the new. Found: the CHANGELOG's "every message is as
it was" held for the corpus only -- `--add-subs` to an output without an
extension now says `output needs an extension`, as the spec's `-o` requires
and every other flow said, where bash said "a . file cannot carry a subtitle
track" (its empty extension read as a container); and a command with several
faults now hears of the options and the probe before the transcript. Both
written down (CHANGELOG, 07-tools.md), tested (fails on the old code in all
three), pinned by two corpus cases.

Section 6.3, reviewed end to end (38dfa03..48e5eea; three iterations, to none
found), adversarially: inputs past what Python's float, int, csv and json hold,
run on the code before 6.3 and after. Found and fixed -- seven crashes, a
traceback each: a CSV/TSV field past `csv`'s 128 KiB (6.3's: gawk had no
limit) now refused by name; six older -- a JSON integer past a double (a time,
a `t_dtw`), JSON nested past the recursion limit, an LRC minute and a SubRip
hour past a double -- now no time, or refused by name; every format's time
fields probed at the extremes after, none crashing; `test_ingest.py`'s
`PAST_LIMITS` pins them (CHANGELOG, 07-tools.md). The cues' sort moved from
`ingest` into `normalize.cues`, which says it orders them -- timed cues only,
by their start before clamping; shown identical on 300,000 cue lists.
`read_file` reads once (no check-then-read race); the formats named once in
the dispatch; the readers' patterns named.

Box 6.4.1, reviewed end to end (335556a..d19bc98; three iterations, to none
found), aimed at what exactness made possible. Found: a `Fraction` of a text
is exact and unbounded -- `1e999999999` builds a billion-digit integer, more
than 4300 digits overflow `int`'s conversion -- so six inputs hung ffman
(killed at 15 s: an exponent, huge or tiny, in CSV, SubRip, a JSON string or
number) and four crashed or were refused (5000 digits in CSV, SubRip, LRC, a
JSON fraction); the code before answered each at once. Fixed: one bounded path,
`fields.exact`, the only text-to-`Fraction` -- a first digit past 10^308 no
number, under 10^-400 zero, 400 significant digits read and a sticky 1 for the
rest; shown to round as the unbounded `Fraction` 180,000 times (half-ms
boundaries with 600-digit tails, 3000-digit numbers, exponents at both bounds),
and in `test_fields.py` by a property whose strategy reaches the hard case --
removing the sticky digit fails it, five runs of five (its first strategy
missed it: four rare conditions at once). Every probe answers at once, as the
old code did (`test_ingest.py`'s `BOUNDLESS`). `ms(number(...))`, thirteen
times, is `fields.time_ms`.

Box 6.4.2, reviewed end to end (f854818..938dd05; two iterations, to none
found), from what exactness made possible. `bar_times`' `decimal()` cannot
refuse: every duration is ffprobe's `%f` text (`probe._seconds`, its only
source), and an eighth of a decimal is one. A font size past a double is an
`OverflowError`, older than this box (carried to 6.10's grammar box). Found: the
exact writer cost three times the floats' (2.79 s for 0.92 s on 5,000
sentences, 65,000 words) -- profiled, not guessed: 410,000 `decimal` calls,
each computing its places twice (`terminates`, then `decimal`), and formatting
the same centre and the same line's y for every event. Now
`values.finite_decimal` (places once; `terminates` gone), the centre written
once a script and each y once (a dict on the writer, no global cache): 1.17 s,
every mode's script byte-identical to before. `POS` reads every form `_number`
writes (`e+16`); a ternary wrapped around its comment, an early return; no such
wrap left in `src`.
In its proofs, `test_a_pop_grows_only_the_word` failed once in eight runs --
passing alone, in context, under load. Its clip's `gradients` defaults to a
random seed and a rotation (this ffmpeg's help): each session drew another
moving background, against a check that only the word changes; seeds 19 and 59
of 72 fail every time, and pass still. The clip pinned (`seed=1:speed=0`). A
sweep of the inputs for the like: `test_blurs`' `geq` `random()` follows its
slicing -- 8 threads drew other blocks than 1 (`8689e9c7` against `0b51fdb3`),
so a many-core builder tested another picture; now in the main graph on one
thread, its picture this one's (`0b51fdb3`, also with `-threads 8`). VHS's
`noise` is unseeded but not random (`vf_noise.c`: -1 is 123457; 1 and 8
threads alike).

Box 6.4.3, reviewed end to end (c16deb7..2a0adf2; two iterations, to none
found), from what reading stdout made possible. The code's own detection on a
real file through the real runner: stdout holds nothing but `frame:` headers
and `key=value` lines (420 of 420 -- the null muxer writes none), stderr is
empty at `-v error`, the row is the picture's; `capture` drains both pipes
(`communicate`), no deadlock; a sample prints one frame past `-frames:v`, as
the log did. The planned height rests on an invariant -- the effects before the
subtitles keep the frame's size -- true by construction (only chromatic
aberration and VHS use size-changing filters, both restore it; CRT is after
the subtitles) but unguarded: `test_effects` measured size, format and frames
for seven effects, not camcorder, from a hand-written list. Now camcorder too
(it keeps them), and a test that every staged effect (`PRE`, `POST`) is
measured -- shown failing, and naming `camcorder`, without it. The findings'
own words about the log (§F) stay: history, resolved by the box.

Box 6.4.4, reviewed end to end (c6dfb27..265202b; two iterations, to none
found), from what it made load-bearing -- the frame passed being the output's.
Burn is the script's one caller (`--preset youtube` refuses `--burn-subs`:
shown); a burn keeps the source's frames -- a GIF changes only their display
delays (the content, animation and all, rendered at the source's times),
datamosh re-times at the average rate, `frame_rate`'s choice. A slideshow's
long frames leave most words gold at once: right -- no frame could show a
pop. Found: the threshold stated loosely ("under ~250 ms"): by the rule the
settle was cut on every word under 240 ms, and with the simulator, visibly to
266-275 ms at 24-30 fps (250 at 60) -- now said so in the code, 07-tools.md,
the CHANGELOG and this plan; the gold and white as named constants
(`_GOLD`: #FFD700, ASS's &HBBGGRR&). Its first matrix failed 106 of 761 -- the sandbox's disk full (4 KB free: old pytest directories and pip/uv caches); freed, the same code passed all 761.

Box 6.4.5, reviewed end to end (1c09157..46b4835; two iterations, nothing
found), from what `w / h` can meet: a zero or negative size and a zero ratio
part are refused before the planner (run: "must be a positive integer",
"parts must be positive"), so the division cannot fail on input; a decimal
--aspect-ratio (2.39:1) reads well beside the reduced ratio. The only other
ratio written as text is chromatic aberration's SAR -- an ffmpeg argument in
ffmpeg's `num/den`, not a message: nothing to share. geometry.py's mentions
of awk are history beside its rule. No code changed; HEAD's proofs stand.

Section 6.5, reviewed end to end (8f59ae0..f66189f; two iterations, to none
found), from what owning every break made load-bearing. Found and fixed: the
units kept a mark by its combining class -- Thai's vowels are marks of class
0, so a line could open on one (`สวัสดี` split `ว`|`ั`); and a Devanagari
conjunct split past its virama, an emoji family at its joiners. Now `_joins`:
a mark by its category (Mn, Mc, Me), a character past a virama (class 9),
either side of a zero-width joiner; tested on the property -- no line opens on a
mark or joiner, none ends on a virama or joiner -- with breaks shifted mid-unit
(its first form passed the old code by parity: 22 characters a line, units of
2). The font matched as libass matches it (`ass_strcasecmp`): `-f "ibm plex
sans"` is measured. Shown: libass draws the face ffman measures -- a bold
render's ink inside Bold's advances (0.989-0.996), outside SemiBold's
(1.003-1.010), Medium's, ExtraLight's (a first check, rendered with estimated
breaks, compared two lines with one: redone). Carried: Thai's word breaking to
the follow-up box; the tests' trailing-comment wraps to 6.12.

Section 6.5, reviewed again with its second box (8f59ae0..8d9ba27; two
iterations, to none found), from how the boxes meet. A timed word wider than a
line: alone on its own line, whole -- its highlight is one, so it cannot break;
the docstring now says so. Hostile sizes, timed: 50,000 unspaced kanji 0.68 s,
a letter and 50,000 marks 0.15 s, 50,000 Latin letters 0.61 s -- linear. One
field splitter (breaks.py's; fields.py's whitespace is a number's, apart).
Found: "a mark" written out four times (`_joins`, `_base`, `Metrics.width`,
`ass._estimate`) -- now `breaks.is_mark`, once; and a count added a boolean --
now plainly.

Section 6.4, reviewed as it now stands (335556a..bd35901, its code since
reshaped by 6.5; two iterations, to none found), from how 6.5 meets it. Found
and fixed, both where the boxes meet: the pop's peak grows each side into ~45%
of a space (bash's rule), and 6.5 made unspaced timed words abut -- rendered,
a Japanese pop at its peak covered 35 px of its neighbours' ink, a spaced one
none; now a word with no space beside it (line edges count) pops unscaled,
and the Japanese covers 0, the English unchanged. The peak counted code
points: a decomposed é peaked lower -- now glyphs (`is_mark`). DRY: ASS's
centiseconds rounded half up by hand, `(ms + 5) // 10` -- the rule now once,
`values.div_half_up` ((2n + d) // 2d; equal to floor(n/d + 1/2) on 202,904
pairs), `round_half_up` through it; a Fraction there cost 45% on 15,000 events
(0.243 to 0.353 s), the integer form none (0.247). Held: the floats left are
the documented ones; the y cache is keyed by the exact y. (A test edit cut a
constant between two tests -- restored from HEAD, every removed line read.) The corpus had no pop on abutting words -- the fix invisible to it: `burn/chunk-pop-ja` added (357 cases).

The motions box, reviewed (0eb9c20; two iterations, to none found), from
libass's rules and hostile sizes. Found and fixed: keyframe times rounded onto
their predecessor -- in a 701-letter rainbow without a fade, one letter's chain
began `[0, 0, 334]`, a `\t(0,0,...)`, which libass runs to the event's end
(`t2 == 0`); a first scan missed it, sampling letter counts that share a factor
with 6 (a boundary that near 0 needs s.n + 6k = 1: n coprime with 6, over 666)
-- now a keyframe on the last moves a ms on. Unbounded cost: a hostile 2,000
letters lit 60 s in lsd made 19.5 MB of script in 14 s, parsed by libass each
frame -- now a run over 10,000 keyframes (a long cue, 84 letters 7 s, ~3,500)
keeps each letter's first colour and is noted: 0.07 MB, 0.05 s. `script`'s note
became notes (a tuple), `burn.py` says each. Held: the budget's estimate bounds
the keyframes from above; the flash counts unchanged; a normal lit run (1,200
\t) costs 0.4 ms a frame.

The colour boxes, reviewed together (7500cde..644cb3d: the text's colours,
their motions, the rectangle; two iterations, to none found), from where they
meet. Found and fixed: the motion budget was an event's for plain subtitles
but each word's in a line -- chunk-word draws a line an event: a 76-letter
line, measured with the shipped font, carried 26,980 \t, 2.7 times the
budget, unnoted; now one budget a line event (`_line_budget`). A lit run's
budget left out the outline's motion its letters carried -- a gold highlight
under one was never held; now counted. DRY: the per-letter loop written three
times (`_letters`, `_boxed_letters`, `_paint`) now `_per_letter`; a \t chain
twice, now `_steps`; whether a lit word's colours are written whole or by
letter decided in three places, three forms -- now one predicate, `whole`,
proven over every combination (2 modes, 2 highlight modes, 4 highlights, 2
fonts, 3 outlines: 192 lit events, each written one way). Tests failing on
the old code: a line's budget, the outline counted. Coverage then found a path no test took -- `--overlay-mode word` under a font in motion, `_paint` budgeting itself: tested.

Section 6.5, reviewed whole (8f59ae0..e791231; two iterations, to none
found), from how its early and late boxes meet. Found: two documents the
later boxes made false -- 07-tools.md's Highlight colour row ("no white, no
black") and the README's names, both now naming them. Architecture: ass.py
had grown to 654 lines and 46 functions, a third of them colour with state of
their own -- now subs/paint.py's Painter (203 lines; ass.py 495), built from
the three colours and the box's measures, not the Style (ass imports paint:
no cycle); ass keeps layout and timing, _box (the pop's curve) and
_line_budget (a line's letters) among them. UNKNOWN, defined in both, now
metrics.py's. _SPACE's comment off its trailing wrap, and the two space
estimates' opposite safeties stated (wrapping's 0.55, wide: lines break early;
the box's 0.15, narrow: it fits). Proven unchanged: every lit word written
one way over 96 combinations (192 events), the corpus identical.

The bar's two commits, reviewed (b1e5ed1..0fb7f24; two iterations, to none
found), from what they claim. Found false: that ffman's padded and blurred fits
place the picture a row apart -- stated in head's docstring, a test's, the
Placement row and the plan, from a hand-built overlay whose formats were not
the render's. ffman's own heads agree on every case measured (4:2:0 640x480
into 360x640, 186 both; into 1080x1920, 556 both; 4:2:2 and 4:4:4 555): each
statement corrected. measure=True stays -- the blurred head read as itself is
exact by construction, for any format; the padded one agrees only as measured.
DRY: "a fit with blurred bars", written in head's match and in burn, is
blurred_fit, once. Types: the bar's word a BarKind (Literal black, blurred).

## 9. Assessed for nixos-config (owner's request, after 6.7.8)

Not ffman's work: two of nixos-config's choices, assessed here, where the work is carried. At
nixos-config `aee27e3` and its nixpkgs pin (rustc 1.95.0 the default, 1.97.1 beside it;
nix-update 1.15.1).

**9.1 imi as a flake input, with a `flake.nix` of its own**

Today `pkgs/imi/default.nix` builds the crates.io crate (`fetchCrate`) with two written hashes:
`src.hash`, and `cargoHash` (its `Cargo.lock`'s 61 crates, vendored as one fixed output).
`nix flake update` reaches neither: it rewrites `flake.lock`, which holds inputs only.

Proposed, as ffsuite: imi's repository (`github:veralvx/imi`) gains a `flake.nix` (packages,
`overlays.default`, checks) building with `cargoLock.lockFile = ./Cargo.lock` -- each crate
fetched against the checksum `Cargo.lock` already holds (nixpkgs' `importCargoLock`), so no
written hash; a git dependency would need one, and at `v0.3.0` there is none. nixos-config takes
it as it takes ffsuite, but by a tag (ffsuite's input names its `main`: no tag before 6.7.12):
`imi.url = "github:veralvx/imi/v0.3.0"`,
`imi.inputs.nixpkgs.follows = "nixpkgs"`, the overlay applied in `modules/tools.nix`.

Measured: tags `v0.1.4` to `v0.3.0`, `main` past the last (`d2c73a4`; `v0.3.0` is `db710d2`) --
so the URL names a tag, and a bump edits it (Nix relocks a changed input itself); untagged,
`nix flake update imi` would follow unreleased commits. The workspace has two members
(`crates/imi`, `crates/imi-core`): the package builds `-p imi`. `rust-toolchain.toml` (1.95) is
rustup's, unread by nixpkgs' cargo; `rust-version = "1.95"` cargo enforces against the rustc it
is given -- under `follows`, nixos-config's, so the MSRV stays the system's question
(`rustPackages_1_97` exists at this pin: a later MSRV need not wait for the channel).

Moving with it (6.7.8's blast radius, measured there): the two tests skipped by name
(`/sys/block`, a terminal) go to imi's package -- better, its tests skip themselves there;
`meta.license` becomes `MIT OR Apache-2.0` (crates.io and its `Cargo.toml`; nixos-config's says
MIT, unverified); in nixos-config, `pkgs/imi` and its export removed, the ISO's lock-node counts
(14 nodes, 9 direct), the installer's, `eval-report.sh`'s three input lists, 07-tools and the
review maps. `cargo-hash` (`tools/cargo-hash.sh`, run-book `cargo-hashes.md`) has no other user
(`fetchCrate` is imi's alone): it could retire with it.

Found stale on the way, left: `modules/tools.nix` calls imi a "unicode lookup" (its keywords:
usb, iso, disk, bootable, flash); `flake.nix`'s export comment, `pkgs/default.nix` and
`pkgs/imi/default.nix`'s header still describe a placeholder `cargoHash`, filled since;
`flake.nix`'s icon-theme comment likewise a `lib.fakeHash` since replaced.

- [ ] Decided with the owner: imi's own flake, then nixos-config taking it as an input -- or
      imi kept as it is.

**9.2 nix-update for the written hashes**

What it does (its source at 1.15.1, read, not run): finds a package in a flake's
`packages.<system>` (or by attribute path from the flake's root); finds the newest version from
its source URL's host (GitHub, Bitbucket, crates.io and others); rewrites the version on its
declaration line, and the old rev or tag and the old hash on every line of that file (text
replacement); computes each new hash by building the fixed output with an empty one and reading
Nix's `got:` -- the trust-on-first-use step this repository's run-books take by hand.

What it reaches here: exported packages only, three of nine sources with written hashes.

| Source                           | Exported             | Fit                                                                                                                                                                   |
| -------------------------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| imi (`src.hash`, `cargoHash`)    | yes                  | partial: its URL is `static.crates.io` (fetchCrate's default here), its lookup takes host `crates.io` only -- `--version` needed; MSRV unchecked (`--build` shows it) |
| yamis-cosmic-icon-theme          | yes                  | full: a GitHub tag                                                                                                                                                    |
| yamis-icon-theme                 | yes                  | partial: a Bitbucket commit beside upstream's 1.5.2 -- `--version` needed                                                                                             |
| jux cosmic (icons, cursors)      | no (unfree)          | --                                                                                                                                                                    |
| libretro-database (`gaming.nix`) | no (a `let` binding) | and its commit is inside the URL, no `rev` to rewrite                                                                                                                 |
| wine-mono `.msi`                 | no (a `let` binding) | its version is wine's, checked by the build                                                                                                                           |
| ArtCNN shader, blur-edges        | no (inline)          | --                                                                                                                                                                    |
| SWORD modules                    | no (unfree)          | `scripts/prefetch-sword-hashes.sh`, their own                                                                                                                         |

Each current hash and rev appears once in its file (counted): the text replacement would touch
nothing else today. Assessed: little to gain. With 9.1, imi's hashes go; what remains in reach
is the two YAMIS themes, one of them fully. Exporting the rest only for the tool adds outputs
nothing else uses. Its place is an occasional command
(`nix run nixpkgs#nix-update -- --flake yamis-cosmic-icon-theme`), not a dependency.

- [ ] Decided with the owner: nix-update named in the run-books as the bump command for the
      exported packages -- or not.
