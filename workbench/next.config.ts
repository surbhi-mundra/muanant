import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // API proxy to the SOVEREIGN backend
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.SOVEREIGN_API_URL || "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
