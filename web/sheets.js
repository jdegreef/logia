// Study sheets: a reader gathers excerpts from the reader into a sheet, adds
// notes of their own, and prints it or shares it by link. Sheets are kept in
// this browser (localStorage "logia.sheets"); a shared link carries the whole
// sheet in its address (/sheets/#s=...), so nothing is stored on a server.
// The reader's own notes are always shown apart from the commentary, as
// theirs. The page's words come from the catalog (sheets.ui, in the
// <script id="sheets-text"> of each page).
(function () {
  "use strict";
  var KEY = "logia.sheets";
  var T = {};
  try { T = JSON.parse((document.getElementById("sheets-text") || {}).textContent || "{}"); } catch (e) { T = {}; }
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  };
  var fmt = function (s, o) { return String(s || "").replace(/\{(\w+)\}/g, function (_m, k) { return o[k] != null ? o[k] : ""; }); };

  function read() {
    try { var x = JSON.parse(localStorage.getItem(KEY) || "null"); return x && x.sheets ? x : { sheets: [], current: null }; }
    catch (e) { return { sheets: [], current: null }; }
  }
  function write(x) { try { localStorage.setItem(KEY, JSON.stringify(x)); return true; } catch (e) { return false; } }
  function newId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function current(x) {
    var s = x.sheets.filter(function (y) { return y.id === x.current; })[0];
    if (!s) {
      s = { id: newId(), title: T.untitled || "My study sheet", items: [] };
      x.sheets.unshift(s);
      x.current = s.id;
    }
    return s;
  }

  // Add an excerpt, by its key ("<work>.<BOOK>.<chapter>.<verse>"), to the sheet being made.
  function add(key) {
    var x = read(), s = current(x);
    var had = s.items.some(function (i) { return i.k === key; });
    if (!had) s.items.push({ k: key });
    return { ok: write(x), already: had, title: s.title, n: s.items.length };
  }
  function has(key) {
    var x = read(), s = x.sheets.filter(function (y) { return y.id === x.current; })[0];
    return !!(s && s.items.some(function (i) { return i.k === key; }));
  }
  window.LogiaSheets = { add: add, has: has };

  // The sheets page ---------------------------------------------------------
  var root = document.getElementById("sheet-app");
  if (!root) return;

  function encode(s) {
    var json = JSON.stringify({ t: s.title, i: s.items });
    var bytes = new TextEncoder().encode(json), bin = "";
    bytes.forEach(function (b) { bin += String.fromCharCode(b); });
    return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function decode(str) {
    try {
      var bin = atob(str.replace(/-/g, "+").replace(/_/g, "/"));
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      var o = JSON.parse(new TextDecoder().decode(bytes));
      var items = (o.i || []).filter(function (it) {
        return (typeof it.k === "string" && /^[a-z0-9-]+\.[1-3]?[A-Z]{2,3}\.\d+\.\d+$/.test(it.k)) || typeof it.n === "string";
      }).slice(0, 200);
      return { title: String(o.t || T.untitled).slice(0, 200), items: items };
    } catch (e) { return null; }
  }

  var chapters = {};
  function chapter(c) {
    if (!chapters[c]) chapters[c] = fetch("/data/" + c + ".json").then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return chapters[c];
  }
  function excerptOf(key) {
    var p = key.split("."), work = p[0], v = +p[3];
    return chapter(p[1] + "." + p[2]).then(function (ch) {
      var w = ch && ch.commentaries.filter(function (x) { return x.work_id === work; })[0];
      var e = w && w.entries.filter(function (x) { return x.start <= v && v <= x.end; })[0];
      return {
        ref: (ch ? ch.bookName : p[1]) + " " + p[2] + ":" + v,
        href: "/" + p[1].toLowerCase() + "/" + p[2] + "/#v" + v + "-" + work,
        author: w ? w.author : work, title: w ? w.title : "", text: e ? e.excerpt : ""
      };
    });
  }

  var shared = null;
  var m = /(?:^#|&)s=([A-Za-z0-9_-]+)/.exec(location.hash);
  if (m) shared = decode(m[1]);
  var store = read();
  var view = shared ? null : (store.sheets.filter(function (y) { return y.id === store.current; })[0] || store.sheets[0] || null);

  function paras(text) {
    return text.split(/\n\s*\n/).map(function (p) { return "<p>" + esc(p.trim()) + "</p>"; }).join("");
  }

  function render() {
    var s = shared || view;
    var list = store.sheets;
    var picker = !shared && list.length > 1
      ? '<label class="lg-sheet-pick">' + esc(T.your_sheets) + ' <select id="sheet-pick">' + list.map(function (y) {
          return '<option value="' + esc(y.id) + '"' + (view && y.id === view.id ? " selected" : "") + ">" + esc(y.title) + "</option>";
        }).join("") + "</select></label>" : "";
    if (!s) {
      root.innerHTML = '<div class="lg-sheet-empty"><h2>' + esc(T.empty_title) + "</h2><p>" + esc(T.empty_text) + '</p><p class="actions">' +
        '<button type="button" class="button" data-sheet="new">' + esc(T["new"]) + '</button> <a class="button ghost" href="/jhn/1/#v14">' +
        esc(T.try_it) + "</a></p></div>";
      return;
    }
    var head = shared
      ? '<p class="lg-sheet-shared">' + esc(T.shared_note) + ' <button type="button" class="button" data-sheet="keep">' + esc(T.keep) + "</button></p>" +
        "<h2 class=\"lg-sheet-title\">" + esc(s.title) + "</h2>"
      : '<div class="lg-sheet-tools">' + picker +
        '<button type="button" class="button ghost" data-sheet="new">' + esc(T["new"]) + "</button>" +
        '<button type="button" class="button ghost" data-sheet="print">' + esc(T.print) + "</button>" +
        '<button type="button" class="button" data-sheet="share">' + esc(T.share) + "</button></div>" +
        '<p class="lg-sheet-msg" role="status" id="sheet-msg"></p>' +
        '<label class="lg-sheet-label" for="sheet-title">' + esc(T.title_label) + '</label><input class="lg-sheet-title-in" id="sheet-title" value="' + esc(s.title) + '">';
    var items = s.items.map(function (it, i) {
      var tools = shared ? "" : '<p class="lg-sheet-item-tools">' +
        '<button type="button" class="lg-linkish" data-move="-1" data-i="' + i + '"' + (i ? "" : " disabled") + ">" + esc(T.up) + "</button>" +
        '<button type="button" class="lg-linkish" data-move="1" data-i="' + i + '"' + (i < s.items.length - 1 ? "" : " disabled") + ">" + esc(T.down) + "</button>" +
        '<button type="button" class="lg-linkish" data-remove="' + i + '">' + esc(T.remove) + "</button></p>";
      if (it.n != null) {
        var body = shared ? paras(it.n) : '<textarea class="lg-sheet-note-in" data-note="' + i + '" rows="3" aria-label="' + esc(T.note_label) + '">' + esc(it.n) + "</textarea>";
        return '<li class="lg-sheet-note"><p class="lg-sheet-who">' + esc(T.note_who) + "</p>" + body + tools + "</li>";
      }
      return '<li class="lg-sheet-ex" data-key="' + esc(it.k) + '"><p class="lg-quiet">…</p>' + tools + "</li>";
    }).join("");
    root.innerHTML = head + '<ol class="lg-sheet-items">' + items + "</ol>" +
      (shared ? "" : '<p><button type="button" class="button ghost" data-sheet="note">' + esc(T.add_note) + "</button></p>" +
        (s.items.length ? "" : '<p class="lg-quiet">' + esc(T.how_to_add) + "</p>"));
    root.querySelectorAll("li.lg-sheet-ex").forEach(function (li) {
      excerptOf(li.getAttribute("data-key")).then(function (x) {
        var tools = li.querySelector(".lg-sheet-item-tools");
        li.innerHTML = '<p class="lg-ref"><a href="' + esc(x.href) + '">' + esc(x.ref) + '</a></p><p class="lg-sheet-who"><b>' + esc(x.author) + "</b>" +
          (x.title ? " · <i>" + esc(x.title) + "</i>" : "") + '</p><div class="lg-sheet-text">' + (x.text ? paras(x.text) : "<p>" + esc(T.missing) + "</p>") + "</div>";
        if (tools) li.appendChild(tools);
      });
    });
  }

  function save() { store.current = view ? view.id : store.current; write(store); }
  function msg(text) { var el = document.getElementById("sheet-msg"); if (el) el.textContent = text; }

  root.addEventListener("click", function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    var what = b.getAttribute("data-sheet");
    if (what === "new") {
      view = { id: newId(), title: T.untitled, items: [] };
      store.sheets.unshift(view); save(); render();
    } else if (what === "keep" && shared) {
      view = { id: newId(), title: shared.title, items: shared.items };
      store.sheets.unshift(view); shared = null; save();
      history.replaceState(null, "", location.pathname);
      render(); msg(T.kept);
    } else if (what === "print") {
      window.print();
    } else if (what === "share" && view) {
      var url = location.origin + location.pathname + "#s=" + encode(view);
      var done = function () { msg(T.copied); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function () { msg(url); });
      else msg(url);
    } else if (what === "note" && view) {
      view.items.push({ n: "" }); save(); render();
      var last = root.querySelectorAll("[data-note]"); if (last.length) last[last.length - 1].focus();
    } else if (b.hasAttribute("data-remove") && view) {
      view.items.splice(+b.getAttribute("data-remove"), 1); save(); render();
    } else if (b.hasAttribute("data-move") && view) {
      var i = +b.getAttribute("data-i"), j = i + +b.getAttribute("data-move");
      var it = view.items[i]; view.items[i] = view.items[j]; view.items[j] = it; save(); render();
    }
  });
  root.addEventListener("input", function (ev) {
    if (!view) return;
    if (ev.target.id === "sheet-title") { view.title = ev.target.value; save(); }
    if (ev.target.hasAttribute("data-note")) { view.items[+ev.target.getAttribute("data-note")].n = ev.target.value; save(); }
  });
  root.addEventListener("change", function (ev) {
    if (ev.target.id !== "sheet-pick") return;
    view = store.sheets.filter(function (y) { return y.id === ev.target.value; })[0];
    save(); render();
  });
  render();
})();
