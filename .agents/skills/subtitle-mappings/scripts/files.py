"""Subtitle files written from times in milliseconds: SubRip, WebVTT, ASS and LRC as their writers
write them. Shared by `words.py` and `mappings.py`.
"""


def clock(ms: int) -> str:
    """SubRip's ``HH:MM:SS,mmm``."""
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def vtt_clock(ms: int) -> str:
    """WebVTT's ``[HH:]MM:SS.mmm``, hours only when some (OpenAI's ``format_timestamp``)."""
    return clock(ms).replace(",", ".").removeprefix("00:")


def ass_clock(ms: int) -> str:
    """ASS's ``h:mm:ss.cc``."""
    return f"{ms // 3600000}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}"


def lrc_clock(ms: int) -> str:
    """LRC's ``mm:ss.xx``."""
    return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}"


def cues(fmt: str, timed: list[tuple[int, int, str]]) -> str:
    """SubRip or WebVTT cues: each (start, end, text)."""
    if fmt == "srt":
        return "".join(
            f"{n}\n{clock(a)} --> {clock(z)}\n{t}\n\n" for n, (a, z, t) in enumerate(timed, 1)
        )
    return "WEBVTT\n\n" + "".join(
        f"{vtt_clock(a)} --> {vtt_clock(z)}\n{t}\n\n" for a, z, t in timed
    )


_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
)
_EVENT_FORMAT = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"


def ass(*events: tuple[int, int, str], size: tuple[int, int], style: str) -> str:
    """An ASS script: PlayRes ``size``, one style, `Default` (``style``: its fields after its
    name), ``events`` each (start, end, text)."""
    width, height = size
    head = (
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n\n"
        f"[V4+ Styles]\n{_STYLE_FORMAT}Style: Default,{style}\n\n[Events]\n{_EVENT_FORMAT}"
    )
    lines = [
        f"Dialogue: 0,{ass_clock(a)},{ass_clock(z)},Default,,0,0,0,,{t}\n" for a, z, t in events
    ]
    return head + "".join(lines)
