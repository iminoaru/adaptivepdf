"""
Embeds a Markdown layer into a PDF file to produce a .pdx file.

Mechanism:
  1. PDF native attachment (EmbeddedFiles) — for programmatic/API access.
  2. Invisible text on page 0 — for LLMs and PDF text extractors (ChatGPT etc.)
     that only read page content, not attachments.

The resulting .pdx file is a fully valid PDF — any viewer opens it as normal.
The markdown layer is invisible to human readers.
"""
from pathlib import Path
import fitz  # PyMuPDF

PDX_ATTACHMENT_KEY = "_pdx_markdown_layer"
_PDX_MARKER_START = "---PDX-MARKDOWN-BEGIN---"
_PDX_MARKER_END = "---PDX-MARKDOWN-END---"


def embed_markdown(pdf_path: str | Path, markdown: str, output_path: str | Path | None = None) -> Path:
    """
    Takes an existing PDF and embeds markdown as an attachment.
    Returns the path to the .pdx file.

    output_path defaults to same location as pdf_path with .pdx extension.
    """
    pdf_path = Path(pdf_path)
    if output_path is None:
        output_path = pdf_path.with_suffix(".pdx")
    output_path = Path(output_path)

    with fitz.open(str(pdf_path)) as doc:
        _write_layers(doc, markdown)
        doc.save(str(output_path))

    return output_path


def embed_markdown_bytes(pdf_bytes: bytes, markdown: str) -> bytes:
    """
    Takes PDF bytes and returns .pdx bytes with markdown embedded.
    Used by the API to avoid temp files.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    _write_layers(doc, markdown)
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out


def _write_layers(doc: fitz.Document, markdown: str) -> None:
    """Embed markdown both as attachment and as invisible page text."""
    _remove_existing_layer(doc)

    # 1. Attachment — for programmatic access
    doc.embfile_add(
        PDX_ATTACHMENT_KEY,
        markdown.encode("utf-8"),
        filename="layer.md",
        ufilename="layer.md",
        desc="PDX Markdown Layer",
    )

    # 2. Inject markdown as render-mode-3 (invisible) text across pages.
    #    Invisible to PDF viewers, readable by text extractors and LLMs.
    _inject_invisible_text(doc, markdown)


_PDX_MARKER = "pdx:markdown"   # sentinel prefix so extractors can identify the layer


def _inject_invisible_text(doc: fitz.Document, markdown: str) -> None:
    """
    Write the markdown as render-mode-3 (invisible) text on the PDF pages.

    Render mode 3 = no fill, no stroke — PDF viewers display nothing.
    PDF text extractors (and LLMs) read the content stream regardless of render
    mode, so they see the full markdown. This is the same technique used by
    searchable PDFs to overlay OCR text over scanned images.

    The text is spread across pages so long documents aren't truncated.
    Each page gets a chunk prefixed with pdx:markdown so extractors
    can identify and reassemble the layer.
    """
    if len(doc) == 0:
        return

    # Remove any previously injected invisible text by re-saving without it
    # (We track injection via the first page's content — simpler: just overwrite)

    header = (
        f"{_PDX_MARKER}\n"
        "This file is in PDX format. The text above this line is the raw PDF visual layer.\n"
        "The structured markdown content follows. Use this for AI/machine processing.\n"
        "---\n"
    )
    lines = (header + markdown).splitlines()
    font_size = 10.0
    line_height = font_size * 1.4

    line_idx = 0
    total_lines = len(lines)

    for page in doc:
        if line_idx >= total_lines:
            break
        rect = page.rect
        x = rect.x0 + 4
        y = rect.y0 + font_size + 2
        y_max = rect.y1 - 4

        while line_idx < total_lines and y <= y_max:
            page.insert_text(
                (x, y),
                lines[line_idx],
                fontsize=font_size,
                render_mode=3,   # invisible: no fill, no stroke
                color=(0, 0, 0),
            )
            y += line_height
            line_idx += 1


def _remove_existing_layer(doc: fitz.Document) -> None:
    """Remove a previously embedded pdx layer if present."""
    try:
        idx = doc.embfile_names().index(PDX_ATTACHMENT_KEY)
        doc.embfile_del(idx)
    except (ValueError, Exception):
        pass
