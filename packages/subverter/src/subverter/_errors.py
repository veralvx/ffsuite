"""The one way subverter refuses: a subverter.Error, its message the reason; input shown safe."""

from typing import Final, Never

_SHOWN: Final = 60  # input quoted in a message: its characters, at most


class Error(Exception):
    """subverter's refusal: the input cannot be read as it stands; the message says why."""


def refuse(message: str) -> Never:
    """Refuse with ``message``."""
    raise Error(message)


def shown(text: str) -> str:
    r"""Input quoted in a message: on one line, each character visible, 60 characters at most.

    What prints nothing as Python writes it: a line break ``\n``, a tab ``\t``, a NUL ``\x00``, a
    BOM ``\ufeff``, a no-break space ``\xa0``.
    """
    one = "".join(char if char.isprintable() else repr(char)[1:-1] for char in text)
    return one if len(one) <= _SHOWN else one[: _SHOWN - 3] + "..."
