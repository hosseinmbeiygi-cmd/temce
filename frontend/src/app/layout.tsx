import type { Metadata, Viewport } from "next";
import "./globals.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

const queryClient = new QueryClient();

export const metadata: Metadata = {
  title: "Iran Market Platform — Quant Research & Backtesting",
  description: "Comprehensive quant research, backtesting, and simulation platform for Iran capital markets.",
  keywords: ["quant", "backtesting", "Iran market", "TSE", "algorithmic trading"],
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased font-sans">
        <QueryClientProvider client={queryClient}>
          <Toaster position="top-right" richColors />
          {children}
        </QueryClientProvider>
      </body>
    </html>
  );
}
