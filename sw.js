var CACHE = "mc-v2";
var SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", function (e) {
e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }));
self.skipWaiting();
});
self.addEventListener("activate", function (e) {
e.waitUntil(
caches.keys().then(function (keys) {
return Promise.all(keys.filter(function (k) { return k !== CACHE; })
.map(function (k) { return caches.delete(k); }));
}).then(function () { return self.clients.claim(); })
);
});
function networkFirst(req, key) {
return fetch(req).then(function (res) {
if (res && res.ok) {
var copy = res.clone();
caches.open(CACHE).then(function (c) { c.put(key, copy); });
}
return res;
}).catch(function () {
return caches.match(key).then(function (hit) {
return hit || caches.match("./index.html");
});
});
}
self.addEventListener("fetch", function (e) {
if (e.request.method !== "GET") return;
var u = new URL(e.request.url);
if (u.origin === self.location.origin) {
e.respondWith(networkFirst(e.request, e.request));
} else if (u.hostname === "raw.githubusercontent.com") {
e.respondWith(networkFirst(e.request, u.origin + u.pathname));
}
});
