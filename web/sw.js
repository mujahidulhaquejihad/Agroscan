/* AgroVet PWA service worker — cache app shell; always network for API. */
const CACHE = "agrovet-shell-v2";
const SHELL = [
  "/",
  "/static/styles.css?v=47",
  "/static/config.js?v=24",
  "/static/i18n.js?v=42",
  "/static/auth.js?v=22",
  "/static/core.js?v=32",
  "/static/features.js?v=29",
  "/static/farmer-ux.js?v=1",
  "/static/app-extra.js?v=18",
  "/static/shop.js?v=14",
  "/static/mobile.js?v=25",
  "/static/pwa.js?v=21",
  "/static/AgroVet_logo-main.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Never cache API / auth / uploads
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(req));
    return;
  }

  // Network-first for navigations; fall back to cache
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("/", copy));
          return res;
        })
        .catch(() => caches.match("/") || caches.match(req))
    );
    return;
  }

  // Cache-first for static shell assets
  event.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((res) => {
        if (res.ok && url.origin === self.location.origin) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      });
    })
  );
});
