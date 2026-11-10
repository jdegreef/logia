// Logia's service worker, so the site works offline and installs as an app.
// scripts/build_site.py publishes it at /sw.js with SHELL filled in: the
// stylesheets and scripts (by their ?v= addresses), the fonts and the
// offline page.
//
// - Pages: the network first, and a copy kept of each one read (the last
//   MAX_PAGES), so a page opened once opens again with no signal.
// - Files whose address never changes (?v=..., /panel/, /comm/, /fonts/):
//   from the cache when there, else the network, then kept.
// - A book kept for offline (the button on a book's page, web/logia.js) is
//   in its own cache, never trimmed.
// - Anything else, and anything on another site (the account API), is left
//   to the browser.
"use strict";

var SHELL = [];
var VERSION = "dev";
var STATIC = "logia-static-" + VERSION;
var PAGES = "logia-pages";
var DATA = "logia-data";
var KEPT = "logia-kept";
var MAX_PAGES = 300;
var MAX_DATA = 400;
var OFFLINE = "/offline/";

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(STATIC).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf("logia-static-") === 0 && k !== STATIC; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function trim(name, max) {
  return caches.open(name).then(function (c) {
    return c.keys().then(function (keys) {
      return Promise.all(keys.slice(0, Math.max(0, keys.length - max)).map(function (k) { return c.delete(k); }));
    });
  });
}

function keep(name, max, request, response) {
  if (!response || !response.ok || response.type !== "basic") return;
  var copy = response.clone();
  caches.open(name).then(function (c) { return c.put(request, copy); }).then(function () { return trim(name, max); });
}

function fixed(url) {
  return /[?&]v=/.test(url.search) || /^\/(panel|comm|fonts)\//.test(url.pathname);
}

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === "navigate") {
    event.respondWith(fetch(req).then(function (res) {
      keep(PAGES, MAX_PAGES, req, res);
      return res;
    }).catch(function () {
      return caches.match(req, { ignoreSearch: true }).then(function (hit) {
        return hit || caches.match(OFFLINE);
      });
    }));
    return;
  }

  if (fixed(url)) {
    event.respondWith(caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        keep(DATA, MAX_DATA, req, res);
        return res;
      });
    }));
  }
});
