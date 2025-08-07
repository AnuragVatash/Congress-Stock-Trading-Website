import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Security headers now handled in middleware for environment-aware behavior
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'unitedstates.github.io',
        port: '',
        pathname: '/images/congress/**',
      },
    ],
  },
};

export default nextConfig;