import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  /** Recharts pulls patterns that break without transpilation in some Next/webpack builds. */
  transpilePackages: ["recharts"],
};

export default nextConfig;
