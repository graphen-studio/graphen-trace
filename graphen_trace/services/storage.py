"""Graphen Trace storage service placeholder."""


# pylint: disable=too-few-public-methods
class Storage:
    """Storage boundary for normalized local data."""

    def is_available(self) -> bool:
        """Returns whether persistent storage has been configured."""
        return False
