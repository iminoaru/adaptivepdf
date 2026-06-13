# Adaptive PDF (pdx)

PDX is an experiment in making one document useful to both people and machines.

A person should be able to open a document and see the original PDF. An AI system or text extractor should be able to read a clean Markdown layer from the same file. The author keeps control of both versions instead of relying on a model to reconstruct the document later.

This repository contains the working prototype. The broader idea and the reasoning behind it are in [vision.md](vision.md) which I did with claude at 1AM out of curiosity.

## What works today

The prototype can:

- convert a regular PDF into structured Markdown;
- preserve headings, lists, emphasis, tables, code, and images where possible;
- embed the Markdown as a PDF attachment;
- expose the Markdown through PDF `ActualText` for compatible text extractors;
- open the visual PDF and Markdown side by side in a browser;
- let the Markdown be edited before exporting the combined document;

The output is still a valid PDF. Normal PDF readers show the original visual document, while supported tools can read the embedded Markdown layer.

This is an early prototype, not a published file standard. PDF extraction is heuristic, so complicated layouts and scanned documents will still need manual correction.

## Repository

`pdx/` contains the Python converter, format reader and writer, FastAPI service.

`viewer/` contains the Next.js viewer and editor.


## Run it locally

The backend requires Python 3.12 and `uv`.

```bash
cd pdx
uv sync
uv run uvicorn api:app --reload --port 8000
```

Start the viewer in another terminal:

```bash
cd viewer
npm install
npm run dev
```

Open `http://localhost:3000` and drop in a PDF. The viewer uses `http://localhost:8000` by default. Set `NEXT_PUBLIC_API_URL` if the API is running elsewhere.


## License

Copyright (c) 2026 Sarthak. No license is currently granted.

The source is public for inspection, but commercial use, redistribution, and derivative work require permission unless a license is added later. A commercial licensing model is still being decided.

