import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    externalDir: true,
  },
  async rewrites() {
    return [
      // Proxy /api/incidents/* → backend de incidencias (puerto 8010)
      {
        source: "/api/incidents/:path*",
        destination: "http://127.0.0.1:8010/api/incidents/:path*",
      },
    ];
  },
};

export default nextConfig;
