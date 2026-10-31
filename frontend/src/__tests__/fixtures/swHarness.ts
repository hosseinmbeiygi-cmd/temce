// هارنس اجرای فایل‌های Service Worker در sandbox برای تست‌های SW.
//
// چرا به شکل `new Function` و نه import: فایل‌های SW در `public/` اند و برای
// محیط worker نوشته شده‌اند؛ import کردنشان در jsdom یا node خودِ ماژول را
// اجرا می‌کند و `self` را نمی‌یابد. پس منبع را می‌خوانیم و با `self` ساختگی
// اجرا می‌کنیم — دقیقاً همان کاری که مرورگر با اسکریپت worker می‌کند.

export type Listener = (event: Record<string, unknown>) => void;

export interface FakeClient {
  url: string;
  postMessage: (data: unknown) => void;
}

export class MockCache {
  store = new Map<string, Response>();

  private keyOf(req: Request | string): string {
    return typeof req === "string" ? req : req.url;
  }

  async put(req: Request | string, res: Response) {
    this.store.set(this.keyOf(req), res.clone());
  }

  async match(req: Request | string) {
    const hit = this.store.get(this.keyOf(req));
    // مثل مرورگر هر بار یک بدنۀ تازه؛ وگرنه تست با «body already read» می‌شکند
    return hit ? hit.clone() : undefined;
  }

  async addAll(inputs: Array<Request | string>) {
    void inputs;
  }

  async delete(req: Request | string) {
    return this.store.delete(this.keyOf(req));
  }

  async keys() {
    return [...this.store.keys()];
  }
}

export class MockCacheStorage {
  caches = new Map<string, MockCache>();

  async open(name: string) {
    const existing = this.caches.get(name);
    if (existing) return existing;
    const created = new MockCache();
    this.caches.set(name, created);
    return created;
  }

  async keys() {
    return [...this.caches.keys()];
  }

  async delete(name: string) {
    return this.caches.delete(name);
  }

  async match(req: Request | string) {
    const url = typeof req === "string" ? req : req.url;
    for (const cache of this.caches.values()) {
      const hit = await cache.match(url);
      if (hit) return hit;
    }
    return undefined;
  }

  /** فقط کش API را برمی‌گرداند تا بتوان در تست «پاسخ از پیش کش‌شده» گذاشت. */
  async anyCache() {
    for (const cache of this.caches.values()) return cache;
    return this.open("seed");
  }
}

export interface SwHandle {
  dispatch(type: string, event: Record<string, unknown>): void;
}

/** یک فایل SW را از متن منبع در sandbox اجرا می‌کند. */
export function loadSwSource(
  source: string,
  env: Record<string, unknown>,
  clients: FakeClient[] = [],
): SwHandle {
  const listeners = new Map<string, Listener[]>();
  const selfObj = {
    addEventListener: (type: string, cb: Listener) => {
      const list = listeners.get(type) ?? [];
      list.push(cb);
      listeners.set(type, list);
    },
    skipWaiting: () => Promise.resolve(),
    clients: {
      claim: () => Promise.resolve(),
      matchAll: () => Promise.resolve(clients),
      openWindow: () => Promise.resolve(),
    },
    registration: { showNotification: () => Promise.resolve() },
  };
  const names = Object.keys(env);
   
  const run = new Function("self", ...names, source) as (...args: unknown[]) => void;
  run(selfObj, ...names.map((n) => env[n]));
  return {
    dispatch(type, event) {
      for (const cb of listeners.get(type) ?? []) cb(event);
    },
  };
}

/** install + activate را اجرا می‌کند تا کش‌ها ساخته شوند؛ handle را برمی‌گرداند. */
export function bootSw(sw: SwHandle): SwHandle {
  sw.dispatch("install", { waitUntil: () => undefined });
  sw.dispatch("activate", { waitUntil: () => undefined });
  return sw;
}

/** یک fetch event می‌فرستد و پاسخ promise شده را برمی‌گرداند. */
export function respondWith(
  sw: SwHandle,
  url: string,
  init: RequestInit = { headers: { accept: "application/json" } },
): Promise<Response> {
  let captured: Promise<Response> | undefined;
  sw.dispatch("fetch", {
    request: new Request(url, init),
    respondWith: (p: Promise<Response>) => {
      captured = p;
    },
  });
  if (!captured) throw new Error(`SW did not call respondWith for ${url}`);
  return captured;
}

export function jsonResponse(body: unknown, headers?: Record<string, string>) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json", ...headers },
  });
}
