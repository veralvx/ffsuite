"""What a note quotes of a text: enough to know it by, never the whole of a huge one."""

from typing import Final

__all__ = ["excerpt"]

# a cue at its longest by Netflix's Timed Text Style Guide (English (USA), II.3 and II.13): two
# lines of 42 characters, and the space joining them
_SHOWN: Final = 2 * 42 + 1


def excerpt(text: str) -> str:
    """``text`` as a note quotes it: whole up to 85 characters (``_SHOWN``), else its first 85.

    The rest counted: ``... (N more characters)``. A note names a text so its reader knows it
    (its line too, where it has one): a line of 400,000 characters, quoted whole, would be that
    much on stderr.
    """
    if len(text) <= _SHOWN:
        return text
    return f"{text[:_SHOWN]}... ({len(text) - _SHOWN} more characters)"
