import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ToastProvider } from "@/components/Toast";
import { ThemeProvider } from "@/components/ThemeProvider";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "LineSight AI — инспекция ЛЭП",
  description: "Анализ видео облёта линий электропередачи",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <meta name="color-scheme" content="dark light" />
        <link rel="preload" href="/fonts/Onest-Variable.ttf" as="font" type="font/ttf" crossOrigin="anonymous" />
        <script id="linesight-theme" dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans antialiased">
        <ThemeProvider><ToastProvider>{children}</ToastProvider></ThemeProvider>
      </body>
    </html>
  );
}
