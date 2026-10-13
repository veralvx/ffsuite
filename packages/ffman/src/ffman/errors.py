"""The one way ffman refuses or fails; input shown safe."""

import re
from typing import Final, Never

import ffmeta
import subverter

PROG: Final = "ffman"  # the program's name, in its messages
_SHOWN: Final = 60  # input quoted in a message: its characters, at most
# Unicode's Cc: C0, DEL, C1 -- a terminal's commands (ECMA-48: ESC, CSI), not text; and a lone
# surrogate, a name's byte not UTF-8 (os.fsdecode's), which stdout writes back raw: 0x9B is CSI
_UNSAFE: Final = re.compile(r"[\x00-\x1f\x7f-\x9f\ud800-\udfff]")


class FfmanError(Exception):
    """A refusal or a failure: reported as ``ffman: error: MESSAGE``, exit status 1."""


# every refusal ffman words as its own: its own, and its libraries' (6.7.5: each refuses with its
# own error; ffman's words for them unchanged)
REFUSALS: Final = (FfmanError, ffmeta.Error, subverter.Error)


def refuse(message: str) -> Never:
    """Refuse with ``message`` (the spec's words)."""
    raise FfmanError(message)


def shown(text: str) -> str:
    r"""Input quoted in a message: on one line, each character visible, 60 characters at most.

    What prints nothing as Python writes it: a line break ``\n``, a tab ``\t``, a NUL ``\x00``, a
    BOM ``\ufeff``, a no-break space ``\xa0``.
    """
    one = "".join(char if char.isprintable() else repr(char)[1:-1] for char in text)
    return one if len(one) <= _SHOWN else one[: _SHOWN - 3] + "..."


def escaped(message: str) -> str:
    r"""``message`` as ffman writes it to a terminal: each control character as Python writes it.

    A transcript's line or a file's name, in a note, a refusal or a path printed, commands no
    terminal: an ESC is ``\x1b``, a tab ``\t``, a name's byte not UTF-8 ``\udc9b`` -- the message
    one line. ffmpeg's log writes ``?`` for most C0 controls (``libavutil/log.c``,
    ``sanitize``); ``shown`` cuts what it quotes, this nothing.
    """
    return _UNSAFE.sub(lambda found: repr(found[0])[1:-1], message)


def refuse_at(source: str, line: int, message: str) -> Never:
    """Refuse at ``source``'s ``line``: ``SOURCE:LINE: message``, lines from 1.

    The GNU Coding Standards' form for a program reading a file (4.4, "Formatting Error
    Messages"), after ffman's own ``ffman: error:``.
    """
    if line < 1:
        msg = f"lines count from 1, not {line}"
        raise ValueError(msg)
    refuse(f"{source}:{line}: {message}")
