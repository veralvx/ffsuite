"""Texts a message quotes (``errors.shown``): past its 60 characters too, what it cuts."""

from hypothesis import strategies as st

# beside any character: what prints nothing, a lone surrogate, the longest escape (``\U000e0080``)
_CHARACTERS = st.characters(codec="utf-8") | st.sampled_from("\x00\t\n\ufeff\ud800\U000e0080")
QUOTED = st.text(alphabet=_CHARACTERS, min_size=50, max_size=130)  # around 61, where it cuts
