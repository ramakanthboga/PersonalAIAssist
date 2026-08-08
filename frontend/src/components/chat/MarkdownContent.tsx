"use client";

import type { ReactNode } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cleanAssistantContent } from "@/lib/chatContent";

const markdownClassName = [
  "chat-md text-[15px] leading-[1.65] text-[hsl(var(--foreground))]",
  "[&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
  "[&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:tracking-tight",
  "[&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:tracking-tight",
  "[&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:text-[15px] [&_h3]:font-semibold",
  "[&_p]:my-2.5",
  "[&_ul]:my-2.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1",
  "[&_ol]:my-2.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:space-y-1",
  "[&_li]:leading-[1.6]",
  "[&_strong]:font-semibold [&_strong]:text-[hsl(var(--foreground))]",
  "[&_a]:text-sky-400 [&_a]:underline [&_a]:underline-offset-2",
  "[&_code]:rounded [&_code]:bg-black/35 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[13px] [&_code]:text-sky-300",
  "[&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-black/35 [&_pre]:p-3",
  "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-[13px]",
  "[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-[hsl(var(--border))] [&_blockquote]:pl-3 [&_blockquote]:text-[hsl(var(--muted-foreground))]",
  "[&_hr]:my-4 [&_hr]:border-[hsl(var(--border))]",
  "[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-[13px]",
  "[&_th]:border [&_th]:border-[hsl(var(--border))] [&_th]:bg-black/25 [&_th]:px-2.5 [&_th]:py-1.5 [&_th]:text-left [&_th]:font-semibold",
  "[&_td]:border [&_td]:border-[hsl(var(--border))] [&_td]:px-2.5 [&_td]:py-1.5 [&_td]:align-top",
].join(" ");

/** Turn trailing [1] / [2] markers into compact citation badges. */
function withCitationMarks(text: string): ReactNode[] {
  const parts = text.split(/(\[\d+\])/g);
  if (parts.length === 1) return [text];

  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (!m) return part;
    return (
      <sup
        key={`cite-${i}-${m[1]}`}
        className="ml-0.5 inline-flex translate-y-[-1px] items-center rounded bg-sky-500/15 px-1 py-px text-[10px] font-semibold text-sky-300"
        title={`Source ${m[1]}`}
      >
        {m[1]}
      </sup>
    );
  });
}

function mapChildren(children: ReactNode): ReactNode {
  if (typeof children === "string") return withCitationMarks(children);
  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === "string") {
        return <span key={i}>{withCitationMarks(child)}</span>;
      }
      return child;
    });
  }
  return children;
}

const components: Components = {
  p: ({ children }) => <p>{mapChildren(children)}</p>,
  li: ({ children }) => <li>{mapChildren(children)}</li>,
  td: ({ children }) => <td>{mapChildren(children)}</td>,
};

interface MarkdownContentProps {
  content: string;
  /** Strip verbose inline RAG citations before render (assistant only). */
  cleanCitations?: boolean;
}

export default function MarkdownContent({
  content,
  cleanCitations = true,
}: MarkdownContentProps) {
  const text = cleanCitations ? cleanAssistantContent(content) : content;

  return (
    <div className={markdownClassName}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
