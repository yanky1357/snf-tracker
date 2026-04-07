const CACHE_NAME = 'reefpilot-v4';
const STATIC_ASSETS = [
    '/',
    '/static/reef/index.html',
    '/static/reef/css/reef-style.css',
    '/static/reef/js/reef-app.js',
    '/static/reef/js/reef-chat.js',
    '/static/reef/js/reef-params.js',
    '/static/reef/js/reef-calc.js',
    '/static/reef/js/reef-tank.js',
    '/manifest.json',
    '/static/reef/js/chart.umd.min.js',
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Always go to network for API calls
    if (url.pathname.startsWith('/reef/api/')) {
        return;
    }

    // Cache-first for static assets
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                if (response.ok && event.request.method === 'GET') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            });
        }).catch(() => {
            if (event.request.mode === 'navigate') {
                return caches.match('/');
            }
        })
    );
});
