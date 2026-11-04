// Search (/search/): every excerpt and every paragraph of a whole text, from
// /data/search.json (built by scripts/build_site.py), searched in the page.
// All the words must appear, each as a word or the start of one; a phrase in
// quotes must appear as written. Results can be narrowed by kind, era,
// tradition and commentator. The query lives in the address: /search/?q=…
(function () {
  "use strict";
  var form = document.getElementById("search-form");
  if (!form) return;
  var input = document.getElementById("q");
  var out = document.getElementById("results");
  var side = document.getElementById("facets");
  var DATA = null, U = null, shown = 30;
  var filters = { k: new Set(), e: new Set(), f: new Set(), w: new Set() };
  var esc = function (s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  };
  var fmt = function (s, v) { return s.replace(/\{(\w+)\}/g, function (_, k) { return v[k]; }); };
  // Letters only, lower-case, accents dropped: "Abraham’s" and "abrahams" meet.
  var fold = function (s) { return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[’']/g, ""); };

  function parse(q) {
    var phrases = [], words = [];
    q.replace(/"([^"]+)"|“([^”]+)”|(\S+)/g, function (_, a, b, w) {
      if (a || b) phrases.push(fold(a || b).replace(/\s+/g, " ").trim());
      else { w = fold(w).replace(/[^\p{L}\p{N}]/gu, ""); if (w) words.push(w); }
    });
    return { phrases: phrases, words: words };
  }
  function test(row, q) {
    if (!row._f) row._f = fold(row.t).replace(/\s+/g, " ");
    var text = row._f, score = 0, first = -1;
    for (var i = 0; i < q.phrases.length; i++) {
      var at = text.indexOf(q.phrases[i]);
      if (at < 0) return null;
      score += 5; if (first < 0 || at < first) first = at;
    }
    for (var j = 0; j < q.words.length; j++) {
      var re = new RegExp("(^|[^\\p{L}\\p{N}])" + q.words[j].replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gu");
      var m, n = 0;
      while ((m = re.exec(text))) { n++; var pos = m.index + m[1].length; if (first < 0 || pos < first) first = pos; }
      if (!n) return null;
      score += 1 + Math.log(n);
    }
    return { score: score - row.t.length / 20000, first: first };
  }
  // The passage around the first match, with every match marked. Positions
  // are found in the folded text, which keeps the original's length except
  // where an accent or apostrophe was dropped, so marks are found afresh.
  function snippet(row, q, first) {
    var t = row.t, lo = Math.max(0, first - 120), hi = Math.min(t.length, first + 220);
    if (lo > 0) lo = t.indexOf(" ", lo) + 1;
    if (hi < t.length) hi = t.lastIndexOf(" ", hi);
    var piece = t.slice(lo, hi), terms = q.phrases.concat(q.words).filter(Boolean);
    var h = esc(piece);
    terms.sort(function (a, b) { return b.length - a.length; }).forEach(function (term) {
      var re = new RegExp("(^|[^\\p{L}\\p{N}>])(" + esc(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s+") + ")", "giu");
      h = h.replace(re, "$1<mark>$2</mark>");
    });
    return (lo > 0 ? "… " : "") + h + (hi < t.length ? " …" : "");
  }

  function facet(key, title, values, label, counts) {
    var items = values.filter(function (v) { return counts[v]; });
    if (items.length < 2 && !filters[key].size) return "";
    return '<fieldset class="lg-facet"><legend>' + esc(title) + "</legend>" + items.map(function (v) {
      return '<label><input type="checkbox" data-facet="' + key + '" value="' + esc(v) + '"' + (filters[key].has(v) ? " checked" : "") +
        "> " + esc(label(v)) + ' <span class="lg-quiet">' + counts[v] + "</span></label>";
    }).join("") + "</fieldset>";
  }

  function run() {
    var raw = input.value.trim();
    var url = raw ? "?q=" + encodeURIComponent(raw) : location.pathname;
    if (location.search !== (raw ? "?q=" + encodeURIComponent(raw) : "")) history.replaceState(null, "", url);
    if (!raw) { out.innerHTML = '<p class="lg-quiet">' + esc(U.empty) + "</p>"; side.innerHTML = ""; return; }
    var q = parse(raw);
    if (!q.words.length && !q.phrases.length) return;
    var hits = [];
    DATA.rows.forEach(function (row) {
      var m = test(row, q);
      if (m) hits.push({ row: row, score: m.score, first: m.first });
    });
    // A paragraph held by an excerpt that is itself a result is shown once, as
    // the excerpt (unless only whole texts are asked for).
    if (!(filters.k.size === 1 && filters.k.has("p"))) {
      var found = new Set(hits.filter(function (h) { return h.row.k === "x"; }).map(function (h) { return h.row.id; }));
      hits = hits.filter(function (h) { return !(h.row.x && h.row.x.some(function (id) { return found.has(id); })); });
    }
    // Counts for each facet come from the hits the other facets let through.
    var keep = function (h, skip) {
      return ["k", "e", "f", "w"].every(function (k) { return k === skip || !filters[k].size || filters[k].has(h.row[k]); });
    };
    var count = function (key) {
      var c = {};
      hits.forEach(function (h) { if (keep(h, key)) c[h.row[key]] = (c[h.row[key]] || 0) + 1; });
      return c;
    };
    var works = Object.keys(DATA.works);
    side.innerHTML = facet("k", U.kinds, ["x", "p"], function (k) { return U["kind_" + k]; }, count("k")) +
      facet("e", U.eras_head, DATA.eras, function (e) { return U.eras[e]; }, count("e")) +
      facet("f", U.families_head, Object.keys(U.families), function (f) { return U.families[f]; }, count("f")) +
      facet("w", U.works_head, works, function (w) {
        var r = DATA.rows.filter(function (x) { return x.w === w; })[0];
        return r ? r.a : w;
      }, count("w"));
    var list = hits.filter(function (h) { return keep(h); }).sort(function (a, b) { return b.score - a.score; });
    var head = '<p class="lg-quiet">' + esc(list.length === 1 ? U.result_one : fmt(U.results, { n: list.length.toLocaleString() })) + "</p>";
    if (!list.length) { out.innerHTML = head + "<p>" + esc(U.none) + "</p>"; return; }
    out.innerHTML = head + '<ol class="lg-results">' + list.slice(0, shown).map(function (h) {
      var r = h.row;
      return '<li><a href="' + esc(r.u) + '"><b>' + esc(r.a) + "</b> · " + esc(r.r) + "</a>" +
        '<span class="lg-quiet"> · <i>' + esc(DATA.works[r.w]) + "</i></span>" +
        "<p>" + snippet(r, q, h.first) + "</p></li>";
    }).join("") + "</ol>" +
      (list.length > shown ? '<button type="button" class="button ghost" id="more">' +
        esc(fmt(U.more, { n: Math.min(30, list.length - shown) })) + "</button>" : "");
  }

  var timer = null;
  function soon() { clearTimeout(timer); shown = 30; timer = setTimeout(run, 160); }
  form.addEventListener("submit", function (e) { e.preventDefault(); shown = 30; if (DATA) run(); });
  input.addEventListener("input", function () { if (DATA) soon(); });
  side.addEventListener("change", function (e) {
    var box = e.target.closest("[data-facet]"); if (!box) return;
    var set = filters[box.getAttribute("data-facet")];
    if (box.checked) set.add(box.value); else set.delete(box.value);
    shown = 30; run();
  });
  out.addEventListener("click", function (e) {
    if (e.target.id === "more") { shown += 30; run(); }
  });

  input.value = new URLSearchParams(location.search).get("q") || "";
  out.innerHTML = '<p class="lg-quiet">…</p>';
  fetch("/data/search.json").then(function (r) { return r.json(); }).then(function (d) {
    DATA = d; U = d.ui;
    out.innerHTML = "";
    run();
    if (!input.value) input.focus();
  }).catch(function () { out.innerHTML = '<p class="lg-quiet">' + esc((U && U.none) || "") + "</p>"; });
})();
