/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  trailingSlash: true,
  // Keep the trailing-slash URLs but let API route handlers answer both
  // /api/backtest and /api/backtest/ directly. Without this, Next returns a
  // 308 before the POST handler runs.
  skipTrailingSlashRedirect: true,
  // Every strategy now lives at /strategies/<slug>; keep old links working.
  async redirects() {
    return [
      { source: "/research", destination: "/strategies/", permanent: true },
      { source: "/research/:slug*", destination: "/strategies/:slug*", permanent: true },
    ];
  },
};

export default nextConfig;
