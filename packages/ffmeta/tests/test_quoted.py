"""ffmeta's messages quote a name or a value its format has not checked by ``_errors.shown``: on
one line, each character visible, 60 characters at most -- here, a name of a control character
and 100 more, in every note and refusal that quotes one."""

from collections.abc import Callable
from fractions import Fraction
from typing import Final

import ffmeta
import pytest
from ffmeta import cue, ffmetadata, vorbis
from ffmeta.chapters import ChapterText, edit_chapters, parse_chapters
from ffmeta.convert import convert
from ffmeta.edit import apply, parse
from ffmeta.model import Chapter, Disc, File, Index, Metadata, Tag, Track

_NAME: Final = "k\x1b" + "x" * 100  # a control character, past 60 characters
_QUOTED: Final = "k\\x1b" + "x" * 52 + "..."  # its first 57 characters, written, then the mark
_ONE: Final = Track(1, "AUDIO", (Index(1, 0, 0),))


def _disc(*tracks: Track, catalog: str | None = None, file: str = "a.flac") -> Metadata:
    return Metadata(disc=Disc((File(file, "WAVE"),), tracks or (_ONE,), catalog=catalog))


def _edited(meta: Metadata, given: ChapterText) -> tuple[str, ...]:
    """A cue's tracks edited: the notes."""
    return edit_chapters(meta, parse_chapters(given), "cue", "x")[1]


_REM: Final = f'REM {_NAME} v\nFILE "a" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
_NEW: Final = f"1:00.01..2:00={_NAME}"  # between frames, its end given, its title long
_NEW_QUOTED: Final = "1:00.01..2:00=k\\x1b" + "x" * 38 + "..."


@pytest.mark.parametrize(
    ("notes", "quoted"),
    [
        pytest.param(
            lambda: vorbis.write(Metadata((Tag(_NAME, "v"),))).notes,
            f"a tag '{_QUOTED}'",
            id="vorbis-tag",
        ),
        pytest.param(
            lambda: (
                vorbis.write(
                    Metadata(chapters=(Chapter(Fraction(0), None, (Tag(_NAME, "v"),)),))
                ).notes
            ),
            f"tag '{_QUOTED}'",
            id="vorbis-chapters-tag",
        ),
        pytest.param(
            lambda: (
                convert(Metadata((Tag(_NAME, "a"), Tag(_NAME, "b"))), "vorbis", "ffmetadata").notes
            ),
            f"a tag '{_QUOTED}': 2 values joined",
            id="joined",
        ),
        pytest.param(
            lambda: ffmetadata.write(Metadata((Tag(_NAME + "\0", "v"),))).notes,
            f"'{_QUOTED}': a NUL",
            id="ffmetadata-tag",
        ),
        pytest.param(
            lambda: convert(cue.read(_REM, "a.cue"), "cue", "vorbis").notes,
            "the disc's REM K\\x1b" + "X" * 48 + "...: none maps it",
            id="rem-command",
        ),
        pytest.param(
            lambda: convert(Metadata((Tag(_NAME, "v"),)), "ffmetadata", "cue", media="m").notes,
            f"the tag '{_QUOTED}': no cue field",
            id="cue-field",
        ),
        pytest.param(
            lambda: cue.write(_disc(catalog=_NAME)).notes,
            f"the CATALOG '{_QUOTED}'",
            id="catalog",
        ),
        pytest.param(
            lambda: cue.write(_disc(Track(1, "AUDIO", (Index(1, 0, 0),), flags=(_NAME,)))).notes,
            f"FLAGS '{_QUOTED}'",
            id="flags",
        ),
        pytest.param(
            lambda: cue.write(_disc(Track(1, "AUDIO", (Index(1, 0, 0),), isrc=_NAME))).notes,
            f"ISRC '{_QUOTED}'",
            id="isrc",
        ),
        pytest.param(
            lambda: cue.write(_disc(file=_NAME + '"')).notes,
            f"the FILE '{_QUOTED}'",
            id="file",
        ),
        pytest.param(
            lambda: _edited(Metadata(), ChapterText(new=(_NEW,))),
            f"--chapter {_NEW_QUOTED}: between frames",
            id="new-chapter",
        ),
        pytest.param(
            lambda: _edited(Metadata(), ChapterText(new=(_NEW,)))[-1:],
            f"--chapter {_NEW_QUOTED}'s end",
            id="new-chapters-end",
        ),
    ],
)
def test_a_note_quotes_a_name_or_a_value_shown(
    notes: Callable[[], tuple[str, ...]], quoted: str
) -> None:
    said = notes()
    assert any(quoted in note for note in said), said
    assert not any("\x1b" in note for note in said)


@pytest.mark.parametrize(
    ("refused", "quoted"),
    [
        pytest.param(
            lambda: ffmetadata.read(f";FFMETADATA1\n{_NAME}=1\n{_NAME}=2\n", "a.ffmeta"),
            f"the key '{_QUOTED}' again",
            id="ffmetadata-key",
        ),
        pytest.param(
            lambda: parse([f"{_NAME}=a", f"{_NAME}=b"], [], [], clear=False),
            f"--set {_QUOTED} twice",
            id="set-twice",
        ),
        pytest.param(
            lambda: parse([f"{_NAME}=a"], [], [_NAME], clear=False),
            f"--set {_QUOTED} and --unset {_QUOTED} contradict",
            id="contradict",
        ),
        pytest.param(
            lambda: apply(_disc(), parse([f"{_NAME}=x"], [], [], clear=False), "cue"),
            f"--set {_QUOTED}: a cue sheet holds no {_QUOTED}",
            id="cue-holds-no",
        ),
        pytest.param(
            lambda: parse_chapters(ChapterText(sets=(f"2:{_NAME}=a", f"2:{_NAME}=b"))),
            f"chapter 2's {_QUOTED} set twice",
            id="chapter-set-twice",
        ),
        pytest.param(
            lambda: _edited(_disc(), ChapterText(sets=(f"1:{_NAME}=x",))),
            f"--chapter-set 1:{_QUOTED}: a cue's track holds no {_QUOTED}",
            id="track-holds-no",
        ),
    ],
)
def test_a_refusal_quotes_a_name_shown(refused: Callable[[], object], quoted: str) -> None:
    with pytest.raises(ffmeta.Error) as error:
        _ = refused()
    assert quoted in str(error.value)
    assert "\x1b" not in str(error.value)
