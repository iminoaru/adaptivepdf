export interface ConvertOptions {
  h1_ratio: number;
  h2_ratio: number;
  h3_ratio: number;
  all_caps_as_heading: boolean;
  exclude_dates: boolean;
  normalize_bullets: boolean;
  extract_images: boolean;
}

export interface ConvertResult {
  markdown: string;
  filename: string;
  stats: {
    raw_blocks: number;
    final_blocks: number;
    tables: number;
    images: number;
    lines: number;
    chars: number;
  };
}

export const DEFAULT_OPTIONS: ConvertOptions = {
  h1_ratio: 1.8,
  h2_ratio: 1.4,
  h3_ratio: 1.15,
  all_caps_as_heading: true,
  exclude_dates: true,
  normalize_bullets: true,
  extract_images: true,
};

export async function convertPdf(
  file: File,
  options: ConvertOptions
): Promise<ConvertResult> {
  const form = new FormData();
  form.append("file", file);
  Object.entries(options).forEach(([k, v]) => form.append(k, String(v)));

  const controller = new AbortController();
  // 5 min timeout for large PDFs
  const timer = setTimeout(() => controller.abort(), 5 * 60 * 1000);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${API}/convert`, {
    method: "POST",
    body: form,
    signal: controller.signal,
  }).finally(() => clearTimeout(timer));

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Conversion failed: ${err}`);
  }

  return res.json();
}

export async function downloadOff(file: File, markdown: string): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  form.append("markdown", markdown);

  const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const res = await fetch(`${API}/package`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Packaging failed: ${err}`);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? file.name;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadMd(markdown: string, filename: string): void {
  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.replace(/\.(pdf|off)$/i, ".md");
  a.click();
  URL.revokeObjectURL(url);
}
