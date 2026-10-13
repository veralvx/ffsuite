"""Transcripts that break the rules on purpose: each one aimed at a reader's or a normaliser's edge.

Stage A proved its first ones equal to bash's (its bash comparison); a later one names its
box. tests/test_ingest.py checks what must hold of any transcript, on each.
"""

from typing import Final

# an ASS's script and its style, its events to follow: the corpus's t.ass
ASS_HEAD: Final = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, \
BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,IBM Plex Sans,57,&H00FFFFFF,&H00000000,&H00000000,0,0,1,2,0,2,40,40,54

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def encoded(text: str | bytes) -> bytes:
    """A transcript's bytes: a ``str`` as UTF-8, ``bytes`` as they are."""
    return text if isinstance(text, bytes) else text.encode()


# what a track's readers take as markup or structure -- SubRip's, mov_text's converter's,
# WebVTT's -- each a text: the chunk's text, and the WebVTT holding it, a reference decoded
# once the overrides are off (6.8.2: the attached track holds the text exactly)
ATTACHED: Final = {
    "a {text} b": "a {text} b",
    "{\\an8}x": "&#123;\\an8}x",
    "a{\\b c": "a&#123;\\b c",
    "{y:i}x": "{y:i}x",
    "a \\N b \\h c\\x": "a \\N b \\h c\\x",
    "<b>x</b> 1 < 2": "&lt;b&gt;x&lt;/b&gt; 1 &lt; 2",
    "& &amp;": "&amp; &amp;amp;",
    "00:00:01,000 --> 00:00:02,000": "00:00:01,000 --&gt; 00:00:02,000",
    "2024": "2024",
}
_ATTACHED_VTT: Final = "WEBVTT\n\n" + "".join(
    f"00:00.{40 * i:03d} --> 00:00.{40 * i + 40:03d}\n{vtt}\n\n"
    for i, vtt in enumerate(ATTACHED.values())
)  # each in the corpus's 0.4 s

HOSTILE: Final = {
    # a line too long for one line, in scripts without spaces: Japanese by kinsoku, Thai by
    # its syllables (6.5): never a line opening on 、 or 。, never after เ -- each a text the
    # code before broke there (の|、, ます|。, และเ|รา)
    "long-ja.srt": "1\n00:00:01,000 --> 00:00:04,000\n日本語の文章は単語の間にスペースを入れないの、ですから一行がとても長くなることがあります。「本当ですか？」と彼は言った。\n",
    "long-th.srt": "1\n00:00:01,000 --> 00:00:04,000\nวันนี้เมื่อวานนี้ฝนตกหนักมากจนน้ำท่วมถนนและเราต้องเดินทางกลับบ้านด้วยความลำบากมากที่สุด\n",
    # Malayalam (6.8.1): the UDHR's article 1 -- measured, a fallback's glyph a size each; with
    # another --font (burn/another-font/), estimated so too, where 0.55 ran past the frame
    "long-ml.srt": "1\n00:00:01,000 --> 00:00:04,000\nമനുഷ്യരെല്ലാവരും തുല്യാവകാശങ്ങളോടും അന്തസ്സോടും സ്വാതന്ത്ര്യത്തോടുംകൂടി ജനിച്ചിട്ടുള്ളവരാണ്\u200c. അന്യോന്യം ഭ്രാതൃഭാവത്തോടെ പെരുമാറുവാനാണ്\u200c മനുഷ്യന്നു വിവേകബുദ്ധിയും മനസ്സാക്ഷിയും സിദ്ധമായിരിക്കുന്നത്\u200c.\n",
    # Unicode 16.0's changes (6.8.1): trigrams wide there, not in 15.1; Arabic Pepet, a 16.0
    # mark -- ffman's own 15.1 tables, so alike under Python 3.13 (15.1) and 3.14 (16.0)
    "unicode-16.srt": "1\n00:00:01,000 --> 00:00:04,000\n\u2630\u2631\u2632\u2633\u2634\u2635\u2636\u2637 trigrams \u2630\u2631\u2632\u2633\u2634\u2635\u2636\u2637\u2630\u2631\u2632\u2633\u2634\u2635\u2636\u2637 and a\u0897 pepet\n",
    # half a millisecond: through a float 504 and 4024 ms, exactly 505 and 4025 -- a
    # centisecond apart in the burned ASS (an LRC: SubRip's fraction is a count of ms, 6.8.2)
    "half-ms.lrc": "[00:00.5045]half\n[00:04.0245]\n",
    "crlf.csv": 'start,end,text\r\n0,1000,"Hello, ""you"""\r\n1000,2000,Two\r\n',
    "bom.srt": "\ufeff1\n00:00:01,000 --> 00:00:02,000\nFirst\n\n2\n00:00:00,500 --> 00:00:01,500\nEarlier\n",
    "unsorted.lrc": "[00:05.00]Later\n[00:01.50]Sooner\n[00:03]Mid\n",
    "settings.vtt": "WEBVTT\n\nNOTE a note\n\n00:01.000 --> 00:02.500 align:start position:10%\n<b>Bold</b> {\\an8}and \\N more\n\n",
    "hours.srt": "1\n100:00:00,000 --> 100:00:01,000\nLate\n",
    "reversed.srt": "1\n00:00:02,000 --> 00:00:01,000\nBackwards\n\n2\n00:00:03,000 --> 00:00:04,000\n   \n",
    "reordered.csv": 'text,end,start\nhi,2000,1000\n"a,b",4000,3000\n',
    "negative.tsv": "start\tend\ttext\n-500\t800\tneg\nx\t900\tbad start\n",
    "texts.json": '{"segments": [{"start": 0.5, "end": "1.25", "text": "a\\tb\\nc \\\\ d"}, {"start": "x", "end": 2, "text": 7}, {"start": 2, "end": 3, "text": null}, {"start": 3, "end": 4.0004, "text": "four", "words": [{"word": "four", "start": 3.1}, {"word": "tied", "start": 3.1, "end": 3.2}, {"word": "gone"}, "bad", {"word": "late", "start": 9}]}]}',
    "cli.json": '{"transcription": [{"offsets": {"from": 0, "to": 1500}, "text": " hi there"}, {"offsets": {"from": "2000", "to": null}, "text": "no end"}, {"offsets": {"from": 3000, "to": 4000}, "text": ["odd"]}]}',
    "-dash.json": '{"segments": [{"start": 0, "end": 1, "text": "dashed"}]}',
    "neither.json": '{"results": []}',
    "invalid.json": "{nope",
    "notes.txt": "plain text\n",
    "subs.xyz": "x\n",
    "empty.srt": "1\n00:00:01,000 --> 00:00:01,000\nzero\n",
    "halves.json": '{"segments": [{"start": 0.0125, "end": 1.0625, "text": "half", "words": [{"word": "half", "start": 0.0625, "end": 0.1125}]}]}',
    "no-newline.srt": "1\n00:01 --> 00:02\nshort times\n2\n5 --> 7\nbare seconds, no blank line before",
    "blank-lines.srt": "\n\n1\n00:00:01,000 --> 00:00:02,000\nx\n\n\n\n2\n00:00:03,000 --> 00:00:04,000\ny\n",
    "gaps.srt": "1\n00:00:01,000 --> 00:00:02,000\n<u>A</u> b\n\n2\n00:00:02,000 --> 00:00:03,000\nA b\n\n3\n00:00:03,000 --> 00:00:04,000\nA <u>b</u>\n\n",
    "short.tsv": "start\tend\ttext\n100\n\n200\t300\tok\n",
    "types.json": '{"result": {"language": "en"}, "transcription": [{"offsets": {"from": 0, "to": 3000}, "text": " one two", "tokens": [7, {"text": " one", "offsets": {"from": true, "to": {"x": 1}}, "t_dtw": 5}, {"text": " two", "offsets": {"from": 1.5, "to": 2500}, "t_dtw": 12}]}, {"offsets": {"from": 3000, "to": 4000}, "text": " ok", "tokens": [{"text": " ok", "offsets": {"from": 3100, "to": 3900}, "t_dtw": 310}]}, {"offsets": {"from": 4000, "to": 5000}, "text": " none", "tokens": [{"text": " none", "offsets": {"from": 4100, "to": 4900}}]}]}',
    "windows.json": '{"segments": [{"start": 1, "end": 3, "text": "w", "words": "nope"}, {"start": 3, "end": 5, "text": "early late own", "words": [{"word": "early", "start": 2.0, "end": 3.2}, {"word": "own", "start": 3.5, "end": 3.7}, {"word": "tail"}, {"word": "late", "start": 6}]}, {"start": 5, "end": 6, "text": "first", "words": ["x", {"word": "a"}, {"word": "b", "start": 5.5, "end": 5.6}]}]}',
    "empty.lrc": "",
    "emptied.srt": "1\n00:00:01,000 --> 00:00:02,000\n<u>A</u> b\n\n2\n00:00:02,000 --> 00:00:03,000\nA <u>b</u>\n\n3\n00:00:03,000 --> 00:00:04,000\nA b\n\n4\n00:00:04,000 --> 00:00:05,000\n<b></b>\n\n",
    "odd-windows.json": '{"transcription": [{"offsets": {"from": null, "to": "zz"}, "text": " w", "tokens": [{"text": " w", "offsets": {"from": 0, "to": 10}, "t_dtw": 1}]}, {"offsets": {"from": false, "to": 900}, "text": " v", "tokens": [{"text": " v", "offsets": {"from": true, "to": {"k": 1}}, "t_dtw": -2}]}, {"offsets": {"from": 1000, "to": 2000}, "text": " u", "tokens": [{"text": " u", "offsets": {"from": 1000.5, "to": 1999}, "t_dtw": 90}]}]}',
    "anchors.json": '{"segments": [{"start": " 5", "end": 7, "text": "spaced"}, {"start": 8, "end": 9, "text": "a b", "words": [{"word": "a"}, {"word": "  "}, {"word": "b", "start": 8.0, "end": 8.5}]}]}',
    "infinite.json": '{"segments": [{"start": "inf", "end": 1e400, "text": "far"}, {"start": 1, "end": 2, "text": "near", "words": [{"word": "near", "start": {}}]}]}',
    "fractions.json": '{"transcription": [{"offsets": {"from": 1000, "to": 2000}, "text": " u v", "tokens": [{"text": " u", "offsets": {"from": 1000.5, "to": 1499.25}, "t_dtw": 90}, {"text": " v", "offsets": {"from": 1500, "to": 1999}, "t_dtw": 95}]}]}',
    "bounds.json": '{"transcription": [{"offsets": {"from": false, "to": [1]}, "text": " w", "tokens": [{"text": " w", "offsets": {"from": 0, "to": 10}, "t_dtw": 1}]}, {"offsets": {"from": 0, "to": 500}, "text": " x", "tokens": [{"text": " x", "offsets": {"from": 0, "to": 500}}]}]}',
    "spaces.srt": "1\n00:00:01,000 --> 00:00:04,000\nno\xa0break and\u3000ideographic spaces here in one quite long line of text to wrap\n",
    # WebVTT's character references (6.8.1, bash's as written): each run between tags
    # decoded -- a decoded tag text, a decoded break a space, an unknown reference as written;
    # inside the corpus's 0.4 s, so the attached SRT holds it too
    "references.vtt": "WEBVTT\n\n00:00.000 --> 00:00.300\nA &amp; B &lt;b&gt;&#10;C &bogus;\n",
    # LRM and RLM (6.8.1): drawn as nothing, so measured as nothing -- one line at the corpus's
    # 320 x 180, as wide as one holds (a word more, two), rendered as without them; measured
    # each a size, two
    "format-characters.vtt": "WEBVTT\n\n00:00.000 --> 00:00.300\n&lrm;she &lrm;said &lrm;the &lrm;name &lrm;was &lrm;written &lrm;right &lrm;to &lrm;left &lrm;in &lrm;her &lrm;own &lrm;hand &lrm;and&rlm;\n",
    # a word joiner and zero-width spaces (6.8.1): UAX #14's, where libass draws neither -- the
    # joined Japanese line breaks before の, not after it; the three words, a line's width and
    # more, part at a zero-width space, not inside a word
    "joiners.srt": "1\n00:00:00,000 --> 00:00:00,300\n日本語の文章は単語の間にスペースを入れないの\u2060で一行がとても長くなる\n\n2\n00:00:00,300 --> 00:00:00,400\nSupercalifragilisticexpialidocious\u200bantidisestablishmentarianism\u200bfloccinaucinihilipilification\n",
    # whisper-cli -ojf's bytes (6.8.1): each token's as whisper wrote them -- 鬱 over two
    # tokens, 心 over two sentences (-ml), a tab raw -- each character in the token and the
    # sentence it starts; before, refused whole: "not valid JSON"
    "bytes.json": (
        b'{"result": {"language": "ja"}, "transcription": ['
        b'{"offsets": {"from": 0, "to": 1000}, "text": "\xe9\xac\xb1\xe3\x81\xaf", "tokens": ['
        b'{"text": "\xe9\xac", "offsets": {"from": 0, "to": 300}, "t_dtw": 5}, '
        b'{"text": "\xb1", "offsets": {"from": 300, "to": 600}, "t_dtw": 30}, '
        b'{"text": "\xe3\x81\xaf", "offsets": {"from": 600, "to": 900}, "t_dtw": 60}]}, '
        b'{"offsets": {"from": 1000, "to": 2000}, "text": "\xe5\xbf", "tokens": ['
        b'{"text": "\xe5\xbf", "offsets": {"from": 1000, "to": 1900}, "t_dtw": 105}]}, '
        b'{"offsets": {"from": 2000, "to": 3000}, "text": "\x83\t\xe3\x81\x84", "tokens": ['
        b'{"text": "\x83", "offsets": {"from": 2000, "to": 2100}, "t_dtw": 205}, '
        b'{"text": "\t\xe3\x81\x84", "offsets": {"from": 2100, "to": 2900}, "t_dtw": 215}]}]}'
    ),
    # whisper-cli -osrt -ml 1 (6.8.1): " Это ёлка и 😀" by whisper's tokens, wrapped by its own
    # whisper_wrap_segment -- ё and 😀 split between cues (its times halved: the corpus's 0.4 s),
    # each joined into the cue it starts; bash burned each byte as libass reads it, the port
    # stopped on a traceback
    "split.srt": (
        b"1\n00:00:00,000 --> 00:00:00,050\n \xd0\xad\xd1\x82\xd0\xbe\n\n"
        b"2\n00:00:00,050 --> 00:00:00,100\n \xd1\n\n"
        b"3\n00:00:00,100 --> 00:00:00,200\n\x91\xd0\xbb\n\n"
        b"4\n00:00:00,200 --> 00:00:00,250\n\xd0\xba\xd0\xb0\n\n"
        b"5\n00:00:00,250 --> 00:00:00,300\n \xd0\xb8\n\n"
        b"6\n00:00:00,300 --> 00:00:00,350\n \xf0\x9f\x98\n\n"
        b"7\n00:00:00,350 --> 00:00:00,400\n\x80\n\n"
    ),
    # a Latin-1 é (6.8.1): refused by its line -- bash burned it as libass reads a byte not
    # UTF-8, its Latin-1 character, and ffmpeg dropped its cue from --add-subs' track; the
    # port stopped on a traceback
    "latin-1.srt": b"1\n00:00:00,000 --> 00:00:00,300\ncaf\xe9\n",
    # a header naming text first, then a record short of its times (6.8.1): its times none, as
    # awk's $n past the last field, so no cue -- the port stopped on an IndexError
    "columns.csv": "text,start,end\nhello\nok,0,300\n",
    # a header after a blank line (6.8.1): the first record its header, a blank line none, as
    # pandas reads one -- before, read as data, every cue untimed: "no timed text found"
    "late-header.csv": "\ntext,start,end\nhello,0,300\n",
    # a text line holding --> (6.8.1): no time either side, so no timing line -- SubRip's text,
    # as ffmpeg reads it; in WebVTT the cue's end, the lines after it up to a blank one no cue's
    # (W3C WebVTT). Before, as bash's awk, `Note: 1` read 1 s and `2` 2 minutes: a cue of `y`
    # from 1 s to 2:00 in each; the SubRip's second cue lost, its `c` a cue at 0 of no length
    "arrows.srt": (
        "1\n00:00:00,000 --> 00:00:00,200\nThe sign said:\nNote: 1 --> 2\ny\n\n"
        + "2\n00:00:00,200 --> 00:00:00,400\na --> b\nc\n"
    ),
    "arrows.vtt": (
        "WEBVTT\n\n00:00.000 --> 00:00.200\nx\nNote: 1 --> 2\ny\n\n"
        + "00:00.200 --> 00:00.400\nnext\n"
    ),
    # LRC's [offset] (6.8.1): every time sooner by it, in ms, the last whole one; one not whole
    # noted, ignored. Before, as bash, none read: `one` at 0.6 s, `two` at 0.7 s
    "offset.lrc": "[offset:abc]\n[offset:+500]\n[00:00.60]one\n[00:00.70]two\n",
    # an LRC line of several stamps (6.8.1): a line each, blanks between them too. Before, as
    # bash, its first alone, the rest its text: `[00:00.30]chorus` from 0, `[00:00.35] spaced`
    "chorus.lrc": "[00:00.00][00:00.30]chorus\n[00:00.15] [00:00.35]\tspaced\n",
    # a seconds fraction not of three digits (6.8.2): SubRip's a count of ms, as ffmpeg and VLC
    # read it; in WebVTT no time, its cue dropped (W3C) -- each noted. Before, as bash, a
    # decimal: `,5` 500 ms, `,25` 250, so `five` ended before it began, dropped; `00:00.2` 200
    "fraction.srt": "1\n00:00:00,5 --> 00:00:00,25\nfive\n\n2\n00:00:00,250 --> 00:00:00,400\nnext\n",
    "fraction.vtt": "WEBVTT\n\n00:00.000 --> 00:00.200\nok\n\n00:00.2 --> 00:00.400\ndropped\n",
    # WebVTT's timing lines wholly the W3C's (6.8.2): bash's lenient forms dropped, noted.
    # Before, as bash: `5 --> 7` 5 to 7 minutes, the sign and the one digit read
    "timestamps.vtt": (
        "WEBVTT\n\n00:00.000 --> 00:00.100\nkept\n\n5 --> 7\nminutes\n\n"
        + "-00:00.100 --> 00:00.200\nsigned\n\n0:00.200 --> 0:00.300\none digit\n\n"
        + "00:00.300 --> 00:00.400\nlast\n"
    ),
    # the next cue's index with no blank line before it (6.8.2): a number alone right before a
    # timing line, the index, as ffmpeg reads it -- noted; `2.` text. Before, as bash, the first
    # cue's text: `first 2`
    "index.srt": "1\n00:00:00,000 --> 00:00:00,200\nfirst\n2\n00:00:00,200 --> 00:00:00,400\n2.\n3\n00:00:00,400 --> 00:00:00,600\nthird\n",
    # ASS's escapes typed in a SubRip (6.8.2): `\N` a line break -- a space, ffman wrapping
    # -- and `\h` a no-break space, as ffmpeg's subrip decoder passes them to libass; an
    # override opening with `\t` dropped as any. Before: burned `one/Ntwo a/hb`, the override
    # `( (0,100,/fs20))` -- its `\t` a space before overrides were removed (bash's order)
    "escapes.srt": "1\n00:00:00,000 --> 00:00:00,400\n{\\t(0,100,\\fs20)}one\\Ntwo a\\hb\n",
    # braces and backslashes drawn as written (6.8.2): libass's \{ and \}, a backslash before a
    # word joiner; a SubRip's own \{ \} its braces, its {d} a block, hidden as libass hides it,
    # noted. Before: burned `a/(b/) c/x (d)`
    "braces.srt": "1\n00:00:00,000 --> 00:00:00,400\na\\{b\\} c\\x {d}\n",
    # a WebVTT without its signature (6.8.2): refused, as the W3C's parser processes no such
    # file (Chromium none). Before: read, as ffmpeg reads it
    "unsigned.vtt": "00:00.000 --> 00:00.400\nno signature\n",
    # line ends (6.8.2): a CR alone one (the W3C's; ffmpeg's SubRip demuxer and VLC 3 alike);
    # SubRip's CR CR LF one, as ffmpeg reads it, WebVTT's two, as the W3C -- each cue then of no
    # text, refused. Before:
    # a CR alone no line end (the SubRip and WebVTT refused, the LRC one line), a CR CR LF's
    # first CR kept (the SubRip's next index joined to its cue's text, the WebVTT read)
    "cr.srt": "1\r00:00:00,000 --> 00:00:00,200\rfirst\rline\r\r2\r00:00:00,200 --> 00:00:00,400\rsecond\r",
    "crcrlf.srt": "1\r\r\n00:00:00,000 --> 00:00:00,200\r\r\nfirst\r\r\nline\r\r\n\r\r\n2\r\r\n00:00:00,200 --> 00:00:00,400\r\r\nsecond\r\r\n",
    "cr.vtt": "WEBVTT\r\r00:00.000 --> 00:00.200\rfirst\rline\r\r00:00.200 --> 00:00.400\rsecond\r",
    "crcrlf.vtt": "WEBVTT\r\r\n\r\r\n00:00.000 --> 00:00.400\r\r\nno text\r\r\n",
    "cr.lrc": "[00:00.00]first\r[00:00.20]second\r",
    # a SubRip cue reads on past an empty line, as ffmpeg (so mpv) reads it -- the text after one
    # kept, noted; the credits after the last cue its text; `2` an index (6.8.2). Before: each
    # cue ended at it, `kept` and `credits` dropped, silently
    "continued.srt": (
        "1\n00:00:00,000 --> 00:00:00,200\nfirst\n\nkept\n\n2\n00:00:00,200 --> 00:00:00,400\n"
        "last\n\ncredits\n"
    ),
    # a SubRip cue reads on past a line of spaces too, as MPC-HC and Subtitle Edit read it, noted
    # (6.8.2); `2` after one an index. Before: the text after it dropped, silently, as ffmpeg's
    # decoder drops it
    "spaced.srt": (
        "1\n00:00:00,000 --> 00:00:00,200\nfirst\n   \nlost\n\n2\n00:00:00,200 --> 00:00:00,400\n"
        "last\n  \ncredits\n"
    ),
    # a WebVTT cue's line of spaces its text, as the W3C reads it (6.8.2). Before: its end
    "whitespace.vtt": "WEBVTT\n\n00:00.000 --> 00:00.400\nfirst\n   \nsecond\n",
    # a WebVTT cue's text after an empty line, no cue's, dropped as the W3C drops it, noted
    # (6.8.2); `NOTE` a comment, `id` the next cue's identifier. Before: dropped, silently
    "stray.vtt": (
        "WEBVTT\n\n00:00.000 --> 00:00.200\nfirst\n\nlost\n\nNOTE a comment\n\nid\n"
        "00:00.200 --> 00:00.400\nsecond\n\nalso lost\n"
    ),
    # a WebVTT's backslashes and braces: text, as every reader shows them (6.8.2). Before: SubRip's
    # reading -- the override gone, a typed \n or \t a space: `C: ew able`
    "typed.vtt": "WEBVTT\n\n00:00.000 --> 00:00.400\nC:\\new \\table {\\an8}\n",
    # a WebVTT's < with no > after it (6.8.2): a tag to the text's end, as the W3C, Chromium and
    # ffmpeg read it, noted -- a decoded &lt; text. Before: text, VLC's reading alone. The note
    # names the rest, its trailing blanks off
    "unclosed.vtt": (
        "WEBVTT\n\n00:00.000 --> 00:00.100\nI <3 you  \n\n00:00.100 --> 00:00.200\nbefore <b\n"
        "ends\n\n00:00.200 --> 00:00.300\nR&amp;D &lt;5 kg\n"
    ),
    # a note's text past 60 characters (6.8.2): quoted as a message quotes input (``shown``), its
    # first 57 and "...". Before: quoted whole, a line of 400,000 characters that much on stderr
    "quoted.srt": "1\n00:00:00,000 --> 00:00:00,300\nfirst\n\n" + "word " * 39 + "end\n",
    # a note's control characters (6.8.2): each as Python writes it, so none commands the terminal.
    # Before: an ESC reached stderr as it was -- an OSC set the terminal's title, an SGR its colour
    "controls.vtt": "WEBVTT\n\n00:00.000 --> 00:00.300\nfirst\n\n\x1b]0;title\x07\x1b[31mred\n",
    # a NUL in a text (6.8.2): U+FFFD, as the W3C reads one, noted. Before: written into the
    # ASS, where libass ended the script -- `fi` drawn, every later cue lost (measured)
    "nul.srt": "1\n00:00:00,000 --> 00:00:00,200\nfi\x00rst\n\n2\n00:00:00,200 --> 00:00:00,400\nsecond\n",
    # a NUL in an ASS (6.8.2): U+FFFD in ffman's copy, burned and attached, noted. Before:
    # burned as it was, libass ended the script there -- `fi` drawn, `second` lost (measured)
    "nul.ass": ASS_HEAD
    + "Dialogue: 0,0:00:00.00,0:00:00.20,Default,,0,0,0,,fi\x00rst\n"
    + "Dialogue: 0,0:00:00.20,0:00:00.40,Default,,0,0,0,,second\n",
    # a UTF-16 ASS (6.8.2): UTF-8 in ffman's copy, as ffmpeg's reader recodes it; one with a
    # lone surrogate refused by its line. Before: copied as it was -- libass, given no codepage,
    # made no script of it, the burn failed; ffmpeg cut the surrogate's line
    "utf-16.ass": (
        "\ufeff"
        + ASS_HEAD
        + "Dialogue: 0,0:00:00.00,0:00:00.20,Default,,0,0,0,,café\n"
        + "Dialogue: 0,0:00:00.20,0:00:00.40,Default,,0,0,0,,second\n"
    ).encode("utf-16-le"),
    "utf-16-bad.ass": (
        "\ufeff" + ASS_HEAD + "Dialogue: 0,0:00:00.00,0:00:00.40,Default,,0,0,0,,fi\ud800rst\n"
    ).encode("utf-16-le", "surrogatepass"),
    # a CP1252 ASS (6.8.2): refused by its line, as a SubRip not UTF-8. Before: burned as libass
    # reads a byte not UTF-8, its Latin-1 character -- the quote's 0x92 a control -- and each
    # event holding one dropped from --add-subs' track by ffmpeg's decoder (measured)
    "cp1252.ass": (
        ASS_HEAD + "Dialogue: 0,0:00:00.00,0:00:00.40,Default,,0,0,0,,café \u2019x\u2019\n"
    ).encode("cp1252"),
    # an .ass that is no script (6.8.2), refused, named, as ffmpeg's reader and libass read it.
    # Before: burned or attached, ffmpeg failed; `[script info]`, its signature lower-cased,
    # burned (libass takes any case) but attached as an LRC -- an empty track, unnoted
    "no-script.ass": "hello\n",
    "lower.ass": ASS_HEAD.replace("[Script Info]", "[script info]")
    + "Dialogue: 0,0:00:00.00,0:00:00.40,Default,,0,0,0,,lower\n",
    # each text attached exactly into every container (6.8.2), burned as written. Before: an
    # attached `{text}` hidden, `\N` a break, `<b>` bold, a cue lost to its timing line
    "attached.vtt": _ATTACHED_VTT,
}
