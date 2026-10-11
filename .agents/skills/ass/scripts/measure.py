"""ASS and SSA, measured: what libass -- the renderer ffmpeg's `subtitles` and `ass` filters
use, and ffman's burn -- reads of a file: the header, each style and each event as it holds
them (`assdump.c`, beside this script), and its warnings.

Usage: python3 measure.py ASSDUMP  (assdump built against libass 0.17.4 -- see assdump.c).
Prints what it found; references/format.md's tables are this output.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ASSDUMP = sys.argv[1] if len(sys.argv) > 1 else "./assdump"

ASS_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
)
ASS_EVENT_FORMAT = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
STYLE = "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1"


def ass(info: str = "ScriptType: v4.00+", styles: str = STYLE, events: str = "") -> str:
    """An ASS file: its [Script Info] lines, its styles, its events (after the Format lines)."""
    return (
        f"[Script Info]\n{info}\n\n[V4+ Styles]\n{ASS_STYLE_FORMAT}\n{styles}\n\n"
        f"[Events]\n{ASS_EVENT_FORMAT}\n{events}\n"
    )


def ev(
    start: str = "0:00:01.00", end: str = "0:00:02.00", text: str = "x", style: str = "Default"
) -> str:
    """A Dialogue line."""
    return f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}"


SSA = """[Script Info]
ScriptType: v4.00

[V4 Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, TertiaryColour, BackColour, \
Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, AlphaLevel, Encoding
Style: Default,Arial,20,16777215,255,0,8421504,-1,0,1,2,2,6,10,10,10,0,0

[Events]
Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: Marked=0,0:00:01.00,0:00:02.00,Default,Bob,0000,0000,0000,,SSA line
"""

# a file each: the header, the sections, the styles
FILES: dict[str, str] = {
    "canonical": ass(events=ev(text="Hello, world")),
    "SSA v4": SSA,
    "no ScriptType": ass(info="Title: t", events=ev()),
    "no styles section": "[Script Info]\nScriptType: v4.00+\n\n[Events]\n"
    + ASS_EVENT_FORMAT
    + "\n"
    + ev()
    + "\n",
    "no format lines": "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
    + STYLE
    + "\n\n[Events]\n"
    + ev()
    + "\n",
    "nothing known": "[Script Info]\nTitle: only\n",
    "lower-case sections": ass(events=ev())
    .replace("[Script Info]", "[script info]")
    .replace("[Events]", "[events]"),
    "lower-case info keys": ass(
        info="ScriptType: v4.00+\nplayresx: 1920\nplayresy: 1080", events=ev()
    ),
    "PlayRes": ass(
        info="ScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nLayoutResX: 1024\nLayoutResY: 576",
        events=ev(),
    ),
    "PlayResX alone": ass(info="ScriptType: v4.00+\nPlayResX: 1920", events=ev()),
    "PlayResX 1280 alone": ass(info="ScriptType: v4.00+\nPlayResX: 1280", events=ev()),
    "PlayResY alone": ass(info="ScriptType: v4.00+\nPlayResY: 1080", events=ev()),
    "header values": ass(
        info="ScriptType: v4.00+\nWrapStyle: 2\nScaledBorderAndShadow: yes\nKerning: yes\n"
        "YCbCr Matrix: TV.709\nLanguage: pt-BR\nTimer: 100.0000",
        events=ev(),
    ),
    "custom style format": ass(events=ev())
    .replace(ASS_STYLE_FORMAT, "Format: Name, Fontsize, Fontname")
    .replace(STYLE, "Style: Default,30,Serif"),
    "custom event format": ass(events="Dialogue: 0:00:01.00,0:00:02.00,custom, order").replace(
        ASS_EVENT_FORMAT, "Format: Start, End, Text"
    ),
    "Actor for Name": ass(
        events="Dialogue: 0,0:00:01.00,0:00:02.00,Default,Bob,0,0,0,,actor"
    ).replace("Style, Name,", "Style, Actor,"),
    "V4++ Styles": "[Script Info]\nScriptType: v4.00++\n\n[V4++ Styles]\nFormat: Name, Fontname, Fontsize\n"
    "Style: Big,Serif,40\n\n[Events]\n" + ASS_EVENT_FORMAT + "\n" + ev(style="Big") + "\n",
    "BOM and CRLF": "\ufeff" + ass(events=ev(text="crlf")).replace("\n", "\r\n"),
    "CR only": ass(events=ev(text="cr")).replace("\n", "\r"),
    "Aegisub garbage and Graphics": ass(events=ev()).replace(
        "\n\n[V4+ Styles]",
        "\n\n[Aegisub Project Garbage]\nVideo File: v.mkv\nPlayResX: 640\n\n[V4+ Styles]",
    )
    + "\n[Graphics]\nfilename: x.png\n",
}

# a style line each (in the canonical file)
STYLES: dict[str, str] = {
    "colours &HAABBGGRR": "Style: S,Arial,20,&H80FF8040,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "colours &HBBGGRR (no alpha)": "Style: S,Arial,20,&HFF8040,&H0000FF,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "colours decimal": "Style: S,Arial,20,16777215,255,0,0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "colour lower-case &h, trailing &": "Style: S,Arial,20,&h00ff8040&,&H0000FF&,0,0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "booleans -1 1 700": "Style: S,Arial,20,&H0,&H0,&H0,&H0,-1,1,700,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "fractions": "Style: S,Arial,20.5,&H0,&H0,&H0,&H0,0,0,0,0,99.5,100,1.5,12.5,1,2.25,0.5,2,10,10,10,1",
    "negatives": "Style: S,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,-50,100,-2,0,1,-1,-1,2,-10,10,10,1",
    "alignments 7 5 3": "Style: A7,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,7,10,10,10,1\n"
    "Style: A5,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,5,10,10,10,1\n"
    "Style: A3,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,3,10,10,10,1",
    "starred name": "Style: *S,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "name with spaces": "Style: My Style ,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "missing fields": "Style: S,Arial,20",
    "BorderStyle 3": "Style: S,Arial,20,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,3,2,2,2,10,10,10,1",
}

# an event each (in the canonical file)
EVENTS: dict[str, str] = {
    "centiseconds": ev("0:00:01.23", "0:00:04.56"),
    "one fraction digit": ev("0:00:01.5", "0:00:02.5"),
    "three fraction digits": ev("0:00:01.500", "0:00:02.500"),
    "two-digit hours": ev("10:00:00.00", "10:00:01.00"),
    "hours 100": ev("100:00:00.00", "100:00:01.00"),
    "minutes 75": ev("0:75:00.00", "0:75:01.00"),
    "no fraction": ev("0:00:01", "0:00:02"),
    "comma fraction": ev("0:00:01,50", "0:00:02,50"),
    "negative": ev("-0:00:01.00", "0:00:02.00"),
    "end before start": ev("0:00:03.00", "0:00:01.00"),
    "text commas, spaces": ev(text="  lead, mid,  trail   "),
    "override tags kept": ev(text="{\\b1}bold{\\b0}\\Nline two{\\k50}kara{\\pos(10,20)}"),
    "style not found": ev(style="Nope"),
    "style lower-case default": ev(style="default"),
    "style starred": ev(style="*Default"),
    "event margins": "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0012,-5,7,,margins",
    "layer": "Dialogue: 5,0:00:01.00,0:00:02.00,Default,,0,0,0,,layer five",
    "effect": "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,Banner;20;1,effect",
    "too few fields": "Dialogue: 0,0:00:01.00,0:00:02.00,Default",
    "no space after colon": "Dialogue:0,0:00:01.00,0:00:02.00,Default,,0,0,0,,glued",
    "Comment line": "Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,a comment",
    "two styles same name": ev(text="which?"),
    "style 'My Style ' asked as 'My Style'": ev(style="My Style"),
    "style 'My Style ' asked as 'My Style '": ev(style="My Style "),
}
SPACED = "Style: My Style ,Serif,40,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1"
STYLES_FOR_EVENT = {
    "two styles same name": STYLE
    + "\nStyle: Default,Serif,40,&H0,&H0,&H0,&H0,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
    "style 'My Style ' asked as 'My Style'": STYLE + "\n" + SPACED,
    "style 'My Style ' asked as 'My Style '": STYLE + "\n" + SPACED,
}


def dump(text: str, work: Path) -> tuple[object, list[str]]:
    """What libass reads of ``text`` (assdump's JSON) and its warnings."""
    path = work / "in.ass"
    _ = path.write_text(text, encoding="utf-8")
    r = subprocess.run([ASSDUMP, str(path)], capture_output=True, text=True, check=True)
    warnings = [  # libass's messages, without the track's address ("[0x...]: ")
        re.sub(r"^\[0x[0-9a-f]+\]: ", "", w)
        for w in r.stderr.splitlines()
        if "Assuming 384x288" not in w
    ]
    return json.loads(r.stdout), warnings


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print("## Files: the track (header, styles but libass's own first, events)\n")
        for name, text in FILES.items():
            track, warnings = dump(text, work)
            if isinstance(track, dict):
                track["styles"] = track["styles"][1:]  # libass's own Default, always first
            print(
                f"{name}: {json.dumps(track, ensure_ascii=False)}"
                + (f" | {warnings}" if warnings else "")
            )
        print("\n## Styles: each as libass holds it (colours RRGGBBAA, AA 00 opaque)\n")
        for name, line in STYLES.items():
            track, warnings = dump(ass(styles=line, events=ev(style="S")), work)
            assert isinstance(track, dict)
            print(
                f"{name}: {json.dumps(track['styles'][1:])}"
                + (f" | {warnings}" if warnings else "")
            )
        print("\n## Events: each as libass holds it\n")
        for name, line in EVENTS.items():
            track, warnings = dump(ass(styles=STYLES_FOR_EVENT.get(name, STYLE), events=line), work)
            assert isinstance(track, dict)
            print(
                f"{name}: {json.dumps(track['events'], ensure_ascii=False)}"
                + (f" | {warnings}" if warnings else "")
            )
        print("\n## libass's own style (styles[0], no style in the file)\n")
        track, _ = dump(FILES["no styles section"], work)
        assert isinstance(track, dict)
        print(json.dumps(track["styles"][0]))


if __name__ == "__main__":
    main()
