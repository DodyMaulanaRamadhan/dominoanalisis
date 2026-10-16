/* Domino Analyzer Pro — service worker (offline shell)

   Strategy: network-first untuk SEMUA permintaan (API dan aset).
   Cache-first untuk aset statis pernah membuat UI lama tetap tampil setelah
   pembaruan (index.html/app.js baru hanya masuk cache di latar belakang),
   sehingga pengguna harus hard-refresh. Dengan network-first, versi terbaru
   selalu dipakai saat server hidup, dan cache tetap menjadi cadangan offline.
   Naikkan CACHE setiap kali aset berubah agar cache lama dibuang saat activate. */
const CACHE = 'domino-analyzer-v3.22';
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
    fetch(event.request).then((res) => {
      if (res.ok) caches.open(CACHE).then((c) => c.put(event.request, res.clone()));
      return res;
    }).catch(() =>
      // offline: pakai cache; navigasi apa pun jatuh ke shell index.html
      caches.match(event.request).then((hit) => hit || caches.match('/index.html'))
    )
  );
});
