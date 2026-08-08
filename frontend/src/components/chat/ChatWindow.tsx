"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import { Send, StopCircle } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useStreaming } from "@/hooks/useStreaming";
import { useDocuments } from "@/hooks/useDocuments";
import MessageBubble from "./MessageBubble";
import StreamingMessage from "./StreamingMessage";
import CitationCard from "./CitationCard";
import DocumentScopeSelector, {
  loadStoredScope,
  persistScope,
  type DocumentScope,
} from "./DocumentScopeSelector";
import type { Citation, Document } from "@/types";

function parseCitations(raw: string | undefined): Citation[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function shortDocName(name: string, max = 36): string {
  const base = name.replace(/\.[^.]+$/i, "").replace(/[_-]+/g, " ").trim();
  return base.length <= max ? base : `${base.slice(0, max - 1).trim()}…`;
}

function buildSuggestionChips(scope: DocumentScope, docs: Document[]): string[] {
  const completed = docs.filter((d) => d.status === "completed");

  if (completed.length === 0) {
    return [
      "Suggest prompts I can ask",
      "What documents do I have?",
      "How do I upload a document?",
    ];
  }

  const scoped = scope.length
    ? completed.filter((d) => scope.includes(d.id))
    : [];

  if (scoped.length === 1) {
    const name = shortDocName(scoped[0].original_filename);
    return [
      `Summarize ${name}`,
      `List the key points in ${name} with brief examples`,
      `What questions can I ask about ${name}?`,
    ];
  }

  if (scoped.length > 1) {
    const names = scoped.slice(0, 2).map((d) => shortDocName(d.original_filename, 24));
    return [
      `Compare key themes across: ${names.join(" and ")}`,
      "Summarize the selected documents",
      "Suggest prompts I can ask about the selected documents",
    ];
  }

  if (completed.length === 1) {
    const name = shortDocName(completed[0].original_filename);
    return [
      `Summarize ${name}`,
      `List the key points in ${name} with brief examples`,
      "Suggest prompts I can ask",
    ];
  }

  return [
    "Summarize my documents",
    "What documents do I have?",
    "Compare the main themes across my documents",
    "Suggest prompts I can ask",
  ];
}

export default function ChatWindow() {
  const [input, setInput] = useState("");
  const [scope, setScope] = useState<DocumentScope>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scopeHydrated = useRef(false);

  const {
    messages,
    activeConversation,
    messagesLoading,
    addLocalMessage,
    fetchConversations,
    fetchMessages,
  } = useChat();

  const { documents, fetchDocuments } = useDocuments();
  const { streamingText, isStreaming, startStream, stopStream } = useStreaming();

  useEffect(() => {
    void fetchDocuments({ silent: true, limit: 200 });
  }, [fetchDocuments]);

  // Restore last scope once docs are available
  useEffect(() => {
    if (scopeHydrated.current) return;
    if (documents.length === 0) return;
    scopeHydrated.current = true;
    const stored = loadStoredScope();
    if (stored.length === 0) return;
    const ok = stored.filter((id) =>
      documents.some((d) => d.id === id && d.status === "completed"),
    );
    if (ok.length) setScope(ok);
  }, [documents]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const completedDocs = useMemo(
    () => documents.filter((d) => d.status === "completed"),
    [documents],
  );

  const selectedDocs = useMemo(
    () => completedDocs.filter((d) => scope.includes(d.id)),
    [scope, completedDocs],
  );

  const handleScopeChange = (next: DocumentScope) => {
    setScope(next);
    persistScope(next);
  };

  const sendText = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;

    setInput("");

    addLocalMessage({
      id: `temp-${Date.now()}`,
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    });

    const conversationIdBefore = activeConversation;

    await startStream(trimmed, {
      conversationId: conversationIdBefore ?? undefined,
      documentIds: scope.length > 0 ? scope : undefined,
      onComplete: async (fullText) => {
        addLocalMessage({
          id: `temp-${Date.now()}-assistant`,
          role: "assistant",
          content: fullText,
          created_at: new Date().toISOString(),
        });
        const convs = await fetchConversations();
        if (!conversationIdBefore && convs[0]) {
          await fetchMessages(convs[0].id);
        }
      },
      onError: (error) => {
        addLocalMessage({
          id: `temp-${Date.now()}-error`,
          role: "assistant",
          content: error,
          created_at: new Date().toISOString(),
        });
      },
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await sendText(input);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const showEmpty = messages.length === 0 && !isStreaming && !messagesLoading;
  const chips = buildSuggestionChips(scope, documents);

  const placeholder =
    selectedDocs.length === 1
      ? `Ask about ${shortDocName(selectedDocs[0].original_filename, 28)}…`
      : selectedDocs.length > 1
        ? `Ask about the ${selectedDocs.length} selected documents…`
        : "Ask about your documents… (or type: suggest prompts)";

  const emptyTitle =
    selectedDocs.length === 1
      ? `Ask about ${shortDocName(selectedDocs[0].original_filename, 42)}`
      : selectedDocs.length > 1
        ? `Ask about ${selectedDocs.length} selected documents`
        : "Ask anything about your documents";

  const emptyHint =
    selectedDocs.length === 1
      ? "Answers are limited to this file. Use Search in to add more files or search all."
      : selectedDocs.length > 1
        ? "Answers are limited to the documents you checked. Clear the filter to search everything."
        : "Check one or more documents under Search in to focus retrieval, or leave All documents selected.";

  return (
    <div className="flex flex-1 flex-col h-full min-h-0">
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4 scrollbar-thin min-h-0">
        {messagesLoading && messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-sm text-[hsl(var(--muted-foreground))]">
            Loading conversation...
          </div>
        )}

        {showEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <h2 className="text-xl font-semibold mb-2 tracking-tight">{emptyTitle}</h2>
            <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-md mb-6 leading-relaxed">
              {emptyHint}
            </p>
            <div className="flex flex-wrap justify-center gap-2 max-w-xl">
              {chips.map((chip) => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => void sendText(chip)}
                  className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--muted))]/40 px-3 py-2 text-left text-[13px] leading-snug hover:bg-[hsl(var(--accent))] transition max-w-xs"
                >
                  {chip}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => {
          const citations = msg.role === "assistant" ? parseCitations(msg.citations) : [];
          return (
            <div key={msg.id}>
              <MessageBubble role={msg.role as "user" | "assistant"} content={msg.content} />
              {citations.length > 0 && <CitationCard citations={citations} />}
            </div>
          );
        })}

        {isStreaming && (
          <StreamingMessage content={streamingText} isStreaming={isStreaming} />
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="border-t px-4 py-3 shrink-0 space-y-2.5">
        <DocumentScopeSelector
          documents={documents}
          value={scope}
          onChange={handleScopeChange}
          disabled={isStreaming}
        />

        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder={placeholder}
            className="flex-1 resize-none rounded-xl border bg-transparent px-4 py-3 text-[15px] leading-relaxed focus:outline-none focus:ring-2 focus:ring-sky-500/60 max-h-32"
            style={{ minHeight: "44px" }}
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={stopStream}
              className="rounded-xl bg-red-600 p-3 text-white hover:bg-red-700 transition"
            >
              <StopCircle className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="rounded-xl bg-blue-600 p-3 text-white hover:bg-blue-700 disabled:opacity-30 transition"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
