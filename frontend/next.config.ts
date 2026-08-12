import type { NextConfig } from "next";

/** Kept for Docker/runtime reference; API proxy is handled by app/api/v1/[...path]. */
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    BACKEND_URL: backendUrl,
  },
};

export default nextConfig;
