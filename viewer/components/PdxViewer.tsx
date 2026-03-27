"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { PdfPanel } from "./PdfPanel";
import { MarkdownPanel } from "./MarkdownPanel";
import { OptionsPanel } from "./OptionsPanel";
import { StatsBar } from "./StatsBar";
import { extractMarkdownFromOff } from "@/lib/extractLayers";
import { convertPdf, downloadOff, downloadMd, DEFAULT_OPTIONS, ConvertOptions, ConvertResult } from "@/lib/api";

interface LoadedDoc {
  pdfBytes: Uint8Array;
  pdfFile?: File;  // original File object, needed for /package
  markdown: string;
  filename: string;
  stats?: ConvertResult["stats"];
}

type Status = "idle" | "loading" | "ready" | "error";

export function PdxViewer() {
  const [status, setStatus] = useState<Status>("idle");
  const [doc, setDoc] = useState<LoadedDoc | null>(null);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [options, setOptions] = useState<ConvertOptions>(DEFAULT_OPTIONS);
  const [showOptions, setShowOptions] = useState(false);
  const [packaging, setPackaging] = useState(false);

  // Auto-load a staged .off file when opened via double-click (?load=<id>)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sid = params.get("load");
    if (!sid) return;
    // Clear the query param so refresh doesn't reload
    window.history.replaceState({}, "", window.location.pathname);
    setStatus("loading");
    fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/staged/${sid}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.error) throw new Error(data.error);
        const binary = atob(data.pdf_b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        setDoc({ pdfBytes: bytes, markdown: data.markdown, filename: data.filename });
        setStatus("ready");
      })
      .catch((e) => {
        setError(e.message);
        setStatus("error");
      });
  }, []);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setStatus("loading");
      setError("");
      try {
        const buf = await file.arrayBuffer();
        const pdfBytes = new Uint8Array(buf);
        try {
          // Try to read markdown attachment — works for smart PDFs
          const markdown = await extractMarkdownFromOff(pdfBytes.slice());
          setDoc({ pdfBytes, markdown, filename: file.name });
          setStatus("ready");
        } catch {
          // No attachment — regular PDF, convert it
          const result = await convertPdf(file, options);
          setDoc({ pdfBytes, pdfFile: file, markdown: result.markdown, filename: result.filename, stats: result.stats });
          setStatus("ready");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed. Is the API running?");
        setStatus("error");
      }
    },
    [options]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const reset = () => {
    setStatus("idle");
    setDoc(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  if (status === "ready" && doc) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
        {/* Topbar */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "0 20px", height: 48, borderBottom: "1px solid var(--border)",
          background: "var(--surface)", flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.04em" }}>pdx</span>
            <span style={{ color: "var(--text-muted)", fontSize: 13 }}>{doc.filename}</span>
            {doc.stats && <StatsBar stats={doc.stats} />}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {doc.pdfFile && (
              <button
                onClick={async () => {
                  setPackaging(true);
                  try { await downloadOff(doc.pdfFile!, doc.markdown); }
                  catch (e) { alert(e instanceof Error ? e.message : "Failed"); }
                  finally { setPackaging(false); }
                }}
                style={ghostBtn}
                disabled={packaging}
              >
                {packaging ? "packaging…" : "export smart PDF"}
              </button>
            )}
            <button onClick={() => downloadMd(doc.markdown, doc.filename)} style={ghostBtn}>
              download .md
            </button>
            <button onClick={reset} style={ghostBtn}>open another</button>
          </div>
        </div>

        {/* Column headers */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          borderBottom: "1px solid var(--border)", background: "var(--surface)", flexShrink: 0,
        }}>
          {[
            { badge: "PDF", label: "human layer", bg: "var(--pdf-badge)", color: "var(--pdf-badge-text)" },
            { badge: "MD", label: "AI layer", bg: "var(--md-badge)", color: "var(--md-badge-text)" },
          ].map(({ badge, label, bg, color }, i) => (
            <div key={badge} style={{
              padding: "8px 20px", display: "flex", alignItems: "center", gap: 8,
              borderRight: i === 0 ? "1px solid var(--border)" : "none",
            }}>
              <span style={{ fontSize: 11, fontWeight: 500, background: bg, color, padding: "1px 7px", borderRadius: 3, letterSpacing: "0.03em" }}>
                {badge}
              </span>
              <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{label}</span>
            </div>
          ))}
        </div>

        {/* Side-by-side panels */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", flex: 1, minHeight: 0 }}>
          <div style={{ borderRight: "1px solid var(--border)", overflow: "hidden" }}>
            <PdfPanel pdfBytes={doc.pdfBytes} />
          </div>
          <div style={{ overflow: "hidden" }}>
            <MarkdownPanel
              markdown={doc.markdown}
              onChange={(md) => setDoc((d) => d ? { ...d, markdown: md } : d)}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: "100vh", display: "flex" }}>
      {/* Left: drop zone */}
      <div style={{
        flex: 1, display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center", gap: 0,
      }}>
        <div style={{ marginBottom: 36, textAlign: "center" }}>
          <div style={{ fontSize: 28, fontWeight: 300, letterSpacing: "0.12em" }}>pdx</div>
          <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 4 }}>adaptive document viewer</div>
        </div>

        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          style={{
            width: 340, height: 190,
            border: `1.5px dashed ${dragging ? "var(--accent)" : "var(--border-strong)"}`,
            borderRadius: 8,
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8,
            cursor: "pointer",
            background: dragging ? "var(--accent-light)" : "var(--surface)",
            transition: "all 0.15s ease",
          }}
        >
          {status === "loading" ? (
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              {doc === null ? "converting…" : "reading layers…"}
            </span>
          ) : (
            <>
              <div style={{ fontSize: 13, fontWeight: 500 }}>drop a PDF</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>or click to browse</div>
              <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
                {["smart PDF → view layers", "regular PDF → convert"].map((t) => (
                  <span key={t} style={{
                    fontSize: 10, color: "var(--text-muted)", background: "var(--accent-light)",
                    padding: "2px 7px", borderRadius: 3,
                  }}>{t}</span>
                ))}
              </div>
            </>
          )}
        </div>

        {status === "error" && (
          <div style={{ marginTop: 14, fontSize: 12, color: "#c0392b", maxWidth: 340, textAlign: "center" }}>
            {error}
          </div>
        )}

        <input ref={inputRef} type="file" accept=".pdf" style={{ display: "none" }} onChange={onFileChange} />
      </div>

      {/* Right: options panel */}
      <div style={{
        width: 280, borderLeft: "1px solid var(--border)", background: "var(--surface)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)" }}>
          <div style={{ fontSize: 12, fontWeight: 600, letterSpacing: "0.03em" }}>Converter options</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>applied when converting a PDF</div>
        </div>
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          <OptionsPanel options={options} onChange={setOptions} />
        </div>
      </div>
    </div>
  );
}

const ghostBtn: React.CSSProperties = {
  fontSize: 12, color: "var(--text-secondary)", background: "none",
  border: "1px solid var(--border)", borderRadius: 4,
  padding: "3px 10px", cursor: "pointer", fontFamily: "inherit",
};
