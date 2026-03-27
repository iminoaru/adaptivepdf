"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  markdown: string;
  onChange: (md: string) => void;
}

export function MarkdownPanel({ markdown, onChange }: Props) {
  const [view, setView] = useState<"rendered" | "raw" | "edit">("rendered");

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Sub-toolbar */}
      <div
        style={{
          display: "flex",
          gap: 2,
          padding: "6px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface)",
          flexShrink: 0,
        }}
      >
        {(["rendered", "raw", "edit"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            style={{
              fontSize: 11,
              padding: "2px 10px",
              borderRadius: 3,
              border: "none",
              cursor: "pointer",
              fontFamily: "inherit",
              background: view === v ? "var(--accent)" : "transparent",
              color: view === v ? "white" : "var(--text-secondary)",
              transition: "all 0.1s",
            }}
          >
            {v}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
        {view === "rendered" ? (
          <div className="md-prose">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              urlTransform={(url) => url}
            >
              {markdown}
            </ReactMarkdown>
          </div>
        ) : view === "raw" ? (
          <pre
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 12,
              lineHeight: 1.65,
              color: "var(--text-primary)",
              background: "none",
              margin: 0,
              padding: 0,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {markdown}
          </pre>
        ) : (
          <textarea
            value={markdown}
            onChange={(e) => onChange(e.target.value)}
            spellCheck={false}
            style={{
              width: "100%",
              height: "100%",
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: 12,
              lineHeight: 1.65,
              color: "var(--text-primary)",
              background: "none",
              border: "none",
              outline: "none",
              resize: "none",
              padding: 0,
              margin: 0,
            }}
          />
        )}
      </div>
    </div>
  );
}
