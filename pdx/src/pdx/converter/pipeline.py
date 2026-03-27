"""
Pipeline: runs a list of Rules over extracted Blocks and produces Markdown.

Rules are tried in order. First rule whose applies() returns True claims the block.
If no rule claims it, the block is treated as a plain paragraph (with inline emphasis).

Context dict carries document-level data (body_font_size, etc.) available to every rule.
"""
from pdx.converter.extractor import Block, ImageBlock, TableBlock, extract_blocks, compute_body_font_size
from pdx.converter.filters import apply_filters
from pdx.converter.merger import merge_paragraph_lines, split_tabular_lines, detect_tables
from pdx.converter.rules.base import Rule
from pdx.converter.rules.emphasis import apply_inline_emphasis
from pdx.converter.rules import HeadingRule, ListRule, CodeRule
from pathlib import Path

# Heading levels that get a section separator before them
_SECTION_HEADING_PREFIXES = ("# ", "## ")


def default_rules(
    h1_ratio: float = 1.8,
    h2_ratio: float = 1.4,
    h3_ratio: float = 1.15,
    all_caps_as_heading: bool = True,
    exclude_dates: bool = True,
    normalize_bullets: bool = True,
) -> list[Rule]:
    """
    Returns the default rule set with configurable parameters.
    Callers can swap individual rules or pass a completely custom list to
    convert_blocks_to_markdown / pdf_to_markdown instead.
    """
    return [
        ListRule(normalize_bullets=normalize_bullets),  # bullets first
        CodeRule(),
        HeadingRule(
            h1_ratio=h1_ratio,
            h2_ratio=h2_ratio,
            h3_ratio=h3_ratio,
            all_caps_as_heading=all_caps_as_heading,
            exclude_dates=exclude_dates,
        ),
    ]


def convert_blocks_to_markdown(
    blocks: list[Block],
    rules: list[Rule] | None = None,
    filters=None,
) -> str:
    if rules is None:
        rules = default_rules()

    blocks = apply_filters(blocks, filters)       # 1. drop headers/footers/page numbers
    blocks = merge_paragraph_lines(blocks)        # 2. rejoin wrapped lines into paragraphs
    blocks = split_tabular_lines(blocks)          # 3. split wide lines into column blocks
    blocks = detect_tables(blocks)                # 4. detect spatial tables
    body_size = compute_body_font_size(blocks)
    context = {"body_font_size": body_size}

    lines: list[str] = []

    for block in blocks:
        # Page break sentinels are physical — skip them entirely.
        # Section boundaries are handled semantically below.
        if isinstance(block, Block) and not block.spans:
            continue

        # Images — lightweight placeholder (the PDF already has the image data)
        if isinstance(block, ImageBlock):
            lines.append(f"![Image ({block.width}x{block.height})]")
            continue

        # Tables are pre-rendered Markdown
        if isinstance(block, TableBlock):
            lines.append(block.markdown)
            continue

        claimed = False
        for rule in rules:
            if rule.applies(block, context):
                md_line = rule.convert(block, context)
                # Insert --- before H1/H2 section boundaries (not before the very first one)
                if lines and any(md_line.startswith(p) for p in _SECTION_HEADING_PREFIXES):
                    lines.append("---")
                lines.append(md_line)
                claimed = True
                break

        if not claimed:
            lines.append(apply_inline_emphasis(block))

    # Join with blank lines between blocks
    md = "\n\n".join(line for line in lines if line.strip())
    return md


def pdf_to_markdown(
    pdf_path: str | Path,
    rules: list[Rule] | None = None,
    filters=None,
) -> str:
    """Top-level entry point: PDF file → Markdown string."""
    blocks = extract_blocks(pdf_path)
    return convert_blocks_to_markdown(blocks, rules, filters)
