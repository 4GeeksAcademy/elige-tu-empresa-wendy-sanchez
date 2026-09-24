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
      // Proxy /api/inventory/* → backend de inventario (puerto 8000)
      {
        source: "/api/inventory/:path*",
        destination: "http://127.0.0.1:8000/inventory/:path*",
      },
    ];
  },
};

export default nextConfig;
