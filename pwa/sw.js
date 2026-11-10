const CACHE_PREFIX = 'dideban-';
const CACHE = CACHE_PREFIX + '__VERSION__';
const SHELL = __PRECACHE__;

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    for (const url of SHELL) {
      const response = await fetch(url, { cache: 'reload' });
      if (!response.ok || response.redirected) throw new Error('Cannot cache ' + url);
      await cache.put(url, response);
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  // Authentication codes and error redirects must never enter Cache Storage.
  if (url.pathname.startsWith('/auth/') || url.searchParams.has('code') || url.searchParams.has('error')) return;
  if (url.pathname === '/sw.js' || url.pathname === '/healthz') return;
  // Fetch each visited page again so a newly published report appears online.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const response = await fetch(request);
      if (response.ok && !response.redirected) await cache.put(request, response.clone());
      return response;
    } catch (error) {
      const cached = await cache.match(request);
      if (cached) return cached;
      if (request.mode === 'navigate') return cache.match('/offline.html');
      return Response.error();
    }
  })());
});
