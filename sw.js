// Market Council service worker (v5).
// Network first for everything it handles; the cache is only a fallback, so the app still opens
// with its last good data when the phone is offline or a data source is down.
var CACHE = "mc-v5";
var SHELL = ["./", "./index.html", "./mc/app.css", "./mc/app.js", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png", "./brief/"];
self.addEventListener("install", function (e) {
e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }));
self.skipWaiting();
});
self.addEventListener("activate", function (e) {
e.waitUntil(caches.keys().then(function (keys) {
return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
}).then(function () { return self.clients.claim(); }));
});
function networkFirst(req, key, sameOrigin) {
var go = sameOrigin ? fetch(req.url, { cache: "no-cache", credentials: "same-origin" }) : fetch(req);
return go.then(function (res) {
if (res && res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(key, copy); }); }
return res;
}).catch(function () {
return caches.match(key).then(function (hit) {
if (hit) return hit;
return sameOrigin ? caches.match("./index.html") : Response.error();
});
});
}
self.addEventListener("fetch", function (e) {
if (e.request.method !== "GET") return;
var u = new URL(e.request.url);
if (u.origin === self.location.origin) {
e.respondWith(networkFirst(e.request, u.origin + u.pathname, true));
} else if (u.hostname === "raw.githubusercontent.com" || (u.hostname === "api.github.com" && u.pathname.indexOf("/contents/") > 0)) {
e.respondWith(networkFirst(e.request, u.origin + u.pathname, false));
}
});
