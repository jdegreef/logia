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

  // Page not found: an address that reads as a reference ("/jn3",
  // "/john/3/16", "/rom-8") is offered as a link.
  (function () {
    var guess = document.getElementById("nf-guess");
    if (!guess || !D) return;
    var path = decodeURIComponent(location.pathname).replace(/\.html?$/, "").replace(/^\/+|\/+$/g, "");
    var words = path.replace(/[\/_+-]+/g, " ").replace(/([a-z])(\d)/gi, "$1 $2").trim();
    var r = parseRef(words) || parseRef(words.replace(/ (\d+) (\d+)$/, " $1:$2"));
    var href, label;
    if (r) { href = refHref(r); label = refLabel(r); }
    else {
      var code = bookOf(words.split(" ")[0]);
      if (code) { href = "/" + code.toLowerCase() + "/"; label = D.names[code]; }
    }
    if (!href) return;
    guess.innerHTML = fmt(esc(guess.getAttribute("data-text")), { link: '<a href="' + esc(href) + '">' + esc(label) + "</a>" });
    guess.hidden = false;
  })();

  // Continue reading: the last verse read (web/reader.js keeps it).
  document.querySelectorAll("[data-resume]").forEach(function (a) {
    var last = null;
    try { last = JSON.parse(localStorage.getItem("logia-last") || "null"); } catch (e) { /* storage blocked */ }
    if (!last || !last.href || last.href.charAt(0) !== "/") return;
    a.href = last.href;
    a.textContent = fmt(a.getAttribute("data-resume"), { ref: last.ref });
    a.hidden = false;
  });

  // Chapters already read: a dot on their chip (web/reader.js keeps the list).
  var read = [];
  try { read = JSON.parse(localStorage.getItem("logia-read") || "[]"); } catch (e) { /* storage blocked */ }
  if (read.length) {
    document.querySelectorAll("a.chap").forEach(function (a) {
      if (read.indexOf(a.getAttribute("href")) >= 0) a.classList.add("lg-read");
    });
  }

  // A button that copies its data-copy text (a work's citation), and says so.
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var label = b.textContent, text = b.getAttribute("data-copy");
      var done = function () { b.textContent = b.getAttribute("data-done"); setTimeout(function () { b.textContent = label; }, 2000); };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () { select(b); });
      else select(b);
    });
  });
  function select(b) {
    var box = b.parentNode.querySelector(".lg-cite-text");
    if (!box) return;
    var range = document.createRange();
    range.selectNodeContents(box);
    var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  }

  // A commentator's page: "By verse" and "By homily" as tabs (both show,
  // one after the other, without script), and a box that goes to a verse
  // ("3:16", "Romans 5:8"): it opens the chapter and marks the row.
  document.querySelectorAll(".lg-tabs").forEach(function (bar) {
    var tabs = [].slice.call(bar.querySelectorAll("[role=tab]"));
    var show = function (tab) {
      tabs.forEach(function (x) {
        var on = x === tab;
        x.setAttribute("aria-selected", on ? "true" : "false");
        x.tabIndex = on ? 0 : -1;
        document.getElementById(x.getAttribute("aria-controls")).hidden = !on;
      });
    };
    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { show(tab); });
      tab.addEventListener("keydown", function (ev) {
        var d = ev.key === "ArrowRight" ? 1 : ev.key === "ArrowLeft" ? -1 : 0;
        if (!d) return;
        var next = tabs[(i + d + tabs.length) % tabs.length];
        show(next); next.focus();
      });
    });
    bar.hidden = false;
    bar.parentNode.classList.add("lg-tabbed");
    show(tabs[0]);
  });
  document.querySelectorAll(".lg-goto").forEach(function (form) {
    var books = JSON.parse(form.getAttribute("data-books"));
    var codes = Object.keys(books);
    var input = form.querySelector("input"), note = form.querySelector("[role=status]");
    var hint = note.textContent;
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var m = input.value.trim().toLowerCase().match(/^(.*?)\s*(\d+)\s*[:.\s]\s*(\d+)$/);
      var code = null;
      if (m && !m[1]) code = codes[0];
      else if (m) {
        var name = m[1].replace(/[.\s]+/g, "");
        codes.forEach(function (c) {
          if (books[c].some(function (n) { return n.replace(/\s/g, "").indexOf(name) === 0; })) code = code || c;
        });
      }
      var ch = code && document.getElementById("ch-" + code.toLowerCase() + "-" + (m && +m[2]));
      var row = null;
      if (ch) {
        var v = +m[3];
        [].forEach.call(ch.querySelectorAll("li[data-from]"), function (li) {
          if (!row && +li.getAttribute("data-from") <= v && v <= +li.getAttribute("data-to")) row = li;
        });
      }
      [].forEach.call(document.querySelectorAll(".lg-hit"), function (x) { x.classList.remove("lg-hit"); });
      if (!row) { note.textContent = form.getAttribute("data-none"); return; }
      note.textContent = hint;
      ch.open = true;
      row.classList.add("lg-hit");
      row.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      var link = row.querySelector("a");
      if (link) link.focus({ preventScroll: true });
    });
  });

  // A link to #id inside a closed <details> opens it.
  function openTarget() {
    var id = decodeURIComponent(location.hash.slice(1));
    var el = id && document.getElementById(id);
    if (!el) return;
    for (var d = el; d; d = d.parentElement) {
      if (d.tagName === "DETAILS") d.open = true;
      if (d.hidden && d.getAttribute("role") === "tabpanel") {
        var tab = document.querySelector('[aria-controls="' + d.id + '"]');
        if (tab) tab.click();
      }
    }
    if (el.tagName === "DETAILS") el.open = true;
  }
  // A work's record folds to one line on a phone; it stays open elsewhere.
  var fold = document.querySelector(".lg-record-fold");
  if (fold && window.matchMedia && window.matchMedia("(max-width: 560px)").matches) fold.removeAttribute("open");
  window.addEventListener("hashchange", openTarget);
  openTarget();

})();
