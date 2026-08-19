import type { Metadata, Viewport } from "next";
import Script from "next/script";
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

const THEME_SCRIPT = `
(function(){
  try {
    // Single source of truth, identical to the useTheme hook:
    // 'theme' in localStorage is 'light' | 'dark' | 'system' (default system).
    var t = localStorage.getItem('theme');
    var mode = (t === 'light' || t === 'dark' || t === 'system') ? t : 'system';
    var dark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var root = document.documentElement;
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    root.classList.toggle('dark', dark);
    function paintBody() {
      if (!document.body) return;
      document.body.classList.toggle('dark-theme', dark);
      document.body.classList.toggle('light-theme', !dark);
    }
    // This script runs from <head> before <body> exists; defer body classes.
    if (document.body) paintBody();
    else document.addEventListener('DOMContentLoaded', paintBody);
  } catch(e) {}
})()
`;

const SW_REGISTER = `
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('/sw.js').then(function(registration) {
      console.log('SW registered:', registration.scope);
    }).catch(function(error) {
      console.log('SW registration failed:', error);
    });
  });
}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" data-scroll-behavior="smooth" suppressHydrationWarning
      className={`${vazirmatn.variable} ${jetbrainsMono.variable}`}>
      <head>
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="بازار" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
      </head>
      <body className="antialiased font-sans" suppressHydrationWarning>
        <Script id="theme-init" strategy="beforeInteractive" dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <Script id="sw-register" strategy="afterInteractive" dangerouslySetInnerHTML={{ __html: SW_REGISTER }} />
        <Providers>
          <NotificationProvider>{children}</NotificationProvider>
        </Providers>
      </body>
    </html>
  );
}
