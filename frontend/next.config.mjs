// API_INTERNAL_URL читается при сборке: rewrites фиксируются в манифесте маршрутов.
const apiUrl = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
