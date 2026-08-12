import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const backendBase = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

// Only these routes issue redirects meant for the browser itself to follow
// (Google's consent screen, then back to the frontend's callback page).
// Everything else is a plain fetch/XHR call from our own JS, where a
// redirect (e.g. FastAPI's trailing-slash 307) is just an implementation
// detail that should be resolved server-side, not relayed to the browser.
const BROWSER_REDIRECT_PATHS = ["/api/v1/auth/google/login", "/api/v1/auth/google/callback"];

// FastAPI routers mounted with these prefixes define their collection route
// as `@router.{method}("/")`, so the backend only accepts the trailing-slash
// form and 307/308-redirects otherwise. Next.js itself strips the trailing
// slash before this handler ever runs, so we add it back here. This avoids
// ever having to "follow" that backend redirect for a POST: doing so
// requires resending the request body, and Node's fetch has a long-standing
// bug detaching the ArrayBuffer backing a Buffer body on redirect-replay.
const REQUIRES_TRAILING_SLASH = new Set(["/api/v1/chat", "/api/v1/documents"]);

async function proxy(req: NextRequest): Promise<Response> {
  const pathname = REQUIRES_TRAILING_SLASH.has(req.nextUrl.pathname)
    ? `${req.nextUrl.pathname}/`
    : req.nextUrl.pathname;
  const target = `${backendBase}${pathname}${req.nextUrl.search}`;
  const isBrowserRedirect = BROWSER_REDIRECT_PATHS.some((p) => req.nextUrl.pathname.startsWith(p));
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (lower === "host" || lower === "connection") return;
    headers.set(key, value);
  });

  const publicHost = req.headers.get("host") || "";
  if (publicHost) {
    headers.set("x-forwarded-host", publicHost);
  }
  const proto = req.headers.get("x-forwarded-proto") || req.nextUrl.protocol.replace(":", "") || "http";
  headers.set("x-forwarded-proto", proto);

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: isBrowserRedirect ? "manual" : "follow",
    cache: "no-store",
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    // Buffer the body instead of piping the raw ReadableStream through.
    // A live stream can only be read once, so if the backend responds with
    // a redirect (e.g. FastAPI's trailing-slash 307 on POST /chat), fetch's
    // "follow" mode cannot replay it to the redirected request and throws,
    // which previously surfaced to users as a bare 500 on chat/upload.
    // A Buffer has no such restriction and can be resent safely.
    init.body = Buffer.from(await req.arrayBuffer());
  }

  const upstream = await fetch(target, init);
  const responseHeaders = new Headers(upstream.headers);
  // Avoid compressed body mismatches when streaming through Next.
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("transfer-encoding");

  // Rewrite same-backend redirect Locations (e.g. FastAPI's trailing-slash
  // redirect) from the internal backend URL to a browser-reachable path.
  // External redirects (Google OAuth) are left untouched so the browser
  // navigates to them directly.
  const location = responseHeaders.get("location");
  if (location && location.startsWith(backendBase)) {
    responseHeaders.set("location", location.slice(backendBase.length) || "/");
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

async function handle(req: NextRequest): Promise<Response> {
  return proxy(req);
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
export const OPTIONS = handle;
export const HEAD = handle;
