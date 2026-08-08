"use client";

import MarkdownContent from "./MarkdownContent";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
}

export default function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[min(80%,42rem)] rounded-2xl px-4 py-3.5 ${
          isUser
            ? "bg-blue-600 text-white text-[15px] leading-relaxed"
            : "bg-[hsl(var(--muted))] text-[hsl(var(--foreground))] shadow-sm ring-1 ring-white/5"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <MarkdownContent content={content} />
        )}
      </div>
    </div>
  );
}
