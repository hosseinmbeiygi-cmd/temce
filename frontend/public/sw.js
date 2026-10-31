const CACHE_NAME = "iran-market-v1";
const STATIC_ASSETS = [
  "/",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

// S1 — سقف عمر دادهٔ مالی، **مشترک** با frontend/public/golddesk-sw.js.
// این فایل scope "/" دارد و همهٔ صفحه‌های غیر /gold را کنترل می‌کند. چون
// CacheStorage در یک origin بین دو Service Worker مشترک است، اگر روزی این
// شاخه cache-first شود می‌تواند ورودیِ کش‌شده توسط SW طلا (یا نسخهٔ قدیمی
// خودش) را سرو کند. قاعدهٔ ثابت در هر دو فایل:
//   ۱) پاسخ /api/v1/gold/* هرگز از cache خوانده و در cache نوشته نمی‌شود؛
//   ۲) هر کشی از دادهٔ مالی باید همین عدد را رعایت کند.
// تست‌ها: frontend/src/__tests__/GoldSwBoundary.test.ts
const FINANCIAL_MAX_AGE_MS = 300_000;
const GOLD_API_PREFIX = "/api/v1/gold/";

function offlineJson() {
  return new Response(
    JSON.stringify({
      error: "Offline",
      financial_max_age_ms: FINANCIAL_MAX_AGE_MS,
    }),
    { status: 503, headers: { "Content-Type": "application/json" } }
  );
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // دادهٔ مالی GoldDesk: همیشه شبکه، هرگز cache (S1).
  if (url.pathname.startsWith(GOLD_API_PREFIX)) {
    event.respondWith(fetch(request).catch(() => offlineJson()));
    return;
  }

  // Network-first for API calls
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request).catch(() => offlineJson()));
    return;
  }

  // Cache-first for static assets
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});
