// Logia's own site script, beside the Open Word Bible's web/site.js: the
// passage search (home, Read, page not found, and the footer), "Continue reading" (the last
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
  // A page without #search-data (all but home, Read and page not found) has
  // only the footer's box, which loads the same data from /search.json when
  // it is first used.
  var waiting = null;
  function withData(then) {
    if (D) return then();
    if (!waiting) {
      waiting = fetch("/search.json").then(function (r) { return r.json(); })
        .then(function (d) { D = d; }, function () { waiting = null; });
    }
    waiting.then(function () { if (D) then(); });
  }

  // "John 3:16", "jn 3.16", "1 Cor 13", "Ps 23 4", "john3:16": a book (any
  // name or abbreviation in D.aliases, or the start of a book's name), then
  // a chapter and maybe a verse. Returns {code, chapter, verse} or null.
  // How many letters to add, drop, change or swap to turn a into b, up to
  // max (then max + 1): for names typed as they sound ("Mathew", "Jhon").
  function distance(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    var prev2 = null, prev = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      var cur = [i], low = i;
      for (j = 1; j <= b.length; j++) {
        var cost = a[i - 1] === b[j - 1] ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
        if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cur[j] = Math.min(cur[j], prev2[j - 2] + 1);
        low = Math.min(low, cur[j]);
      }
      if (low > max) return max + 1;
      prev2 = prev; prev = cur;
    }
    return prev[b.length];
  }
  function bookOf(name) {
    var key = name.toLowerCase().replace(/[.\s]+/g, " ").trim().replace(/^(i{1,3})\s/, function (m, r) { return r.length + " "; });
    if (!key) return null;
    if (D.aliases[key]) return D.aliases[key];
    var squeezed = key.replace(/ /g, "");
    if (D.aliases[squeezed]) return D.aliases[squeezed];
    var hits = Object.keys(D.names).filter(function (c) {
      return D.names[c].toLowerCase().replace(/ /g, "").indexOf(squeezed) === 0;
    });
    if (hits.length === 1) return hits[0];
    // Near misses: one slip in a short name, two in a long one, against the
    // books' names and their usual forms; only when one book is nearest.
    if (squeezed.length < 4) return null;
    var max = squeezed.length > 6 ? 2 : 1;
    function nearest(keys, codeOf) {
      var best = null, bestD = max + 1, tie = false;
      keys.forEach(function (k) {
        var d = distance(squeezed, k.toLowerCase().replace(/ /g, ""), max), code = codeOf(k);
        if (d < bestD) { best = code; bestD = d; tie = false; }
        else if (d === bestD && code !== best) tie = true;
      });
      return best && !tie ? best : null;
    }
    // The books' own names first ("Jhon" is John, not "Jon" for Jonah).
    return nearest(Object.keys(D.names).map(function (c) { return D.names[c]; }), function (n) {
      return Object.keys(D.names).filter(function (c) { return D.names[c] === n; })[0];
    }) || nearest(Object.keys(D.aliases), function (k) { return D.aliases[k]; });
  }
  // Whether a book's chapter has commentary (D.has: "1-3,7" per book).
  function hasCommentary(code, chapter) {
    return (D.has[code] || "").split(",").some(function (r) {
      var ab = r.split("-"); return chapter >= +ab[0] && chapter <= +(ab[1] || ab[0]);
    });
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
    if (r) {
      var note = D.ui[r.verse ? "verse" : "chapter"];
      if (D.has && !hasCommentary(r.code, r.chapter)) note += " · " + D.ui.text_only;
      out.push({ href: refHref(r), title: refLabel(r), note: note });
    }
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
    var people = D.people.filter(function (p) { return p[0].toLowerCase().indexOf(low) >= 0; });
    // A commentator's name misspelt ("calvn", "agustine"): any word of it
    // within a slip or two.
    if (!people.length && low.length >= 4 && !r) {
      people = D.people.filter(function (p) {
        return p[0].toLowerCase().split(/[\s.]+/).some(function (w) { return w.length >= 3 && distance(low, w, low.length > 6 ? 2 : 1) <= (low.length > 6 ? 2 : 1); });
      }).map(function (p) { return [p[0], p[1], fmt(D.ui.meant, { name: p[0] })]; });
    }
    people.forEach(function (p) { if (out.length < 8) out.push({ href: p[1], title: p[0], note: p[2] }); });
    // Anything that isn't only a reference can be looked for in the
    // excerpts' own words (/search/, full_text below).
    if (!r && low.length >= 3 && D.ui.words) {
      out.push({ href: "/search/?q=" + encodeURIComponent(q.trim()), title: fmt(D.ui.words, { q: q.trim() }), note: D.ui.words_note });
    }
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
        // The link is the option (an option may hold nothing focusable).
        return '<li role="none"><a role="option" id="' + list.id + "-" + i + '"' + (i === at ? ' aria-selected="true"' : "") + ' href="' + esc(x.href) +
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
    input.addEventListener("focus", function () { withData(function () {}); });
    input.addEventListener("input", function () { withData(render); });
    input.addEventListener("keydown", function (e) {
      if (!items.length) return;
      if (e.key === "ArrowDown") { at = (at + 1) % items.length; mark(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { at = (at - 1 + items.length) % items.length; mark(); e.preventDefault(); }
      else if (e.key === "Escape") { list.hidden = true; input.setAttribute("aria-expanded", "false"); }
    });
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      withData(function () {
        if (!items.length) render();
        if (items.length) location.href = items[Math.max(0, at)].href;
      });
    });
    document.addEventListener("click", function (e) { if (!form.contains(e.target)) { list.hidden = true; input.setAttribute("aria-expanded", "false"); } });
  });

  // The header's search pop-up (search_palette in scripts/build_site.py): a
  // modal <dialog>, so focus stays inside it and Esc closes it. The search
  // button, "/" and Ctrl+K (or ⌘K) open it; a click outside its box, the
  // Esc button or Esc closes it, and focus goes back where it was.
  var palette = document.getElementById("palette");
  if (palette && palette.showModal) {
    var palInput = palette.querySelector("input"), palBack = null;
    var openPalette = function () {
      if (palette.open) { palInput.focus(); return; }
      palBack = document.activeElement;
      document.documentElement.classList.add("palette-open");
      palette.showModal();
      palInput.focus();
      palInput.select();
      withData(function () {});
    };
    palette.addEventListener("close", function () {
      document.documentElement.classList.remove("palette-open");
      // The phone menu closes behind the pop-up: then back to its button.
      var back = palBack && palBack.offsetParent ? palBack : document.querySelector(".menu-btn");
      if (back && back.offsetParent && back.focus) back.focus();
    });
    palette.addEventListener("click", function (e) { if (e.target === palette) palette.close(); });
    palette.querySelector("[data-search-close]").addEventListener("click", function () { palette.close(); });
    document.querySelectorAll("[data-search-open]").forEach(function (b) {
      b.addEventListener("click", function (e) { e.preventDefault(); openPalette(); });
    });
    document.addEventListener("keydown", function (e) {
      var typing = /input|textarea|select/i.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
      if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey) && !e.altKey) { e.preventDefault(); openPalette(); }
      else if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); openPalette(); }
    });
  }

  // Page not found: an address that reads as a reference ("/jn3",
  // "/john/3/16", "/rom-8") or names a commentator ("/calvin") is offered
  // as a link.
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
      else {
        // A commentator's name or page id ("/calvin", "/chrysostom",
        // "/commentators/augustin"): the first whose id or a name word
        // matches a word of the address.
        var plain = function (x) { return x.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); };
        var asked = plain(words).split(" ").filter(function (w) { return w.length > 3 && w !== "commentators"; });
        D.people.some(function (p) {
          var id = p[1].split("/")[2], names = plain(p[0]).split(/[\s.]+/);
          var hit = asked.some(function (w) {
            return w === id || names.indexOf(w) >= 0 || (w.length > 5 && id.indexOf(w.slice(0, -1)) === 0);
          });
          if (hit) { href = p[1]; label = p[0]; }
          return hit;
        });
      }
    }
    if (!href) return;
    // An address that is plainly a reference (/John.3.16, /jn3:16, /rom8) goes
    // straight to its page; a name or a near miss is offered as a link.
    if (r && location.pathname.split("/").filter(Boolean).length === 1) { location.replace(href); return; }
    guess.innerHTML = fmt(esc(guess.getAttribute("data-text")), { link: '<a href="' + esc(href) + '">' + esc(label) + "</a>" });
    guess.hidden = false;
  })();

  // Continue reading: the last verse read (web/reader.js keeps it).
  document.querySelectorAll("[data-resume]").forEach(function (a) {
    var last = null;
    try { last = JSON.parse(localStorage.getItem("logia-last") || "null"); } catch (e) { /* storage blocked */ }
    if (!last || !last.href || last.href.charAt(0) !== "/") return;
    // A book page offers to go on only in its own book, before its start button.
    var only = a.getAttribute("data-resume-book");
    if (only && last.href.indexOf(only) !== 0) return;
    a.href = last.href;
    a.textContent = fmt(a.getAttribute("data-resume"), { ref: last.ref });
    a.hidden = false;
    if (only && a.nextElementSibling) a.nextElementSibling.classList.add("ghost");
  });

  // Home: Continue reading. The last verse read (logia-last, kept by
  // web/reader.js), then up to four other chapters read lately (logia-read).
  var cont = document.querySelector(".lg-continue");
  if (cont) {
    var lastAt = null, readList = [];
    try {
      lastAt = JSON.parse(localStorage.getItem("logia-last") || "null");
      readList = JSON.parse(localStorage.getItem("logia-read") || "[]");
    } catch (e) { /* storage blocked */ }
    if (lastAt && lastAt.href && lastAt.href.charAt(0) === "/") {
      var names = JSON.parse(cont.getAttribute("data-books"));
      var main = cont.querySelector(".lg-continue-main");
      main.href = lastAt.href;
      main.querySelector("b").textContent = lastAt.ref;
      var here = lastAt.href.split("#")[0], seen = {}, items = [];
      readList.slice().reverse().forEach(function (h) {
        var m = h.match(/^\/([a-z0-9]{3})\/(\d+)\/$/);
        if (!m || h === here || seen[h] || !names[m[1]] || items.length >= 4) return;
        seen[h] = true;
        items.push('<li><a href="' + esc(h) + '">' + esc(fmt(cont.getAttribute("data-chapter"), { book: names[m[1]], chapter: m[2] })) + "</a></li>");
      });
      if (items.length) {
        var recent = cont.querySelector(".lg-continue-recent");
        recent.querySelector("ul").innerHTML = items.join("");
        recent.hidden = false;
      }
      cont.hidden = false;
    }
  }

  // Home: the verse of the day. The page holds the day it was built on; the
  // reader's own day is fetched from /votd/<n>.html when it differs.
  var votd = document.querySelector("[data-votd]");
  if (votd) {
    var now = new Date(), epoch = votd.getAttribute("data-votd-epoch").split("-");
    var days = Math.floor((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - Date.UTC(+epoch[0], +epoch[1] - 1, +epoch[2])) / 864e5);
    var n = +votd.getAttribute("data-votd-n"), want = ((days % n) + n) % n;
    var dateLabel = votd.querySelector(".lg-votd-date");
    try {
      dateLabel.textContent = "· " + now.toLocaleDateString(document.documentElement.lang || undefined, { weekday: "long", day: "numeric", month: "long" });
      dateLabel.hidden = false;
    } catch (e) { /* no date formatting */ }
    if (want !== +votd.getAttribute("data-votd")) {
      fetch("/votd/" + want + ".html").then(function (r) { return r.ok ? r.text() : null; }).then(function (html) {
        if (!html) return;
        var panel = votd.querySelector(".lg-votd-panel");
        if (panel) panel.outerHTML = html;
        votd.setAttribute("data-votd", want);
      }).catch(function () { /* keep the built day's verse */ });
    }
  }

  // The book page's chapter bar: say which end has more chapters out of
  // view, so the CSS can fade that edge.
  document.querySelectorAll(".lg-book-bar .chap-pills").forEach(function (row) {
    var mark = function () {
      var room = row.scrollWidth - row.clientWidth;
      var left = row.scrollLeft > 4, right = row.scrollLeft < room - 4;
      if (room <= 4) row.removeAttribute("data-more");
      else row.setAttribute("data-more", left && right ? "both" : left ? "start" : "end");
    };
    row.addEventListener("scroll", mark, { passive: true });
    window.addEventListener("resize", mark);
    mark();
  });

  // Chapters already read: a dot on their chip (web/reader.js keeps the list).
  var read = [];
  try { read = JSON.parse(localStorage.getItem("logia-read") || "[]"); } catch (e) { /* storage blocked */ }
  if (read.length) {
    document.querySelectorAll("a.chap").forEach(function (a) {
      if (read.indexOf(a.getAttribute("href")) >= 0) a.classList.add("lg-read");
    });
    // A book page: a tick on each chapter read, and how many.
    document.querySelectorAll(".lg-toc-book > li > a").forEach(function (a) {
      if (read.indexOf(a.getAttribute("href")) >= 0) a.parentNode.classList.add("lg-read");
    });
    document.querySelectorAll("[data-read-count]").forEach(function (p) {
      var prefix = p.getAttribute("data-prefix");
      var n = read.filter(function (h) { return /^\/[a-z0-9]+\/\d+\/$/.test(h) && h.indexOf(prefix) === 0; }).length;
      if (!n) return;
      p.textContent = fmt(p.getAttribute("data-read-count"), { n: n });
      p.hidden = false;
    });
  }

  // A book page's "Go to a verse" box: "5:3", "5 3" or "5.3" opens the
  // chapter at that verse.
  // A verse page's voices rail: mark the voice now at the top of the screen.
  var vrail = document.querySelector(".lg-vrail");
  if (vrail && "IntersectionObserver" in window) {
    var railLinks = {};
    vrail.querySelectorAll("a").forEach(function (a) { railLinks[a.getAttribute("href").slice(1)] = a; });
    var seen = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { seen[en.target.id] = en.isIntersecting; });
      var first = null;
      document.querySelectorAll(".lg-voice").forEach(function (sec) { if (!first && seen[sec.id]) first = sec.id; });
      Object.keys(railLinks).forEach(function (id) {
        if (id === first) railLinks[id].setAttribute("aria-current", "true"); else railLinks[id].removeAttribute("aria-current");
      });
    }, { rootMargin: "-30% 0px -50% 0px" });
    document.querySelectorAll(".lg-voice").forEach(function (sec) { io.observe(sec); });
  }

  document.querySelectorAll(".lg-verse-go").forEach(function (form) {
    var verses = JSON.parse(form.getAttribute("data-verses"));
    var input = form.querySelector("input"), note = form.querySelector("[role=status]");
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var m = input.value.trim().match(/(\d+)\s*[:.\s]\s*(\d+)$/) || input.value.trim().match(/^(\d+)$/);
      var ch = m && +m[1], v = m && m[2] ? +m[2] : 1;
      if (!m || !verses[ch] || v < 1 || v > verses[ch]) { note.textContent = form.getAttribute("data-none"); return; }
      location.href = form.getAttribute("data-book") + ch + "/#v" + v;
    });
  });

  // The header (site_header in scripts/build_site.py): the chapter pickers,
  // the "Continue" pill, the dark-mode button and the reading progress line.
  (function () {
    var holder = document.getElementById("nav-data");
    var N = holder ? JSON.parse(holder.textContent) : null;
    var where = document.querySelector(".lg-where");
    var hereBook = where ? where.getAttribute("data-book") : null;
    var hereChapter = where ? +where.getAttribute("data-chapter") : 0;

    // A book's chapters as links: gold-edged where there is commentary, a
    // dot where the reader has been, the current one filled.
    function grid(code) {
      var b = N.books[code], out = [];
      for (var c = 1; c <= b.n; c++) {
        var href = "/" + code.toLowerCase() + "/" + c + "/";
        var has = b.has.indexOf(c) >= 0, cur = code === hereBook && c === hereChapter;
        out.push('<a href="' + href + '" class="lg-ch' + (has ? " lg-has" : "") + (read.indexOf(href) >= 0 ? " lg-read" : "") + '"' +
          (cur ? ' aria-current="page"' : "") + (has ? ' title="' + esc(b.name + " " + c + ", " + N.ui.has) + '"' : "") + ">" + c + "</a>");
      }
      return '<p class="dd-head">' + esc(fmt(N.ui.chapters, { book: b.name })) + "</p>" +
        '<div class="lg-chgrid' + (b.n > 60 ? " lg-chgrid-long" : "") + '">' + out.join("") + "</div>";
    }

    if (N && where) {
      var btn = where.querySelector(".lg-where-btn"), pop = document.getElementById("lg-where-pop");
      var shut = function (back) {
        if (pop.hidden) return;
        pop.hidden = true; btn.setAttribute("aria-expanded", "false");
        if (back) btn.focus();
      };
      btn.addEventListener("click", function () {
        if (!pop.hidden) { shut(false); return; }
        var others = Object.keys(N.books).filter(function (c) { return c !== hereBook && N.books[c].has.length; });
        pop.innerHTML = grid(hereBook) + (others.length ? '<p class="dd-head">' + esc(N.ui.others) + '</p><div class="lg-where-books">' +
          others.map(function (c) { return '<a href="/' + c.toLowerCase() + '/">' + esc(N.books[c].name) + "</a>"; }).join("") + "</div>" : "");
        pop.hidden = false; btn.setAttribute("aria-expanded", "true");
        var first = pop.querySelector('[aria-current="page"]') || pop.querySelector("a");
        if (first) first.focus();
      });
      pop.addEventListener("keydown", function (e) { if (e.key === "Escape") { e.stopPropagation(); shut(true); } });
      document.addEventListener("click", function (e) { if (!where.contains(e.target)) shut(false); });
      where.addEventListener("focusout", function (e) { if (e.relatedTarget && !where.contains(e.relatedTarget)) shut(false); });
    }

    // The Read menu: the chapters of the book pointed at, beside the books.
    var chapters = document.querySelector("[data-nav-chapters]");
    if (N && chapters) {
      var shown = null;
      var show = function (code) {
        if (!N.books[code] || code === shown) return;
        shown = code; chapters.innerHTML = grid(code); chapters.hidden = false;
      };
      var books = document.querySelectorAll(".dd-book[data-book]");
      var start = hereBook && N.books[hereBook].has.length ? hereBook : null;
      if (!start) {
        var last = null;
        try { last = JSON.parse(localStorage.getItem("logia-last") || "null"); } catch (e) { /* storage blocked */ }
        var m = last && last.href && last.href.match(/^\/([a-z0-9]{3})\//);
        start = m && N.books[m[1].toUpperCase()] ? m[1].toUpperCase() : (books[0] && books[0].getAttribute("data-book").toUpperCase());
      }
      if (start) show(start);
      books.forEach(function (a) {
        var code = a.getAttribute("data-book").toUpperCase();
        a.addEventListener("mouseenter", function () { show(code); });
        a.addEventListener("focus", function () { show(code); });
      });
    }

    // One tap between light and dark: the settings menu's own theme buttons
    // (web/site.js) do the choosing, so the two always agree. It returns to
    // the light or dark mode chosen last (sepia, night...).
    var toggle = document.querySelector("[data-theme-toggle]");
    var themes = document.querySelector('#colour-menu [data-pref="theme"]');
    if (toggle && themes) {
      var root = document.documentElement, dark = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
      var isDark = function () {
        var v = root.getAttribute("data-theme");
        return v === "dark" || v === "night" || (v === "auto" && !!dark && dark.matches);
      };
      var sync = function () { toggle.setAttribute("aria-pressed", isDark() ? "true" : "false"); };
      toggle.hidden = false;
      sync();
      document.addEventListener("logia:prefs", sync);
      if (dark && dark.addEventListener) dark.addEventListener("change", sync);
      toggle.addEventListener("click", function () {
        var was = root.getAttribute("data-theme") || "light", to;
        try {
          if (isDark()) { localStorage.setItem("logia-last-dark", was === "auto" ? "dark" : was); to = localStorage.getItem("logia-last-light") || "light"; }
          else { localStorage.setItem("logia-last-light", was === "auto" ? "light" : was); to = localStorage.getItem("logia-last-dark") || "dark"; }
        } catch (e) { to = isDark() ? "light" : "dark"; }
        var option = themes.querySelector('[data-value="' + to + '"]');
        if (option) option.click();
      });
    }

    // How far through the chapter's text, or a whole homily's, the reader has scrolled.
    var bar = document.querySelector(".lg-progress span"), text = document.getElementById("text") || document.querySelector(".lg-whole");
    if (bar && text) {
      var tick = false;
      var update = function () {
        tick = false;
        var r = text.getBoundingClientRect(), span = r.height - window.innerHeight * 0.6;
        var p = span > 0 ? Math.min(1, Math.max(0, (window.innerHeight * 0.4 - r.top) / span)) : 1;
        bar.style.transform = "scaleX(" + p.toFixed(3) + ")";
      };
      window.addEventListener("scroll", function () { if (!tick) { tick = true; requestAnimationFrame(update); } }, { passive: true });
      window.addEventListener("resize", update);
      update();
    }
  })();

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
  // The commentators page: book chips that narrow the cards to those who
  // comment on that book and dim the other lives on the timeline.
  document.querySelectorAll(".lg-pick").forEach(function (pick) {
    var chips = [].slice.call(pick.querySelectorAll("button"));
    var cards = [].slice.call(pick.parentNode.querySelectorAll("li[data-books]"));
    var rows = [].slice.call(document.querySelectorAll(".lg-tl-row[data-author]"));
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        var book = chip.getAttribute("data-book"), shown = {};
        chips.forEach(function (x) { x.setAttribute("aria-pressed", x === chip ? "true" : "false"); });
        cards.forEach(function (li) {
          var on = !book || li.getAttribute("data-books").split(" ").indexOf(book) >= 0;
          li.hidden = !on;
          if (on) shown[li.getAttribute("data-author")] = true;
        });
        rows.forEach(function (row) { row.classList.toggle("lg-tl-dim", !shown[row.getAttribute("data-author")]); });
      });
    });
    pick.hidden = false;
  });
  document.querySelectorAll(".lg-goto:not(.lg-goto-work)").forEach(function (form) {
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

  // A work's page: go to the verse in the work's chapter page, to the
  // excerpt whose verses hold it (data-ranges: "from-to,..." a chapter).
  document.querySelectorAll(".lg-goto-work").forEach(function (form) {
    var books = JSON.parse(form.getAttribute("data-books"));
    var ranges = JSON.parse(form.getAttribute("data-ranges"));
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
      var list = code && ranges[code][String(+m[2])];
      var from = null;
      if (list) {
        var v = +m[3];
        list.split(",").forEach(function (r) {
          var p = r.split("-");
          if (from === null && +p[0] <= v && v <= +p[1]) from = p[0];
        });
      }
      if (from === null) { note.textContent = form.getAttribute("data-none"); return; }
      note.textContent = hint;
      location.href = form.getAttribute("data-base") + code.toLowerCase() + "/" + (+m[2]) + "/#v" + from;
    });
  });

  // A commentator's page: a passage in their words, a different one each
  // day (the page shows the first without script), and another on request.
  document.querySelectorAll(".lg-own[data-quotes]").forEach(function (fig) {
    var pool = JSON.parse(fig.getAttribute("data-quotes"));
    if (pool.length < 2) return;
    var p = fig.querySelector("blockquote p"), meta = fig.querySelector(".lg-quiet");
    var link = meta.querySelector("a"), work = meta.querySelector("i"), next = fig.querySelector(".lg-own-next");
    var at = Math.floor(Date.now() / 864e5) % pool.length;
    var show = function () {
      var x = pool[at];
      // As in_quotes() in build_site.py: no second mark when the passage opens with one.
      p.textContent = /^[“"‘']/.test(x.q) ? x.q : "“" + x.q + "”";
      link.textContent = x.ref; link.href = x.href; work.textContent = x.work;
    };
    show();
    next.hidden = false;
    next.addEventListener("click", function () { at = (at + 1) % pool.length; show(); });
  });

  // One book or all of them: the switch hides the other books' rows, chapter
  // bar, maps and start-here passages (with all, one passage from each book).
  document.querySelectorAll(".lg-bookpick").forEach(function (pick) {
    var buttons = [].slice.call(pick.querySelectorAll("button"));
    var page = pick.closest(".lg-author") || document;
    var set = function (book) {
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-book") === book)); });
      [].forEach.call(page.querySelectorAll("[data-book]:not(button)"), function (el) {
        var mine = !book || el.getAttribute("data-book") === book;
        if (el.hasAttribute("data-rank")) mine = book ? mine : el.getAttribute("data-rank") === "0";
        el.hidden = !mine;
      });
      try { sessionStorage.setItem("lg-book", book); } catch (err) { /* private window */ }
    };
    buttons.forEach(function (b) { b.addEventListener("click", function () { set(b.getAttribute("data-book")); }); });
    pick.hidden = false;
    var kept = null;
    try { kept = sessionStorage.getItem("lg-book"); } catch (err) { /* private window */ }
    if (kept && buttons.some(function (b) { return b.getAttribute("data-book") === kept; })) set(kept);
  });

  // The bar of sections: the one being read is marked, and the chapter bar
  // below it sits under it.
  document.querySelectorAll(".lg-secbar").forEach(function (bar) {
    var strip = bar.querySelector(".lg-secbar-in"), links = [].slice.call(strip.querySelectorAll("a"));
    var page = bar.closest(".lg-author");
    var fit = function () { if (page) page.style.setProperty("--secbar-h", bar.offsetHeight + "px"); };
    fit();
    window.addEventListener("resize", fit);
    if (!("IntersectionObserver" in window)) return;
    var seen = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (x) { seen[x.target.id] = x.isIntersecting; });
      var on = null;
      links.forEach(function (a) { if (!on && seen[a.getAttribute("href").slice(1)]) on = a; });
      links.forEach(function (a) {
        if (a === on) { a.setAttribute("aria-current", "true"); strip.scrollLeft = a.offsetLeft - strip.offsetLeft - 16; }
        else a.removeAttribute("aria-current");
      });
    }, { rootMargin: "-120px 0px -55% 0px" });
    links.forEach(function (a) {
      var el = document.getElementById(a.getAttribute("href").slice(1));
      if (el) io.observe(el);
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
  // Offline (web/sw.js): register the service worker, the "Keep this book
  // for offline" button on a book's page, and the list on /offline/ of what
  // this device holds. Cache names match web/sw.js.
  var canKeep = "serviceWorker" in navigator && "caches" in window &&
    (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1");
  if (canKeep) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () { /* not available here */ });
    });
  }

  var keepBox = document.querySelector("[data-keep]");
  if (keepBox && canKeep) {
    var keepUrls = JSON.parse(keepBox.getAttribute("data-keep"));
    var keepBtn = keepBox.querySelector("button");
    var keepSay = keepBox.querySelector("[role=status]");
    var keepDone = function () { keepBtn.hidden = true; keepSay.textContent = keepBox.getAttribute("data-done"); };
    keepBox.hidden = false;
    caches.open("logia-kept").then(function (c) {
      return Promise.all([c.match(keepUrls[0]), c.match(keepUrls[keepUrls.length - 1])]);
    }).then(function (hits) { if (hits[0] && hits[1]) keepDone(); }).catch(function () { /* ignore */ });
    keepBtn.addEventListener("click", function () {
      keepBtn.disabled = true;
      var failed = 0;
      caches.open("logia-kept").then(function (cache) {
        var one = function (i) {
          if (i >= keepUrls.length) return Promise.resolve();
          keepSay.textContent = fmt(keepBox.getAttribute("data-saving"), { done: i + 1, total: keepUrls.length });
          return fetch(keepUrls[i]).then(function (res) {
            if (!res.ok) throw new Error(res.status);
            return res.clone().text().then(function (html) {
              var m = html.match(/<script type="application\/json" id="chapter-data">([\s\S]*?)<\/script>/);
              var data = m ? JSON.parse(m[1]) : {};
              var files = [data.panel, data.comm].filter(Boolean);
              return Promise.all(files.map(function (u) { return cache.add(u); })).then(function () { return cache.put(keepUrls[i], res); });
            });
          }).catch(function () { failed++; }).then(function () { return one(i + 1); });
        };
        return one(0);
      }).then(function () {
        keepBtn.disabled = false;
        if (failed) keepSay.textContent = keepBox.getAttribute("data-failed");
        else keepDone();
      });
    });
  }

  var offlineList = document.getElementById("lg-offline-list");
  if (offlineList && "caches" in window) {
    Promise.all(["logia-kept", "logia-pages"].map(function (name) {
      return caches.open(name).then(function (c) {
        return c.keys().then(function (keys) {
          return Promise.all(keys.reverse().map(function (k) {
            return c.match(k).then(function (res) { return res.text(); }).then(function (html) {
              var m = html.match(/<title>([^<]*)<\/title>/);
              return { href: new URL(k.url).pathname, title: m ? m[1].replace(/ · Logia$/, "") : new URL(k.url).pathname };
            });
          }));
        });
      });
    })).then(function (lists) {
      var seen = {}, rows = [];
      lists[0].concat(lists[1]).forEach(function (p) {
        if (seen[p.href] || p.href === "/offline/" || !/\/$/.test(p.href)) return;
        seen[p.href] = 1;
        rows.push('<li><a href="' + esc(p.href) + '">' + p.title + "</a></li>");
      });
      offlineList.innerHTML = rows.length ? rows.join("") : "<li>" + esc(offlineList.getAttribute("data-none")) + "</li>";
    }).catch(function () { offlineList.innerHTML = "<li>" + esc(offlineList.getAttribute("data-none")) + "</li>"; });
  }
  // /search/: the words of every excerpt, through Pagefind's index in
  // /pagefind/ (build_search_index in scripts/build_site.py). Filters for
  // era, tradition and book are chips with the count each would give; the
  // commentator is a list. The query and filters are kept in the address,
  // so a search can be shared.
  (function () {
    var form = document.querySelector("form.lg-fts");
    if (!form) return;
    var U = JSON.parse(form.getAttribute("data-ui"));
    var input = form.querySelector("#fts-q"), status = document.getElementById("fts-status");
    var list = document.getElementById("fts-results"), more = document.getElementById("fts-more");
    var who = form.querySelector("#fts-who");
    var src = form.getAttribute("data-pagefind");
    if (!src) return;
    var pf = null, allCounts = {}, chosen = { era: [], tradition: [], book: [], commentator: [] }, results = [], shown = 0, run = 0, timer = null;
    var params = new URLSearchParams(location.search);
    input.value = params.get("q") || "";
    Object.keys(chosen).forEach(function (k) { chosen[k] = params.getAll(k); });
    function filters(but) {
      var f = {};
      Object.keys(chosen).forEach(function (k) { if (k !== but && chosen[k].length) f[k] = { any: chosen[k] }; });
      return f;
    }
    // Each group's counts as if nothing were chosen in it, so its other
    // values stay offered: one more search for each group with a choice.
    function facetCounts(q, counts) {
      var groups = Object.keys(chosen).filter(function (k) { return chosen[k].length; });
      return Promise.all(groups.map(function (k) {
        return pf.search(q || null, { filters: filters(k) }).then(function (s) { counts[k] = s.filters[k] || {}; });
      })).then(function () { return counts; });
    }
    function keep() {
      var p = new URLSearchParams();
      if (input.value.trim()) p.set("q", input.value.trim());
      Object.keys(chosen).forEach(function (k) { chosen[k].forEach(function (v) { p.append(k, v); }); });
      var qs = p.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
    }
    function chips(counts) {
      form.querySelectorAll(".lg-fts-group[data-filter]").forEach(function (g) {
        var k = g.getAttribute("data-filter"), c = counts[k] || {};
        var names = Object.keys(c).filter(function (v) { return c[v] || chosen[k].indexOf(v) >= 0; });
        if (k === "era" || k === "book") {
          var order = Object.keys(allCounts[k] || {});
          names.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
        } else names.sort();
        if (k === "commentator") {
          who.innerHTML = '<option value="">' + esc(who.options[0].text) + "</option>" + names.map(function (v) {
            return '<option value="' + esc(v) + '"' + (chosen[k].indexOf(v) >= 0 ? " selected" : "") + ">" + esc(v) + " (" + (c[v] || 0) + ")</option>";
          }).join("");
        } else {
          g.querySelector(".lg-fts-chips").innerHTML = names.map(function (v) {
            return '<button type="button" class="cx-chip" data-k="' + k + '" data-v="' + esc(v) + '" aria-pressed="' + (chosen[k].indexOf(v) >= 0) + '">' +
              esc(v) + ' <span class="cx-chip-n">' + (c[v] || 0) + "</span></button>";
          }).join("");
        }
        g.hidden = !names.length;
      });
    }
    function card(d) {
      var m = d.meta;
      return '<li class="lg-fts-hit"><p class="lg-fts-head"><a href="' + esc(m.link) + '"><b>' + esc(m.title) + "</b></a>" +
        ' <span class="lg-quiet">' + esc(m.dates) + " · <i>" + esc(m.work) + "</i></span></p>" +
        '<p class="lg-fts-text">' + d.excerpt + "</p></li>";
    }
    function showMore() {
      var next = results.slice(shown, shown + 10);
      shown += next.length;
      more.hidden = true;
      return Promise.all(next.map(function (r) { return r.data(); })).then(function (ds) {
        list.insertAdjacentHTML("beforeend", ds.map(card).join(""));
        more.hidden = shown >= results.length;
      });
    }
    // "author:calvin light", "era:early book:john": a word before a colon
    // (U.operators) chooses a filter, matched to the start of its values.
    function operators() {
      var ops = U.operators || {}, left = [], changed = false;
      input.value.trim().split(/\s+/).forEach(function (w) {
        var m = /^([a-z]+):(.+)$/i.exec(w), k = m && ops[m[1].toLowerCase()];
        var values = k && Object.keys(allCounts[k] || {});
        var want = m && m[2].toLowerCase().replace(/[_-]/g, " ");
        var hit = values && values.filter(function (v) {
          var low = v.toLowerCase();
          return low.indexOf(want) === 0 || low.split(/\s+/).some(function (x) { return x.indexOf(want) === 0; });
        })[0];
        if (hit) { if (chosen[k].indexOf(hit) < 0) chosen[k].push(hit); changed = true; } else if (w) left.push(w);
      });
      if (changed) input.value = left.join(" ");
      return input.value.trim();
    }
    // The old editions' spellings of a modern word (U.spellings: "show" also
    // finds "shew"): one more search for each, the results merged, best first.
    function variants(q) {
      var sp = U.spellings || {}, words = q.toLowerCase().split(/\s+/), out = [], extra = [];
      words.forEach(function (w, i) {
        (sp[w] || []).forEach(function (old) {
          var copy = words.slice(); copy[i] = old; out.push(copy.join(" ")); extra.push(old);
        });
      });
      return { queries: out.slice(0, 4), words: extra.slice(0, 4) };
    }
    function find(q, f) {
      var base = pf.search(q || null, f), more2 = q ? variants(q) : { queries: [], words: [] };
      if (!more2.queries.length) return base;
      return Promise.all([base].concat(more2.queries.map(function (v) { return pf.search(v, f); }))).then(function (all) {
        var seen = {}, merged = [];
        all.forEach(function (s) { s.results.forEach(function (r) { if (!seen[r.id]) { seen[r.id] = true; merged.push(r); } }); });
        merged.sort(function (a, b) { return b.score - a.score; });
        var extra = all.slice(1).some(function (s) { return s.results.length; });
        return { results: merged, filters: all[0].filters, oldWords: extra ? more2.words : [] };
      });
    }
    function search() {
      var q = operators(), mine = ++run, any = Object.keys(filters()).length;
      keep();
      if (!q && !any) { list.innerHTML = ""; more.hidden = true; status.textContent = U.start; chips(allCounts); return; }
      status.textContent = U.searching;
      find(q, { filters: filters() }).then(function (s) {
        if (mine !== run) return;
        results = s.results; shown = 0; list.innerHTML = "";
        var counts = {};
        Object.keys(s.filters).forEach(function (k) { counts[k] = s.filters[k]; });
        facetCounts(q, counts).then(function (c) { if (mine === run) chips(c); });
        status.innerHTML = esc(!results.length ? fmt(U.none, { q: q })
          : any ? fmt(U.count_filtered, { n: results.length.toLocaleString() })
          : fmt(results.length === 1 ? U.count_one : U.count, { n: results.length.toLocaleString(), q: q })) +
          (any ? ' <button type="button" class="cx-chip-all" data-clear>' + esc(U.clear) + "</button>" : "") +
          (s.oldWords && s.oldWords.length ? ' <span class="lg-quiet">' + esc(fmt(U.spelling_note, { words: s.oldWords.join(", ") })) + "</span>" : "");
        return showMore();
      }).catch(function () { if (mine === run) status.textContent = U.failed; });
    }
    import(src).then(function (m) {
      pf = m;
      return pf.options({ excerptLength: 36 }).then(function () { return pf.filters(); });
    }).then(function (all) {
      allCounts = all;
      search();
    }).catch(function () { status.textContent = U.failed; });
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { if (pf) search(); }, 250); });
    form.addEventListener("submit", function (e) { e.preventDefault(); if (pf) search(); });
    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-k]");
      if (!b || !pf) return;
      var k = b.getAttribute("data-k"), v = b.getAttribute("data-v"), i = chosen[k].indexOf(v);
      if (i >= 0) chosen[k].splice(i, 1); else chosen[k].push(v);
      search();
    });
    who.addEventListener("change", function () { chosen.commentator = who.value ? [who.value] : []; if (pf) search(); });
    status.addEventListener("click", function (e) {
      if (!e.target.closest("[data-clear]")) return;
      Object.keys(chosen).forEach(function (k) { chosen[k] = []; });
      search();
    });
    more.addEventListener("click", showMore);
  })();

  // Under an excerpt printed whole (verse and work pages): copy it with its
  // citation, or share a link to it (excerpt_actions in scripts/build_site.py).
  // Where the clipboard is refused, the text is shown to copy by hand.
  document.querySelectorAll(".lg-xact").forEach(function (box) {
    var note = box.querySelector(".lg-xact-note");
    function show(text, copy) {
      note.hidden = false;
      note.textContent = text;
      if (copy !== undefined) {
        var area = document.createElement("textarea");
        area.readOnly = true; area.rows = 4; area.className = "lg-xact-copy"; area.value = copy;
        note.appendChild(area); area.select();
      }
    }
    function copy(text, done) {
      if (!navigator.clipboard) return show(box.dataset.byHand, text);
      navigator.clipboard.writeText(text).then(function () { show(done); }, function () { show(box.dataset.byHand, text); });
    }
    box.querySelectorAll("[data-xact]").forEach(function (b) {
      b.hidden = false;
      b.addEventListener("click", function () {
        if (b.dataset.xact === "share") {
          if (navigator.share) {
            navigator.share({ title: box.dataset.title, text: box.dataset.title, url: box.dataset.url }).catch(function () { /* closed */ });
            return;
          }
          return copy(box.dataset.url, box.dataset.linked);
        }
        var text = box.closest("article").querySelector(".lg-text");
        copy("\u201c" + (text ? text.innerText.trim() : "") + "\u201d\n\n" + box.dataset.cite, box.dataset.done);
      });
    });
  });
  // Verse and passage pages: compare two voices side by side (compare_dialog
  // in scripts/build_site.py). The names are chips, two of them chosen; each
  // column holds that voice's section as the page prints it, unfolded.
  var cmp = document.querySelector("dialog.lg-cmp"), cmpOpen = document.querySelector(".lg-cmp-open");
  var voicesHere = [].slice.call(document.querySelectorAll("section.lg-voice"));
  if (cmp && cmpOpen && cmp.showModal && voicesHere.length > 1) {
    var picked = [voicesHere[0].id, voicesHere[voicesHere.length - 1].id];
    var picks = cmp.querySelector(".lg-cmp-picks"), cols = cmp.querySelector(".lg-cmp-cols");
    var nameOf = function (sec) { var h = sec.querySelector("h3"); return h ? h.textContent.trim() : sec.id; };
    voicesHere.forEach(function (sec) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "cx-chip"; b.setAttribute("data-voice", sec.id); b.textContent = nameOf(sec);
      picks.appendChild(b);
    });
    var drawCompare = function () {
      picks.querySelectorAll("[data-voice]").forEach(function (b) { b.setAttribute("aria-pressed", picked.indexOf(b.getAttribute("data-voice")) >= 0); });
      cols.innerHTML = "";
      picked.forEach(function (id) {
        var sec = document.getElementById(id), col = sec.cloneNode(true);
        col.removeAttribute("id");
        col.className = "lg-cmp-col";
        col.querySelectorAll("[id]").forEach(function (x) { x.removeAttribute("id"); });
        col.querySelectorAll(".lg-xact, .lg-unfold, .lg-vq, .lg-vx-more").forEach(function (x) { x.remove(); });
        col.querySelectorAll(".lg-folded").forEach(function (x) { x.classList.remove("lg-folded"); });
        cols.appendChild(col);
      });
    };
    picks.addEventListener("click", function (e) {
      var b = e.target.closest("[data-voice]"); if (!b) return;
      var id = b.getAttribute("data-voice"), i = picked.indexOf(id);
      if (i >= 0) { if (picked.length > 1) picked.splice(i, 1); }
      else { picked.push(id); if (picked.length > 2) picked.shift(); }
      drawCompare();
    });
    cmpOpen.hidden = false;
    cmpOpen.addEventListener("click", function () { drawCompare(); cmp.showModal(); });
    cmp.querySelector(".lg-cmp-close").addEventListener("click", function () { cmp.close(); });
    cmp.addEventListener("click", function (e) { if (e.target === cmp) cmp.close(); });
  }

  // A sortable table (the most-discussed verses): a heading's button sorts
  // by its column's data-sort, highest first, then lowest on a second press.
  // "Show all" reveals the rows held back.
  document.querySelectorAll("table.lg-sortable").forEach(function (table) {
    var body = table.tBodies[0];
    table.querySelectorAll("[data-sort-col]").forEach(function (b) {
      b.addEventListener("click", function () {
        var col = +b.getAttribute("data-sort-col"), th = b.parentNode;
        var down = th.getAttribute("aria-sort") !== "descending";
        table.querySelectorAll("th[aria-sort]").forEach(function (x) { x.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", down ? "descending" : "ascending");
        var rows = [].slice.call(body.rows);
        rows.sort(function (a, c) {
          var x = +a.cells[col].getAttribute("data-sort"), y = +c.cells[col].getAttribute("data-sort");
          return down ? y - x : x - y;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
    var more = table.closest("section").querySelector("[data-show-rows]");
    if (more) more.addEventListener("click", function () {
      [].forEach.call(body.rows, function (r) { r.hidden = false; });
      more.parentNode.remove();
    });
  });

  // /readings/: each day's next date, the next of them named first, and a
  // calendar to show only its readings (kept as logia-calendar). A day the
  // chosen calendar gives no reading for is faded.
  var readings = document.querySelectorAll(".lg-reading[data-dates]");
  if (readings.length) {
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var lang = document.documentElement.lang || undefined, soonest = null;
    readings.forEach(function (li) {
      var next = li.getAttribute("data-dates").split(" ").map(function (d) { var p = d.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); })
        .filter(function (d) { return d >= today; })[0];
      if (!next) return;
      var label = li.querySelector(".lg-reading-date");
      try { label.textContent = next.toLocaleDateString(lang, { weekday: "long", day: "numeric", month: "long", year: "numeric" }); label.hidden = false; }
      catch (e) { /* no date formatting */ }
      if (!soonest || next < soonest.date) soonest = { li: li, date: next, text: label.textContent };
    });
    var nextBox = document.querySelector(".lg-reading-next");
    if (soonest && nextBox) {
      var a = soonest.li.querySelector("a");
      nextBox.innerHTML = fmt(esc(nextBox.getAttribute("data-next")), { name: '<a href="' + esc(a.getAttribute("href")) + '">' + esc(a.querySelector("b").textContent) + "</a>", date: esc(soonest.text) });
      nextBox.hidden = false;
      soonest.li.classList.add("lg-reading-soon");
    }
    var calPick = document.querySelector(".lg-cal-pick");
    var setCal = function (cal) {
      calPick.querySelectorAll("[data-cal]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-cal") === cal); });
      readings.forEach(function (li) {
        var has = !cal || li.getAttribute("data-cals").split(" ").indexOf(cal) >= 0;
        li.classList.toggle("lg-reading-off", !has);
        li.querySelectorAll("[data-cal]").forEach(function (x) { x.hidden = !!cal && x.getAttribute("data-cal") !== cal; });
      });
      try { localStorage.setItem("logia-calendar", cal); } catch (e) { /* storage blocked */ }
    };
    if (calPick) {
      calPick.addEventListener("click", function (e) { var b = e.target.closest("[data-cal]"); if (b) setCal(b.getAttribute("data-cal")); });
      var savedCal = ""; try { savedCal = localStorage.getItem("logia-calendar") || ""; } catch (e) { /* storage blocked */ }
      if (savedCal && calPick.querySelector('[data-cal="' + savedCal + '"]')) setCal(savedCal);
    }
  }

  // Glossary words in the excerpts (verse, work and whole-text pages): the
  // first use on the page of each word in /glossary.json is marked, and
  // pressing it shows what it means, with a link to its entry. The excerpt's
  // words are unchanged; only a button is put round the first use.
  var texts = document.querySelectorAll(".lg-text, .lg-whole");
  if (texts.length && window.fetch) {
    fetch("/glossary.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (G) {
      if (!G) return;
      var terms = G.terms.map(function (x, i) {
        try { return { i: i, re: new RegExp(x.m, x.f), x: x }; } catch (e) { return null; }
      }).filter(Boolean);
      var left = terms.slice();
      texts.forEach(function (box) {
        if (!left.length) return;
        var walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT, {
          acceptNode: function (n) { return n.parentNode.closest("a, button, mark, sup, .lg-gloss-term") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
        });
        var nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(function (node) {
          for (var k = 0; k < left.length; k++) {
            var m = left[k].re.exec(node.nodeValue);
            if (!m || !m[0]) continue;
            // A pattern may match the start of a word ("glorif"): take the whole word.
            var end = m.index + m[0].length;
            while (end < node.nodeValue.length && /[A-Za-z\u00C0-\u024F]/.test(node.nodeValue.charAt(end))) end++;
            var after = node.splitText(m.index), rest = after.splitText(end - m.index);
            var b = document.createElement("button");
            b.type = "button"; b.className = "lg-gloss-term"; b.setAttribute("data-g", left[k].i); b.setAttribute("aria-expanded", "false");
            b.title = left[k].x.t;
            after.parentNode.replaceChild(b, after); b.appendChild(after);
            left.splice(k, 1);
            node = rest; k = -1;
            if (!left.length) break;
          }
        });
      });
      var pop = null, from = null;
      function closePop() { if (pop) { pop.remove(); pop = null; } if (from) { from.setAttribute("aria-expanded", "false"); from.focus(); from = null; } }
      document.addEventListener("click", function (e) {
        var b = e.target.closest(".lg-gloss-term");
        if (pop && !e.target.closest(".lg-gloss-pop") && b !== from) closePop();
        if (!b || b === from) { if (b === from) closePop(); return; }
        var x = G.terms[+b.getAttribute("data-g")];
        from = b; b.setAttribute("aria-expanded", "true");
        pop = document.createElement("div");
        pop.className = "lg-gloss-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", x.t);
        pop.innerHTML = "<b>" + esc(x.t) + "</b><p>" + esc(x.d) + '</p><p><a href="' + esc(x.h) + '">' + esc(G.ui.more) + "</a></p>" +
          '<button type="button" class="lg-gloss-x" aria-label="' + esc(G.ui.close) + '">×</button>';
        document.body.appendChild(pop);
        var r = b.getBoundingClientRect(), w = Math.min(320, window.innerWidth - 24);
        pop.style.width = w + "px";
        pop.style.left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left + window.scrollX)) + "px";
        pop.style.top = (r.bottom + window.scrollY + 8) + "px";
        pop.querySelector(".lg-gloss-x").addEventListener("click", closePop);
        pop.querySelector("a").focus();
      });
      document.addEventListener("keydown", function (e) { if (e.key === "Escape" && pop) closePop(); });
    }).catch(function () { /* no glossary: the text stays as it is */ });
  }

  // The glossary: a box that keeps only the entries whose word or meaning
  // has what is typed, and hides the groups left empty.
  var glossFind = document.getElementById("gloss-q");
  if (glossFind) {
    glossFind.parentNode.hidden = false;
    var entries = [].slice.call(document.querySelectorAll("dl.lg-gloss > div"));
    glossFind.addEventListener("input", function () {
      var q = glossFind.value.trim().toLowerCase();
      entries.forEach(function (d) { d.hidden = !!q && d.textContent.toLowerCase().indexOf(q) < 0; });
      document.querySelectorAll("dl.lg-gloss").forEach(function (dl) {
        dl.closest("section").hidden = !!q && !dl.querySelector(":scope > div:not([hidden])");
      });
    });
  }

  // Keyboard shortcuts, when no box has the keys and no modifier is held:
  // j and k step to the next or previous verse (or homily), ] and [ to the
  // next or previous chapter, c compares voices, ? shows them all. Each
  // presses a link or button the page already has, so a page without it
  // just ignores the key. (/ opens the search, above; the reader's own
  // arrow keys still step through its verses.)
  (function () {
    var holder = document.getElementById("keys-text");
    if (!holder) return;
    var K = JSON.parse(holder.textContent), box = null;
    function press(sel) {
      var el = [].filter.call(document.querySelectorAll(sel), function (x) { return x.offsetParent !== null || x.closest("header"); })[0]
        || document.querySelector(sel);
      if (!el) return false;
      el.click();
      return true;
    }
    function help() {
      if (!box) {
        box = document.createElement("dialog");
        box.className = "lg-keys";
        box.setAttribute("aria-labelledby", "keys-h");
        box.innerHTML = '<div class="lg-keys-head"><h2 id="keys-h">' + esc(K.title) + '</h2><button type="button" class="lg-cmp-close" data-close aria-label="' +
          esc(K.close) + '">×</button></div><dl>' + K.list.map(function (r) { return "<div><dt><kbd>" + esc(r[0]) + "</kbd></dt><dd>" + esc(r[1]) + "</dd></div>"; }).join("") +
          '</dl><p class="lg-quiet">' + esc(K.note) + "</p>";
        document.body.appendChild(box);
        box.querySelector("[data-close]").addEventListener("click", function () { box.close(); });
        box.addEventListener("click", function (e) { if (e.target === box) box.close(); });
      }
      if (box.showModal && !box.open) box.showModal();
    }
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
      var t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      if (document.querySelector("dialog[open]") && e.key !== "?") return;
      var done = false;
      if (e.key === "?") { help(); done = true; }
      else if (e.key === "j") done = press("#next") || press('.lg-vstrip a[rel="next"]') || press('.lg-turns a[rel="next"]');
      else if (e.key === "k") done = press("#prev") || press('.lg-vstrip a[rel="prev"]') || press('.lg-turns a[rel="prev"]');
      else if (e.key === "]") done = press('.lg-turn-btn[rel="next"]') || press('.cx-bar-in > a[rel="next"]');
      else if (e.key === "[") done = press('.lg-turn-btn[rel="prev"]') || press('.cx-bar-in > a[rel="prev"]');
      else if (e.key === "c") done = press("[data-compare]") || press(".lg-cmp-open");
      if (done) e.preventDefault();
    });
  })();

  // A work's contents beside its pages: scrolled so the page being read shows.
  var tocBox = document.querySelector(".lg-work-toc"), tocHere = tocBox && tocBox.querySelector("[aria-current]");
  if (tocHere && tocBox.scrollHeight > tocBox.clientHeight) tocBox.scrollTop = tocHere.offsetTop - tocBox.clientHeight / 3;

  // Verse pages: the strip of the chapter's verses scrolls to this one.
  var near = document.querySelector(".lg-near"), here = near && near.querySelector("[aria-current]");
  if (here) near.scrollLeft = here.offsetLeft - near.offsetLeft - (near.clientWidth - here.offsetWidth) / 2;
  // Verse pages: a long excerpt shows its first eight lines with a fade and
  // "Read all 412 words" (scripts/build_site.py, verse_excerpt). The one the
  // address points to opens in full.
  document.querySelectorAll(".lg-foldable").forEach(function (box) {
    var btn = box.nextElementSibling;
    if (!btn || !btn.classList.contains("lg-unfold")) return;
    var art = box.closest(".lg-vx");
    if (art && location.hash && location.hash.slice(1) === art.id) return;
    var line = parseFloat(getComputedStyle(box).lineHeight) || 30;
    if (box.scrollHeight <= line * 11) return;
    box.style.setProperty("--fold", line * 8 + "px");
    box.classList.add("lg-folded");
    btn.hidden = false;
    btn.addEventListener("click", function () {
      box.classList.remove("lg-folded");
      btn.remove();
    });
  });
})();
