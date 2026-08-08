"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronDown, FileText, Layers, Search, X } from "lucide-react";
import type { Document } from "@/types";

const SCOPE_STORAGE_KEY = "pai.chat.documentScope";

/** Empty array = all documents; otherwise selected document IDs. */
export type DocumentScope = string[];

interface DocumentScopeSelectorProps {
  documents: Document[];
  value: DocumentScope;
  onChange: (scope: DocumentScope) => void;
  disabled?: boolean;
}

function displayName(doc: Document): string {
  return doc.original_filename || doc.filename || "Untitled";
}

function shortName(name: string, max = 40): string {
  const base = name.replace(/\.[^.]+$/i, "").replace(/[_-]+/g, " ").trim();
  return base.length <= max ? base : `${base.slice(0, max - 1).trim()}…`;
}

/** Normalize legacy single-id / "all" storage into string[]. */
export function loadStoredScope(): DocumentScope {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(SCOPE_STORAGE_KEY);
    if (!raw || raw === "all") return [];
    if (raw.startsWith("[")) {
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed)) {
        return parsed.filter((x): x is string => typeof x === "string" && x.length > 0);
      }
      return [];
    }
    // Legacy: single document id string
    return [raw];
  } catch {
    return [];
  }
}

export function persistScope(scope: DocumentScope): void {
  if (typeof window === "undefined") return;
  try {
    if (!scope.length) {
      sessionStorage.setItem(SCOPE_STORAGE_KEY, "all");
    } else {
      sessionStorage.setItem(SCOPE_STORAGE_KEY, JSON.stringify(scope));
    }
  } catch {
    // ignore quota / private mode
  }
}

export default function DocumentScopeSelector({
  documents,
  value,
  onChange,
  disabled = false,
}: DocumentScopeSelectorProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const completed = useMemo(
    () => documents.filter((d) => d.status === "completed"),
    [documents],
  );

  const selectedSet = useMemo(() => new Set(value), [value]);
  const selectedDocs = useMemo(
    () => completed.filter((d) => selectedSet.has(d.id)),
    [completed, selectedSet],
  );

  // Drop deleted / incomplete ids from selection
  useEffect(() => {
    if (value.length === 0 || completed.length === 0) return;
    const valid = value.filter((id) => completed.some((d) => d.id === id));
    if (valid.length !== value.length) {
      onChange(valid);
      persistScope(valid);
    }
  }, [value, completed, onChange]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return completed;
    return completed.filter((d) => displayName(d).toLowerCase().includes(q));
  }, [completed, query]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setQuery("");
      }
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (open) {
      window.setTimeout(() => searchRef.current?.focus(), 0);
    }
  }, [open]);

  const commit = (next: DocumentScope) => {
    onChange(next);
    persistScope(next);
  };

  const selectAll = () => {
    commit([]);
  };

  const toggleDoc = (id: string) => {
    if (selectedSet.has(id)) {
      commit(value.filter((x) => x !== id));
    } else {
      commit([...value, id]);
    }
  };

  const label =
    selectedDocs.length === 0
      ? completed.length === 0
        ? "No documents ready"
        : `All documents (${completed.length})`
      : selectedDocs.length === 1
        ? shortName(displayName(selectedDocs[0]), 36)
        : `${selectedDocs.length} documents selected`;

  const title =
    selectedDocs.length === 0
      ? label
      : selectedDocs.map((d) => displayName(d)).join(", ");

  const isScoped = selectedDocs.length > 0;

  return (
    <div ref={rootRef} className="relative">
      <div className="flex flex-wrap items-center gap-2">
        <span className="shrink-0 text-[11px] font-semibold uppercase tracking-wide text-[hsl(var(--muted-foreground))]">
          Search in
        </span>
        <button
          type="button"
          disabled={disabled || completed.length === 0}
          onClick={() => setOpen((v) => !v)}
          className={`inline-flex max-w-full items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px] transition ${
            isScoped
              ? "border-sky-500/40 bg-sky-500/10 text-[hsl(var(--foreground))]"
              : "border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 text-[hsl(var(--foreground))]"
          } hover:bg-[hsl(var(--accent))] disabled:opacity-40`}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-multiselectable="true"
        >
          {isScoped ? (
            <FileText className="h-3.5 w-3.5 shrink-0 text-sky-400" />
          ) : (
            <Layers className="h-3.5 w-3.5 shrink-0 text-[hsl(var(--muted-foreground))]" />
          )}
          <span className="truncate font-medium" title={title}>
            {label}
          </span>
          <ChevronDown
            className={`h-3.5 w-3.5 shrink-0 text-[hsl(var(--muted-foreground))] transition ${open ? "rotate-180" : ""}`}
          />
        </button>

        {isScoped && (
          <button
            type="button"
            onClick={selectAll}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[12px] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition"
            title="Search all documents"
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        )}
      </div>

      {open && (
        <div
          className="absolute bottom-full left-0 z-30 mb-2 w-[min(100vw-2rem,24rem)] overflow-hidden rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--background))] shadow-xl"
          role="listbox"
          aria-multiselectable="true"
        >
          <div className="border-b border-[hsl(var(--border))] p-2 space-y-2">
            <div className="flex items-center gap-2 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/30 px-2.5 py-1.5">
              <Search className="h-3.5 w-3.5 shrink-0 text-[hsl(var(--muted-foreground))]" />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter documents…"
                className="w-full bg-transparent text-[13px] outline-none placeholder:text-[hsl(var(--muted-foreground))]"
              />
            </div>
            <p className="px-0.5 text-[11px] text-[hsl(var(--muted-foreground))]">
              Select one or more documents. Leave none checked to search all.
            </p>
          </div>

          <ul className="max-h-64 overflow-y-auto py-1 scrollbar-thin">
            <li>
              <button
                type="button"
                role="option"
                aria-selected={!isScoped}
                onClick={selectAll}
                className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] transition ${
                  !isScoped ? "bg-sky-500/10" : "hover:bg-[hsl(var(--muted))]/50"
                }`}
              >
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                    !isScoped
                      ? "border-sky-400 bg-sky-500/20 text-sky-300"
                      : "border-[hsl(var(--border))]"
                  }`}
                >
                  {!isScoped && <Check className="h-3 w-3" />}
                </span>
                <Layers className="h-3.5 w-3.5 shrink-0 text-[hsl(var(--muted-foreground))]" />
                <span className="flex-1 font-medium">All documents</span>
                <span className="text-[11px] text-[hsl(var(--muted-foreground))]">{completed.length}</span>
              </button>
            </li>

            {filtered.length === 0 ? (
              <li className="px-3 py-4 text-center text-[12px] text-[hsl(var(--muted-foreground))]">
                No matching documents
              </li>
            ) : (
              filtered.map((doc) => {
                const active = selectedSet.has(doc.id);
                return (
                  <li key={doc.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={active}
                      onClick={() => toggleDoc(doc.id)}
                      className={`flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] transition ${
                        active ? "bg-sky-500/10" : "hover:bg-[hsl(var(--muted))]/50"
                      }`}
                    >
                      <span
                        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${
                          active
                            ? "border-sky-400 bg-sky-500/20 text-sky-300"
                            : "border-[hsl(var(--border))]"
                        }`}
                      >
                        {active && <Check className="h-3 w-3" />}
                      </span>
                      <FileText className="h-3.5 w-3.5 shrink-0 text-sky-400" />
                      <span className="min-w-0 flex-1 truncate" title={displayName(doc)}>
                        {displayName(doc)}
                      </span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>

          <div className="flex items-center justify-between border-t border-[hsl(var(--border))] px-3 py-2">
            <span className="text-[11px] text-[hsl(var(--muted-foreground))]">
              {isScoped ? `${selectedDocs.length} selected` : "Searching all"}
            </span>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setQuery("");
              }}
              className="rounded-md bg-sky-600 px-2.5 py-1 text-[12px] font-medium text-white hover:bg-sky-500 transition"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
