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

    // Continue: the last verse read, as a pill in the bar (not on its own page).
    var pill = document.querySelector("[data-resume-pill]");
    if (pill) {
      var at = null;
      try { at = JSON.parse(localStorage.getItem("logia-last") || "null"); } catch (e) { /* storage blocked */ }
      if (at && at.href && at.href.charAt(0) === "/" && at.href.split("#")[0] !== location.pathname) {
        pill.href = at.href;
        pill.querySelector("span").textContent = at.ref;
        pill.title = fmt(pill.getAttribute("data-resume-pill"), { ref: at.ref });
        pill.setAttribute("aria-label", pill.title);
        pill.hidden = false;
      }
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

    // How far through the chapter's text the reader has scrolled.
    var bar = document.querySelector(".lg-progress span"), text = document.getElementById("text");
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
