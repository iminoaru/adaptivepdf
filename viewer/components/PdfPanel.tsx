"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  pdfBytes: Uint8Array;
}

export function PdfPanel({ pdfBytes }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [pageCount, setPageCount] = useState(0);
  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        // Worker served as a static file from /public to avoid Turbopack bundling issues
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.mjs";

        // Slice to get a fresh copy — pdf.js transfers (detaches) the ArrayBuffer
        // to its worker, which breaks on re-renders (React Strict Mode runs effects twice).
        const doc = await pdfjsLib.getDocument({ data: pdfBytes.slice() }).promise;
        if (cancelled) return;

        setPageCount(doc.numPages);

        const container = containerRef.current;
        if (!container) return;
        container.innerHTML = "";

        for (let i = 1; i <= doc.numPages; i++) {
          if (cancelled) return;
          const page = await doc.getPage(i);
          const viewport = page.getViewport({ scale: 1.6 });

          const wrapper = document.createElement("div");
          wrapper.style.cssText = `
            background: white;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            margin: 16px auto;
            width: fit-content;
          `;

          const canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          canvas.style.display = "block";

          wrapper.appendChild(canvas);
          container.appendChild(wrapper);

          const ctx = canvas.getContext("2d")!;
          await page.render({ canvasContext: ctx, viewport }).promise;
        }
      } catch (e) {
        if (!cancelled) setError("Could not render PDF.");
        console.error(e);
      }
    }

    render();
    return () => { cancelled = true; };
  }, [pdfBytes]);

  if (error) {
    return (
      <div style={{ padding: 24, fontSize: 13, color: "var(--text-secondary)" }}>
        {error}
      </div>
    );
  }

  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
        background: "var(--bg)",
        padding: "8px 0",
      }}
    >
      <div ref={containerRef} />
      {pageCount === 0 && (
        <div style={{ padding: 24, fontSize: 13, color: "var(--text-muted)" }}>
          rendering…
        </div>
      )}
    </div>
  );
}
