import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Security headers now handled in middleware for environment-aware behavior
  async rewrites() {
    return [
      // Disguise Vercel Analytics endpoint to avoid ad blockers
      {
        source: '/va/:path*',
        destination: 'https://congressalpha.vercel.app/_vercel/insights/:path*',
      },
      // Disguise Vercel Speed Insights endpoint to avoid ad blockers
      {
        source: '/vs/:path*',
        destination: 'https://congressalpha.vercel.app/_vercel/speed-insights/:path*',
      },
    ];
  },
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