import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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