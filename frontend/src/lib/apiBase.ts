/**
 * Browser-facing API base.
 * Default is same-origin `/api/v1` (Next.js rewrites proxy to FastAPI),
 * so Cloudflare Tunnel / HTTPS frontends do not call http://localhost:8000.
 */
export const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "/api/v1");
