// API_INTERNAL_URL читается при сборке: rewrites фиксируются в манифесте маршрутов.
const apiUrl = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  experimental: {
    // Загрузка видео идёт через rewrites. По умолчанию Next.js обрезает тело запроса на 10 МБ
    // (в логе: «Request body exceeded 10MB»), и API получает битый файл. Лимит API — MAX_UPLOAD_MB (500).
    middlewareClientMaxBodySize: "600mb",
    // Долгая загрузка большого файла не должна обрываться по таймауту прокси (мс).
    proxyTimeout: 600_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
