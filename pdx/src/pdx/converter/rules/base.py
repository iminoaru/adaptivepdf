"""Base interface for all converter rules."""
from abc import ABC, abstractmethod
from pdx.converter.extractor import Block


class Rule(ABC):
    """
    A Rule inspects a Block and either claims it (returning Markdown)
    or passes (returning None) so the next rule can try.
    """

    @abstractmethod
    def applies(self, block: Block, context: dict) -> bool:
        """Return True if this rule should handle the block."""
        ...

    @abstractmethod
    def convert(self, block: Block, context: dict) -> str:
        """Convert block to a Markdown string."""
        ...
