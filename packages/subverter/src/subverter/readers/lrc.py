"""LRC: a line's time, its text."""

import re
from typing import Final

from subverter.readers.fields import exact, ms
from subverter.readers.utf8 import by_line
from subverter.transcript import Cue

__all__ = ["rows"]

_STAMP: Final = re.compile(r"\[([0-9]+):([0-9]+(?:[.][0-9]+)?)\](.*)")  # [mm:ss.xx]text


def rows(lines: list[str], name: str) -> list[Cue]:
    """Starts only: each line ends where the next starts (the last 3 s later).

    Each character joined across the lines it spans, in the file's order, then sorted
    (``utf8.by_line``: what is still not UTF-8, refused by its line).
    """
    stamped: list[tuple[int, int, str]] = []  # each timed line: its start, its index, its text
    for i, line in enumerate(lines):
        m = _STAMP.fullmatch(line)
        if m is None:
            continue
        minutes, seconds = exact(m[1]), exact(m[2])
        if minutes is None or seconds is None:  # past a double's range: no time, no line
            continue
        start = ms(minutes * 60 + seconds, 1000)
        if start is not None:
            stamped.append((start, i, m[3]))
    whole = by_line([(i + 1, text) for _, i, text in stamped], name)
    timed = list(zip((s for s, _, _ in stamped), whole, strict=True))
    timed.sort(key=lambda t: t[0])  # stable, as sort -s
    ends = [t[0] for t in timed[1:]] + ([timed[-1][0] + 3000] if timed else [])
    return [Cue(s, e, t) for (s, t), e in zip(timed, ends, strict=True)]
