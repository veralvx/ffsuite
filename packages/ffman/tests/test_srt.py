"""srt: a transcript as the SRT ffmpeg converts into a container's track -- each text written for
its codec, so the track holds it exactly (decisions.md, "Attached text")."""

import json
import re
from pathlib import Path
from typing import Final, cast

import pytest
import subverter
from hypothesis import given
from hypothesis import strategies as st
from subverter.transcript import Chunk

from ffman.cli import main
from ffman.subs.srt import srt
from tests.support.ingesting import ingested
from tests.support.media import tool
from tests.support.transcripts import ATTACHED, HOSTILE, encoded

WJ: Final = "\u2060"  # a word joiner
_TIMING: Final = "00:00:01,000 --> 00:00:02,000"


def cue(text: str) -> str:
    return f"1\n00:00:00,000 --> 00:00:01,000\n{text}\n\n"


@pytest.mark.parametrize(
    ("codec", "text", "written"),
    [
        ("srt", "plain & simple", "plain & simple"),
        # Matroska's SubRip, read by ffmpeg's decoder and libass: a { with a } after it libass's
        # \{; any other { and every backslash and < before a word joiner
        ("srt", "a {text} b", f"a \\{{{WJ}text}} b"),
        ("srt", "{a} {b", f"\\{{{WJ}a}} {{{WJ}b"),
        ("srt", "a{\\b c", f"a{{{WJ}\\{WJ}b c"),
        ("srt", "a \\N b \\h c\\x", f"a \\{WJ}N b \\{WJ}h c\\{WJ}x"),
        ("srt", "<b>x</b> 1 < 2 & &amp;", f"<{WJ}b>x<{WJ}/b> 1 <{WJ} 2 & &amp;"),
        ("srt", _TIMING, f"{WJ}{_TIMING}"),
        # mov_text, stored as ffmpeg's encoder takes it from ASS: each {, \ and < before a joiner
        ("mov_text", "a {text} b", f"a {{{WJ}text}} b"),
        ("mov_text", "a{\\b c \\N", f"a{{{WJ}\\{WJ}b c \\{WJ}N"),
        ("mov_text", "<b>x</b> & &amp;", f"<{WJ}b>x<{WJ}/b> & &amp;"),
        ("mov_text", "a --> b", f"{WJ}a --> b"),
        # WebVTT: the W3C's references for & < >, and each { and \ before a joiner
        ("webvtt", "a {text} b \\N", f"a {{{WJ}text}} b \\{WJ}N"),
        ("webvtt", "<b>x</b> 1 < 2 & &amp;", "&lt;b&gt;x&lt;/b&gt; 1 &lt; 2 &amp; &amp;amp;"),
        ("webvtt", "a --> b", "a --&gt; b"),
    ],
)
def test_each_text_is_written_for_its_codec(codec: str, text: str, written: str) -> None:
    assert srt((Chunk(0, 1000, text, ""),), None, codec=codec) == cue(written)


# what a text may hold that a SubRip reader reads: ASS's escapes and tags, MicroDVD's style, a
# timing line -- not a "<", which ffman's own reader takes as ffmpeg does not (`untagged`)
_RUNS: Final = ("{", "}", "\\", "N", "h", "{\\an8}", "{\\i1", "y:", "-->", "1", "x", " ")


@given(st.lists(st.sampled_from((*_RUNS, _TIMING)), min_size=1, max_size=10).map("".join))
def test_matroskas_text_reads_back_as_itself(text: str) -> None:
    """One cue, read as ffmpeg's demuxer, its decoder and libass read it (subverter's model)."""
    text = text.strip()
    if not text:
        return
    written = srt((Chunk(0, 1000, text, ""),), None, codec="srt").encode()
    (read,) = subverter.read("srt", written, "x.srt").cues
    assert subverter.drawn(read.text).text.replace(WJ, "") == text


# what a WebVTT text may hold that the W3C reads: references, tags, a timing line's arrow
_MARKUP: Final = ("&", "amp;", "lt;", "#60;", "<", ">", "b", "/", "-->", "{", "\\", "N", "x", " ")
_W3C_TAG: Final = re.compile(r"<[^>]*>?")  # the W3C's tokenizer: from a "<" to a ">" or the end


@given(st.lists(st.sampled_from(_MARKUP), min_size=1, max_size=10).map("".join))
def test_webms_text_reads_back_as_itself(text: str) -> None:
    """One cue's line, read as the W3C reads a cue's: no timing line, tags off, references decoded."""
    line = srt((Chunk(0, 1000, text, ""),), None, codec="webvtt").split("\n")[2]
    assert "-->" not in line  # "collect a WebVTT block": a line holding it ends the cue
    assert subverter.decoded(_W3C_TAG.sub("", line)).replace(WJ, "") == text


@pytest.fixture(scope="module")
def sounds(ffmpeg: str, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Ten seconds of sound in each family's container: Matroska, MP4, WebM."""
    folder = tmp_path_factory.mktemp("sounds")
    codecs = {"mka": "flac", "m4a": "aac", "webm": "libopus"}
    for ext, codec in codecs.items():
        _ = tool(ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=d=10", "-c:a", codec,
                 str(folder / f"s.{ext}"))  # fmt: skip
    return {ext: folder / f"s.{ext}" for ext in codecs}


def stored(ffmpeg: str, ffprobe: str, path: Path) -> list[str]:
    """The texts a container's track holds, as its format's readers take them, joiners off."""
    if path.suffix == ".m4a":  # mov_text: a sample's 16-bit length, its text, its style boxes
        probe = tool(ffprobe, "-v", "error", "-select_streams", "s", "-show_packets",
                     "-show_data", "-of", "json", str(path))  # fmt: skip
        packets = cast("list[dict[str, str]]", json.loads(probe)["packets"])
        samples = [_unhex(p["data"]) for p in packets]
        texts = [s[2 : 2 + int.from_bytes(s[:2], "big")].decode() for s in samples]
    else:  # SubRip read as ffmpeg and libass read it; WebVTT's references decoded (the W3C's)
        fmt = "srt" if path.suffix == ".mka" else "webvtt"
        data = tool(ffmpeg, "-v", "error", "-i", str(path), "-map", "0:s:0", "-c:s", "copy",
                    "-f", fmt, "-")  # fmt: skip
        cues = subverter.read(fmt.replace("webvtt", "vtt"), data.encode(), f"x.{fmt}").cues
        if fmt == "srt":
            texts = [subverter.drawn(c.text).text for c in cues]
        else:
            texts = [subverter.decoded(subverter.untagged(c.text)) for c in cues]
    return [t.replace(WJ, "") for t in texts if t]


def _unhex(dump: str) -> bytes:
    """ffprobe's -show_data hexdump, back to bytes (each line: an offset, 16 bytes in hex)."""
    return b"".join(bytes.fromhex(line[10:50].replace(" ", "")) for line in dump.split("\n"))


@pytest.mark.parametrize("ext", ["mka", "m4a", "webm"])
def test_each_containers_track_holds_the_text_exactly(
    ffmpeg: str, ffprobe: str, sounds: dict[str, Path], tmp_path: Path, ext: str
) -> None:
    """Attached by ffman, through ffmpeg's decoder and the container's encoder: the text."""
    vtt = tmp_path / "attached.vtt"
    _ = vtt.write_bytes(encoded(HOSTILE["attached.vtt"]))
    assert [c.text for c in ingested(str(vtt)).chunks] == list(ATTACHED)
    out = tmp_path / f"o.{ext}"
    assert main(["convert", "-i", str(sounds[ext]), "--add-subs", str(vtt), "-o", str(out)]) == 0
    assert stored(ffmpeg, ffprobe, out) == list(ATTACHED)
