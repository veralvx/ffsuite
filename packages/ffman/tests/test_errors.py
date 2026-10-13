import pytest

from ffman.errors import FfmanError, escaped, refuse, refuse_at, shown


def test_refuse_says_the_message() -> None:
    with pytest.raises(FfmanError, match=r"^convert: --input is required$"):
        refuse("convert: --input is required")


def test_refuse_at_names_the_file_and_line_as_gnu_does() -> None:
    with pytest.raises(FfmanError, match=r"^album\.cue:12: a TRACK number outside 01-99: 100$"):
        refuse_at("album.cue", 12, "a TRACK number outside 01-99: 100")
    with pytest.raises(FfmanError, match=r"^tags\.txt:1: no '=' in a comment$"):
        refuse_at("tags.txt", 1, "no '=' in a comment")


def test_refuse_at_counts_lines_from_one() -> None:
    with pytest.raises(ValueError, match=r"^lines count from 1, not 0$"):
        refuse_at("a.cue", 0, "x")


def test_shown_puts_input_on_one_line_of_60_characters_at_most() -> None:
    assert shown("short") == "short"
    assert shown("a\r\nb") == "a\\r\\nb"  # one line: the breaks, written
    assert shown("x" * 60) == "x" * 60
    assert shown("x" * 61) == "x" * 57 + "..."
    assert len(shown("y" * 1000)) == 60
    # what prints nothing, visible
    assert shown("\ufeffa\tb\x00c\xa0d") == "\\ufeffa\\tb\\x00c\\xa0d"


@pytest.mark.parametrize(
    ("message", "written"),
    [
        ("a\x1b]0;title\x07b", "a\\x1b]0;title\\x07b"),  # an OSC: no command reaches the terminal
        ("\x1b[31mred", "\\x1b[31mred"),  # an SGR: no colour
        ("a\tb\nc\rd", "a\\tb\\nc\\rd"),  # C0's line controls too: one line
        ("\x00\x7f\x85\x9b", "\\x00\\x7f\\x85\\x9b"),  # NUL, DEL, C1's NEL and CSI
        ("C:\\new caf\u00e9 \u00a0\u200f", "C:\\new caf\u00e9 \u00a0\u200f"),  # no control: as is
    ],
    ids=["osc", "sgr", "line-controls", "nul-del-c1", "kept"],
)
def test_escaped_writes_each_control_character_as_python_does(message: str, written: str) -> None:
    assert escaped(message) == written
