import type { NextConfig } from "next";

// The app talks to the Fineprint API through this same origin, so one URL (or
// one share link) serves both. Point FINEPRINT_API_URL elsewhere if needed.
const API_URL = process.env.FINEPRINT_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
