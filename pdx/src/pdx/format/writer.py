"""
Smart PDF writer — ActualText approach.

Embeds markdown into a PDF so that:
- Humans see the original formatted PDF (visual rendering untouched)
- Text extractors (MuPDF, Poppler, Acrobat) return ONLY the markdown
- The attachment provides a fallback for programmatic access

How it works:
1. Each page's visual content is wrapped in /Span with EMPTY ActualText
   → extractors skip all visual text (return nothing)
2. Page 0 gets a single invisible character wrapped in /Span with ActualText = markdown
   → extractors return the full markdown for that character
3. Net result: extract_text(smart_pdf) == markdown
"""
import re
import fitz
from pathlib import Path

OFF_ATTACHMENT_KEY = "_off_markdown_layer"

# Matches ![alt](data:...) image embeds — strip for ActualText to save space
_DATA_URI_RE = re.compile(r"!\[([^\]]*)\]\(data:[^)]+\)")


def create_off(pdf_source: str | Path | bytes, markdown: str,
               output_path: str | Path | None = None) -> Path:
    """Create a smart PDF from a PDF and its markdown. Returns output path."""
    if isinstance(pdf_source, (str, Path)):
        pdf_bytes = Path(pdf_source).read_bytes()
        if output_path is None:
            output_path = Path(pdf_source).with_suffix(".pdf")
    else:
        pdf_bytes = pdf_source
        if output_path is None:
            output_path = Path("output.pdf")

    output_path = Path(output_path)
    output_path.write_bytes(build_off_bytes(pdf_bytes, markdown))
    return output_path


def build_off_bytes(pdf_bytes: bytes, markdown: str) -> bytes:
    """Build smart PDF bytes — original PDF with ActualText markdown layer."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    _write_layers(doc, markdown)
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out


def _encode_actualtext_hex(text: str) -> str:
    """Encode a string as UTF-16BE hex with BOM prefix for PDF ActualText."""
    utf16 = text.encode("utf-16-be")
    return "FEFF" + utf16.hex().upper()


def _write_layers(doc: fitz.Document, markdown: str) -> None:
    """Embed markdown into the PDF using ActualText + attachment."""
    # 1. Attachment — clean programmatic access (viewer, CLI)
    _remove_existing_attachment(doc)
    doc.embfile_add(
        OFF_ATTACHMENT_KEY,
        markdown.encode("utf-8"),
        filename="layer.md",
        ufilename="layer.md",
        desc="OFF Markdown Layer",
    )

    # 2. ActualText wrapping
    #    Use a stripped version for ActualText (no base64 data URIs — too large)
    #    The full markdown with images lives in the attachment
    at_markdown = _DATA_URI_RE.sub(r"[Image: \1]", markdown)
    md_hex = _encode_actualtext_hex(at_markdown)

    for i, page in enumerate(doc):
        # Insert an invisible placeholder char — this registers /helv in page resources
        # so we can reference it in raw PDF operators below
        page.insert_text(
            (page.rect.x0 + 72, page.rect.y0 + page.rect.height / 2),
            "X",
            fontsize=12,
            render_mode=3,
        )
        page.clean_contents()
        xrefs = page.get_contents()
        if not xrefs:
            continue
        xref = xrefs[0]
        stream = doc.xref_stream(xref)

        # Wrap ALL existing content (visual + placeholder) in empty ActualText
        # → extractors return nothing for this block
        new_stream = (
            b"/Span <</ActualText <FEFF>>> BDC\n"
            + stream
            + b"\nEMC\n"
        )

        # Page 0 only: add invisible text block with full markdown as ActualText
        # The single "X" character acts as an anchor — extractors see it and return
        # the ActualText (full markdown) instead
        if i == 0:
            y_pos = int(page.rect.y1 - 50)
            new_stream += (
                f"/Span <</ActualText <{md_hex}>>> BDC\n".encode()
                + f"q BT /helv 12 Tf 3 Tr 1 0 0 1 72 {y_pos} Tm [(X)] TJ ET Q\n".encode()
                + b"EMC\n"
            )

        doc.update_stream(xref, new_stream)


def _remove_existing_attachment(doc: fitz.Document) -> None:
    try:
        idx = doc.embfile_names().index(OFF_ATTACHMENT_KEY)
        doc.embfile_del(idx)
    except (ValueError, Exception):
        pass
