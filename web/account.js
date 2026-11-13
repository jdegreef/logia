// Accounts on Logia, shared with openwordbible.org: Logia has no sign-in of
// its own. "Sign in" goes to Open Word Bible's /handoff/ page, which signs
// the reader in there (email, password, Google or passkey) and sends them
// back to /signed-in/#code=...&to=... with a single-use code. This script
// trades the code for an API token of Logia's own (POST
// /api/auth/handoff/redeem) and keeps it, with a copy of the account, in
// localStorage as logia.account. The API is Open Word Bible's
// (backend/logia/ in the open-word-bible repository), named by the
// logia-api meta tag.
//
// It runs the header's account menu, the /signed-in/ and /saved/ pages, and
// gives web/reader.js window.LogiaAccount: who is signed in, the reader's
// saved and liked comments, and the public like counts.
(function () {
  "use strict";
  var KEY = "logia.account";
  var API = (document.querySelector('meta[name="logia-api"]') || {}).content || "";
  var OWB = (document.querySelector('meta[name="logia-owb"]') || {}).content || "";
  var TEXT = document.getElementById("account-text");
  var T = TEXT ? JSON.parse(TEXT.textContent) : {};

  function saved() {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; }
  }
  function store(value) {
    try {
      if (value) localStorage.setItem(KEY, JSON.stringify(value));
      else localStorage.removeItem(KEY);
    } catch (e) { /* storage blocked: signed in for this page only */ }
  }
  // A path on this site to come back to: never //host, /\host or control characters.
  function safePath(path) {
    path = String(path || "");
    if (path.charAt(0) !== "/" || /^\/[\/\\]/.test(path) || /[\x00-\x1f\x7f]/.test(path)) return "/";
    if (/^\/signed-in\//.test(path)) return "/";
    return path;
  }
  function here() { return location.pathname + location.search + location.hash; }
  function signInUrl(to) {
    return OWB + "/handoff/?site=logia&to=" + encodeURIComponent(safePath(to || here()));
  }

  // A call to the API. A 401 means the token is gone: the account is
  // forgotten and the error says signedOut.
  function api(path, options) {
    options = options || {};
    var headers = {};
    var account = options.anonymous ? null : saved();
    if (account && account.token) headers.Authorization = "Bearer " + account.token;
    if (options.body) headers["Content-Type"] = "application/json";
    return fetch(API + path, {
      method: options.method || "GET", headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    }).catch(function () {
      throw new Error(T.offline || "Offline");
    }).then(function (r) {
      if (r.status === 401 && !options.anonymous) {
        store(null);
        document.documentElement.classList.remove("signed-in");
        var e = new Error(T.signed_out || "Signed out");
        e.signedOut = true;
        throw e;
      }
      if (r.status === 204) return null;
      return r.json().then(function (data) {
        if (!r.ok) throw new Error(data.detail || T.error || "Error");
        return data;
      }, function () { throw new Error(T.error || "Error"); });
    });
  }

  // The reader's saved and liked comments, fetched once per page.
  var marks = null;
  function loadMarks() {
    if (!saved()) return Promise.resolve(null);
    if (!marks) {
      marks = api("/api/logia/me").then(function (data) {
        var m = { saved: {}, liked: {} };
        data.saved.forEach(function (s) { m.saved[s.key] = s.at; });
        data.liked.forEach(function (k) { m.liked[k] = true; });
        return m;
      }).catch(function () { marks = null; return null; });
    }
    return marks;
  }
  function setMark(kind, key, on) {
    var path = "/api/logia/" + (kind === "saved" ? "saved/" : "likes/") + encodeURIComponent(key);
    return api(path, { method: on ? "PUT" : "DELETE" }).then(function () {
      return loadMarks().then(function (m) {
        if (!m) return;
        if (on) m[kind][key] = kind === "saved" ? new Date().toISOString() : true;
        else delete m[kind][key];
      });
    });
  }
  function likeCounts(chapter) {
    return api("/api/logia/likes?chapter=" + encodeURIComponent(chapter), { anonymous: true })
      .then(function (d) { return d.counts; }, function () { return {}; });
  }

  // Comments saved on this device by a reader who isn't signed in
  // (logia-saved-local: {key: when}), and the collections a reader groups
  // their saves into (logia-collections: {key: name}). Both stay on the
  // device; signed in, a device save can be moved into the account.
  function readLocal(name) { try { return JSON.parse(localStorage.getItem(name) || "{}"); } catch (e) { return {}; } }
  function writeLocal(name, v) { try { localStorage.setItem(name, JSON.stringify(v)); return true; } catch (e) { return false; } }
  var device = {
    saved: function () { return readLocal("logia-saved-local"); },
    has: function (key) { return !!readLocal("logia-saved-local")[key]; },
    toggle: function (key) {
      var m = readLocal("logia-saved-local"), on = !m[key];
      if (on) m[key] = new Date().toISOString(); else delete m[key];
      return writeLocal("logia-saved-local", m) ? on : !on;
    },
    remove: function (key) { var m = readLocal("logia-saved-local"); delete m[key]; writeLocal("logia-saved-local", m); },
    collections: function () { return readLocal("logia-collections"); },
    setCollection: function (key, name) {
      var c = readLocal("logia-collections");
      if (name) c[key] = name; else delete c[key];
      writeLocal("logia-collections", c);
    }
  };

  window.LogiaAccount = {
    user: function () { var a = saved(); return a && a.user; },
    signInUrl: signInUrl,
    marks: loadMarks,
    setMark: setMark,
    likeCounts: likeCounts,
    device: device
  };

  // The header's account menu (account_menu in scripts/build_site.py), as on
  // openwordbible.org: "Sign in" signed out; the reader's initial signed in.
  (function () {
    var box = document.querySelector(".account-menu");
    if (!box) return;
    var signIn = box.querySelector("[data-login]");
    var account = saved();
    if (!account || !account.user) {
      document.documentElement.classList.remove("signed-in");
      var back = function () { signIn.href = signInUrl(); };
      back();
      signIn.addEventListener("click", back);
      signIn.addEventListener("auxclick", back);
      return;
    }
    var user = account.user;
    var name = user.display_name || user.email;
    var button = box.querySelector(".avatar-btn");
    var pop = box.querySelector(".account-pop");
    box.querySelector(".account-initial").textContent = name.charAt(0).toUpperCase();
    box.querySelector(".who-name").textContent = user.display_name || "";
    box.querySelector(".who-email").textContent = user.email;
    button.setAttribute("aria-label", button.getAttribute("aria-label") + " (" + name + ")");
    signIn.hidden = true;
    button.hidden = false;
    function open(show) {
      pop.hidden = !show;
      button.setAttribute("aria-expanded", show ? "true" : "false");
      if (show) pop.querySelector("a, button").focus();
    }
    button.addEventListener("click", function () { open(pop.hidden); });
    document.addEventListener("click", function (e) { if (!pop.hidden && !box.contains(e.target)) open(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !pop.hidden) { open(false); button.focus(); }
    });
    box.querySelector(".sign-out").addEventListener("click", function () {
      function done() { store(null); location.reload(); }
      api("/api/auth/sign-out", { method: "POST" }).then(done, done);
    });
  })();

  // /signed-in/: back from Open Word Bible with a single-use code.
  (function () {
    var root = document.getElementById("signed-in");
    if (!root) return;
    var params = new URLSearchParams(location.hash.slice(1));
    var code = params.get("code");
    var to = safePath(params.get("to"));
    try { history.replaceState(null, "", location.pathname); } catch (e) { /* the code is used at once anyway */ }
    var status = document.getElementById("signed-in-status");
    var retry = document.getElementById("signed-in-retry");
    retry.href = signInUrl(to);
    if (!code) { status.textContent = T.sign_in_failed; retry.hidden = false; return; }
    api("/api/auth/handoff/redeem", { method: "POST", body: { code: code }, anonymous: true }).then(function (data) {
      store({ token: data.token, user: data.user });
      location.replace(to);
    }).catch(function (err) {
      status.textContent = T.sign_in_failed + " " + err.message;
      retry.hidden = false;
    });
  })();

  // /saved/: the reader's saved comments, newest first, with their text from
  // the chapters' data files (/data/<BOOK>.<chapter>.json).
  (function () {
    var root = document.getElementById("saved-page");
    if (!root) return;
    var list = document.getElementById("saved-list");
    var note = document.getElementById("saved-note");
    var esc = function (s) {
      return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
    };
    // Every save, the account's and this device's, newest first. Signed
    // out with nothing on the device: what saving does (#saved-empty).
    var signedIn = !!saved();
    var local = device.saved();
    if (!signedIn && !Object.keys(local).length) {
      var empty = document.getElementById("saved-empty");
      if (empty) {
        empty.hidden = false;
        empty.querySelectorAll("[data-login]").forEach(function (a) { a.href = signInUrl(); });
      } else {
        note.innerHTML = esc(T.saved_signed_out) + ' <a href="' + esc(signInUrl()) + '">' + esc(T.sign_in) + "</a>";
      }
      return;
    }
    var tools = document.getElementById("saved-tools"), picks = document.getElementById("saved-collections");
    var shownCollection = "", items = [];
    (signedIn ? loadMarks() : Promise.resolve({ saved: {} })).then(function (m) {
      if (!m) { note.textContent = T.error; m = { saved: {} }; }
      var all = {};
      Object.keys(m.saved).forEach(function (k) { all[k] = { at: m.saved[k], device: false }; });
      Object.keys(local).forEach(function (k) { if (!all[k]) all[k] = { at: local[k], device: true }; });
      var keys = Object.keys(all).sort(function (a, b) { return all[b].at < all[a].at ? -1 : 1; });
      if (!keys.length) { note.textContent = T.saved_empty; return; }
      var chapters = {};
      keys.forEach(function (k) { var p = k.split("."); chapters[p[1] + "." + p[2]] = true; });
      return Promise.all(Object.keys(chapters).map(function (c) {
        return fetch("/data/" + c + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
      })).then(function (files) {
        var data = {};
        files.forEach(function (f) { if (f) data[f.book + "." + f.chapter] = f; });
        note.innerHTML = signedIn ? "" : esc(T.saved_on_device) + ' <a href="' + esc(signInUrl()) + '">' + esc(T.sign_in) + "</a>";
        items = keys.map(function (k) {
          var p = k.split("."), work = p[0], v = +p[3], ch = data[p[1] + "." + p[2]];
          var w = ch && ch.commentaries.filter(function (x) { return x.work_id === work; })[0];
          var e = w && w.entries.filter(function (x) { return x.start <= v && v <= x.end; })[0];
          return { key: k, device: all[k].device, ref: (ch ? ch.bookName : p[1]) + " " + p[2] + ":" + v,
            href: "/" + p[1].toLowerCase() + "/" + p[2] + "/#v" + v + "-" + work, w: w, text: e ? e.excerpt : "" };
        });
        draw();
        if (tools) tools.hidden = false;
      });
    });
    // The list as it is, filtered to one collection when one is chosen.
    function draw() {
      var coll = device.collections();
      var names = Object.keys(coll).map(function (k) { return coll[k]; }).filter(function (n, i, a) { return a.indexOf(n) === i; }).sort();
      if (picks) {
        picks.innerHTML = names.length ? ['<button type="button" class="cx-chip" data-coll="" aria-pressed="' + (!shownCollection) + '">' + esc(T.collection_all) + "</button>"]
          .concat(names.map(function (n) { return '<button type="button" class="cx-chip" data-coll="' + esc(n) + '" aria-pressed="' + (n === shownCollection) + '">' + esc(n) + "</button>"; })).join("") : "";
      }
      var dl = document.getElementById("saved-collection-names");
      if (dl) dl.innerHTML = names.map(function (n) { return '<option value="' + esc(n) + '">'; }).join("");
      list.innerHTML = visible().map(function (it) {
        if (!it.w) return '<li class="lg-saved" data-key="' + esc(it.key) + '"><p class="lg-ref"><a href="' + esc(it.href) + '">' + esc(it.ref) + "</a></p></li>";
        var words = it.text.split(/\n\s*\n/)[0].split(/\s+/);
        var text = words.slice(0, 60).join(" ") + (words.length > 60 ? "…" : "");
        return '<li class="lg-saved" data-key="' + esc(it.key) + '"><p class="lg-ref"><a href="' + esc(it.href) + '">' +
          esc(it.ref) + "</a>" + (it.device ? ' <span class="lg-saved-device">' + esc(T.on_device) + "</span>" : "") + '</p><p class="lg-saved-who"><b>' + esc(it.w.author) + "</b> · <i>" + esc(it.w.title) + "</i></p>" +
          '<p class="lg-saved-text">' + esc(text) + '</p><p class="lg-saved-actions"><a href="' + esc(it.href) + '">' + esc(T.open_in_reader) + "</a>" +
          '<label class="lg-saved-coll"><span>' + esc(T.collection) + '</span><input type="text" list="saved-collection-names" value="' + esc(coll[it.key] || "") +
          '" data-coll-for="' + esc(it.key) + '" placeholder="' + esc(T.collection_placeholder) + '"></label>' +
          (it.device && signedIn ? '<button type="button" class="lg-linkish" data-keep>' + esc(T.keep_in_account) + "</button>" : "") +
          '<button type="button" class="lg-linkish" data-remove>' + esc(T.remove) + "</button></p></li>";
      }).join("");
    }
    function visible() {
      var coll = device.collections();
      return items.filter(function (it) { return !shownCollection || coll[it.key] === shownCollection; });
    }
    // The shown saves as text: each excerpt whole, then who, which work, the
    // verse and the link, for notes, a handout or a paper.
    function asText() {
      return visible().filter(function (it) { return it.w; }).map(function (it) {
        var cite = T.citation.replace("{name}", it.w.author).replace("{title}", it.w.title).replace("{ref}", it.ref).replace("{url}", location.origin + it.href);
        return "\u201c" + it.text.trim() + "\u201d\n" + cite;
      }).join("\n\n---\n\n");
    }
    if (picks) picks.addEventListener("click", function (e) {
      var b = e.target.closest("[data-coll]"); if (!b) return;
      shownCollection = b.getAttribute("data-coll"); draw();
    });
    list.addEventListener("change", function (e) {
      var input = e.target.closest("[data-coll-for]"); if (!input) return;
      device.setCollection(input.getAttribute("data-coll-for"), input.value.trim());
      draw();
    });
    var copyBtn = document.getElementById("saved-copy"), dlBtn = document.getElementById("saved-download");
    if (copyBtn) copyBtn.addEventListener("click", function () {
      var text = asText(), label = copyBtn.textContent;
      var done = function () { copyBtn.textContent = T.copied; setTimeout(function () { copyBtn.textContent = label; }, 2000); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { note.textContent = T.copy_failed; });
    });
    if (dlBtn) dlBtn.addEventListener("click", function () {
      var url = URL.createObjectURL(new Blob([asText() + "\n"], { type: "text/plain;charset=utf-8" }));
      var a = document.createElement("a");
      a.href = url; a.download = "logia-" + (shownCollection || "saved").toLowerCase().replace(/[^a-z0-9]+/g, "-") + ".txt";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    });
    list.addEventListener("click", function (e) {
      var keep = e.target.closest("[data-keep]");
      if (keep) {
        var li0 = keep.closest("[data-key]"), key0 = li0.getAttribute("data-key");
        keep.disabled = true;
        setMark("saved", key0, true).then(function () {
          device.remove(key0);
          items.forEach(function (it) { if (it.key === key0) it.device = false; });
          draw();
        }).catch(function (err) { keep.disabled = false; note.textContent = err.message; });
        return;
      }
      var b = e.target.closest("[data-remove]"); if (!b) return;
      var li = b.closest("[data-key]"), key = li.getAttribute("data-key");
      var it = items.filter(function (x) { return x.key === key; })[0];
      var gone = function () {
        items = items.filter(function (x) { return x.key !== key; });
        device.setCollection(key, "");
        draw();
        if (!items.length) note.textContent = T.saved_empty;
      };
      if (it && it.device) { device.remove(key); gone(); return; }
      b.disabled = true;
      setMark("saved", key, false).then(gone).catch(function (err) { b.disabled = false; note.textContent = err.message; });
    });
  })();
})();
