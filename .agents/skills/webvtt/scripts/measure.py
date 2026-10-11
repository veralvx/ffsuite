"""WebVTT, measured: what a browser's parser -- an implementation of the W3C algorithm in use --
makes of a file, through a <track> element: each cue's identifier, times, settings, region, text
and the DOM its text builds (getCueAsHTML); and which of the API's members the browser has.

Usage: python3 measure.py  (needs Python's playwright and its Chromium). Prints what it found;
references/format.md's tables are this output, at Chromium 141.0.7390.37.
"""

import base64
import json
from typing import Any

from playwright.sync_api import sync_playwright

HEAD = "WEBVTT\n\n"
T = "00:00:01.000 --> 00:00:02.000"

# a file's text each: the parser's edges
FILES: dict[str, str] = {
    "canonical": HEAD + f"1\n{T}\nHello\nworld\n",
    "no identifier": HEAD + f"{T}\nno id\n",
    "BOM": "\ufeff" + HEAD + f"{T}\nbom\n",
    "header text": "WEBVTT - a title\nKind: captions\nLanguage: en\n\n" + f"{T}\nheader\n",
    "header tab": "WEBVTT\tx\n\n" + f"{T}\ntab\n",
    "lower-case signature": "webvtt\n\n" + f"{T}\nlower\n",
    "signature glued": "WEBVTTx\n\n" + f"{T}\nglued\n",
    "no blank after header": "WEBVTT\n" + f"{T}\nno blank\n",
    "CRLF": (HEAD + f"{T}\nwindows\nline\n").replace("\n", "\r\n"),
    "CR": (HEAD + f"{T}\nmac\nline\n").replace("\n", "\r"),
    "NUL": HEAD + f"{T}\na\x00b\n",
    "no hours": HEAD + "00:01.000 --> 00:02.500\nno hours\n",
    "one-digit hour": HEAD + "1:00:00.000 --> 1:00:01.000\none digit\n",
    "hours 100": HEAD + "100:00:00.000 --> 100:00:01.000\nhundred\n",
    "minutes 60, no hours": HEAD + "60:00.000 --> 61:00.000\nsixty\n",
    "minutes 60 with hours": HEAD + "00:60:00.000 --> 00:61:00.000\nbad\n",
    "comma": HEAD + "00:00:01,000 --> 00:00:02,000\ncomma\n",
    "two-digit ms": HEAD + "00:00:01.50 --> 00:00:02.50\ntwo\n",
    "four-digit ms": HEAD + "00:00:01.5000 --> 00:00:02.5000\nfour\n",
    "no spaces round -->": HEAD + "00:00:01.000-->00:00:02.000\nglued\n",
    "tabs round -->": HEAD + "00:00:01.000\t-->\t00:00:02.000\ntabs\n",
    "end before start": HEAD + "00:00:03.000 --> 00:00:01.000\nbackwards\n",
    "end equals start": HEAD + "00:00:01.000 --> 00:00:01.000\nzero\n",
    "out of order": HEAD + f"00:00:05.000 --> 00:00:06.000\nlater\n\n{T}\nearlier\n",
    "overlap": HEAD + "00:00:01.000 --> 00:00:04.000\nlong\n\n00:00:02.000 --> 00:00:03.000\nin\n",
    "blank line in text": HEAD + f"{T}\nfirst\n\nsecond\n",
    "arrow in text": HEAD + f"{T}\nbefore\na --> b\nafter\n",
    "empty payload": HEAD + f"{T}\n\n00:00:03.000 --> 00:00:04.000\nnext\n",
    "identifier with spaces": HEAD + f"my cue 1\n{T}\nid\n",
    "two identifier lines": HEAD + f"a\nb\n{T}\ntwo ids\n",
    "NOTE": HEAD + f"NOTE a comment\nmore\n\n{T}\nafter note\n",
    "NOTE with arrow": HEAD + f"NOTE\n{T}\ninside note?\n",
    "STYLE and REGION": HEAD
    + "STYLE\n::cue(.yellow) { color: yellow }\n\n"
    + "REGION\nid:fred width:40% lines:3 regionanchor:0%,100% viewportanchor:10%,90% scroll:up\n\n"
    + f"{T} region:fred\n<c.yellow>in a region</c>\n",
    "STYLE after a cue": HEAD
    + f"{T}\nfirst\n\nSTYLE\n::cue {{ color: red }}\n\n"
    + "00:00:03.000 --> 00:00:04.000\nlater\n",
    "settings": HEAD
    + f"{T} vertical:rl line:-2,end position:30%,line-left size:40% align:end\n"
    + "settings\n",
    "line percent": HEAD + f"{T} line:10.5%,center\npercent\n",
    "line, no alignment": HEAD + f"{T} line:-2\nline -2\n",
    "line percent, no alignment": HEAD + f"{T} line:10.5%\nline 10.5%\n",
    "position, no alignment": HEAD + f"{T} position:30%\nposition 30%\n",
    "region alone": HEAD + "REGION\nid:fred width:40% lines:2\n\n" + f"{T} region:fred\nin fred\n",
    "bad settings": HEAD + f"{T} line:abc position:130% size:x align:middle foo:bar\nbad\n",
    "duplicate setting": HEAD + f"{T} align:start align:end\ndup\n",
    "region and line": HEAD + "REGION\nid:r\n\n" + f"{T} region:r line:0\nline drops region\n",
}

# a cue's text each: the tag and reference grammar
TEXTS: dict[str, str] = {
    "b i u": "<b>b</b> <i>i</i> <u>u</u>",
    "class": "<c.yellow.big>classes</c>",
    "classes on b": "<b.loud>b with class</b>",
    "voice": "<v Bob>voice</v>",
    "voice unclosed": "<v Bob>no end tag",
    "voice with class": "<v.first.loud Esme Tiu>classed voice</v>",
    "voice no annotation": "<v>no name</v>",
    "lang": "<lang en-GB>colour</lang> <lang fr>couleur</lang>",
    "ruby": "<ruby>漢<rt>kan</rt>字<rt>ji</rt></ruby>",
    "timestamps (karaoke)": "<00:00:01.000>one <00:00:01.500>two <00:00:01.800>three",
    "timestamp without hours": "a <00:01.500>b",
    "bad timestamp": "a <00:00:01,500>b",
    "unknown tag": "<s>strike?</s> <font color=red>font?</font> <span>span</span>",
    "upper-case tag": "<B>upper</B>",
    "unclosed b": "<b>open",
    "stray end tag": "a</b> b",
    "misnested": "<b>1<i>2</b>3</i>",
    "entities": "&amp; &lt; &gt; &nbsp;|&lrm;&rlm; &#169; &#x263A; &eacute;",
    "no semicolon": "&amp &lt; AT&T",
    "unknown entity": "&bogus; &;",
    "lone <": "a < b",
    "less-than glued": "a<b",
    "tab and spaces": "a\tb  c",
    "trailing spaces": "trail   ",
}


def page_for(vtt: str) -> str:
    src = "data:text/vtt;base64," + base64.b64encode(vtt.encode("utf-8")).decode()
    return f'<video id=v><track id=t kind=subtitles src="{src}" default></video>'


JS = """async () => {
  const t = document.getElementById('t');
  if (t.readyState < 2) {
    const result = await new Promise(ok => {
      t.onload = () => ok('loaded'); t.onerror = () => ok('error');
      setTimeout(() => ok('timeout'), 5000);
    });
    if (result !== 'loaded') return {status: result};
  }
  const dom = node => {
    const out = [];
    for (const n of node.childNodes) {
      if (n.nodeType === 3) out.push(JSON.stringify(n.data));
      else if (n.nodeType === 7) out.push('<?' + n.target + ' ' + n.data + '>');
      else {
        let a = n.localName;
        for (const at of n.attributes) a += ' ' + at.name + '=' + JSON.stringify(at.value);
        out.push('<' + a + '>' + dom(n) + '</' + n.localName + '>');
      }
    }
    return out.join('');
  };
  const cues = Array.from(t.track.cues).map(c => {
    const r = c.region;
    return {id: c.id, start: c.startTime, end: c.endTime, text: c.text,
            dom: dom(c.getCueAsHTML()), vertical: c.vertical, snapToLines: c.snapToLines,
            line: c.line, lineAlign: c.lineAlign, position: c.position,
            positionAlign: c.positionAlign, size: c.size, align: c.align,
            region: r && {id: r.id, width: r.width, lines: r.lines,
                          regionAnchor: [r.regionAnchorX, r.regionAnchorY],
                          viewportAnchor: [r.viewportAnchorX, r.viewportAnchorY],
                          scroll: r.scroll}};
  });
  return {status: 'loaded', cues};
}"""

# a cue's settings when it has none (Chromium has no lineAlign or positionAlign: None)
DEFAULTS = {
    "vertical": "",
    "snapToLines": True,
    "line": "auto",
    "lineAlign": None,
    "position": "auto",
    "positionAlign": None,
    "size": 100,
    "align": "center",
    "region": None,
}


def show(result: dict[str, Any]) -> str:
    """A cue list, each cue's settings only where they differ from the defaults."""
    if result["status"] != "loaded":
        return f"[{result['status']}]"
    cues = []
    for cue in result["cues"]:
        kept = {k: v for k, v in cue.items() if k not in DEFAULTS or DEFAULTS[k] != v}
        cues.append(kept)
    return json.dumps(cues, ensure_ascii=False)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        print(f"Chromium {browser.version}")
        page = browser.new_page()

        def parse(vtt: str) -> dict[str, Any]:
            page.set_content(page_for(vtt))
            return page.evaluate(JS)

        print("\n## Files: the cues parsed (settings shown where not the default)\n")
        for name, vtt in FILES.items():
            print(f"{name}: {show(parse(vtt))}")
        print("\n## Cue text: text and the DOM it builds\n")
        for name, text in TEXTS.items():
            result = parse(HEAD + f"{T}\n{text}\n")
            cue = result["cues"][0] if result.get("cues") else {}
            print(f"{name}: {text!r} -> {cue.get('dom')}")
        print("\n## The interfaces present\n")
        page.set_content("<p>")
        print(
            page.evaluate(
                "() => ({VTTCue: 'VTTCue' in window, VTTRegion: 'VTTRegion' in window,"
                " lineAlign: 'lineAlign' in VTTCue.prototype,"
                " positionAlign: 'positionAlign' in VTTCue.prototype,"
                " region: 'region' in VTTCue.prototype})"
            )
        )
        print("\n## Defaults: a cue without settings\n")
        cue = parse(HEAD + f"{T}\nx\n")["cues"][0]
        print(json.dumps({k: cue[k] for k in DEFAULTS}))
        browser.close()


if __name__ == "__main__":
    main()
