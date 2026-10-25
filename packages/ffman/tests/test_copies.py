"""ffman's helpers its libraries copy -- each its own, ffman importing none of theirs: held equal.

A message ffmeta words is one ffman prints (``ffman: error: ...``); a time either rounds is one
the other reads back. The copies are deliberate (a library imports nothing of ffman); a copy
that drifted would change a message or a time unseen, so each is held to ffman's on any input.
"""

from collections.abc import Callable, Iterator
from fractions import Fraction
from typing import SupportsIndex, final, override

import ffmeta._errors
import ffmeta._values
import pytest
import subverter._errors
import subverter._values
from hypothesis import example, given
from hypothesis import strategies as st

from ffman import errors, values
from tests.support.quoted import QUOTED


@given(QUOTED)
@example("x" * 61)  # its first 60 printable: cut only past them
@example("x" * 60 + "\n")
def test_each_shown_is_ffmans(text: str) -> None:
    expected = errors.shown(text)
    assert ffmeta._errors.shown(text) == expected
    assert subverter._errors.shown(text) == expected


@final
class _Unread(str):
    """A text read in its first 61 characters alone: iterated, made a ``str`` or sliced past them, it fails."""

    __slots__: tuple[str, ...] = ()

    @override
    def __iter__(self) -> Iterator[str]:  # ty: ignore[invalid-method-override] -- str's LiteralString
        message = "iterated"
        raise AssertionError(message)

    @override
    def __getitem__(self, key: SupportsIndex | slice) -> str:  # ty: ignore[invalid-method-override]
        span = range(len(self))[key] if isinstance(key, slice) else range(1)
        if len(span) > 61:  # shown's 60, and one to tell a text past them
            message = f"{len(span)} characters read"
            raise AssertionError(message)
        return super().__getitem__(key)

    @override
    def __str__(self) -> str:
        message = "copied whole"
        raise AssertionError(message)


@pytest.mark.parametrize(
    "shown",
    [errors.shown, ffmeta._errors.shown, subverter._errors.shown],
    ids=["ffman", "ffmeta", "subverter"],
)
def test_each_shown_reads_no_more_than_it_quotes(shown: Callable[[str], str]) -> None:
    # its first 61 characters: each one or more shown, so past 60 the quote is cut, its 57 theirs
    assert shown(_Unread("\x00" * 10**6)) == "\\x00" * 14 + "\\..."
    assert shown(_Unread("ab")) == "ab"


@given(st.text(max_size=20), st.integers(min_value=-3, max_value=10**6), st.text(max_size=40))
def test_ffmetas_refuse_at_is_ffmans(source: str, line: int, message: str) -> None:
    if line < 1:  # a caller's mistake, not a refusal: each says so alike
        with pytest.raises(ValueError, match=f"^lines count from 1, not {line}$"):
            ffmeta._errors.refuse_at(source, line, message)
        with pytest.raises(ValueError, match=f"^lines count from 1, not {line}$"):
            errors.refuse_at(source, line, message)
        return
    with pytest.raises(ffmeta.Error) as theirs:
        ffmeta._errors.refuse_at(source, line, message)
    with pytest.raises(errors.FfmanError) as ours:
        errors.refuse_at(source, line, message)
    assert str(theirs.value) == str(ours.value)


# exact halves are where rounding half up is decided, and arbitrary fractions are seldom one
HALVES = st.integers(min_value=-(10**6), max_value=10**6).map(lambda k: Fraction(2 * k + 1, 2))


@given(st.one_of(st.fractions(), HALVES))
@example(Fraction(1, 2))
@example(Fraction(-1, 2))
@example(Fraction(5, 2))
@example(Fraction(-3, 2))
def test_each_round_half_up_is_ffmans(value: Fraction) -> None:
    expected = values.round_half_up(value)
    assert ffmeta._values.round_half_up(value) == expected
    assert subverter._values.round_half_up(value) == expected
