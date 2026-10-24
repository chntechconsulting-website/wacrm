// Service Worker for Caching Static & Dynamic Images in WA! CRM
const IMAGE_CACHE_NAME = 'wacrm-images-v1';

// Key static images to precache on install for instant loading
const PRECACHE_IMAGE_URLS = [
  '/crm-mascot.png',
  '/wa-crm-logo-transparent.png',
  '/wa-crm-logo-dark.png',
  '/wa-crm-app-icon.png',
  '/logo.png',
  '/favicon.png',
  '/favicon.ico',
  '/mascot/pingo-celebrate.png',
  '/mascot/pingo-point-right.png',
  '/mascot/pingo-run.png',
  '/mascot/pingo-walk.png'
];

// Install: Precache primary UI branding and mascot images
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(IMAGE_CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_IMAGE_URLS).catch((err) => {
        console.warn('Precache partial warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// Activate: Clean up old image cache versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== IMAGE_CACHE_NAME && key.startsWith('wacrm-images-')) {
            return caches.delete(key);
          }
          return null;
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Cache-First strategy for images (png, jpg, jpeg, svg, webp, gif, ico)
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Check if the request is an image
  const isImage = 
    request.destination === 'image' ||
    /\.(png|jpg|jpeg|svg|webp|gif|ico|avif)(\?.*)?$/i.test(url.pathname);

  if (isImage && request.method === 'GET') {
    event.respondWith(
      caches.open(IMAGE_CACHE_NAME).then((cache) => {
        return cache.match(request).then((cachedResponse) => {
          if (cachedResponse) {
            // Background update (stale-while-revalidate pattern for freshness)
            fetch(request).then((networkResponse) => {
              if (networkResponse && networkResponse.status === 200) {
                cache.put(request, networkResponse.clone());
              }
            }).catch(() => {
              // Ignore offline/network drop errors for background sync
            });
            return cachedResponse;
          }

          // Not in cache: fetch from network and store in cache
          return fetch(request).then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              cache.put(request, networkResponse.clone());
            }
            return networkResponse;
          }).catch((err) => {
            // Return empty fallback or let browser handle missing image
            throw err;
          });
        });
      })
    );
  }
});
