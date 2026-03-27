"""
List detection rule.

Strategy:
  - Bullet lists: text starts with common bullet chars (•, -, *, –, ▪, ◦)
    OR any single Unicode symbol/arrow/dingbat character followed by whitespace.
  - Ordered lists: text starts with digit(s) + period/paren (1. or 1))
  - Indentation tracked via bbox x0 for nested lists (future)
"""
import re
import unicodedata
from pdx.converter.extractor import Block
from pdx.converter.rules.base import Rule

# Explicit common ASCII/near-ASCII bullets
_BULLET_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219\u00B7\u2027\-\*\u2013\u25AA\u25AB]\s+")
_ORDERED_RE = re.compile(r"^\d+[\.\)]\s+")


def _is_symbol_bullet(text: str) -> bool:
    """
    Return True if the line starts with a single non-alphanumeric symbol
    (Unicode category So, Sm, Po, Ps, Pe, or any Emoji/arrow block)
    followed by whitespace. Catches ▶, ►, →, ✓, ✦, ◆, etc.
    """
    if len(text) < 2:
        return False
    ch = text[0]
    # Must be followed by whitespace
    if not text[1].isspace():
        return False
    # Skip plain ASCII punctuation that isn't a bullet (quotes, commas, etc.)
    if ch in '"\'`,;:.!?()[]{}':
        return False
    cat = unicodedata.category(ch)
    # So=Symbol other, Sm=Symbol math, Po=Punct other, Sk=Symbol modifier
    # Also catch anything outside Basic Latin that precedes a space
    return cat.startswith("S") or (cat == "Po" and ord(ch) > 127)


class ListRule(Rule):
    """
    Configurable list detection.

    normalize_bullets: if True, all bullet chars are converted to `-`.
                       Set False to preserve the original character.
    """

    def __init__(self, normalize_bullets: bool = True):
        self.normalize_bullets = normalize_bullets

    def applies(self, block: Block, context: dict) -> bool:
        text = block.text
        return bool(_BULLET_RE.match(text) or _ORDERED_RE.match(text) or _is_symbol_bullet(text))

    def convert(self, block: Block, context: dict) -> str:
        text = block.text

        if _BULLET_RE.match(text) or _is_symbol_bullet(text):
            # Strip the leading bullet character + whitespace
            content = text[1:].lstrip()
            prefix = "- " if self.normalize_bullets else f"{text[0]} "
            return f"{prefix}{content}"

        if _ORDERED_RE.match(text):
            return text

        return text
