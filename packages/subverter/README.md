# subverter

Subtitle and transcript readers into one model: SubRip, WebVTT, LRC, CSV and
TSV, and whisper-cli's and WhisperX's JSON.

A file read becomes what it holds: its cues, the word timings where the format
keeps them, notes on what it held that the model does not, and a refusal --
with its reason -- for what cannot be read.

| Format  | Read as                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SubRip  | cues -- UTF-8, or UTF-16 by its BOM (ffmpeg's); lines ending at an LF, a CRLF or a CR, the CRs before an LF part of its end (ffmpeg's); a cue's text on past an empty line to the next timing line, noted, as ffmpeg reads it, and past a line of spaces, noted, as MPC-HC reads it; a time hours, minutes and seconds, its fraction optional (VLC's, noted), one not of three digits a count of ms, as ffmpeg and VLC read it, and a number alone right before a timing line the next cue's index, as ffmpeg reads it, each noted; `has_ass_escapes`: its texts are ASS's, `drawn` reading them as ffmpeg's decoder and libass do (its tags as that decoder reads them, `<br>` a break; `{...}` blocks hidden; `\N`, `\n`, `\h`, `\{`, `\}`); WhisperX's highlighted cues read back into words |
| WebVTT  | cues -- lines ending at each CRLF, CR or LF (W3C); a cue ending at an empty line alone (W3C), a block of text after it in no cue dropped, noted; a file not opening with `WEBVTT` refused; each timing line the W3C's, else its block dropped, noted; `has_references`: its texts hold HTML character references, each run between tags `decoded`; its tags `untagged(..., webvtt=True)`, one no `>` closes running to the text's end (W3C; `unclosed`)                                                                                                                                                                                                                                                                                                                                         |
| LRC     | a line's times, its text -- UTF-8, or UTF-16 by its BOM, and lines ending, as SubRip's; a line a stamp; every time moved by `[offset:]` (ms, `+` sooner), noted                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| CSV/TSV | start, end, text (milliseconds), columns by header, as whisper-cli and WhisperX write them                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| JSON    | whisper-cli's and WhisperX's: chunks and word timings                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

## Installing

```sh
pip install subverter
```

Python 3.13 or later; the standard library alone.

## Using it

```pycon
>>> import subverter
>>> reading = subverter.read("srt", b"1\n00:00:01,000 --> 00:00:02,500\nHello <i>there</i>\n", "talk.srt")
>>> reading.cues
(Cue(start=1000, end=2500, text='Hello <i>there</i>', segment=''),)
>>> subverter.untagged(reading.cues[0].text)
'Hello there'
>>> subverter.read("json", b"[1, 2]", "talk.json")
Traceback (most recent call last):
  ...
subverter.Error: not a whisper-cli (.transcription) or WhisperX (.segments) JSON transcript: talk.json
```

Times are milliseconds. A text that cannot be read is refused: `subverter.Error`, its message the
reason. Texts are UTF-8 (a SubRip's or an LRC's may be UTF-16, by its BOM): a character whisper-cli
splits between tokens or, with `-ml`, cues is joined into the text it starts in; what else is not
UTF-8 is refused by its line (`not UTF-8: talk.srt (line 3)`), a JSON's by its path. A NUL reads as
U+FFFD, as the W3C reads one, noted. A note quotes a text on one line, each character visible (a
control character as Python writes it, `\x1b`), 60 characters at most.

## Licence

Part of [ffsuite](https://github.com/veramachine/ffsuite), beside ffman: its own package.
Licensed under either of
[MIT](https://github.com/veramachine/ffsuite/blob/main/packages/subverter/LICENSE-MIT)
or [Apache-2.0](https://github.com/veramachine/ffsuite/blob/main/packages/subverter/LICENSE-APACHE),
at your option.
