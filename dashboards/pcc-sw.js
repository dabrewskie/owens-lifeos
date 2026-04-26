const CACHE = 'pcc-v2-2026-04-26';
const SHELL = [
  '/protocol_command_center.html',
  '/pcc-manifest.json',
  '/pcc-icon-192.png',
  '/pcc-icon-512.png'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Stale-while-revalidate for shell, network-first for /health/* and /api/*
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const isData = url.pathname.startsWith('/health/') || url.pathname.startsWith('/api/');
  if (isData) {
    e.respondWith(
      fetch(e.request).then(r => {
        const copy = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy));
        return r;
      }).catch(() => caches.match(e.request))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then(c => c || fetch(e.request).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(cc => cc.put(e.request, copy));
      return r;
    }))
  );
});
