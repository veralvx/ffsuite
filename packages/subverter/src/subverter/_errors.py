"""subverter's refusals (a subverter.Error, its message the reason) and notes: input shown safe."""

from collections.abc import Sequence
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


def counted(found: Sequence[tuple[int, str]], what: str) -> tuple[str, ...]:
    """The note of ``found``'s lines, each (line, text), if any: counted, the first by its line."""
    if not found:
        return ()
    line, text = found[0]
    return (f"{len(found)} {what}: the first, {shown(text)} on line {line}",)
