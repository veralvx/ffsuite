"""A standard output that is a terminal, as a test sees it: what ffman writes, kept."""

import io
from typing import override


class Terminal(io.StringIO):
    """A ``StringIO`` whose ``isatty`` says yes."""

    @override
    def isatty(self) -> bool:
        """A terminal."""
        return True
