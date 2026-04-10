const CACHE_VERSION = 'smartcents-admin-v1.04';
const CACHE_NAME = CACHE_VERSION;
const ASSETS = [
  '/admin.html',
  '/admin-manifest.json',
  '/icon-192.png',
  '/icon-512.png'
];

// Install — cache assets
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS))
  );
  // Don't skipWaiting automatically — wait for user to trigger update
});

// Activate — delete old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch — network first for admin.html so updates are detected
self.addEventListener('fetch', e => {
  if (e.request.url.includes('admin.html')) {
    e.respondWith(
      fetch(e.request).then(response => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        return response;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request))
    );
  }
});

// Handle SKIP_WAITING message — this is what makes applyUpdate() work
self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
