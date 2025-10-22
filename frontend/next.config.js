/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  swcMinify: true,
  // No rewrites needed anymore - we use Next.js API routes for proxying
  // The API routes handle backend URL detection and proxying dynamically
  // srcDir: 'src' // Explicitly set src directory for Next.js App Router
};

module.exports = nextConfig
