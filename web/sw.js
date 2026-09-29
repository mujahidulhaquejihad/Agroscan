/* AgroScan PWA service worker — cache app shell; always network for API. */
const CACHE = "agroscan-shell-v24";
const SHELL = [
  "/",
  "/login",
  "/signup",
  "/static/styles.css?v=84",
  "/static/config.js?v=26",
  "/static/i18n.js?v=66",
  "/static/auth.js?v=25",
  "/static/core.js?v=41",
  "/static/crop.js?v=5",
  "/static/features.js?v=40",
  "/static/farmer-ux.js?v=4",
  "/static/app-extra.js?v=31",
  "/static/shop.js?v=17",
  "/static/geo.js?v=2",
  "/static/mobile.js?v=28",
  "/static/ads.js?v=3",
  "/static/pwa.js?v=23",
  "/static/AgroScan_logo-main.png",
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
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/admin") ||
    url.pathname.startsWith("/vendor")
  ) {
    event.respondWith(fetch(req));
    return;
  }

  // Network-first for navigations; fall back to cache
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match("/") || caches.match("/index.html")))
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
