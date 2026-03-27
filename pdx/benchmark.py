"""
Benchmark: Normal PDF vs Smart PDF

Measures:
1. File size overhead (normal vs smart)
2. Text extraction time across libraries (PyMuPDF, pdftotext/Poppler)
3. Extracted text quality (char count, line count, structure markers)
4. LLM token counts (tiktoken cl100k_base — used by GPT-4, Claude is similar)
5. End-to-end conversion time (PDF → smart PDF)
"""
import time
import sys
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict

import fitz  # PyMuPDF
import subprocess
import shutil

# Optional: tiktoken for token counting
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")
    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))
except ImportError:
    _enc = None
    def count_tokens(text: str) -> int:
        # rough estimate: 1 token ≈ 4 chars
        return len(text) // 4

# Check for pdftotext (Poppler)
HAS_PDFTOTEXT = shutil.which("pdftotext") is not None


@dataclass
class ExtractionResult:
    library: str
    time_ms: float
    chars: int
    lines: int
    tokens: int
    has_markdown_syntax: bool  # contains #, ##, -, **, etc.
    sample: str = ""  # first 200 chars


@dataclass
class BenchmarkResult:
    filename: str
    pages: int
    normal_size_kb: float
    smart_size_kb: float
    size_overhead_pct: float
    conversion_time_ms: float
    normal_extractions: list[ExtractionResult] = field(default_factory=list)
    smart_extractions: list[ExtractionResult] = field(default_factory=list)


def extract_pymupdf(pdf_bytes: bytes) -> ExtractionResult:
    start = time.perf_counter()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    elapsed = (time.perf_counter() - start) * 1000

    has_md = any(marker in text for marker in ["# ", "## ", "- ", "**", "```"])
    return ExtractionResult(
        library="PyMuPDF",
        time_ms=round(elapsed, 2),
        chars=len(text),
        lines=len(text.splitlines()),
        tokens=count_tokens(text),
        has_markdown_syntax=has_md,
        sample=text[:200].replace("\n", "\\n"),
    )


def extract_pdftotext(pdf_path: Path) -> ExtractionResult | None:
    if not HAS_PDFTOTEXT:
        return None
    start = time.perf_counter()
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=30,
    )
    text = result.stdout
    elapsed = (time.perf_counter() - start) * 1000

    has_md = any(marker in text for marker in ["# ", "## ", "- ", "**", "```"])
    return ExtractionResult(
        library="pdftotext (Poppler)",
        time_ms=round(elapsed, 2),
        chars=len(text),
        lines=len(text.splitlines()),
        tokens=count_tokens(text),
        has_markdown_syntax=has_md,
        sample=text[:200].replace("\n", "\\n"),
    )


def run_benchmark(pdf_path: Path) -> BenchmarkResult:
    from pdx.converter import pdf_to_markdown
    from pdx.format.writer import build_off_bytes

    pdf_bytes = pdf_path.read_bytes()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = len(doc)
    doc.close()

    normal_size = len(pdf_bytes) / 1024

    # Convert to markdown
    md_start = time.perf_counter()
    markdown = pdf_to_markdown(pdf_path)
    md_time = (time.perf_counter() - md_start) * 1000

    # Build smart PDF
    smart_start = time.perf_counter()
    smart_bytes = build_off_bytes(pdf_bytes, markdown)
    smart_time = (time.perf_counter() - smart_start) * 1000

    total_conversion = md_time + smart_time
    smart_size = len(smart_bytes) / 1024
    overhead = ((smart_size - normal_size) / normal_size) * 100

    result = BenchmarkResult(
        filename=pdf_path.name,
        pages=pages,
        normal_size_kb=round(normal_size, 1),
        smart_size_kb=round(smart_size, 1),
        size_overhead_pct=round(overhead, 1),
        conversion_time_ms=round(total_conversion, 1),
    )

    # --- Extract from normal PDF ---
    result.normal_extractions.append(extract_pymupdf(pdf_bytes))

    # Write temp files for pdftotext
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        normal_tmp = Path(tmp.name)
    pt_result = extract_pdftotext(normal_tmp)
    if pt_result:
        result.normal_extractions.append(pt_result)
    normal_tmp.unlink(missing_ok=True)

    # --- Extract from smart PDF ---
    result.smart_extractions.append(extract_pymupdf(smart_bytes))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(smart_bytes)
        smart_tmp = Path(tmp.name)
    pt_result = extract_pdftotext(smart_tmp)
    if pt_result:
        result.smart_extractions.append(pt_result)
    smart_tmp.unlink(missing_ok=True)

    return result


def print_result(r: BenchmarkResult):
    print(f"\n{'='*70}")
    print(f"  {r.filename}  ({r.pages} pages)")
    print(f"{'='*70}")

    print(f"\n  File Size")
    print(f"    Normal:    {r.normal_size_kb:>10.1f} KB")
    print(f"    Smart:     {r.smart_size_kb:>10.1f} KB")
    print(f"    Overhead:  {r.size_overhead_pct:>+9.1f}%")

    print(f"\n  Conversion Time: {r.conversion_time_ms:.0f} ms")

    print(f"\n  Normal PDF Extraction")
    print(f"    {'Library':<22} {'Time':>8} {'Chars':>8} {'Lines':>6} {'Tokens':>7} {'Has MD':>6}")
    print(f"    {'-'*58}")
    for e in r.normal_extractions:
        print(f"    {e.library:<22} {e.time_ms:>7.1f}ms {e.chars:>7} {e.lines:>6} {e.tokens:>7} {'yes' if e.has_markdown_syntax else 'no':>6}")

    print(f"\n  Smart PDF Extraction")
    print(f"    {'Library':<22} {'Time':>8} {'Chars':>8} {'Lines':>6} {'Tokens':>7} {'Has MD':>6}")
    print(f"    {'-'*58}")
    for e in r.smart_extractions:
        print(f"    {e.library:<22} {e.time_ms:>7.1f}ms {e.chars:>7} {e.lines:>6} {e.tokens:>7} {'yes' if e.has_markdown_syntax else 'no':>6}")

    # Token savings
    if r.normal_extractions and r.smart_extractions:
        normal_tokens = r.normal_extractions[0].tokens
        smart_tokens = r.smart_extractions[0].tokens
        if normal_tokens > 0:
            savings = ((normal_tokens - smart_tokens) / normal_tokens) * 100
            print(f"\n  Token Impact (PyMuPDF)")
            print(f"    Normal: {normal_tokens:>7} tokens")
            print(f"    Smart:  {smart_tokens:>7} tokens")
            print(f"    Change: {savings:>+6.1f}%")


def print_summary(results: list[BenchmarkResult]):
    print(f"\n\n{'='*70}")
    print(f"  SUMMARY")
    print(f"{'='*70}")
    print(f"\n  {'File':<35} {'Pages':>5} {'Size Δ':>8} {'Normal Tok':>10} {'Smart Tok':>10} {'Token Δ':>8}")
    print(f"  {'-'*76}")

    total_normal_tokens = 0
    total_smart_tokens = 0

    for r in results:
        nt = r.normal_extractions[0].tokens if r.normal_extractions else 0
        st = r.smart_extractions[0].tokens if r.smart_extractions else 0
        total_normal_tokens += nt
        total_smart_tokens += st
        delta = ((nt - st) / nt * 100) if nt else 0
        name = r.filename[:33]
        print(f"  {name:<35} {r.pages:>5} {r.size_overhead_pct:>+7.1f}% {nt:>10} {st:>10} {delta:>+7.1f}%")

    if total_normal_tokens:
        total_delta = ((total_normal_tokens - total_smart_tokens) / total_normal_tokens) * 100
        print(f"  {'-'*76}")
        print(f"  {'TOTAL':<35} {'':>5} {'':>8} {total_normal_tokens:>10} {total_smart_tokens:>10} {total_delta:>+7.1f}%")

    # Markdown syntax check
    print(f"\n  Markdown Syntax Detection")
    print(f"  {'File':<35} {'Normal':>10} {'Smart':>10}")
    print(f"  {'-'*55}")
    for r in results:
        n_md = "yes" if r.normal_extractions and r.normal_extractions[0].has_markdown_syntax else "no"
        s_md = "yes" if r.smart_extractions and r.smart_extractions[0].has_markdown_syntax else "no"
        print(f"  {r.filename[:33]:<35} {n_md:>10} {s_md:>10}")


def main():
    opts_dir = Path(__file__).parent / "opts"
    pdfs = sorted(opts_dir.glob("*.pdf"))

    if not pdfs:
        print("No PDFs found in opts/")
        sys.exit(1)

    # Allow filtering by CLI arg
    if len(sys.argv) > 1:
        names = set(sys.argv[1:])
        pdfs = [p for p in pdfs if p.name in names or p.stem in names]

    print(f"Benchmarking {len(pdfs)} PDF(s)...")
    print(f"Libraries: PyMuPDF{', pdftotext (Poppler)' if HAS_PDFTOTEXT else ''}")
    print(f"Token counter: {'tiktoken (cl100k_base)' if _enc else 'estimate (~4 chars/token)'}")

    results = []
    for pdf in pdfs:
        try:
            r = run_benchmark(pdf)
            print_result(r)
            results.append(r)
        except Exception as e:
            print(f"\n  SKIP {pdf.name}: {e}")

    if len(results) > 1:
        print_summary(results)


if __name__ == "__main__":
    main()
