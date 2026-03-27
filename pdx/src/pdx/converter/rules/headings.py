"""
Heading detection rule.

Strategy (deterministic, no ML):
  - Font size ratio vs body: >=1.8x → H1, >=1.4x → H2, >=1.15x → H3
  - ALL_CAPS bold lines → H2 (section separators, regardless of font size)
  - Multi-line blocks and bullet lines are never headings
"""
import re
from pdx.converter.extractor import Block
from pdx.converter.rules.base import Rule

# Lines that look like dates are never headings even if bold
_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}"
    r"|\d{4}\s*[–\-]\s*(present|\d{4})"
    r"|\b(present|current)\b",
    re.IGNORECASE,
)

# Lines starting with bullet/dash chars are list items, not headings
_BULLET_START_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219\u00B7\u2027\u2013\u2014\-\*]\s")


def _is_all_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 3 and all(c.isupper() for c in letters)


class HeadingRule(Rule):
    """
    Configurable heading detection based on font-size ratios and text signals.

    Thresholds are constructor arguments so callers can tune per document type.
    A research paper with 14pt body and 18pt titles needs different ratios
    than a resume with 10pt body and 21pt name.
    """

    def __init__(
        self,
        h1_ratio: float = 1.8,
        h2_ratio: float = 1.4,
        h3_ratio: float = 1.15,
        max_chars: int = 120,
        all_caps_as_heading: bool = True,
        exclude_dates: bool = True,
    ):
        self.h1_ratio = h1_ratio
        self.h2_ratio = h2_ratio
        self.h3_ratio = h3_ratio
        self.max_chars = max_chars
        self.all_caps_as_heading = all_caps_as_heading
        self.exclude_dates = exclude_dates

    def applies(self, block: Block, context: dict) -> bool:
        text = block.text
        if not text or len(text) > self.max_chars:
            return False
        if _BULLET_START_RE.match(text):
            return False  # let ListRule handle it
        if self.exclude_dates and _DATE_RE.search(text):
            return False

        body = context.get("body_font_size", 12.0)
        ratio = block.dominant_font_size / body if body else 1.0

        if ratio >= self.h3_ratio:
            return True
        if self.all_caps_as_heading and block.is_bold and _is_all_caps(text):
            return True

        return False

    def convert(self, block: Block, context: dict) -> str:
        body = context.get("body_font_size", 12.0)
        ratio = block.dominant_font_size / body if body else 1.0

        if ratio >= self.h1_ratio:
            level = 1
        elif ratio >= self.h2_ratio:
            level = 2
        elif ratio >= self.h3_ratio:
            level = 3
        elif _is_all_caps(block.text):
            level = 2
        else:
            level = 3

        return f"{'#' * level} {block.text}"
