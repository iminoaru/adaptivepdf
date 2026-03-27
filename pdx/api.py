"""
Adaptive PDF API — FastAPI backend.

POST /convert            PDF → markdown + stats
POST /build-smart-pdf    PDF (base64) + markdown → smart PDF
POST /package            PDF upload + markdown → smart PDF download
POST /read               smart PDF → markdown
"""
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from pdx.converter import pdf_to_markdown, default_rules, extract_blocks, compute_body_font_size
from pdx.converter.filters import apply_filters
from pdx.converter.merger import merge_paragraph_lines, split_tabular_lines, detect_tables, TableBlock
from pdx.converter.extractor import Block, ImageBlock
from pdx.format.writer import build_off_bytes
from pdx.format.reader import read_markdown_from_bytes
import tempfile, pathlib, uuid, time

app = FastAPI(title="adaptive-pdf-api")

# In-memory staging store: id → {markdown, pdf_b64, filename, ts}
_staged: dict[str, dict] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    h1_ratio: float = Form(1.8),
    h2_ratio: float = Form(1.4),
    h3_ratio: float = Form(1.15),
    all_caps_as_heading: bool = Form(True),
    exclude_dates: bool = Form(True),
    normalize_bullets: bool = Form(True),
    extract_images: bool = Form(True),
):
    pdf_bytes = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = pathlib.Path(tmp.name)

    try:
        rules = default_rules(
            h1_ratio=h1_ratio,
            h2_ratio=h2_ratio,
            h3_ratio=h3_ratio,
            all_caps_as_heading=all_caps_as_heading,
            exclude_dates=exclude_dates,
            normalize_bullets=normalize_bullets,
        )

        try:
            blocks = extract_blocks(tmp_path, extract_images=extract_images)
        except Exception:
            # Fall back to no images if extraction fails
            blocks = extract_blocks(tmp_path, extract_images=False)
        raw_block_count = sum(1 for b in blocks if isinstance(b, Block) and b.spans)

        blocks = apply_filters(blocks)
        blocks = merge_paragraph_lines(blocks)
        blocks = split_tabular_lines(blocks)
        blocks = detect_tables(blocks)

        table_count = sum(1 for b in blocks if isinstance(b, TableBlock))
        image_count = sum(1 for b in blocks if isinstance(b, ImageBlock))
        final_block_count = sum(1 for b in blocks if isinstance(b, Block) and b.spans)

        from pdx.converter.pipeline import convert_blocks_to_markdown
        markdown = convert_blocks_to_markdown(blocks, rules, filters=[])

        return JSONResponse({
            "markdown": markdown,
            "filename": file.filename or "document.pdf",
            "stats": {
                "raw_blocks": raw_block_count,
                "final_blocks": final_block_count,
                "tables": table_count,
                "images": image_count,
                "lines": len(markdown.splitlines()),
                "chars": len(markdown),
            }
        })
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/build-smart-pdf")
async def build_smart_pdf(
    pdf_base64: str = Form(...),
    markdown: str = Form(...),
    filename: str = Form("document"),
):
    """
    Build a smart PDF from base64-encoded PDF + markdown.
    Used by the Google Docs add-on.
    """
    import base64
    try:
        pdf_bytes = base64.b64decode(pdf_base64)
    except Exception:
        return JSONResponse({"error": "Invalid base64 PDF data"}, status_code=400)

    smart_bytes = build_off_bytes(pdf_bytes, markdown)
    return Response(
        content=smart_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename} (Smart).pdf"'},
    )


@app.post("/stage")
async def stage(file: UploadFile = File(...)):
    """
    Stage a .off file for the viewer to pick up via ?load=<id>.
    Used by the OffOpener app so double-clicking a .off file opens the viewer.
    Staged entries expire after 60 seconds.
    """
    import base64
    data = await file.read()
    from pdx.format.reader import read_markdown_from_bytes, _extract_pdf_bytes
    text = data.decode("utf-8")
    markdown = read_markdown_from_bytes(data)
    pdf_bytes = _extract_pdf_bytes(text)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    # Evict old entries
    now = time.time()
    for k in list(_staged):
        if now - _staged[k]["ts"] > 60:
            del _staged[k]

    sid = uuid.uuid4().hex[:12]
    _staged[sid] = {
        "markdown": markdown,
        "pdf_b64": pdf_b64,
        "filename": file.filename or "document.off",
        "ts": now,
    }
    return JSONResponse({"id": sid})


@app.get("/staged/{sid}")
async def get_staged(sid: str):
    entry = _staged.get(sid)
    if not entry:
        return JSONResponse({"error": "Not found or expired"}, status_code=404)
    return JSONResponse({
        "markdown": entry["markdown"],
        "pdf_b64": entry["pdf_b64"],
        "filename": entry["filename"],
    })


@app.post("/read")
async def read_off(file: UploadFile = File(...)):
    """Extract markdown from a .off file."""
    data = await file.read()
    try:
        md = read_markdown_from_bytes(data)
        return JSONResponse({"markdown": md, "filename": file.filename or "document.off"})
    except Exception:
        return JSONResponse({"error": "Could not read markdown from this file"}, status_code=400)


@app.post("/package")
async def package(
    file: UploadFile = File(...),
    markdown: str = Form(...),
):
    """
    Build a .off file from a PDF + markdown and return it for download.
    Client sends the original PDF bytes + the already-converted markdown.
    """
    pdf_bytes = await file.read()
    off_bytes = build_off_bytes(pdf_bytes, markdown)
    filename = file.filename or "document.pdf"
    return Response(
        content=off_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
