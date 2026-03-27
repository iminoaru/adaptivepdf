/**
 * Client-side extraction of the markdown layer from a .off file.
 * .off files are valid PDFs with markdown embedded as a file attachment.
 */

const OFF_ATTACHMENT_KEY = "_off_markdown_layer";

export async function extractMarkdownFromOff(pdfBytes: Uint8Array): Promise<string> {
  const pdfjsLib = await import("pdfjs-dist");
  pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.mjs";

  const doc = await pdfjsLib.getDocument({ data: pdfBytes.slice() }).promise;
  const attachments = (await doc.getAttachments()) as Record<
    string, { filename: string; content: Uint8Array }
  > | null;

  if (!attachments || !attachments[OFF_ATTACHMENT_KEY]) {
    throw new Error("No markdown layer found.");
  }

  return new TextDecoder().decode(attachments[OFF_ATTACHMENT_KEY].content);
}
