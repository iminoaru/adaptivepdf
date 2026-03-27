/**
 * Adaptive PDF — Google Docs Add-on
 *
 * Exports the current Google Doc as a Smart PDF where:
 * - Humans see the formatted PDF
 * - Machines (LLMs, extractors) get clean markdown
 */

const API_URL = "https://adaptivepdf.onrender.com";

function onInstall(e) {
  onOpen(e);
}

function onOpen(e) {
  DocumentApp.getUi()
    .createMenu("Adaptive PDF")
    .addItem("Export as Smart PDF", "showSidebar")
    .addToUi();
}

function showSidebar() {
  const html = HtmlService.createHtmlOutputFromFile("Sidebar")
    .setTitle("Adaptive PDF");
  DocumentApp.getUi().showSidebar(html);
}

// ─── Document → Markdown ───────────────────────────────────────────

function docToMarkdown() {
  const doc = DocumentApp.getActiveDocument();
  const body = doc.getBody();
  const numChildren = body.getNumChildren();
  const lines = [];
  let prevType = null;

  for (let i = 0; i < numChildren; i++) {
    const el = body.getChild(i);
    const type = el.getType();

    if (type === DocumentApp.ElementType.PARAGRAPH) {
      const para = el.asParagraph();
      const heading = para.getHeading();

      // Detect code blocks: consecutive fully-monospace paragraphs
      if (heading === DocumentApp.ParagraphHeading.NORMAL && isFullyMonospace(para)) {
        const codeLines = [para.getText()];
        while (i + 1 < numChildren) {
          const next = body.getChild(i + 1);
          if (next.getType() === DocumentApp.ElementType.PARAGRAPH &&
              next.asParagraph().getHeading() === DocumentApp.ParagraphHeading.NORMAL &&
              isFullyMonospace(next.asParagraph())) {
            codeLines.push(next.asParagraph().getText());
            i++;
          } else {
            break;
          }
        }
        lines.push("```\n" + codeLines.join("\n") + "\n```");
        prevType = "code";
        continue;
      }

      const text = formatRuns(para);

      if (!text.trim()) {
        continue;
      }

      if (heading === DocumentApp.ParagraphHeading.HEADING1) {
        if (lines.length > 0) lines.push("---");
        lines.push("# " + text);
      } else if (heading === DocumentApp.ParagraphHeading.HEADING2) {
        if (lines.length > 0) lines.push("---");
        lines.push("## " + text);
      } else if (heading === DocumentApp.ParagraphHeading.HEADING3) {
        lines.push("### " + text);
      } else if (heading === DocumentApp.ParagraphHeading.HEADING4) {
        lines.push("#### " + text);
      } else if (heading === DocumentApp.ParagraphHeading.HEADING5) {
        lines.push("##### " + text);
      } else if (heading === DocumentApp.ParagraphHeading.HEADING6) {
        lines.push("###### " + text);
      } else {
        lines.push(text);
      }
      prevType = "paragraph";

    } else if (type === DocumentApp.ElementType.LIST_ITEM) {
      const item = el.asListItem();
      const glyph = item.getGlyphType();
      const nesting = item.getNestingLevel();
      const indent = "  ".repeat(nesting);
      const text = formatRuns(item);

      if (isOrderedGlyph(glyph)) {
        lines.push(indent + "1. " + text);
      } else {
        lines.push(indent + "- " + text);
      }
      prevType = "list";

    } else if (type === DocumentApp.ElementType.TABLE) {
      const table = el.asTable();
      lines.push(tableToMarkdown(table));
      prevType = "table";

    } else if (type === DocumentApp.ElementType.HORIZONTAL_RULE) {
      lines.push("---");
      prevType = "hr";

    } else if (type === DocumentApp.ElementType.INLINE_IMAGE) {
      lines.push("![Image]");
      prevType = "image";
    }
  }

  return lines.join("\n\n");
}

function formatRuns(element) {
  const text = element.editAsText();
  const full = text.getText();
  if (!full) return "";

  let result = "";
  let i = 0;

  while (i < full.length) {
    // Find the end of this run (same formatting)
    let j = i + 1;
    while (j < full.length &&
           text.isBold(j) === text.isBold(i) &&
           text.isItalic(j) === text.isItalic(i) &&
           text.isStrikethrough(j) === text.isStrikethrough(i) &&
           (text.getLinkUrl(j) || null) === (text.getLinkUrl(i) || null) &&
           isMonospace(text.getFontFamily(j)) === isMonospace(text.getFontFamily(i))) {
      j++;
    }

    let chunk = full.substring(i, j);
    const bold = text.isBold(i);
    const italic = text.isItalic(i);
    const strike = text.isStrikethrough(i);
    const link = text.getLinkUrl(i);
    const mono = isMonospace(text.getFontFamily(i));

    if (mono) {
      chunk = "`" + chunk + "`";
    } else {
      if (link) {
        chunk = "[" + chunk + "](" + link + ")";
      }
      if (bold && italic) {
        chunk = "***" + chunk + "***";
      } else if (bold) {
        chunk = "**" + chunk + "**";
      } else if (italic) {
        chunk = "*" + chunk + "*";
      }
      if (strike) {
        chunk = "~~" + chunk + "~~";
      }
    }

    result += chunk;
    i = j;
  }

  return result;
}

const MONO_FONTS = ["courier", "consolas", "monospace", "roboto mono", "source code", "fira code", "ibm plex mono", "jetbrains mono", "menlo", "monaco"];

function isMonospace(fontFamily) {
  if (!fontFamily) return false;
  const lower = fontFamily.toLowerCase();
  return MONO_FONTS.some(f => lower.includes(f));
}

function isFullyMonospace(element) {
  const text = element.editAsText();
  const full = text.getText();
  if (!full || !full.trim()) return false;
  for (let i = 0; i < full.length; i++) {
    if (!isMonospace(text.getFontFamily(i))) return false;
  }
  return true;
}

function isOrderedGlyph(glyph) {
  return glyph === DocumentApp.GlyphType.NUMBER ||
         glyph === DocumentApp.GlyphType.LATIN_UPPER ||
         glyph === DocumentApp.GlyphType.LATIN_LOWER ||
         glyph === DocumentApp.GlyphType.ROMAN_UPPER ||
         glyph === DocumentApp.GlyphType.ROMAN_LOWER;
}

function tableToMarkdown(table) {
  const rows = table.getNumRows();
  if (rows === 0) return "";

  const lines = [];

  for (let r = 0; r < rows; r++) {
    const row = table.getRow(r);
    const cells = [];
    for (let c = 0; c < row.getNumCells(); c++) {
      const cell = row.getCell(c);
      const cellText = formatRuns(cell.editAsText()).replace(/\n/g, " ").trim();
      cells.push(cellText);
    }
    lines.push("| " + cells.join(" | ") + " |");

    // Separator after header row
    if (r === 0) {
      lines.push("| " + cells.map(() => "---").join(" | ") + " |");
    }
  }

  return lines.join("\n");
}

// ─── Export Flow ───────────────────────────────────────────────────

function exportSmartPdf() {
  const doc = DocumentApp.getActiveDocument();
  const docId = doc.getId();
  const fileName = doc.getName();

  // 1. Convert doc structure to markdown
  const markdown = docToMarkdown();

  // 2. Export as PDF
  const pdfUrl = "https://docs.google.com/feeds/download/documents/export/Export?id=" +
                 docId + "&exportFormat=pdf";
  const pdfResponse = UrlFetchApp.fetch(pdfUrl, {
    headers: { Authorization: "Bearer " + ScriptApp.getOAuthToken() }
  });
  const pdfBytes = pdfResponse.getBlob().getBytes();
  const pdfBase64 = Utilities.base64Encode(pdfBytes);

  // 3. Send to API
  const boundary = "----AdaptivePDF" + Date.now();
  const payload = buildMultipartPayload(boundary, pdfBase64, markdown, fileName);

  const apiResponse = UrlFetchApp.fetch(API_URL + "/build-smart-pdf", {
    method: "post",
    contentType: "multipart/form-data; boundary=" + boundary,
    payload: payload,
    muteHttpExceptions: true
  });

  if (apiResponse.getResponseCode() !== 200) {
    throw new Error("API error: " + apiResponse.getContentText());
  }

  // 4. Save to Drive and return download link
  const smartPdfBlob = apiResponse.getBlob().setName(fileName + " (Smart).pdf");
  const file = DriveApp.createFile(smartPdfBlob);

  return {
    url: file.getUrl(),
    downloadUrl: "https://drive.google.com/uc?export=download&id=" + file.getId(),
    name: file.getName(),
    markdownPreview: markdown.substring(0, 500)
  };
}

function buildMultipartPayload(boundary, pdfBase64, markdown, fileName) {
  // We send the PDF as base64 and markdown as a form field
  let payload = "";

  // PDF file (base64 encoded)
  payload += "--" + boundary + "\r\n";
  payload += 'Content-Disposition: form-data; name="pdf_base64"\r\n\r\n';
  payload += pdfBase64 + "\r\n";

  // Markdown
  payload += "--" + boundary + "\r\n";
  payload += 'Content-Disposition: form-data; name="markdown"\r\n\r\n';
  payload += markdown + "\r\n";

  // Filename
  payload += "--" + boundary + "\r\n";
  payload += 'Content-Disposition: form-data; name="filename"\r\n\r\n';
  payload += fileName + "\r\n";

  payload += "--" + boundary + "--\r\n";
  return payload;
}

// ─── Preview Only ─────────────────────────────────────────────────

function previewMarkdown() {
  return docToMarkdown();
}
