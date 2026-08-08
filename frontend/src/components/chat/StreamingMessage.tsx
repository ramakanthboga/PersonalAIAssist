"use client";

import { Loader2 } from "lucide-react";
import MarkdownContent from "./MarkdownContent";

interface StreamingMessageProps {
  content: string;
  isStreaming: boolean;
}

export default function StreamingMessage({ content, isStreaming }: StreamingMessageProps) {
  return (
    <div className="flex gap-3 justify-start">
      <div className="max-w-[min(80%,42rem)] rounded-2xl px-4 py-3.5 bg-[hsl(var(--muted))] shadow-sm ring-1 ring-white/5">
        {content ? (
          <div className="relative">
            <MarkdownContent content={content} />
            {isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-sky-500 animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        ) : isStreaming ? (
          <div className="flex items-center gap-2 text-[15px] text-[hsl(var(--muted-foreground))]">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
