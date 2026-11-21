const CACHE = 'secure-login-v1';

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE).then(cache =>
            cache.addAll([
                '/',
                '/static/style.css',
                '/static/manifest.json'
            ])
        )
    );
});

self.addEventListener('fetch', event => {
    if (event.request.method === 'GET') {
        event.respondWith(
            fetch(event.request).catch(() =>
                caches.match(event.request)
            )
        );
    }
});
