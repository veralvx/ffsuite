"""The one way ffmeta refuses: an ffmeta.Error, its message the reason; input shown safe."""

from typing import Final, Never

_SHOWN: Final = 60  # input quoted in a message: its characters, at most


class Error(Exception):
    """ffmeta's refusal: the input cannot be read, converted or written as it stands.

    The message says why.
    """


def refuse(message: str) -> Never:
    """Refuse with ``message``."""
    raise Error(message)


def shown(text: str) -> str:
    r"""Input quoted in a message: on one line, each character visible, 60 characters at most.

    What prints nothing as Python writes it: a line break ``\n``, a tab ``\t``, a NUL ``\x00``, a
    BOM ``\ufeff``, a no-break space ``\xa0``. Its first 61 characters alone read: each is one
    shown or more, so a text past 60 is cut, its first 57 shown theirs.
    """
    head = text[: _SHOWN + 1]
    one = "".join(char if char.isprintable() else repr(char)[1:-1] for char in head)
    return one if len(one) <= _SHOWN else one[: _SHOWN - 3] + "..."


def refuse_at(source: str, line: int, message: str) -> Never:
    """Refuse at ``source``'s ``line``: ``SOURCE:LINE: message``, lines from 1.

    The GNU Coding Standards' form for a program reading a file (4.4, "Formatting Error
    Messages").
    """
    if line < 1:
        msg = f"lines count from 1, not {line}"
        raise ValueError(msg)
    refuse(f"{source}:{line}: {message}")
