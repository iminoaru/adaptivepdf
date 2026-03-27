"""
Block-level filters — run before rules to remove noise blocks entirely.

A filter is a callable(Block) -> bool; True = is noise, drop it.
Filters are cheaper than rules: they short-circuit early and produce no output.
"""
import re
from pdx.converter.extractor import Block

# Standalone page number: 1–4 digits only
_PAGE_NUM_RE = re.compile(r"^\d{1,4}$")

# Roman numeral page numbers (front matter): i, ii, iii, ...
_ROMAN_RE = re.compile(r"^[ivxlcdm]{1,6}$", re.IGNORECASE)

# Tolerance in points for grouping blocks on the same horizontal band
_MARGIN_Y_TOLERANCE = 2


def _detect_margin_ys(blocks: list[Block]) -> set[float]:
    """
    Find y0 positions that are confirmed footer/header bands.

    A real margin band must satisfy ALL of:
    1. Contains a digit-only or roman numeral block (page number anchor)
    2. That y-position is in the physical margin zone:
       top 10% of page (header) OR bottom 15% of page (footer)
    3. Appears on a significant fraction of total pages (>=20%, min 3)

    This rejects TOC page numbers, which live in the content zone (middle of page)
    and only appear on a handful of pages.

    pdf_block_id encodes page_num as: page_num = pdf_block_id // 10000
    """
    from collections import defaultdict

    # Estimate page dimensions from block bboxes
    page_heights: dict[int, float] = {}
    total_pages = 0
    for b in blocks:
        if not hasattr(b, 'pdf_block_id') or b.pdf_block_id < 0:
            continue
        page_num = b.pdf_block_id // 10000
        # Track max y (bottom of block) as page height proxy
        bottom = b.bbox[3]
        if page_num not in page_heights or bottom > page_heights[page_num]:
            page_heights[page_num] = bottom
        total_pages = max(total_pages, page_num + 1)

    # Use median page height across all pages
    if page_heights:
        sorted_heights = sorted(page_heights.values())
        page_height = sorted_heights[len(sorted_heights) // 2]
    else:
        page_height = 792.0  # US letter fallback

    header_zone_max = page_height * 0.10
    footer_zone_min = page_height * 0.85

    # Map y-position → set of page numbers that have a digit-only block there
    y_to_pages: dict[int, set[int]] = defaultdict(set)

    for b in blocks:
        if not hasattr(b, 'pdf_block_id') or b.pdf_block_id < 0:
            continue
        text = b.text.strip()
        if _PAGE_NUM_RE.match(text) or (_ROMAN_RE.match(text) and len(text) <= 5):
            y = round(b.bbox[1])
            # Only consider blocks physically in the margin zone
            if y <= header_zone_max or y >= footer_zone_min:
                page_num = b.pdf_block_id // 10000
                y_to_pages[y].add(page_num)

    # Require the band to appear on ≥20% of pages (at least 3)
    min_pages = max(3, int(total_pages * 0.20))
    return {y for y, pages in y_to_pages.items() if len(pages) >= min_pages}


def build_margin_filter(blocks: list[Block]):
    """
    Returns a filter function that drops blocks in detected margin bands.
    Call once per document, then pass the returned function to apply_filters.
    """
    margin_ys = _detect_margin_ys(blocks)
    if not margin_ys:
        return None  # no footers detected — no-op

    def _in_margin(block: Block) -> bool:
        y = round(block.bbox[1])
        return any(abs(y - my) <= _MARGIN_Y_TOLERANCE for my in margin_ys)

    return _in_margin


def apply_filters(blocks: list[Block], filters=None) -> list[Block]:
    """
    Run a list of filter functions over blocks, dropping any that match.

    If filters is None, the margin filter is auto-detected from the blocks.
    Pass filters=[] to disable all filtering.
    """
    if filters is None:
        margin_filter = build_margin_filter(blocks)
        filters = [margin_filter] if margin_filter else []
    return [b for b in blocks if not any(f(b) for f in filters)]
