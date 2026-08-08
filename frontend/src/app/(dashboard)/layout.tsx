"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/auth";
import { useAuth } from "@/hooks/useAuth";
import Sidebar from "@/components/layout/Sidebar";
import { ChatProvider } from "@/hooks/useChat";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const activeView = pathname?.startsWith("/documents") ? "documents" : "chat";

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace("/login");
    }
  }, [router]);

  const handleViewChange = (view: "chat" | "documents") => {
    router.push(view === "chat" ? "/chat" : "/documents");
  };

  // Remount chat state whenever the signed-in account changes (per-account isolation).
  return (
    <ChatProvider key={user?.id ?? "signed-out"}>
      <div className="flex h-screen overflow-hidden">
        <Sidebar activeView={activeView} onViewChange={handleViewChange} />
        <main className="flex-1 flex flex-col overflow-hidden">{children}</main>
      </div>
    </ChatProvider>
  );
}
