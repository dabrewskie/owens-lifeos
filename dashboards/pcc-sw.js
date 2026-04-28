// pcc-sw.js — kill switch (2026-04-27)
// Previous v2 service worker cached the HTML shell aggressively. After live
// edits to protocol_command_center.html, Chrome served the stale cached copy
// and the page rendered broken. This SW deletes all caches, unregisters
// itself, and passes every fetch straight through to the network. Once Tory
// loads the page once with this SW active, future loads have NO SW at all.

self.addEventListener('install', (event) => {
  // Activate immediately, don't wait for tabs to close.
  self.skipWaiting();
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    Promise.all([
      // Take control of all open tabs immediately.
      self.clients.claim(),
      // Belt-and-suspenders cache purge.
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k)))),
      // Unregister self so future page loads don't have a SW.
      self.registration.unregister(),
    ])
  );
});

// Pass-through: never serve from cache.
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
