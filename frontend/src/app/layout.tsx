import type { Metadata, Viewport } from "next";
import "./globals.css";
import { TelegramProvider } from "@/context/telegram";
import { LanguageProvider } from "@/context/language";

export const metadata: Metadata = {
  title: "TeleDock",
  description: "Premium Telegram utilities for Uzbekistan",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#0ea5e9",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">
        <TelegramProvider>
          <LanguageProvider>
            {children}
          </LanguageProvider>
        </TelegramProvider>
      </body>
    </html>
  );
}
