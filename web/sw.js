/* Domino Analyzer Pro — service worker (offline shell)
   Strategy: network-first for API, cache-first for static assets. */
const CACHE = 'domino-analyzer-v3.2';
const CORE = ['/', '/index.html', '/styles.css', '/app.js', '/manifest.json', '/icon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/')) return; // API selalu network

  event.respondWith(
    caches.match(event.request).then((hit) => {
      if (hit) {
        // revalidate in background
        fetch(event.request).then((res) => {
          if (res.ok) caches.open(CACHE).then((c) => c.put(event.request, res.clone()));
        }).catch(() => {});
        return hit;
      }
      return fetch(event.request).then((res) => {
        if (res.ok) caches.open(CACHE).then((c) => c.put(event.request, res.clone()));
        return res;
      }).catch(() => caches.match('/index.html'));
    })
  );
});
