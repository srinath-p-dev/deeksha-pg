import type { NextConfig } from "next";

const API = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Produces a small self-contained server for the Docker image
  output: "standalone",
  poweredByHeader: false,
  // Tailwind CSS v4 runs as a Turbopack loader on .css files
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Dev convenience: browser calls to /api/* are forwarded to FastAPI so the
  // site and API share one origin (cookies just work, no CORS). In production,
  // Caddy routes /api/* to FastAPI before requests ever reach Next.js.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
