"""The one way subverter refuses: a subverter.Error, its message the reason; input shown safe."""

from typing import Final, Never

_SHOWN: Final = 60  # input quoted in a message: its characters, at most
_ESCAPED: Final = {"\r": "\\r", "\n": "\\n", "\t": "\\t"}


class Error(Exception):
    """subverter's refusal: the input cannot be read as it stands; the message says why."""


def refuse(message: str) -> Never:
    """Refuse with ``message``."""
    raise Error(message)


def shown(text: str) -> str:
    r"""Input quoted in a message: on one line, each character visible, 60 characters at most.

    A line break or tab as its escape; any other character that prints nothing (a NUL, a BOM, a
    no-break space) as Python writes it, ``\x00``, ``\ufeff``.
    """
    one = "".join(
        _ESCAPED.get(char, char if char.isprintable() else repr(char)[1:-1]) for char in text
    )
    return one if len(one) <= _SHOWN else one[: _SHOWN - 3] + "..."
