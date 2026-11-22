import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  experimental: {
    // Limit worker concurrency during static page generation to prevent OS commit exhaustion on high core-count hosts
    cpus: process.env.CI ? 2 : 2,
  },
};

export default nextConfig;
