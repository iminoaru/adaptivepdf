"use client";

import { ConvertOptions } from "@/lib/api";

interface Props {
  options: ConvertOptions;
  onChange: (o: ConvertOptions) => void;
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}>
      <div
        onClick={() => onChange(!checked)}
        style={{
          width: 32,
          height: 18,
          borderRadius: 9,
          background: checked ? "var(--accent)" : "var(--border-strong)",
          position: "relative",
          flexShrink: 0,
          marginTop: 2,
          transition: "background 0.15s",
          cursor: "pointer",
        }}
      >
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: "white",
            position: "absolute",
            top: 3,
            left: checked ? 17 : 3,
            transition: "left 0.15s",
          }}
        />
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 1 }}>{hint}</div>}
      </div>
    </label>
  );
}

function Slider({
  label,
  hint,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 12, color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" }}>
          {value.toFixed(2)}×
        </span>
      </div>
      {hint && <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>{hint}</div>}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: "var(--accent)" }}
      />
    </div>
  );
}

export function OptionsPanel({ options, onChange }: Props) {
  const set = (patch: Partial<ConvertOptions>) => onChange({ ...options, ...patch });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 12 }}>
          Headings
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Slider
            label="H1 threshold"
            hint="Font ratio vs body to classify as H1"
            value={options.h1_ratio}
            min={1.3}
            max={2.5}
            step={0.05}
            onChange={(v) => set({ h1_ratio: v })}
          />
          <Slider
            label="H2 threshold"
            value={options.h2_ratio}
            min={1.1}
            max={1.9}
            step={0.05}
            onChange={(v) => set({ h2_ratio: v })}
          />
          <Slider
            label="H3 threshold"
            value={options.h3_ratio}
            min={1.05}
            max={1.5}
            step={0.05}
            onChange={(v) => set({ h3_ratio: v })}
          />
          <Toggle
            label="ALL CAPS → heading"
            hint="Bold all-caps lines become H2 regardless of size"
            checked={options.all_caps_as_heading}
            onChange={(v) => set({ all_caps_as_heading: v })}
          />
          <Toggle
            label="Exclude dates from headings"
            hint="Lines with date patterns are never classified as headings"
            checked={options.exclude_dates}
            onChange={(v) => set({ exclude_dates: v })}
          />
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 12 }}>
          Lists & Text
        </div>
        <Toggle
          label="Normalize bullets"
          hint="Convert all bullet chars (•, –, ▪) to -"
          checked={options.normalize_bullets}
          onChange={(v) => set({ normalize_bullets: v })}
        />
      </div>

      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: 12 }}>
          Images
        </div>
        <Toggle
          label="Extract images"
          hint="Embed images as base64 in Markdown — increases file size significantly"
          checked={options.extract_images}
          onChange={(v) => set({ extract_images: v })}
        />
      </div>
    </div>
  );
}
