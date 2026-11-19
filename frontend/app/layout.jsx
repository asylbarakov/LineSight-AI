import "./globals.css";

export const metadata = {
  title: "LineSight AI",
  description: "Видеоаналитика инфраструктуры",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
