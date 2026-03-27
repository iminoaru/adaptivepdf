

> Started: 19 March 2026, 1AM
> Status: Idea stage — prototype begins tomorrow
> Language: Python (core), TypeScript (viewer + web layer)
> Built by: Sarthak

---

## The origin story

Started with a resume problem.

Writing a resume for ATS makes it keyword-dense and robotic.
Writing it for a human hiring manager makes it personal and story-driven.
The same file has to do both — and it always fails at one or the other.

The question: can a PDF detect who is reading it and show different
content in real time?

That question unraveled into something much bigger.

---

## What we explored and ruled out

### Can a PDF do real-time detection natively?

PDF JavaScript exists (Adobe JS), but only runs in Adobe Acrobat.
Chrome's viewer, Safari, iOS, most mobile apps — none execute PDF JS.
Any "smart" behavior breaks for the majority of human readers.
Dead end for dynamic switching inside a standard PDF.

### Is there any existing file format that does this?

Did a deep research pass across:
- W3C proposals, IETF drafts, ISO/OASIS standards
- HTML + JSON-LD, Tagged PDF, EPUB 3, DITA XML
- Jupyter Notebooks, JSON Resume, OpenBadges
- AI-era proposals: llms.txt, ai.txt, TDMRep
- Startups: Docugami, Unstructured.io, LlamaIndex, Docling, Marker

Verdict: NO single file format exists that dynamically renders
different presentations to humans, AI systems, and automated parsers
from one document.

HTML + JSON-LD gets ~85% of the way there but:
- No formal spec declaring it as an adaptive document paradigm
- No AI/LLM-optimized layer (Schema.org was designed for search in 2011)
- No standardized consumer-type detection API
- No declarative mechanism for mapping layers to consumer types

The gap is real and confirmed by research.

### Why "pass to AI to convert after the fact" defeats the purpose

The obvious shortcut: take a PDF, pass it to an LLM, let it generate
a structured version. This is what the whole industry does right now.

Problems:
- You trust AI's interpretation, not the author's intent
- Information gets lost, hallucinated, or reframed
- Source of truth becomes ambiguous
- It's a band-aid, not a standard

The author should DECLARE what each layer contains.
Not an AI guessing it afterward.

---

## The core insight

> The document should be born with multiple layers natively.
> Not a conversion tool. Not a parser.
> The document IS the source of truth for all consumers simultaneously.

Like responsive web design — write once, renders differently per consumer.
But instead of screen sizes, it's consumer TYPES:

  Human   → visual designed layer
  LLM/AI  → clean Markdown layer
  API     → key-value / JSON layer

---

## The format: .pdx

### Why .pdx
- Short, professional, memorable
- Feels like PDF's natural evolved cousin
- Unused in mainstream file formats
- Signals lineage without being derivative

### The three native layers

  Same .pdx file
         |
  ┌──────────────────┐
  │  Who's reading?  │
  └──────────────────┘
         |
  ┌──────┬──────┬──────────┐
  Human  ATS    LLM/AI     API
    |      |       |         |
  Visual  KW-   Markdown  Key-value
  layer  dense   layer    / JSON

Layer 1 — Visual PDF layer (for humans)
  Beautiful design, personal voice, emotional resonance
  Optimized for skimmability and first impressions

Layer 2 — Markdown layer (for LLMs / AI)  ← V1 focus
  Clean, structured, semantically rich Markdown
  LLMs read it top to bottom — no chunking, no RAG needed
  Author intent preserved, not guessed by AI

Layer 3 — Key-value / JSON layer (for APIs)  ← V3 scope
  Structured data parseable without an AI intermediary
  Contract terms, resume fields, research metadata

### Detection logic

  fs.read() / programmatic access  →  Markdown / AI layer
  Manual open / interactive         →  Visual PDF layer

File system reads are almost never humans.
Simplest, most reliable signal. No JS needed. Works everywhere.

---

## Why the timing is right

### The old way LLMs process PDFs (RAG pipeline — still widely used)

  upload PDF → extract raw text → OCR if image-based
  → chunk it → embed chunks → store in vector DB
  → retrieve relevant chunks on query

Problems:
  - Chunking destroys context (related info split across chunks)
  - OCR is lossy (loses formatting, tables, structure)
  - Embeddings are approximate (fuzzy retrieval, things get missed)
  - No author intent (AI guesses structure, doesn't read declared structure)

### What's replacing RAG right now

  - Long context windows (Gemini 1.5, Claude, GPT-4 — whole doc at once)
  - Native document understanding in newer models
  - Structured extraction before reasoning

### Where .pdx fits

A .pdx file with a native Markdown layer IS what LLMs want natively.
No extraction. No chunking. No OCR. The structured layer is just there.

This format makes RAG pipelines obsolete for normal-sized documents.
The document itself is the structured data.

---

## How adoption works — the killer insight

### Nobody should have to change how they write

The authoring experience stays completely identical.
Magic happens at the export / save step.

### .docx is just a ZIP

A .docx file is literally a ZIP containing XML files.
You can embed a Markdown layer as an extra XML file inside that ZIP.
Word never breaks — it ignores files it doesn't recognize.

  User writes in Word normally
       |
  Save → xpdf add-in fires
       |
  Generates Markdown layer automatically
       |
  Embeds it as hidden XML inside the .docx ZIP
       |
  Same file. Two layers. Zero friction.

### Google Workspace Add-on

Google Apps Script lets you add native menu items:

  Extensions → xpdf → Export as .pdx

Triggers on click. Reads document. Generates Markdown layer.
Assembles .pdx file. Prompts download. Feels completely native.

### Microsoft Office Add-in

Office JS adds a button in the Word ribbon:

  File → Export → Export as .pdx

Works across Word, Excel, PowerPoint.

### Distribution

  Google → Chrome Web Store (Workspace Add-on)
  Microsoft → AppSource (Office Add-in)

Users install once. Every document from that point is .pdx exportable.
Zero friction. They never leave their existing tools.

This is the go-to-market. Not a new editor. Not a new app.
A plugin inside tools people already use every day.

---

## What does NOT exist yet (confirmed)

- A format where the AUTHOR controls what humans vs ATS vs LLMs see
- AI-aware document layers baked into the authoring process
- A viewer that detects context and serves the right layer
- Any "Adaptive Document Profile" standard
- Consumer-type detection built into any file format spec

The whole industry is retrofitting AI onto old documents (conversion tools).
.pdx is the format where every new document is natively multi-layered.

---

## The bigger vision

Every document created from now can be AI-first from scratch.

  Every research paper    → AI-readable layer baked in at publish time
  Every resume            → semantic layer the LLM reads directly
  Every contract          → key-value layer APIs parse without a lawyer
  Every product manual    → structured layer any AI assistant queries
  Every Google Sheet      → data layer APIs consume without scraping

The moat: once enough people author in this format, and once enough
ATS/AI systems support the SDK, you own the standard.
That's how Adobe won. That's how Figma won.
First mover on a format is a massive defensible position.

---

## Build plan

### Stack
  Core engine     →  Python
  Viewer / web    →  TypeScript
  Add-ins         →  Google Apps Script + Office JS

### V1 scope (start here — Python)
  - Take any existing PDF
  - Auto-generate clean Markdown layer
  - Embed Markdown inside same file (PDF metadata or attached file)
  - Detection: checks HOW file was opened → serves right layer
  - No new editor needed
  - No chunking (that's a V3 problem)
  - Prove it works end to end with a resume
