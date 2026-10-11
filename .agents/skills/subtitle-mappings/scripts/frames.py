"""Subtitles drawn, and read back from their frames: libass through ffmpeg's `ass` filter, a
frame at each millisecond asked; Chromium through a `<track>` on a video seeked to each time.
A frame's ink is read by colour, word by word or as one box. Shared by `words.py` and
`mappings.py`.
"""

import base64
import subprocess
from collections import Counter
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def ffmpeg(binary: str, *args: str) -> bytes:
    """ffmpeg's output on ``args``."""
    return subprocess.run([binary, "-v", "error", *args], capture_output=True, check=True).stdout


def rgb(binary: str, image: Path) -> bytes:
    """An image's pixels, RGB."""
    return ffmpeg(binary, "-i", str(image), "-f", "rawvideo", "-pix_fmt", "rgb24", "-")


def libass(binary: str, script: Path, times: tuple[int, ...], size: tuple[int, int]) -> list[bytes]:
    """The frames libass draws of ``script`` at each time (ms), on black, RGB."""
    # each frame at its time + 0.5 ms (time base 1/2000): the filter truncates to whole ms
    at = "0"
    for n, ms in reversed(list(enumerate(times))):
        at = f"if(eq(N,{n}),{2 * ms + 1},{at})"
    width, height = size
    blank = f"color=c=black:s={width}x{height}:r=1:d={len(times)}"  # a frame a time
    graph = f"settb=1/2000,setpts='{at}',ass='{script}'"
    frames = ffmpeg(binary, "-f", "lavfi", "-i", blank, "-vf", graph, "-fps_mode",
                    "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-")  # fmt: skip
    one = width * height * 3
    if len(frames) != one * len(times):  # a frame lost would shift every later one
        raise SystemExit(f"{len(frames) // one} frames drawn of {len(times)}")
    return [frames[k * one : (k + 1) * one] for k in range(len(times))]


def _seek(page: Page, ms: int) -> None:
    """The video at ``ms``, its cues drawn (two frames after the seek)."""
    page.evaluate(
        """t => new Promise(done => {
            const v = document.querySelector("video");
            const drawn = () => requestAnimationFrame(() => requestAnimationFrame(done));
            v.addEventListener("seeked", drawn, {once: true});
            v.currentTime = t;
        })""",
        ms / 1000,
    )


def chromium(
    binary: str,
    work: Path,
    tracks: dict[str, tuple[str, str]],
    times: tuple[int, ...],
    size: tuple[int, int],
) -> tuple[str, dict[str, list[bytes]]]:
    """Chromium's version, and the frames it draws of each track at each time (ms), RGB.

    ``tracks``: a name each, its WebVTT and the page's CSS (``::cue`` rules, made the video's).
    The video is black, lasting 2 s or more past the last time.
    """
    width, height = size
    clip = work / "clip.webm"
    seconds = max(times) // 1000 + 3
    _ = ffmpeg(binary, "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=10:d={seconds}",
               "-c:v", "libvpx", "-y", str(clip))  # fmt: skip
    video = base64.b64encode(clip.read_bytes()).decode()
    shot = work / "shot.png"
    drawn: dict[str, list[bytes]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        for name, (vtt, css) in tracks.items():
            track = base64.b64encode(vtt.encode()).decode()
            page.set_content(
                f"<style>body {{ margin: 0; background: #000 }} "
                f"{css.replace('::cue', 'video::cue')}</style>"
                f'<video width="{width}" height="{height}" src="data:video/webm;base64,{video}">'
                f'<track default kind="subtitles" src="data:text/vtt;base64,{track}"></video>'
            )
            loaded = "document.querySelector('video').readyState >= 1"
            page.wait_for_function(f"{loaded} && document.querySelector('track').readyState == 2")
            drawn[name] = []
            for ms in times:
                _seek(page, ms)
                _ = page.screenshot(path=shot)
                drawn[name].append(rgb(binary, shot))
        version = browser.version
        browser.close()
    return version, drawn


# a pixel's channels (0-255): ink, at least INK in one; grey and white, channels within HUE of one
# another, CSS's gray (128) at least GREY, white at least WHITE; a colour, one at least LIT and
# the others under DARK -- anti-aliased edges fall between
INK, HUE, GREY, WHITE, LIT, DARK = 64, 16, 112, 192, 128, 96


def colour(r: int, g: int, b: int) -> str | None:
    """A pixel's colour: white, grey or one channel lit; none on an edge."""
    lo, hi = min(r, g, b), max(r, g, b)
    if hi - lo <= HUE:
        return "white" if lo >= WHITE else "grey" if lo >= GREY else None
    for name, (main, other) in {"red": (r, max(g, b)), "blue": (b, max(r, g)),
                                "green": (g, max(r, b))}.items():  # fmt: skip
        if main >= LIT and other < DARK:
            return name
    return None


def dominant(word: Counter[str]) -> str:
    """A word's colour: the one most of its classed pixels have."""
    return max((k for k in word if k != "ink"), key=word.__getitem__, default="unclassed")


GAP = 6  # columns without ink between words: more than between letters, less than a space


def words_in(frame: bytes, width: int) -> list[Counter[str]]:
    """Each word drawn in an RGB frame, left to right: its pixels' colours, counted."""
    height = len(frame) // (3 * width)
    columns: list[Counter[str]] = []
    for x in range(width):
        found: Counter[str] = Counter()
        for y in range(height):
            i = 3 * (y * width + x)
            if max(frame[i : i + 3]) >= INK:
                found["ink"] += 1
                name = colour(*frame[i : i + 3])
                if name:
                    found[name] += 1
        columns.append(found)
    words: list[Counter[str]] = []
    blank = GAP
    for found in columns:
        if not found:
            blank += 1
            continue
        if blank >= GAP:
            words.append(Counter())
        words[-1] += found
        blank = 0
    return words


def box(frame: bytes, width: int) -> tuple[int, int, int, int] | None:
    """The ink's bounding box in an RGB frame, (left, top, right, bottom) exclusive; none."""
    height = len(frame) // (3 * width)
    xs: list[int] = []
    ys: list[int] = []
    for y in range(height):
        row = frame[3 * y * width : 3 * (y + 1) * width]
        inked = [x for x in range(width) if max(row[3 * x : 3 * x + 3]) >= INK]
        if inked:
            xs += (inked[0], inked[-1])
            ys.append(y)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if ys else None
