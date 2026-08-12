"use client";

import { useEffect, useState } from "react";
import { clearTokens } from "@/lib/auth";
import { API_BASE } from "@/lib/apiBase";

interface GoogleSignInButtonProps {
  label?: string;
}

/**
 * Always visible Gmail / Google sign-in entry point.
 * Hits backend OAuth start URL; backend returns 503 if credentials are missing.
 */
export default function GoogleSignInButton({
  label = "Continue with Google",
}: GoogleSignInButtonProps) {
  const [hint, setHint] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/providers`);
        if (!res.ok) {
          if (!cancelled) setHint("Google sign-in is temporarily unavailable.");
          return;
        }
        const data = (await res.json()) as { google?: boolean };
        if (!cancelled && !data.google) {
          setHint(
            "Google sign-in is not configured on the server. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, then restart the backend.",
          );
        }
      } catch {
        if (!cancelled) {
          setHint("Cannot reach the API.");
        }
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => {
          clearTokens();
          window.location.href = `${API_BASE}/auth/google/login`;
        }}
        className="flex w-full items-center justify-center gap-2 rounded-md border border-[hsl(var(--border))] bg-white px-4 py-2.5 text-sm font-medium text-gray-800 hover:bg-gray-100 transition"
      >
        <GoogleIcon />
        {checking ? "Continue with Google…" : label}
      </button>
      {hint && (
        <p className="text-[11px] leading-snug text-amber-400/90">{hint}</p>
      )}
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M12 10.2v3.6h5.1c-.2 1.2-1.5 3.6-5.1 3.6-3.1 0-5.6-2.5-5.6-5.6S8.9 6.2 12 6.2c1.8 0 3 .7 3.7 1.4l2.5-2.4C16.7 3.7 14.5 2.7 12 2.7 6.9 2.7 2.7 6.9 2.7 12S6.9 21.3 12 21.3c5.2 0 8.7-3.7 8.7-8.8 0-.6-.1-1-.2-1.5H12z"
      />
      <path
        fill="#34A853"
        d="M3.9 7.4 6.8 9.6C7.6 7.5 9.6 6.2 12 6.2c1.8 0 3 .7 3.7 1.4l2.5-2.4C16.7 3.7 14.5 2.7 12 2.7 8.3 2.7 5.1 4.8 3.9 7.4z"
      />
      <path
        fill="#4A90E2"
        d="M12 21.3c2.4 0 4.5-.8 6-2.2l-2.8-2.2c-.8.5-1.8.9-3.2.9-3.5 0-6.5-2.4-7.5-5.6L3.8 14.6C5 18.4 8.2 21.3 12 21.3z"
      />
      <path
        fill="#FBBC05"
        d="M4.5 12c0-.8.1-1.5.3-2.2L3.9 7.4C3.3 8.7 3 10.3 3 12s.3 3.3.9 4.6l2.9-2.2c-.2-.7-.3-1.4-.3-2.4z"
      />
    </svg>
  );
}
