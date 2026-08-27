import type { NextConfig } from "next";

const API = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname,
  },
  agentRules: false,
  async rewrites() {
    return [
      { source: "/api/backend/analyze", 
        destination: `${API}/analyze` 
      },
      {
        source: "/api/backend/inspect-workbook",
        destination: `${API}/inspect-workbook`,
      },
      { source: "/api/backend/health", 
        destination: `${API}/health` 
      },
      {
        source: "/api/backend/observability",
        destination: `${API}/observability`,
      },
      {
        source: "/api/backend/datasets/:path*",
        destination: `${API}/datasets/:path*`,
      },
    ];
  },
};

export default nextConfig;
