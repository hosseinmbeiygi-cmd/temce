// GoldDesk Service Worker — PWA با اولویت شبکه و TTL برای دادهٔ مالی.
//
// نسخهٔ قبلی هر پاسخ OK را روی /api/ بدون مهر زمانی در کش می‌گذاشت و در قطعی
// شبکه همان کش را بی‌قیدوشرط برمی‌گرداند؛ یعنی کاربر می‌توانست نرخِ دیروز را
// ببیند و همان‌جا تصمیم بگیرد (F9). این نسخه:
//   ۱) فقط /api/v1/gold/* را با network-first کش می‌کند و هر پاسخ را مهر می‌زند؛
//   ۲) پاسخ مالی کهنه‌تر از TTL را هرگز سرو نمی‌کند — حتی آفلاین باشیم؛
//   ۳) کش‌ها نسخه دارند تا ارتقا، ورودی بی‌مهرِ نسخهٔ قبل را دوباره مصرف نکند؛
//   ۴) به client ها خبر آفلاین/آنلاین/ردِ دادهٔ کهنه می‌فرستد تا بنر دقیق باشد.

// v2: ساختار ورودی کش عوض شد (مهر زمانی). نسخهٔ قبلی باید دور ریخته شود،
// وگرنه response های بی‌مهرِ v1 «کهنه» حساب شده و آفلاین هیچ داده‌ای نیست.
const CACHE_VERSION = "v2";
const STATIC_CACHE = `golddesk-static-${CACHE_VERSION}`;
const API_CACHE = `golddesk-api-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  "/gold",
  "/gold/futures",
  "/gold/options",
  "/gold/macro",
  "/gold/etf",
  "/gold/physical",
  "/gold/antigravity",
  "/gold/chat",
  "/gold/portfolio",
  "/gold/analytics",
  "/gold/alerts",
  "/gold/backtest",
  "/gold/tokens",
  "/gold/health",
  "/gold/settings",
  "/golddesk-manifest.json",
];

// پاسخ مالی نباید «تقریباً الان» باشد ولی ۳ روز کهنه. این عدد **سقف عمر مالی
// مشترک همهٔ Service Workerهاست** و `public/sw.js` هم همین نام و همین مقدار را
// اعلام می‌کند؛ تغییرش باید در هر دو فایل هم‌زمان انجام شود
// (تست: frontend/src/__tests__/GoldSwBoundary.test.ts).
// هم‌راستا با کادنس اسنپ‌شات کامل در C10 (هر ۳۰۰ ثانیه یک snapshot).
const FINANCIAL_MAX_AGE_MS = 300_000;

const GOLD_API_PREFIX = "/api/v1/gold/";
const CACHED_AT_HEADER = "x-golddesk-cached-at";

// ── Install: cache static shell ─────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS).catch(() => {
      // ignore errors for not-yet-cached pages
    }))
  );
});

// ── Activate: clean old caches ───────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== API_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  );
});

// ── Fetch ────────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== "GET") return;

  // دادهٔ مالی GoldDesk: network-first با کشِ مهرزده و آستانهٔ TTL
  if (url.pathname.startsWith(GOLD_API_PREFIX)) {
    event.respondWith(goldApiFirst(request));
    return;
  }

  // بقیهٔ API: هرگز کش نمی‌شود. کشیدن /api/v1/funds یا /api/v1/stocks همین‌جا
  // می‌تواند دادهٔ مالی کهنهٔ بخش‌های دیگر را هم سرو کند.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkOnly(request));
    return;
  }

  // GoldDesk pages: cache-first (اسکلت آفلاین)
  if (url.pathname.startsWith("/gold")) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Static assets: cache-first
  event.respondWith(cacheFirst(request, API_CACHE));
});

// ── helpers ──────────────────────────────────────────────

/** به همهٔ پنجره‌های باز پیام وضعیت می‌فرستد (بنر آفلاین UI از همین خبر می‌شود). */
function notify(type, extra) {
  if (!self.clients || !self.clients.matchAll) return;
  self.clients
    .matchAll({ type: "window", includeUncontrolled: true })
    .then((clients) => {
      for (const client of clients) {
        client.postMessage(Object.assign({ type: "golddesk:" + type }, extra || {}));
      }
    })
    .catch(() => {
      /* a client closing mid-push is not an error worth surfacing */
    });
}

/** پاسخ را با مهر زمانی بازمی‌سازد تا عمرش در کش قابل اندازه‌گیری باشد. */
async function stamp(response, at) {
  const body = await response.text();
  const headers = new Headers(response.headers);
  headers.set(CACHED_AT_HEADER, String(at));
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

/** عمر پاسخِ کش‌شده بر حسب میلی‌ثانیه؛ بدون مهر = بی‌نهایت (یعنی کهنه). */
function ageOf(response) {
  const raw = response.headers.get(CACHED_AT_HEADER);
  if (!raw) return Infinity;
  const at = Number(raw);
  if (!Number.isFinite(at)) return Infinity;
  return Date.now() - at;
}

function offlineJson(reason, status) {
  return new Response(JSON.stringify({ success: false, error: reason, offline: true }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function goldApiFirst(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const response = await fetch(request);
    notify("online");
    if (response.ok) {
      const stamped = await stamp(response, Date.now());
      cache.put(request, stamped.clone()).catch(() => undefined);
      return stamped;
    }
    return response;
  } catch (err) {
    notify("offline");
    const cached = await cache.match(request);
    if (!cached) return offlineJson("offline", 503);
    const age = ageOf(cached);
    if (age <= FINANCIAL_MAX_AGE_MS) return cached;
    // داده هست ولی کهنه‌تر از TTL است: سروش نکن، و صریح خبر بده.
    notify("stale-refused", { age_ms: age });
    return offlineJson("offline_stale", 504);
  }
}

async function networkOnly(request) {
  try {
    return await fetch(request);
  } catch (err) {
    notify("offline");
    return offlineJson("offline", 503);
  }
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone()).catch(() => undefined);
    }
    return response;
  } catch (err) {
    // fallback: return offline page if HTML
    if (request.headers.get("accept")?.includes("text/html")) {
      const shell = await caches.match("/gold");
      if (shell) return shell;
    }
    return new Response("Offline", { status: 503 });
  }
}

// ── Push notifications ───────────────────────────────────
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
  event.waitUntil(self.clients.openWindow(url));
});
