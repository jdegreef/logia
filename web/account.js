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

  window.LogiaAccount = {
    user: function () { var a = saved(); return a && a.user; },
    signInUrl: signInUrl,
    marks: loadMarks,
    setMark: setMark,
    likeCounts: likeCounts
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
    if (!saved()) {
      note.innerHTML = esc(T.saved_signed_out) + ' <a href="' + esc(signInUrl()) + '">' + esc(T.sign_in) + "</a>";
      return;
    }
    loadMarks().then(function (m) {
      if (!m) { note.textContent = T.error; return; }
      var keys = Object.keys(m.saved).sort(function (a, b) { return m.saved[b] < m.saved[a] ? -1 : 1; });
      if (!keys.length) { note.textContent = T.saved_empty; return; }
      var chapters = {};
      keys.forEach(function (k) { var p = k.split("."); chapters[p[1] + "." + p[2]] = true; });
      return Promise.all(Object.keys(chapters).map(function (c) {
        return fetch("/data/" + c + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
      })).then(function (files) {
        var data = {};
        files.forEach(function (f) { if (f) data[f.book + "." + f.chapter] = f; });
        note.textContent = "";
        list.innerHTML = keys.map(function (k) {
          var p = k.split("."), work = p[0], v = +p[3], ch = data[p[1] + "." + p[2]];
          var w = ch && ch.commentaries.filter(function (x) { return x.work_id === work; })[0];
          var ref = (ch ? ch.bookName : p[1]) + " " + p[2] + ":" + v;
          var href = "/" + p[1].toLowerCase() + "/" + p[2] + "/#v" + v + "-" + work;
          if (!w) {
            return '<li class="lg-saved"><p class="lg-ref"><a href="' + esc(href) + '">' + esc(ref) + "</a></p></li>";
          }
          var e = w.entries.filter(function (x) { return x.start <= v && v <= x.end; })[0];
          var first = e ? e.excerpt.split(/\n\s*\n/)[0] : "";
          var words = first.split(/\s+/);
          var text = words.slice(0, 60).join(" ") + (words.length > 60 ? "…" : "");
          return '<li class="lg-saved" data-key="' + esc(k) + '"><p class="lg-ref"><a href="' + esc(href) + '">' +
            esc(ref) + '</a></p><p class="lg-saved-who"><b>' + esc(w.author) + "</b> · <i>" + esc(w.title) + "</i></p>" +
            '<p class="lg-saved-text">' + esc(text) + '</p><p class="lg-saved-actions"><a href="' + esc(href) + '">' +
            esc(T.open_in_reader) + '</a><button type="button" class="lg-linkish" data-remove>' + esc(T.remove) + "</button></p></li>";
        }).join("");
      });
    });
    list.addEventListener("click", function (e) {
      var b = e.target.closest("[data-remove]"); if (!b) return;
      var li = b.closest("[data-key]");
      b.disabled = true;
      setMark("saved", li.getAttribute("data-key"), false).then(function () {
        li.remove();
        if (!list.children.length) note.textContent = T.saved_empty;
      }).catch(function (err) { b.disabled = false; note.textContent = err.message; });
    });
  })();
})();
