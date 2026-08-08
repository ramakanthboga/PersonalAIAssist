"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useDocuments } from "@/hooks/useDocuments";
import { useChat } from "@/hooks/useChat";
import DocumentCard from "./DocumentCard";
import UploadZone from "./UploadZone";
import { persistScope } from "@/components/chat/DocumentScopeSelector";
import { RefreshCw, FileText, Trash2 } from "lucide-react";

export default function DocumentList() {
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const router = useRouter();
  const {
    documents,
    total,
    loading,
    error,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    reindex,
    clearAll,
  } = useDocuments();
  const { clearLocalChatState, newConversation } = useChat();

  const handleAsk = (documentId: string) => {
    persistScope([documentId]);
    newConversation();
    router.push("/chat");
  };

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleUpload = async (file: File) => {
    await uploadDocument(file);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this document? This cannot be undone.")) return;
    setDeleteError(null);
    try {
      await deleteDocument(id);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete document");
    }
  };

  const handleReindex = async () => {
    if (confirm("Re-index all documents? This may take a while.")) {
      await reindex();
      await fetchDocuments();
    }
  };

  const handleClearAll = async () => {
    if (
      !confirm(
        "Clear ALL documents and chat history? Search index will be wiped. This cannot be undone.",
      )
    ) {
      return;
    }
    setDeleteError(null);
    setClearing(true);
    try {
      await clearAll();
      clearLocalChatState();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to clear data");
    } finally {
      setClearing(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b px-6 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-medium">Documents</h2>
          <span className="rounded-full bg-[hsl(var(--muted))] px-2 py-0.5 text-xs">
            {total}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleClearAll}
            disabled={clearing || total === 0}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10 transition disabled:opacity-40"
            title="Delete all documents and chat history"
          >
            <Trash2 className="h-3.5 w-3.5" /> Clear all
          </button>
          <button
            onClick={handleReindex}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs hover:bg-[hsl(var(--accent))] transition"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Re-index
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-thin">
        <UploadZone onUpload={handleUpload} />

        {error && (
          <div className="rounded-md bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {deleteError && (
          <div className="rounded-md bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
            {deleteError}
          </div>
        )}

        {loading && documents.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-[hsl(var(--muted-foreground))]">
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <FileText className="h-12 w-12 text-[hsl(var(--muted-foreground))] mb-3" />
            <p className="text-sm font-medium">No documents yet</p>
            <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
              Upload PDFs, Word docs, spreadsheets, or images to get started
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <DocumentCard
                key={doc.id}
                document={doc}
                onDelete={handleDelete}
                onAsk={handleAsk}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
