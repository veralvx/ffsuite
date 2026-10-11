"""Transcripts that break the rules on purpose: each one aimed at a reader's or a normaliser's edge.

Stage A proved its first ones equal to bash's (its bash comparison); a later one names its
box. tests/test_ingest.py checks what must hold of any transcript, on each.
"""

from typing import Final


def encoded(text: str | bytes) -> bytes:
    """A transcript's bytes: a ``str`` as UTF-8, ``bytes`` as they are."""
    return text if isinstance(text, bytes) else text.encode()


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
    # half a millisecond: through a float 504 and 4024 ms, exactly 505 and 4025 --
    # a centisecond apart in the burned ASS
    "half-ms.srt": "1\n00:00:00,5045 --> 00:00:04,0245\nhalf\n",
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
}
