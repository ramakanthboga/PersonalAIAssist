/**
 * Clean assistant markdown for display: strip verbose RAG citation prose
 * the model sometimes embeds (full filenames + page numbers). Compact [n]
 * markers are kept — the Sources panel carries document/page details.
 */
export function cleanAssistantContent(content: string): string {
  if (!content) return content;

  let text = content;

  // (Source: anything.pdf, Page 10) — including truncated/variant forms
  text = text.replace(
    /\s*\(\s*Source\s*:\s*[^)]+?(?:,\s*Page\s*\d+)?\s*\)/gi,
    "",
  );

  // Trailing (Page 10) / (Pages 10–11) left over from older prompts
  text = text.replace(/\s*\(\s*Pages?\s*\d+(?:\s*[-–—]\s*\d+)?\s*\)/gi, "");

  // "Source: filename.pdf, Page 10" without parentheses (end of line / clause)
  text = text.replace(
    /\s*Source\s*:\s*[^\n]{0,120}?\.pdf\s*,?\s*Page\s*\d+/gi,
    "",
  );

  // Collapse leftover whitespace without destroying markdown structure
  text = text.replace(/[ \t]+\n/g, "\n");
  text = text.replace(/[ \t]{2,}/g, " ");
  text = text.replace(/\n{3,}/g, "\n\n");

  return text.trim();
}
