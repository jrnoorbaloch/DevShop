/* DevShop service worker: network-first for pages, cache-first for assets. */
const BASE = "__BASE__";
const CACHE = "devshop-__BUILD__";
const CORE = [`${BASE}/`, `${BASE}/assets/style.css`, `${BASE}/assets/app.js`, `${BASE}/assets/index.json`, `${BASE}/assets/favicon.svg`];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const isAsset = url.pathname.startsWith(`${BASE}/assets/`);
  if (isAsset) {
    e.respondWith(caches.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res;
    })));
  } else {
    e.respondWith(fetch(req).then((res) => {
      const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res;
    }).catch(() => caches.match(req).then((hit) => hit || caches.match(`${BASE}/`))));
  }
});
