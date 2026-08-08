"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { apiFetch } from "@/lib/api";
import type { Conversation, Message } from "@/types";

interface ChatContextValue {
  conversations: Conversation[];
  messages: Message[];
  activeConversation: string | null;
  loading: boolean;
  messagesLoading: boolean;
  fetchConversations: () => Promise<Conversation[]>;
  fetchMessages: (conversationId: string) => Promise<void>;
  deleteConversation: (conversationId: string) => Promise<void>;
  addLocalMessage: (message: Message) => void;
  newConversation: () => void;
  setActiveConversation: (id: string | null) => void;
  clearLocalChatState: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

function normalizeMessages(data: unknown): Message[] {
  if (Array.isArray(data)) return data as Message[];
  if (data && typeof data === "object" && Array.isArray((data as { messages?: unknown }).messages)) {
    return (data as { messages: Message[] }).messages;
  }
  return [];
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [messagesLoading, setMessagesLoading] = useState(false);

  const fetchConversations = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<Conversation[]>("/chat/conversations");
      const list = Array.isArray(data) ? data : [];
      setConversations(list);
      return list;
    } catch {
      return [] as Conversation[];
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMessages = useCallback(async (conversationId: string) => {
    setActiveConversation(conversationId);
    setMessagesLoading(true);
    try {
      const data = await apiFetch<Message[]>(`/chat/conversations/${conversationId}`);
      setMessages(normalizeMessages(data));
    } catch {
      setMessages([]);
    } finally {
      setMessagesLoading(false);
    }
  }, []);

  const deleteConversation = useCallback(async (conversationId: string) => {
    await apiFetch(`/chat/conversations/${conversationId}`, { method: "DELETE" });
    setConversations((prev) => prev.filter((c) => c.id !== conversationId));
    setActiveConversation((current) => {
      if (current === conversationId) {
        setMessages([]);
        return null;
      }
      return current;
    });
  }, []);

  const addLocalMessage = useCallback((message: Message) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  const newConversation = useCallback(() => {
    setActiveConversation(null);
    setMessages([]);
  }, []);

  const clearLocalChatState = useCallback(() => {
    setConversations([]);
    setMessages([]);
    setActiveConversation(null);
  }, []);

  return (
    <ChatContext.Provider
      value={{
        conversations,
        messages,
        activeConversation,
        loading,
        messagesLoading,
        fetchConversations,
        fetchMessages,
        deleteConversation,
        addLocalMessage,
        newConversation,
        setActiveConversation,
        clearLocalChatState,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return ctx;
}
