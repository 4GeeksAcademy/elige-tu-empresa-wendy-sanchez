import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    externalDir: true,
  },
  async rewrites() {
    return [
      // Proxy /api/incidents/* → Incidents API (nombre Docker: incidents-backend)
      {
        source: "/api/incidents/:path*",
        destination: "http://incidents-backend:8010/api/incidents/:path*",
      },
      // Proxy /api/inventory/* → HealthCore API (nombre Docker: backend)
      {
        source: "/api/inventory/:path*",
        destination: "http://backend:8000/inventory/:path*",
      },
    ];
  },
};

export default nextConfig;
