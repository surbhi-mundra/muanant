/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep Turbopack anchored to the directory that owns this app's package.json.
  // This avoids resolving Next from the repository's parent workspace in preview.
  turbopack: {
    root: process.cwd(),
  },
  allowedDevOrigins: ["127.0.0.1", "localhost"],
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
