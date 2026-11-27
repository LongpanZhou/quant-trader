/** @type {import('next').NextConfig} */
const nextConfig = {
  images: { unoptimized: true },
  trailingSlash: true,
  // Keep the trailing-slash URLs but let API route handlers answer both
  // /api/backtest and /api/backtest/ directly. Without this, Next returns a
  // 308 before the POST handler runs.
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
