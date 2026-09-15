import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "./providers";
import { NotificationProvider } from "./notification-provider";

// Fonts are self-hosted (next/font/local) so the build never depends on
// fetching from Google Fonts — the app must build & run offline/behind
// restricted networks (Google domains are often unreachable in IR).
const vazirmatn = localFont({
  src: [
    { path: "../fonts/Vazirmatn-Light.woff2", weight: "300", style: "normal" },
    { path: "../fonts/Vazirmatn-Regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/Vazirmatn-Medium.woff2", weight: "500", style: "normal" },
    { path: "../fonts/Vazirmatn-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "../fonts/Vazirmatn-Bold.woff2", weight: "700", style: "normal" },
    { path: "../fonts/Vazirmatn-ExtraBold.woff2", weight: "800", style: "normal" },
    { path: "../fonts/Vazirmatn-Black.woff2", weight: "900", style: "normal" },
  ],
  display: "swap",
  variable: "--font-vazirmatn",
});

const jetbrainsMono = localFont({
  src: "../fonts/JetBrainsMono-wght.woff2",
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Iran Market Platform — Quant Research & Backtesting",
  description: "Comprehensive quant research, backtesting, and simulation platform for Iran capital markets.",
  keywords: ["quant", "backtesting", "Iran market", "TSE", "algorithmic trading"],
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "بازار",
  },
  formatDetection: {
    telephone: false,
  },
};

export const viewport: Viewport = {
  themeColor: "#0b1220",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" data-scroll-behavior="smooth" suppressHydrationWarning
      className={`${vazirmatn.variable} ${jetbrainsMono.variable}`}>
      <head>
        {/* Material Icons moved to self-hosted lucide-react to keep offline/IR capability */}
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="بازار" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
        <link rel="manifest" href="/golddesk-manifest.json" />
        <meta name="theme-color" content="#f59e0b" />
      </head>
      <body className="antialiased font-sans" suppressHydrationWarning>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:right-2 focus:z-[100] focus:rounded-lg focus:bg-card focus:px-4 focus:py-2 focus:text-ink focus:shadow-lg">
          پرش به محتوای اصلی
        </a>
        <Providers>
          <NotificationProvider>{children}</NotificationProvider>
        </Providers>
      </body>
    </html>
  );
}
