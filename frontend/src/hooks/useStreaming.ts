"use client";

import { useState, useRef, useCallback } from "react";
import { getAccessToken, refreshAccessToken, clearTokens } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/** Drop stack traces / internal paths if a bad error ever reaches the client. */
function safeClientError(message: string): string {
  const text = (message || "").trim();
  if (!text) return "Something went wrong. Please try again.";
  const looksInternal =
    text.length > 400 ||
    /traceback|site-packages|file:\/\/\/|cursor-sdk-bridge|node:internal\/|\bat\s+\S+\s+\(/i.test(
      text,
    );
  if (looksInternal) {
    return "The AI service is temporarily unavailable. Please try again in a moment.";
  }
  return text;
}

export function useStreaming() {
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (
      message: string,
      options?: {
        conversationId?: string;
        documentId?: string;
        documentIds?: string[];
        onToken?: (token: string) => void;
        onComplete?: (fullText: string) => void;
        onError?: (error: string) => void;
      },
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setStreamingText("");
      setIsStreaming(true);

      let fullText = "";
      let streamHadError = false;

      const ids =
        options?.documentIds && options.documentIds.length > 0
          ? options.documentIds
          : options?.documentId
            ? [options.documentId]
            : null;

      const postChat = async () =>
        fetch(`${API_BASE}/chat/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getAccessToken()}`,
          },
          body: JSON.stringify({
            message,
            conversation_id: options?.conversationId || null,
            document_id: ids?.length === 1 ? ids[0] : null,
            document_ids: ids && ids.length > 0 ? ids : null,
            stream: true,
          }),
          signal: controller.signal,
        });

      try {
        let res = await postChat();

        if (res.status === 401) {
          const refreshed = await refreshAccessToken();
          if (refreshed) {
            res = await postChat();
          } else {
            clearTokens();
            if (typeof window !== "undefined") {
              window.location.href = "/login";
            }
            throw new Error("Session expired — please log in again");
          }
        }

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const detail =
            typeof body.detail === "string"
              ? body.detail
              : `Error ${res.status}`;
          throw new Error(safeClientError(detail));
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const payload = line.slice(6).trim();
            if (payload === "[DONE]") continue;

            try {
              const parsed = JSON.parse(payload);
              if (parsed.error) {
                streamHadError = true;
                options?.onError?.(safeClientError(String(parsed.error)));
                continue;
              }
              if (parsed.token) {
                fullText += parsed.token;
                setStreamingText(fullText);
                options?.onToken?.(parsed.token);
              }
            } catch {
              // skip malformed events
            }
          }
        }

        if (!streamHadError) {
          options?.onComplete?.(fullText);
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          options?.onError?.(
            safeClientError(err instanceof Error ? err.message : "Stream failed"),
          );
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [],
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { streamingText, isStreaming, startStream, stopStream };
}
