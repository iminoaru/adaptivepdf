"use client";

interface Stats {
  raw_blocks: number;
  final_blocks: number;
  tables: number;
  images: number;
  lines: number;
  chars: number;
}

export function StatsBar({ stats }: { stats: Stats }) {
  const items = [
    { label: "blocks", value: stats.final_blocks },
    { label: "lines", value: stats.lines },
    { label: "chars", value: stats.chars.toLocaleString() },
    ...(stats.tables > 0 ? [{ label: "tables", value: stats.tables }] : []),
    ...(stats.images > 0 ? [{ label: "images", value: stats.images }] : []),
  ];

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      {items.map((item) => (
        <span key={item.label} style={{ fontSize: 11, color: "var(--text-muted)" }}>
          <span style={{ color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums" }}>
            {item.value}
          </span>{" "}
          {item.label}
        </span>
      ))}
    </div>
  );
}
