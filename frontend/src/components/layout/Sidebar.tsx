"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, FileText, Plus, Trash2, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useChat } from "@/hooks/useChat";
import type { Conversation } from "@/types";

interface SidebarProps {
  activeView: "chat" | "documents";
  onViewChange: (view: "chat" | "documents") => void;
}

export default function Sidebar({ activeView, onViewChange }: SidebarProps) {
  const { user, logout } = useAuth();
  const {
    conversations,
    fetchConversations,
    deleteConversation,
    newConversation,
    activeConversation,
    fetchMessages,
    clearLocalChatState,
  } = useChat();
  const router = useRouter();

  // Load only this account's conversations (API is already user-scoped).
  useEffect(() => {
    if (!user?.id) {
      clearLocalChatState();
      return;
    }
    clearLocalChatState();
    void fetchConversations();
  }, [user?.id, fetchConversations, clearLocalChatState]);

  const handleLogout = () => {
    clearLocalChatState();
    logout();
    router.push("/login");
  };

  const handleSelectConversation = (conversationId: string) => {
    if (activeView !== "chat") {
      onViewChange("chat");
    }
    void fetchMessages(conversationId);
  };

  return (
    <aside className="flex h-full w-64 flex-col border-r bg-[hsl(var(--muted)/0.3)]">
      <div className="flex items-center gap-2 border-b p-4">
        <FileText className="h-5 w-5 text-blue-500" />
        <span className="font-semibold text-sm">PersonalAIAssist</span>
      </div>

      <div className="flex gap-1 p-2">
        <button
          onClick={() => onViewChange("chat")}
          className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition ${
            activeView === "chat" ? "bg-blue-600 text-white" : "hover:bg-[hsl(var(--accent))]"
          }`}
        >
          <MessageSquare className="inline h-3.5 w-3.5 mr-1" /> Chat
        </button>
        <button
          onClick={() => onViewChange("documents")}
          className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition ${
            activeView === "documents" ? "bg-blue-600 text-white" : "hover:bg-[hsl(var(--accent))]"
          }`}
        >
          <FileText className="inline h-3.5 w-3.5 mr-1" /> Docs
        </button>
      </div>

      {activeView === "chat" && (
        <>
          <button
            onClick={newConversation}
            className="mx-2 mt-1 flex items-center gap-2 rounded-md border border-dashed px-3 py-2 text-xs hover:bg-[hsl(var(--accent))] transition"
          >
            <Plus className="h-3.5 w-3.5" /> New Chat
          </button>

          <nav className="flex-1 overflow-y-auto p-2 space-y-0.5 scrollbar-thin">
            {conversations.map((conv: Conversation) => (
              <div
                key={conv.id}
                className={`group flex items-center justify-between rounded-md px-3 py-2 text-xs cursor-pointer transition ${
                  activeConversation === conv.id
                    ? "bg-[hsl(var(--accent))]"
                    : "hover:bg-[hsl(var(--accent)/0.5)]"
                }`}
                onClick={() => handleSelectConversation(conv.id)}
              >
                <span className="truncate flex-1">{conv.title || "Untitled"}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-[hsl(var(--muted-foreground))] hover:text-red-400 transition"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </nav>
        </>
      )}

      {activeView === "documents" && <div className="flex-1" />}

      <div className="border-t p-3 flex items-center justify-between">
        <span className="text-xs text-[hsl(var(--muted-foreground))] truncate">
          {user?.email}
        </span>
        <button onClick={handleLogout} className="text-[hsl(var(--muted-foreground))] hover:text-red-400 transition">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
