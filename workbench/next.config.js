/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep Turbopack anchored to the directory that owns this app's package.json.
  turbopack: {
    root: process.cwd(),
  },
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Allow large file uploads (PDFs can be big)
  middlewareClientMaxBodySize: "100mb",
  // Increase proxy timeout for long-running RAG queries (Ollama is slow)
  httpAgentOptions: {
    keepAlive: true,
    timeout: 300000, // 5 minutes
  },
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
