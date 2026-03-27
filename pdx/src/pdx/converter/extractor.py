"""
Extracts raw Block objects from a PDF using PyMuPDF.
No interpretation here — just geometry and text/image with font metadata.
"""
from dataclasses import dataclass, field
from pathlib import Path
import base64
import fitz  # PyMuPDF


@dataclass
class Span:
    text: str
    font_size: float
    is_bold: bool
    is_italic: bool
    is_monospace: bool
    x0: float = 0.0   # left edge of span on page (used for column detection)


@dataclass
class Block:
    """One logical block of text from the PDF (paragraph, heading, list item, etc.)"""
    spans: list[Span] = field(default_factory=list)
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)  # x0, y0, x1, y1
    pdf_block_id: int = -1  # which PDF text block this line came from (for line joining)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans).strip()

    @property
    def dominant_font_size(self) -> float:
        if not self.spans:
            return 0.0
        total_chars = sum(len(s.text) for s in self.spans)
        if total_chars == 0:
            return self.spans[0].font_size
        return sum(s.font_size * len(s.text) for s in self.spans) / total_chars

    @property
    def is_bold(self) -> bool:
        return any(s.is_bold for s in self.spans)

    @property
    def is_monospace(self) -> bool:
        return all(s.is_monospace for s in self.spans if s.text.strip())


@dataclass
class ImageBlock:
    """An image extracted from the PDF, embedded as base64."""
    data_uri: str          # ready-to-use data URI: data:image/png;base64,...
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    width: int = 0
    height: int = 0

    @property
    def text(self) -> str:
        return ""

    @property
    def spans(self) -> list:
        return []


@dataclass
class TableBlock:
    """A table detected from spatial layout, pre-rendered as Markdown."""
    markdown: str
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)

    @property
    def text(self) -> str:
        return self.markdown

    @property
    def spans(self) -> list:
        return []


_MONOSPACE_KEYWORDS = {"courier", "mono", "consolas", "inconsolata", "menlo", "sourcecodepro"}


def _is_monospace(font_name: str) -> bool:
    name = font_name.lower()
    return any(kw in name for kw in _MONOSPACE_KEYWORDS)


def _is_bold(flags: int) -> bool:
    # PyMuPDF flag bit 4 (value 16) = bold
    return bool(flags & 16)


def _is_italic(flags: int) -> bool:
    # PyMuPDF flag bit 1 (value 2) = italic
    return bool(flags & 2)


# Minimum image dimensions to include — filters out icons, bullets, decorations
_MIN_IMAGE_WIDTH = 80
_MIN_IMAGE_HEIGHT = 80


def _extract_page_images(page: fitz.Page, doc: fitz.Document) -> list[ImageBlock]:
    """Extract images from a page, skipping tiny decorative ones."""
    images: list[ImageBlock] = []
    seen_xrefs: set[int] = set()

    for img_info in page.get_images(full=True):
        xref = img_info[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        try:
            raw = doc.extract_image(xref)
        except Exception:
            continue

        w, h = raw["width"], raw["height"]
        if w < _MIN_IMAGE_WIDTH or h < _MIN_IMAGE_HEIGHT:
            continue

        ext = raw["ext"]  # e.g. "png", "jpeg"
        mime = f"image/{'jpeg' if ext == 'jpeg' else ext}"
        b64 = base64.b64encode(raw["image"]).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"

        # Get bbox of image on page (use first occurrence)
        bbox = (0.0, 0.0, float(w), float(h))
        for item in page.get_image_rects(xref):
            bbox = tuple(item)  # type: ignore
            break

        images.append(ImageBlock(data_uri=data_uri, bbox=bbox, width=w, height=h))

    return images


def extract_blocks(
    pdf_path: str | Path,
    extract_images: bool = False,  # TODO: implement pdx://page/N/xref/M lazy refs for viewer
) -> list[Block | ImageBlock]:
    """
    Returns a flat list of Blocks (one per line) and ImageBlocks, across all pages,
    sorted by vertical position so images appear in reading order with the text.
    Page breaks are sentinel empty Blocks with no spans.
    """
    blocks: list[Block | ImageBlock] = []

    with fitz.open(str(pdf_path)) as doc:
        for page_num, page in enumerate(doc):
            if page_num > 0:
                blocks.append(Block())  # page break sentinel

            page_items: list[Block | ImageBlock] = []

            raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            for block_idx, rb in enumerate(raw_blocks):
                if rb.get("type") != 0:
                    continue
                # Use a globally unique block id (page * 10000 + block_idx)
                block_id = page_num * 10000 + block_idx
                for line in rb.get("lines", []):
                    block = Block(bbox=tuple(line["bbox"]), pdf_block_id=block_id)
                    for span in line.get("spans", []):
                        raw_text = span.get("text", "")
                        if not raw_text:
                            continue
                        block.spans.append(Span(
                            text=raw_text,
                            font_size=round(span["size"], 2),
                            is_bold=_is_bold(span["flags"]),
                            is_italic=_is_italic(span["flags"]),
                            is_monospace=_is_monospace(span.get("font", "")),
                            x0=span["bbox"][0],
                        ))
                    if block.text:
                        page_items.append(block)

            if extract_images:
                page_items.extend(_extract_page_images(page, doc))

            # Sort by y0 so images appear in reading order with surrounding text
            page_items.sort(key=lambda b: b.bbox[1])
            blocks.extend(page_items)

    return blocks


def compute_body_font_size(blocks: list[Block | ImageBlock]) -> float:
    """
    The most common font size across all blocks = body text size.
    Used by rules to determine heading levels relatively.
    """
    from collections import Counter
    sizes: list[float] = []
    for b in blocks:
        for s in b.spans:
            if s.text.strip():
                sizes.append(round(s.font_size, 1))
    if not sizes:
        return 12.0
    return Counter(sizes).most_common(1)[0][0]
