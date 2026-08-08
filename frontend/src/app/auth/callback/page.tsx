"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FileText, Loader2 } from "lucide-react";
import { setTokens } from "@/lib/auth";

/** Google OAuth lands here: /auth/callback#access_token=...&refresh_token=... */
export default function OAuthCallbackPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = typeof window !== "undefined" ? window.location.hash.replace(/^#/, "") : "";
    const query = typeof window !== "undefined" ? window.location.search.replace(/^\?/, "") : "";
    const params = new URLSearchParams(hash || query);

    const err = params.get("error");
    if (err) {
      setError(err);
      return;
    }

    const access = params.get("access_token");
    const refresh = params.get("refresh_token");
    if (!access || !refresh) {
      setError("Missing sign-in tokens. Please try Google sign-in again.");
      return;
    }

    setTokens(access, refresh);
    window.history.replaceState({}, document.title, "/auth/callback");
    router.replace("/chat");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4 text-center">
        <div className="flex justify-center">
          <FileText className="h-10 w-10 text-blue-500" />
        </div>
        {error ? (
          <>
            <h1 className="text-xl font-semibold">Sign-in failed</h1>
            <p className="text-sm text-red-400">{error}</p>
            <Link href="/login" className="inline-block text-sm text-blue-500 hover:underline">
              Back to Sign In
            </Link>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Completing Google sign-in…
          </div>
        )}
      </div>
    </div>
  );
}
