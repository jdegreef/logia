// The reference checker (/review/citations/, scripts/build_more.py): one
// Scripture reference at a time, as the commentary prints it, beside the verse
// scripts/find_refs.py took it for. A person answers Right, Wrong or Skip (Y,
// N, S); the answers stay in this browser (localStorage "logia-review") until
// they send them as a GitHub issue or a file, which scripts/apply_reviews.py
// adds to library/citations/. Nothing here changes a status by itself.
(function () {
  "use strict";
  var app = document.getElementById("review-app");
  if (!app) return;
  var U = JSON.parse((document.getElementById("review-text") || {}).textContent || "{}");
  var INDEX = JSON.parse(app.getAttribute("data-index") || "[]");
  var BOOKS = JSON.parse(app.getAttribute("data-books") || "{}");
  var KEY = "logia-review";
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  };
  var fmt = function (s, o) { return String(s || "").replace(/\{(\w+)\}/g, function (_m, k) { return o[k] != null ? o[k] : ""; }); };
  function store() {
    try { var x = JSON.parse(localStorage.getItem(KEY) || "null"); return x && x.answers ? x : { name: "", answers: {} }; }
    catch (e) { return { name: "", answers: {} }; }
  }
  function save(x) { try { localStorage.setItem(KEY, JSON.stringify(x)); } catch (e) { /* storage blocked: this visit only */ } }
  var S = store();
  var rows = [], at = 0, history = [], what = "", skipped = {};
  function idOf(r) { return r[0] + "@" + r[1] + "@" + r[3]; }
  function label(start, end) {
    var a = start.split("."), b = end.split(".");
    var name = (BOOKS[a[0]] || a[0]) + " " + a[1] + ":" + a[2];
    if (end === start) return name;
    return name + "–" + (a[1] === b[1] ? b[2] : b[1] + ":" + b[2]);
  }
  function count() { return Object.keys(S.answers).length; }

  function picker() {
    var params = new URLSearchParams(location.search), want = params.get("work"), chosen = null;
    INDEX.forEach(function (w) {
      w.b.forEach(function (b) { var v = w.w + "." + b[0]; if (!chosen && want && (v === want || w.w === want)) chosen = v; });
    });
    var opts = INDEX.map(function (w) {
      return w.b.map(function (b) {
        var v = w.w + "." + b[0];
        return '<option value="' + esc(v) + '"' + (v === chosen ? " selected" : "") + ">" +
          esc(w.a + ", " + w.t + " · " + b[1]) + " (" + esc(fmt(U.left, { n: b[2].toLocaleString() })) + ")</option>";
      }).join("");
    }).join("");
    return '<label class="lg-review-pick">' + esc(U.pick) + ' <select id="rv-pick">' + opts + "</select></label>";
  }

  function tools() {
    var n = count();
    return '<div class="lg-review-send"><p class="lg-quiet">' + esc(fmt(U.sent_note, { n: n })) + "</p>" +
      '<label>' + esc(U.name_label) + ' <input id="rv-name" value="' + esc(S.name || "") + '" autocomplete="name"></label>' +
      '<p><button type="button" class="button" data-rv="issue"' + (n ? "" : " disabled") + ">" + esc(U.send) + "</button> " +
      '<button type="button" class="button ghost" data-rv="download"' + (n ? "" : " disabled") + ">" + esc(U.download) + "</button> " +
      '<button type="button" class="lg-linkish" data-rv="clear"' + (n ? "" : " disabled") + ">" + esc(U.clear) + "</button></p>" +
      '<p class="lg-quiet" id="rv-msg" role="status"></p></div>';
  }

  function nextOpen(from) {
    for (var i = from; i < rows.length; i++) if (!S.answers[idOf(rows[i])] && !skipped[idOf(rows[i])]) return i;
    return -1;
  }

  function show() {
    var card = document.getElementById("rv-card");
    at = nextOpen(0);
    var left = rows.filter(function (r) { return !S.answers[idOf(r)]; }).length;
    var head = '<p class="lg-quiet">' + esc(fmt(U.progress, { done: count().toLocaleString(), left: left.toLocaleString(), what: what })) + "</p>";
    if (at < 0) { card.innerHTML = head + "<p><b>" + esc(U.done_all) + "</b></p>"; return; }
    var r = rows[at];
    var excerpt = r[0].split("."), href = "/" + excerpt[1].toLowerCase() + "/" + excerpt[2] + "/" + excerpt[3] + "/#" + r[0];
    card.innerHTML = head +
      '<blockquote class="lg-review-ctx"><p>…' + esc(r[5]) + "<mark>" + esc(r[2]) + "</mark>" + esc(r[6]) + '…</p></blockquote>' +
      '<p class="lg-quiet"><a href="' + esc(href) + '" target="_blank" rel="noopener">' + esc(label(excerpt[1] + "." + excerpt[2] + "." + excerpt[3], excerpt[1] + "." + excerpt[2] + "." + excerpt[3])) + "</a> · " + esc(U.points_to) + "</p>" +
      '<div class="lg-review-target"><b>' + esc(label(r[3], r[4])) + "</b> " + (r[7] ? esc(r[7]) : '<span class="lg-quiet">' + esc(U.no_text) + "</span>") + "</div>" +
      '<p class="lg-review-keys"><button type="button" class="button lg-rv-yes" data-a="y"><span class="kbd">Y</span> ' + esc(U.right) + "</button> " +
      '<button type="button" class="button lg-rv-no" data-a="n"><span class="kbd">N</span> ' + esc(U.wrong) + "</button> " +
      '<button type="button" class="button ghost" data-a="s"><span class="kbd">S</span> ' + esc(U.skip) + "</button> " +
      '<button type="button" class="lg-linkish" data-a="u"' + (history.length ? "" : " disabled") + ">" + esc(U.undo) + "</button></p>";
  }

  function answer(a) {
    if (a === "u") {
      var last = history.pop();
      if (last) { delete S.answers[last]; delete skipped[last]; save(S); }
      return redraw();
    }
    if (at < 0) return;
    var r = rows[at], id = idOf(r);
    if (a === "s") skipped[id] = true;
    else { S.answers[id] = { in: r[0], at: r[1], start: r[3], end: r[4], ok: a === "y" }; save(S); }
    history.push(id);
    redraw();
  }

  function redraw() {
    show();
    var t = document.getElementById("rv-tools");
    if (t) t.innerHTML = tools();
  }

  function load(v) {
    var card = document.getElementById("rv-card");
    card.innerHTML = '<p class="lg-quiet">' + esc(U.loading) + "</p>";
    var sel = document.getElementById("rv-pick");
    what = sel && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].text.replace(/ \([^)]*\)$/, "") : v;
    fetch("/review/data/" + v + ".json").then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
      .then(function (d) { rows = d; skipped = {}; history = []; show(); })
      .catch(function () { card.innerHTML = '<p class="lg-quiet">' + esc(U.failed) + "</p>"; });
  }

  function payload() {
    return { reviewer: S.name || "", answers: Object.keys(S.answers).map(function (k) { return S.answers[k]; }) };
  }

  app.innerHTML = picker() + '<div class="lg-review-card" id="rv-card" aria-live="polite"></div><div id="rv-tools">' + tools() + "</div>";
  var pick = document.getElementById("rv-pick");
  if (pick && pick.value) load(pick.value);
  app.addEventListener("change", function (ev) { if (ev.target.id === "rv-pick") load(ev.target.value); });
  app.addEventListener("input", function (ev) { if (ev.target.id === "rv-name") { S.name = ev.target.value.trim(); save(S); } });
  app.addEventListener("click", function (ev) {
    var b = ev.target.closest("button");
    if (!b) return;
    if (b.hasAttribute("data-a")) return answer(b.getAttribute("data-a"));
    var msg = document.getElementById("rv-msg"), what2 = b.getAttribute("data-rv");
    if (what2 === "download") {
      var blob = new Blob([JSON.stringify(payload(), null, 1)], { type: "application/json" });
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "logia-answers.json";
      document.body.appendChild(a); a.click(); a.remove();
    } else if (what2 === "issue") {
      var p = payload();
      var body = U.issue_intro + "\n\n```json\n" + JSON.stringify(p) + "\n```\n";
      var url = U.github + "/issues/new?labels=reference-checks&title=" + encodeURIComponent(fmt(U.issue_title, { name: p.reviewer || "?", n: p.answers.length })) +
        "&body=" + encodeURIComponent(body);
      if (url.length > 7500) { if (msg) msg.textContent = U.too_long; return; }
      window.open(url, "_blank", "noopener");
    } else if (what2 === "clear") {
      S.answers = {}; save(S); redraw();
    }
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.target.closest && ev.target.closest("input, select, textarea") || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    var k = ev.key.toLowerCase();
    if (k === "y" || k === "n" || k === "s") { ev.preventDefault(); answer(k); }
  });
})();
