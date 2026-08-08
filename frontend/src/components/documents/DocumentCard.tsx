"use client";

import { FileText, Trash2, Clock, CheckCircle, AlertCircle, Loader2, MessageSquare } from "lucide-react";
import type { Document } from "@/types";

interface DocumentCardProps {
  document: Document;
  onDelete: (id: string) => void;
  onAsk?: (id: string) => void;
}

const STATUS_CONFIG = {
  pending: { icon: Clock, color: "text-yellow-400", label: "Pending" },
  processing: { icon: Loader2, color: "text-blue-400", label: "Processing" },
  completed: { icon: CheckCircle, color: "text-green-400", label: "Ready" },
  failed: { icon: AlertCircle, color: "text-red-400", label: "Failed" },
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function DocumentCard({ document: doc, onDelete, onAsk }: DocumentCardProps) {
  const statusInfo = STATUS_CONFIG[doc.status] || STATUS_CONFIG.pending;
  const StatusIcon = statusInfo.icon;
  const canAsk = doc.status === "completed" && !!onAsk;

  return (
    <div className="group flex items-center justify-between rounded-lg border p-3 hover:bg-[hsl(var(--muted)/0.3)] transition">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <FileText className="h-8 w-8 shrink-0 text-blue-400" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate">{doc.original_filename}</p>
          <div className="flex items-center gap-3 text-xs text-[hsl(var(--muted-foreground))]">
            <span>{formatFileSize(doc.file_size)}</span>
            <span>{formatDate(doc.created_at)}</span>
            {doc.status === "completed" && <span>{doc.chunk_count} chunks</span>}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className={`flex items-center gap-1 text-xs ${statusInfo.color}`}>
          <StatusIcon className={`h-3.5 w-3.5 ${doc.status === "processing" ? "animate-spin" : ""}`} />
          <span>{statusInfo.label}</span>
        </div>
        {canAsk && (
          <button
            type="button"
            onClick={() => onAsk(doc.id)}
            className="inline-flex items-center gap-1 rounded-md border border-[hsl(var(--border))] px-2 py-1 text-[12px] text-[hsl(var(--muted-foreground))] opacity-0 group-hover:opacity-100 hover:border-sky-500/40 hover:text-sky-300 transition"
            title="Ask about this document in Chat"
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Ask
          </button>
        )}
        <button
          type="button"
          onClick={() => onDelete(doc.id)}
          className="opacity-0 group-hover:opacity-100 text-[hsl(var(--muted-foreground))] hover:text-red-400 transition p-1"
          title="Delete document"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
