const CACHE_PREFIX = `fpl-decision-lab:${self.registration.scope}:`;
const CACHE_NAME = `${CACHE_PREFIX}__BUILD_ID__`;
const APP_SHELL = [
  "./index.html", "./assets/styles.css?v=20", "./assets/runtime.js?v=20",
  "./assets/decision-log.js?v=20", "./assets/app.js?v=20",
  "./assets/scenario-compare.js?v=21",
  "./assets/decision-card.js?v=22",
  "./manifest.webmanifest", "./public/favicon.png", "./public/icon-192.png",
  "./public/icon-512.png", "./data/latest.json", "./data/briefing.md"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const isData = /\/data\/(latest\.json|briefing\.md)$/.test(new URL(request.url).pathname);
  const cacheKey = request.mode === "navigate" ? "./index.html" : request;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(request, {signal: controller.signal});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    // Do not replace the offline snapshot with an HTML error or invalid JSON.
    if (request.url.includes("/data/latest.json")) await response.clone().json();
    // A full cache must not turn a successful online request into a failed load.
    await cache.put(cacheKey, response.clone()).catch(() => {});
    return response;
  } catch {
    const cached = await cache.match(cacheKey);
    if (!cached) return new Response("Offline cache unavailable", {status: 503, headers: {"Content-Type": "text/plain"}});
    if (!isData) return cached;
    const headers = new Headers(cached.headers);
    headers.set("X-FPL-Cache", "offline");
    return new Response(await cached.arrayBuffer(), {status: 200, headers});
  } finally { clearTimeout(timer); }
}

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || !event.request.url.startsWith(self.registration.scope)) return;
  event.respondWith(networkFirst(event.request));
});
