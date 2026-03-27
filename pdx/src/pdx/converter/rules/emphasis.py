"""
Inline emphasis rule — wraps bold/italic spans within a paragraph.
This is the fallback for body text that has mixed formatting.

Note: this rule never 'claims' a block (always returns False from applies).
Instead, it post-processes the text returned by the paragraph fallback.
Use it explicitly in the pipeline as a text transformer.
"""
from pdx.converter.extractor import Block, Span


def _style_key(span: Span) -> tuple[bool, bool]:
    return (span.is_bold, span.is_italic)


def _merge_spans(spans: list[Span]) -> list[Span]:
    """Merge consecutive spans that share the same bold/italic style."""
    if not spans:
        return []
    merged: list[Span] = [Span(
        text=spans[0].text,
        font_size=spans[0].font_size,
        is_bold=spans[0].is_bold,
        is_italic=spans[0].is_italic,
        is_monospace=spans[0].is_monospace,
    )]
    for span in spans[1:]:
        if _style_key(span) == _style_key(merged[-1]):
            merged[-1].text += span.text
        else:
            merged.append(Span(
                text=span.text,
                font_size=span.font_size,
                is_bold=span.is_bold,
                is_italic=span.is_italic,
                is_monospace=span.is_monospace,
            ))
    return merged


def apply_inline_emphasis(block: Block) -> str:
    """
    Render spans with inline Markdown emphasis.
    Consecutive spans with same style are merged before wrapping
    to avoid output like **S****ARTHAK**.
    """
    parts: list[str] = []

    for span in _merge_spans(block.spans):
        text = span.text
        if not text:
            continue
        if span.is_bold or span.is_italic:
            # Strip surrounding whitespace from the text and reattach outside
            # markers to avoid **word ** (trailing space breaks Markdown rendering)
            lstrip = len(text) - len(text.lstrip())
            rstrip = len(text) - len(text.rstrip())
            prefix = text[:lstrip]
            suffix = text[len(text) - rstrip:] if rstrip else ""
            inner = text[lstrip: len(text) - rstrip if rstrip else len(text)]
            if not inner:
                parts.append(text)
                continue
            if span.is_bold and span.is_italic:
                parts.append(f"{prefix}***{inner}***{suffix}")
            elif span.is_bold:
                parts.append(f"{prefix}**{inner}**{suffix}")
            else:
                parts.append(f"{prefix}*{inner}*{suffix}")
        else:
            parts.append(text)

    return "".join(parts).strip()
