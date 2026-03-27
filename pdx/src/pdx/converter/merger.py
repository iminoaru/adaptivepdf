"""
Post-extraction passes that improve structural quality before rules run.

1. merge_paragraph_lines  — rejoin lines from the same PDF text block into
                            paragraphs, handling soft hyphens at line breaks.

2. detect_tables          — detect grid-arranged text blocks and convert them
                            to TableBlocks with Markdown table syntax.
"""
import re
from collections import defaultdict
from pdx.converter.extractor import Block, ImageBlock, TableBlock, Span

AnyBlock = Block | ImageBlock | TableBlock

# Bullet/list starters — never merge these with preceding text
_BULLET_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219\u00B7\u2027\u2013\u2014\-\*]\s")
_ORDERED_RE = re.compile(r"^\d+[\.\)]\s")

# Max font size difference (pt) to still consider lines as same paragraph
_FONT_TOLERANCE = 0.6

# Soft hyphen / hard hyphen at line end — signals word break, join without space
_HYPHEN_BREAK_RE = re.compile(r"[\u00AD\-‐]$")


def _is_joinable(prev: Block, curr: Block) -> bool:
    """True if curr should be appended to prev as a paragraph continuation."""
    if prev.pdf_block_id != curr.pdf_block_id:
        return False
    if prev.pdf_block_id == -1:
        return False
    if not prev.spans or not curr.spans:
        return False
    if abs(prev.dominant_font_size - curr.dominant_font_size) > _FONT_TOLERANCE:
        return False
    # Don't merge list items
    if _BULLET_RE.match(curr.text) or _ORDERED_RE.match(curr.text):
        return False
    return True


# Characters that signal a sentence/section end — don't join after these
_SENTENCE_END_RE = re.compile(r"[.!?:;]\s*$")

# Lines starting with these patterns are standalone — never join to previous
_STANDALONE_RE = re.compile(
    r"^("
    r"[A-Z][A-Z\s]{4,}"          # ALL CAPS heading (5+ chars)
    r"|[A-Z][a-z]+\s+[A-Z]"      # Title Case start (e.g. "Lumira Labs")
    r")"
)

# Max vertical gap (in multiples of font size) to still consider joining
_MAX_LINE_GAP_RATIO = 1.8


def _is_cross_block_joinable(prev: Block, curr: Block) -> bool:
    """True if curr should be joined to prev across different PDF block IDs.

    Heuristic: if the previous line appears to end mid-sentence and the current
    line continues naturally (starts lowercase or continues punctuation), join them.
    """
    if not prev.spans or not curr.spans:
        return False
    # Must be similar font sizes
    if abs(prev.dominant_font_size - curr.dominant_font_size) > _FONT_TOLERANCE:
        return False
    # Don't merge list items or headings
    if _BULLET_RE.match(curr.text) or _ORDERED_RE.match(curr.text):
        return False
    # Don't merge standalone lines (all-caps headings, title case)
    if _STANDALONE_RE.match(curr.text):
        return False
    # Don't merge if prev ended with sentence-ending punctuation
    if _SENTENCE_END_RE.search(prev.text):
        return False
    # Only merge if curr starts lowercase (continuation) or with common
    # mid-sentence starters (and, or, the, with, etc.)
    first_char = curr.text.lstrip()[0] if curr.text.strip() else ""
    if not first_char:
        return False
    if not (first_char.islower() or first_char in ",(\"'"):
        return False
    # Check vertical proximity — gap should be roughly one line height
    prev_bottom = prev.bbox[3]
    curr_top = curr.bbox[1]
    gap = curr_top - prev_bottom
    line_height = prev.dominant_font_size * _MAX_LINE_GAP_RATIO
    if gap > line_height or gap < -2:  # negative = overlap (different column)
        return False
    # Same left margin (within tolerance) — rules out multi-column layouts
    if abs(prev.bbox[0] - curr.bbox[0]) > 20:
        return False
    return True


def merge_paragraph_lines(blocks: list[AnyBlock]) -> list[AnyBlock]:
    """
    Merge consecutive Block lines that belong to the same PDF text block.

    Handles:
    - Normal continuation: join with a single space
    - Hyphen line breaks: remove the hyphen and join directly (e.g. "im-\nmutable" → "immutable")
    """
    merged: list[AnyBlock] = []

    for block in blocks:
        if (
            merged
            and isinstance(block, Block)
            and isinstance(merged[-1], Block)
            and (
                _is_joinable(merged[-1], block)
                or _is_cross_block_joinable(merged[-1], block)
            )
        ):
            prev = merged[-1]
            prev_text = prev.text

            if _HYPHEN_BREAK_RE.search(prev_text):
                # Strip the trailing hyphen from the last span, join directly
                last_span = prev.spans[-1]
                last_span.text = _HYPHEN_BREAK_RE.sub("", last_span.text)
            else:
                # Normal continuation — insert a space between lines
                prev.spans.append(Span(
                    text=" ",
                    font_size=prev.spans[-1].font_size,
                    is_bold=False,
                    is_italic=False,
                    is_monospace=False,
                ))

            prev.spans.extend(block.spans)
            # Expand bbox to cover both lines
            bx0, by0, bx1, by1 = prev.bbox
            cx0, cy0, cx1, cy1 = block.bbox
            prev.bbox = (min(bx0, cx0), min(by0, cy0), max(bx1, cx1), max(by1, cy1))
        else:
            merged.append(block)

    return merged


# ── Pre-split: single blocks whose spans are table columns ───────────────────

# If consecutive spans within one block have a gap wider than this, split the
# block into separate column-blocks so the table detector can see them.
_COLUMN_GAP_PT = 18.0


def split_tabular_lines(blocks: list[AnyBlock]) -> list[AnyBlock]:
    """
    Split single-line blocks that contain multiple column values separated by
    large horizontal gaps (e.g. "SUN  MOON  MARS  MERC" on one PDF line).

    PyMuPDF merges all spans on a line into one Block regardless of x-gaps.
    This pass re-splits them so detect_tables can see multiple blocks per row.

    Split blocks get pdf_block_id = -1 so the paragraph merger never joins them.
    """
    result: list[AnyBlock] = []
    for block in blocks:
        if not isinstance(block, Block) or len(block.spans) < 2:
            result.append(block)
            continue

        # Find split points: gap between end of span[i] and start of span[i+1]
        # We approximate span end as span[i+1].x0 - gap, using x0 of next span.
        groups: list[list[Span]] = [[block.spans[0]]]
        for i in range(1, len(block.spans)):
            prev_x0 = block.spans[i - 1].x0
            curr_x0 = block.spans[i].x0
            # Estimate previous span width from its text length and font size
            # (rough: ~0.6 × font_size per character is a reasonable EM width)
            approx_prev_width = len(block.spans[i - 1].text) * block.spans[i - 1].font_size * 0.55
            gap = curr_x0 - (prev_x0 + approx_prev_width)
            if gap > _COLUMN_GAP_PT:
                groups.append([])
            groups[-1].append(block.spans[i])

        if len(groups) < 3:
            # Only 1 gap = wide word space, not a column separator. Pass through.
            result.append(block)
            continue

        # Emit one Block per group
        bx0, by0, bx1, by1 = block.bbox
        for group in groups:
            if not group:
                continue
            gx0 = group[0].x0
            gx1 = group[-1].x0 + len(group[-1].text) * group[-1].font_size * 0.55
            new_block = Block(
                spans=group,
                bbox=(gx0, by0, max(gx1, gx0 + 4), by1),
                pdf_block_id=-1,  # prevent paragraph merger from joining these
            )
            if new_block.text.strip():
                result.append(new_block)

    return result


# ── Spatial table detection ──────────────────────────────────────────────────

_MIN_COLS = 2
_MIN_ROWS = 2
_ROW_Y_TOLERANCE = 6       # pt — y-midpoints within this = same row
_COL_X_TOLERANCE = 15.0    # pt — x0s within this = same column
_MIN_COL_SPAN = 60         # pt — min horizontal spread to count as multi-column


def _bbox_y_mid(b: AnyBlock) -> float:
    return (b.bbox[1] + b.bbox[3]) / 2


def _group_into_rows(blocks: list[Block]) -> list[list[Block]]:
    """Group blocks by approximate y-midpoint into rows, sorted by x within each row."""
    if not blocks:
        return []
    sorted_blocks = sorted(blocks, key=_bbox_y_mid)
    rows: list[list[Block]] = [[sorted_blocks[0]]]
    row_y = _bbox_y_mid(sorted_blocks[0])
    for b in sorted_blocks[1:]:
        y = _bbox_y_mid(b)
        if abs(y - row_y) <= _ROW_Y_TOLERANCE:
            rows[-1].append(b)
        else:
            row_y = y
            rows.append([b])
    return [sorted(r, key=lambda b: b.bbox[0]) for r in rows]


def _cluster_xs(xs: list[float]) -> list[float]:
    """
    Cluster x-positions by proximity and return one center per column.
    Only x0s from rows that look like table rows (spread >= MIN_COL_SPAN) should
    be passed here so prose left-margins don't create phantom columns.
    """
    clusters: list[list[float]] = []
    for x in sorted(xs):
        if clusters and x - clusters[-1][-1] <= _COL_X_TOLERANCE:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [sum(c) / len(c) for c in clusters]


def _assign_col(x: float, col_centers: list[float]) -> int:
    """Return index of the nearest column center (within 2× tolerance), or -1."""
    best, best_d = -1, float("inf")
    for i, c in enumerate(col_centers):
        d = abs(x - c)
        if d <= _COL_X_TOLERANCE * 2 and d < best_d:
            best, best_d = i, d
    return best


def _row_is_multicolumn(row: list[Block], col_centers: list[float]) -> bool:
    """True if this row has blocks in 2+ distinct columns spanning MIN_COL_SPAN."""
    if len(row) < _MIN_COLS:
        return False
    xs = [b.bbox[0] for b in row]
    if max(xs) - min(xs) < _MIN_COL_SPAN:
        return False
    cols_used = {_assign_col(b.bbox[0], col_centers) for b in row}
    cols_used.discard(-1)
    return len(cols_used) >= _MIN_COLS


def _row_to_cells(row: list[Block], col_centers: list[float], n: int) -> dict[int, str]:
    """Assign blocks to columns, merging same-column blocks with a space."""
    cells: dict[int, str] = {}
    for b in row:
        col = _assign_col(b.bbox[0], col_centers)
        if col < 0:
            col = n - 1
        text = b.text.strip()
        cells[col] = (cells[col] + " " + text).strip() if col in cells else text
    return cells


def _merge_wrapped_rows(cell_rows: list[dict[int, str]]) -> list[dict[int, str]]:
    """
    Merge "continuation" rows into the previous row.

    A PDF table cell that wraps across multiple lines produces multiple
    spatial rows where the first column is empty and only middle/right
    columns have text. Detect this and join those cells into the row above.

    Heuristic: a row is a continuation if:
    - Its leftmost populated column index > 0 (first column empty), AND
    - It has fewer populated columns than the previous row
    """
    if not cell_rows:
        return []
    merged = [dict(cell_rows[0])]
    for cells in cell_rows[1:]:
        non_empty = {k for k, v in cells.items() if v}
        if not non_empty:
            continue
        prev = merged[-1]
        prev_non_empty = {k for k, v in prev.items() if v}
        is_continuation = (
            min(non_empty) > 0                          # first col empty
            and len(non_empty) <= len(prev_non_empty)   # not wider than prev
        )
        if is_continuation:
            for col, text in cells.items():
                if text:
                    prev[col] = (prev.get(col, "") + " " + text).strip()
        else:
            merged.append(dict(cells))
    return merged


def _build_table_markdown(table_rows: list[list[Block]], col_centers: list[float]) -> str:
    """
    Render table rows as a Markdown table with wrapped-cell merging.
    Columns are assigned by x0 proximity to col_centers.
    """
    n = len(col_centers)
    cell_rows = [_row_to_cells(r, col_centers, n) for r in table_rows]
    cell_rows = _merge_wrapped_rows(cell_rows)

    def render(cells: dict[int, str]) -> str:
        return "| " + " | ".join(cells.get(i, "") for i in range(n)) + " |"

    lines = [render(cell_rows[0])]
    lines.append("| " + " | ".join(["---"] * n) + " |")
    for cells in cell_rows[1:]:
        lines.append(render(cells))
    return "\n".join(lines)


def detect_tables(blocks: list[AnyBlock]) -> list[AnyBlock]:
    """
    Detect grid-arranged text blocks and replace them with TableBlocks.

    Algorithm:
    1. Collect windows of consecutive plain text blocks.
    2. Group into rows by y-midpoint.
    3. Derive column structure only from rows that already look multi-column
       (2+ blocks, spread >= MIN_COL_SPAN). This prevents prose from creating
       phantom columns.
    4. Re-evaluate each row against the derived column structure.
    5. Find contiguous runs of table rows (>= MIN_ROWS) and emit TableBlocks.
    6. Non-table blocks in the window pass through unchanged.
    """
    result: list[AnyBlock] = []
    i = 0

    while i < len(blocks):
        block = blocks[i]

        if not isinstance(block, Block) or not block.spans:
            result.append(block)
            i += 1
            continue

        # Collect a window of consecutive plain text blocks
        window: list[Block] = []
        j = i
        while j < len(blocks) and isinstance(blocks[j], Block) and blocks[j].spans:
            window.append(blocks[j])  # type: ignore
            j += 1

        if len(window) < _MIN_ROWS * _MIN_COLS:
            result.extend(window)
            i = j
            continue

        rows = _group_into_rows(window)

        # Step 1: derive column centers from rows that already look multi-column
        seed_x0s: list[float] = []
        for row in rows:
            if len(row) >= _MIN_COLS:
                xs = [b.bbox[0] for b in row]
                if max(xs) - min(xs) >= _MIN_COL_SPAN:
                    seed_x0s.extend(xs)

        if not seed_x0s:
            result.extend(window)
            i = j
            continue

        col_centers = _cluster_xs(seed_x0s)
        if len(col_centers) < _MIN_COLS:
            result.extend(window)
            i = j
            continue

        # Step 2: classify each row
        row_flags = [_row_is_multicolumn(r, col_centers) for r in rows]

        # Step 3: find contiguous table runs (>= MIN_ROWS)
        runs: list[tuple[int, int]] = []
        run_start = None
        for idx, flag in enumerate(row_flags):
            if flag and run_start is None:
                run_start = idx
            elif not flag and run_start is not None:
                if idx - run_start >= _MIN_ROWS:
                    runs.append((run_start, idx))
                run_start = None
        if run_start is not None and len(rows) - run_start >= _MIN_ROWS:
            runs.append((run_start, len(rows)))

        if not runs:
            result.extend(window)
            i = j
            continue

        # Step 4: emit — non-table rows as blocks, table runs as TableBlock
        table_row_indices: set[int] = set()
        for rs, re in runs:
            for r in range(rs, re):
                table_row_indices.add(r)

        emitted: set[int] = set()
        for r_idx, row in enumerate(rows):
            if r_idx not in table_row_indices:
                result.extend(row)
            else:
                for run_idx, (rs, re) in enumerate(runs):
                    if rs <= r_idx < re and run_idx not in emitted:
                        emitted.add(run_idx)
                        table_rows = rows[rs:re]

                        # Recompute column centers from just this table's rows
                        tbl_x0s: list[float] = []
                        for tr in table_rows:
                            xs = [b.bbox[0] for b in tr]
                            if len(tr) >= _MIN_COLS and max(xs) - min(xs) >= _MIN_COL_SPAN:
                                tbl_x0s.extend(xs)
                        final_cols = _cluster_xs(tbl_x0s) if len(tbl_x0s) >= 2 else col_centers

                        md = _build_table_markdown(table_rows, final_cols)
                        all_bboxes = [b.bbox for tr in table_rows for b in tr]
                        result.append(TableBlock(
                            markdown=md,
                            bbox=(
                                min(bb[0] for bb in all_bboxes),
                                min(bb[1] for bb in all_bboxes),
                                max(bb[2] for bb in all_bboxes),
                                max(bb[3] for bb in all_bboxes),
                            ),
                        ))
                        break

        i = j

    return result
