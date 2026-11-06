// Logia's own site script, beside the Open Word Bible's web/site.js: the
// passage search (home, Read, page not found), "Continue reading" (the last
// verse read, kept by web/reader.js), and opening a closed <details> that a
// link points into. The search reads its book names and commentators from
// the page's #search-data (search_data in scripts/build_site.py).
(function () {
  "use strict";
  var esc = function (s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  };
  var fmt = function (s, vals) { return s.replace(/\{(\w+)\}/g, function (_, k) { return vals[k] !== undefined ? vals[k] : ""; }); };
  var holder = document.getElementById("search-data");
  var D = holder ? JSON.parse(holder.textContent) : null;

  // "John 3:16", "jn 3.16", "1 Cor 13", "Ps 23 4", "john3:16": a book (any
  // name or abbreviation in D.aliases, or the start of a book's name), then
  // a chapter and maybe a verse. Returns {code, chapter, verse} or null.
  function bookOf(name) {
    var key = name.toLowerCase().replace(/[.\s]+/g, " ").trim().replace(/^(i{1,3})\s/, function (m, r) { return r.length + " "; });
    if (!key) return null;
    if (D.aliases[key]) return D.aliases[key];
    var squeezed = key.replace(/ /g, "");
    if (D.aliases[squeezed]) return D.aliases[squeezed];
    var hits = Object.keys(D.names).filter(function (c) {
      return D.names[c].toLowerCase().replace(/ /g, "").indexOf(squeezed) === 0;
    });
    return hits.length === 1 ? hits[0] : null;
  }
  function parseRef(q) {
    if (!D) return null;
    var m = String(q).trim().match(/^((?:[1-3]|i{1,3})?\s*[a-z][a-z.\s]*?)\s*(\d+)(?:\s*[:.,\s]\s*(\d+))?\s*$/i);
    if (!m) return null;
    var code = bookOf(m[1]);
    if (!code) return null;
    var chapter = +m[2], verse = m[3] ? +m[3] : null;
    if (chapter < 1 || chapter > D.chapters[code]) return null;
    return { code: code, chapter: chapter, verse: verse };
  }
  function refHref(r) { return "/" + r.code.toLowerCase() + "/" + r.chapter + "/" + (r.verse ? "#v" + r.verse : ""); }
  function refLabel(r) { return D.names[r.code] + " " + r.chapter + (r.verse ? ":" + r.verse : ""); }

  // What a query could mean, best first: a reference, books, commentators.
  function suggest(q) {
    var out = [], low = q.trim().toLowerCase();
    if (!low || !D) return out;
    var r = parseRef(q);
    if (r) out.push({ href: refHref(r), title: refLabel(r), note: D.ui[r.verse ? "verse" : "chapter"] });
    Object.keys(D.names).forEach(function (c) {
      if (out.length < 6 && D.names[c].toLowerCase().indexOf(low) === 0 && !(r && r.code === c)) {
        out.push({ href: "/" + c.toLowerCase() + "/", title: D.names[c], note: fmt(D.ui.book, { n: D.chapters[c] }) });
      }
    });
    if (!r && /^[a-z0-9 ]+$/.test(low)) {
      var b = bookOf(low);
      if (b && !out.some(function (x) { return x.title === D.names[b]; })) {
        out.unshift({ href: "/" + b.toLowerCase() + "/", title: D.names[b], note: fmt(D.ui.book, { n: D.chapters[b] }) });
      }
    }
    D.people.forEach(function (p) {
      if (out.length < 8 && p[0].toLowerCase().indexOf(low) >= 0) out.push({ href: p[1], title: p[0], note: p[2] });
    });
    return out;
  }
  window.LogiaSearch = { parseRef: parseRef, refHref: refHref, refLabel: refLabel, suggest: suggest };

  // The search box: a combobox whose list shows what the query could mean;
  // Enter, or the button, goes to the first.
  document.querySelectorAll("form.lg-search").forEach(function (form) {
    var input = form.querySelector("input"), list = form.querySelector(".lg-sugg"), items = [], at = -1;
    function render() {
      items = suggest(input.value);
      at = items.length ? 0 : -1;
      list.innerHTML = items.length ? items.map(function (x, i) {
        return '<li role="option" id="' + list.id + "-" + i + '"' + (i === at ? ' aria-selected="true"' : "") + '><a href="' + esc(x.href) +
          '" tabindex="-1"><b>' + esc(x.title) + "</b><span>" + esc(x.note) + "</span></a></li>";
      }).join("") : (input.value.trim() ? '<li class="lg-sugg-none">' + esc(D.ui.none) + "</li>" : "");
      list.hidden = !input.value.trim();
      input.setAttribute("aria-expanded", !list.hidden);
      mark();
    }
    function mark() {
      list.querySelectorAll("[role=option]").forEach(function (li, i) { li.setAttribute("aria-selected", i === at); });
      if (at >= 0) input.setAttribute("aria-activedescendant", list.id + "-" + at); else input.removeAttribute("aria-activedescendant");
    }
    input.addEventListener("input", render);
    input.addEventListener("keydown", function (e) {
      if (!items.length) return;
      if (e.key === "ArrowDown") { at = (at + 1) % items.length; mark(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { at = (at - 1 + items.length) % items.length; mark(); e.preventDefault(); }
      else if (e.key === "Escape") { list.hidden = true; input.setAttribute("aria-expanded", "false"); }
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!items.length) render();
      if (items.length) location.href = items[Math.max(0, at)].href;
    });
    document.addEventListener("click", function (e) { if (!form.contains(e.target)) { list.hidden = true; input.setAttribute("aria-expanded", "false"); } });
    // "/" focuses the search, as on many reading sites.
    document.addEventListener("keydown", function (e) {
      if (e.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) { e.preventDefault(); input.focus(); }
    });
  });

  // Continue reading: the last verse read (web/reader.js keeps it).
  document.querySelectorAll("[data-resume]").forEach(function (a) {
    var last = null;
    try { last = JSON.parse(localStorage.getItem("logia-last") || "null"); } catch (e) { /* storage blocked */ }
    if (!last || !last.href || last.href.charAt(0) !== "/") return;
    a.href = last.href;
    a.textContent = fmt(a.getAttribute("data-resume"), { ref: last.ref });
    a.hidden = false;
  });

  // A link to #id inside a closed <details> opens it.
  function openTarget() {
    var id = decodeURIComponent(location.hash.slice(1));
    var el = id && document.getElementById(id);
    if (!el) return;
    for (var d = el; d; d = d.parentElement) if (d.tagName === "DETAILS") d.open = true;
    if (el.tagName === "DETAILS") el.open = true;
  }
  window.addEventListener("hashchange", openTarget);
  openTarget();
})();
