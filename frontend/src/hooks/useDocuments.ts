"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { apiFetch, apiUpload, ApiError } from "@/lib/api";
import type { Document, DocumentListResponse } from "@/types";

const ACTIVE_STATUSES = new Set(["pending", "processing"]);
const POLL_INTERVAL_MS = 2000;

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const documentsRef = useRef(documents);
  documentsRef.current = documents;

  const fetchDocuments = useCallback(async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
    silent?: boolean;
  }) => {
    const silent = params?.silent === true;
    if (!silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const query = new URLSearchParams();
      if (params?.status) query.set("status", params.status);
      if (params?.limit) query.set("limit", String(params.limit));
      if (params?.offset) query.set("offset", String(params.offset));
      const qs = query.toString();
      const data = await apiFetch<DocumentListResponse>(`/documents/${qs ? `?${qs}` : ""}`);
      setDocuments(data.documents);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  // Poll while any document is still being ingested so UI leaves "Processing" promptly.
  useEffect(() => {
    const hasActive = documents.some((d) => ACTIVE_STATUSES.has(d.status));
    if (!hasActive) return;

    const timer = window.setInterval(() => {
      void fetchDocuments({ silent: true });
    }, POLL_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [documents, fetchDocuments]);

  const uploadDocument = async (file: File): Promise<Document> => {
    const doc = await apiUpload<Document>("/documents/upload", file);
    setDocuments((prev) => {
      const without = prev.filter((d) => d.id !== doc.id);
      return [doc, ...without];
    });
    setTotal((prev) => (documentsRef.current.some((d) => d.id === doc.id) ? prev : prev + 1));
    await fetchDocuments({ silent: true });
    return doc;
  };

  const deleteDocument = async (id: string) => {
    try {
      await apiFetch(`/documents/${id}`, { method: "DELETE" });
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        throw err;
      }
    }
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    setTotal((prev) => Math.max(0, prev - 1));
  };

  const reindex = async () => {
    await apiFetch("/documents/reindex", { method: "POST" });
    await fetchDocuments({ silent: true });
  };

  const clearAll = async (): Promise<{ deleted_documents: number; deleted_conversations: number }> => {
    const result = await apiFetch<{ deleted_documents: number; deleted_conversations: number }>(
      "/documents/clear",
      { method: "DELETE" },
    );
    setDocuments([]);
    setTotal(0);
    return result;
  };

  return {
    documents,
    total,
    loading,
    error,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    reindex,
    clearAll,
  };
}
