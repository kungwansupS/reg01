import type { NextConfig } from "next";

// Server-side rewrite target (baked at build time for standalone output)
// In Docker: http://backend:5000 (via build arg)
// In dev: http://localhost:5000 (default)
const BACKEND_INTERNAL = process.env.BACKEND_INTERNAL_URL || "http://localhost:5000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_INTERNAL}/api/:path*` },
      { source: "/socket.io/:path*", destination: `${BACKEND_INTERNAL}/socket.io/:path*` },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
    ],
  },
};

export default nextConfig;
