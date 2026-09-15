// GoldDesk Service Worker — PWA offline-first
const CACHE_NAME = "golddesk-v1";
const STATIC_CACHE = "golddesk-static-v1";
const RUNTIME_CACHE = "golddesk-runtime-v1";

const STATIC_ASSETS = [
  "/gold",
  "/gold/portfolio",
  "/gold/analytics",
  "/gold/alerts",
  "/gold/backtest",
  "/gold/chat",
  "/gold/tokens",
  "/gold/settings",
  "/golddesk-manifest.json",
];

// ── Install: cache static shell ─────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        // ignore errors for not-yet-cached pages
      });
    })
  );
  self.skipWaiting();
});

// ── Activate: clean old caches ───────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== RUNTIME_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: network-first for /api, cache-first for /gold ──
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API: network first, fallback to cache
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request));
    return;
  }

  // GoldDesk pages: cache-first
  if (url.pathname.startsWith("/gold")) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Static assets: cache-first
  if (request.method === "GET") {
    event.respondWith(cacheFirst(request, RUNTIME_CACHE));
  }
});

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({ success: false, error: { message: "offline" } }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // fallback: return offline page if HTML
    if (request.headers.get("accept")?.includes("text/html")) {
      const cache = await caches.open(STATIC_CACHE);
      const offline = await cache.match("/gold");
      if (offline) return offline;
    }
    return new Response("Offline", { status: 503 });
  }
}

// ── Push notifications (future) ──────────────────────────
self.addEventListener("push", (event) => {
  if (!event.data) return;
  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || "GoldDesk", {
      body: data.body || "",
      icon: "/icons/golddesk-192.png",
      badge: "/icons/golddesk-192.png",
      data: { url: data.url || "/gold" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/gold";
  event.waitUntil(clients.openWindow(url));
});
