"""
.off format reader — extracts the markdown layer from a .off file (PDF container).
"""
import fitz
import subprocess
import sys
from pathlib import Path

from pdx.format.writer import OFF_ATTACHMENT_KEY


class NoOffLayerError(Exception):
    pass


def read_markdown(off_path: str | Path) -> str:
    off_path = Path(off_path)
    with fitz.open(str(off_path)) as doc:
        return _extract_from_doc(doc, off_path.name)


def read_markdown_from_bytes(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    result = _extract_from_doc(doc, "document.off")
    doc.close()
    return result


def _extract_from_doc(doc: fitz.Document, name: str) -> str:
    names = doc.embfile_names()
    if OFF_ATTACHMENT_KEY not in names:
        raise NoOffLayerError(f"No markdown layer found in '{name}'.")
    idx = names.index(OFF_ATTACHMENT_KEY)
    return doc.embfile_get(idx).decode("utf-8")


def open_pdf(off_path: str | Path) -> None:
    """Open a .off file in the system PDF viewer (it's a valid PDF)."""
    off_path = Path(off_path)
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", "Preview", str(off_path)], check=True)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(off_path)], check=True)
    elif sys.platform == "win32":
        subprocess.run(["start", str(off_path)], shell=True, check=True)
