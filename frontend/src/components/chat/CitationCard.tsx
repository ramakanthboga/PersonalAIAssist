"use client";

import { useMemo, useState } from "react";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";

interface Citation {
  document: string;
  page: number;
  chunk: string;
}

interface CitationCardProps {
  citations: Citation[];
}

interface GroupedSource {
  document: string;
  pages: number[];
  preview: string;
  count: number;
}

function shortName(name: string, max = 48): string {
  const base = name.replace(/\.[^.]+$/i, "").replace(/[_-]+/g, " ").trim();
  return base.length <= max ? base : `${base.slice(0, max - 1).trim()}…`;
}

function formatPages(pages: number[]): string {
  if (pages.length === 0) return "";
  if (pages.length === 1) return `p. ${pages[0]}`;
  if (pages.length <= 4) return `pp. ${pages.join(", ")}`;
  return `pp. ${pages.slice(0, 3).join(", ")} +${pages.length - 3}`;
}

function groupCitations(citations: Citation[]): GroupedSource[] {
  const map = new Map<string, { pages: Set<number>; preview: string; count: number }>();

  for (const c of citations) {
    const key = c.document || "Unknown document";
    let entry = map.get(key);
    if (!entry) {
      entry = { pages: new Set(), preview: c.chunk || "", count: 0 };
      map.set(key, entry);
    }
    if (c.page > 0) entry.pages.add(c.page);
    entry.count += 1;
    if (!entry.preview && c.chunk) entry.preview = c.chunk;
  }

  return Array.from(map.entries()).map(([document, { pages, preview, count }]) => ({
    document,
    pages: Array.from(pages).sort((a, b) => a - b),
    preview,
    count,
  }));
}

export default function CitationCard({ citations }: CitationCardProps) {
  const groups = useMemo(() => groupCitations(citations), [citations]);
  const [expanded, setExpanded] = useState(false);

  if (!citations || citations.length === 0) return null;

  const visible = expanded ? groups : groups.slice(0, 3);
  const hiddenCount = groups.length - visible.length;

  return (
    <div className="mt-3 max-w-[80%]">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-[hsl(var(--muted-foreground))]">
        Sources
      </p>
      <ul className="space-y-1.5">
        {visible.map((g) => (
          <li key={g.document} className="group relative">
            <div className="flex items-start gap-2 rounded-md border border-[hsl(var(--border))]/80 bg-[hsl(var(--background))]/40 px-3 py-2 text-[13px] leading-snug">
              <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[hsl(var(--muted-foreground))]" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-[hsl(var(--foreground))]" title={g.document}>
                  {shortName(g.document)}
                </p>
                {g.pages.length > 0 && (
                  <p className="mt-0.5 text-[12px] text-[hsl(var(--muted-foreground))]">
                    {formatPages(g.pages)}
                  </p>
                )}
              </div>
            </div>

            {g.preview && (
              <div
                className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-80 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--background))] p-3 shadow-xl group-hover:block"
                role="tooltip"
              >
                <p className="mb-1 text-[12px] font-medium leading-snug text-[hsl(var(--foreground))]">
                  {shortName(g.document, 64)}
                  {g.pages.length > 0 ? ` · ${formatPages(g.pages)}` : ""}
                </p>
                <p className="text-[12px] leading-relaxed text-[hsl(var(--muted-foreground))] line-clamp-5">
                  {g.preview}
                </p>
              </div>
            )}
          </li>
        ))}
      </ul>

      {groups.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-1.5 inline-flex items-center gap-1 text-[12px] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" />
              Show fewer
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              {hiddenCount} more source{hiddenCount === 1 ? "" : "s"}
            </>
          )}
        </button>
      )}
    </div>
  );
}
