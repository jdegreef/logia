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
  // What a control did, said to a screen reader: one polite status line for
  // the page, emptied first so the same words are said again.
  var say = function (text) {
    var el = document.getElementById("lg-say");
    if (!el) {
      el = document.createElement("p");
      el.id = "lg-say"; el.className = "sr-only"; el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.textContent = "";
    setTimeout(function () { el.textContent = text; }, 60);
  };
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
  // ... and a range: "John 1:1-14", "John 1:1–2:11" ({..., to: {chapter, verse}}).
  function parseRef(q) {
    if (!D) return null;
    var m = String(q).trim().match(/^((?:[1-3]|i{1,3})?\s*[a-z][a-z.\s]*?)\s*(\d+)(?:\s*[:.,\s]\s*(\d+))?(?:\s*[-–—]\s*(\d+)(?:\s*[:.]\s*(\d+))?)?\s*$/i);
    if (!m) return null;
    var code = bookOf(m[1]);
    if (!code) return null;
    var chapter = +m[2], verse = m[3] ? +m[3] : null;
    if (chapter < 1 || chapter > D.chapters[code]) return null;
    var r = { code: code, chapter: chapter, verse: verse };
    if (m[4] && verse) r.to = m[5] ? { chapter: +m[4], verse: +m[5] } : { chapter: chapter, verse: +m[4] };
    return r;
  }
  // A range's own page where it has one (a passage with commentary), else
  // the reader at its first verse.
  function rangeHref(r) {
    var key = r.code + "." + r.chapter + "." + r.verse + "-" + r.to.chapter + "." + r.to.verse;
    return (D.readings && D.readings[key]) || (D.passages && D.passages[key]) || refHref(r);
  }
  function rangeLabel(r) {
    return refLabel(r) + "–" + (r.to.chapter !== r.chapter ? r.to.chapter + ":" : "") + r.to.verse;
  }
  function refHref(r) { return "/" + r.code.toLowerCase() + "/" + r.chapter + "/" + (r.verse ? "#v" + r.verse : ""); }
  function refLabel(r) { return D.names[r.code] + " " + r.chapter + (r.verse ? ":" + r.verse : ""); }

  // What a query could mean, best first: a reference, books, commentators.
  function suggest(q) {
    var out = [], low = q.trim().toLowerCase();
    if (!low || !D) return out;
    // "Calvin John 3:16": a commentator's name, then a reference, goes to
    // what that commentator says there.
    var who = low.match(/^([a-z.\s]+?)\s+(?:on\s+)?((?:[1-3]\s*)?[a-z][a-z.\s]*\d.*)$/i);
    if (who && D.people) {
      var wr = parseRef(who[2]);
      var person = wr && D.people.filter(function (p) {
        return p[0].toLowerCase().split(/[\s.]+/).indexOf(who[1].trim().replace(/\s+/g, " ").split(" ").pop()) >= 0;
      })[0];
      if (person && person[3] && person[3][wr.code]) {
        var label = refLabel(wr);
        out.push({ href: "/" + wr.code.toLowerCase() + "/" + wr.chapter + "/" + (wr.verse ? "#v" + wr.verse + "-" + person[3][wr.code] : ""),
                   title: fmt(D.ui.who_on, { name: person[0], ref: label }), note: D.ui.in_reader });
        return out;
      }
    }
    var r = parseRef(q);
    if (r && r.to) {
      out.push({ href: rangeHref(r), title: rangeLabel(r), note: D.ui.passage });
    } else if (r) {
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
  window.LogiaSearch = { parseRef: parseRef, refHref: refHref, refLabel: refLabel, suggest: suggest,
    esc: esc, fmt: fmt, withData: withData, distance: distance };

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
    // An address that is plainly a reference (/John.3.16, /jn3:16, /rom8,
    // /rom/8:28, /romans/8/28-30/) goes straight to its page, so a link
    // typed by hand still lands; a name or a near miss is offered as a link.
    var parts = location.pathname.split("/").filter(Boolean);
    if (r && (parts.length === 1 || (parts.length <= 3 && bookOf(parts[0])))) { location.replace(href); return; }
    guess.innerHTML = fmt(esc(guess.getAttribute("data-text")), { link: '<a href="' + esc(href) + '">' + esc(label) + "</a>" });
    guess.hidden = false;
  })();

  // Continue reading: the last verse read (web/reader.js keeps it), and in
  // the Read menu once web/site.js has fetched the header's menus.
  var resume = function () { document.querySelectorAll("[data-resume]").forEach(function (a) {
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
  }); };
  resume();
  document.addEventListener("logia:menus", resume);

  // A whole homily: a thin line under the header shows how far through it
  // the reader is.
  var whole = document.querySelector(".lg-whole"), bar = document.querySelector(".lg-read-progress span");
  if (whole && bar) {
    var drawn = false;
    var draw = function () {
      drawn = false;
      var r = whole.getBoundingClientRect(), span = r.height - window.innerHeight * 0.6;
      var done = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 1;
      bar.style.transform = "scaleX(" + done.toFixed(3) + ")";
    };
    window.addEventListener("scroll", function () { if (!drawn) { drawn = true; requestAnimationFrame(draw); } }, { passive: true });
    draw();
  }

  // Home: "This Sunday", the first of the coming days on or after today.
  (function () {
    var now = new Date(), shown = false;
    var today = now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" + ("0" + now.getDate()).slice(-2);
    document.querySelectorAll(".lg-thisday[data-date]").forEach(function (a) {
      var on = !shown && a.getAttribute("data-date") >= today;
      a.hidden = !on;
      if (on) shown = true;
    });
  })();

  // Home: the church year's banner. Each [data-season] lists the spans
  // ("YYYY-MM-DD:YYYY-MM-DD", the last date the day itself) it shows in; of
  // those that hold today, the one whose day comes soonest is shown.
  (function () {
    var now = new Date(), best = null, bestDay = "";
    var today = now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" + ("0" + now.getDate()).slice(-2);
    document.querySelectorAll("[data-season]").forEach(function (el) {
      el.hidden = true;
      el.getAttribute("data-season").split(",").forEach(function (span) {
        var ab = span.split(":");
        if (today >= ab[0] && today <= ab[1] && (!best || ab[1] < bestDay)) { best = el; bestDay = ab[1]; }
      });
    });
    if (best) best.hidden = false;
  })();

  // The verse of the day as a picture to share (1200 x 630): the verse, the
  // first words of its three voices with their names, and logia.faith,
  // drawn from the card as it stands; shared where the device can, else saved.
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-votd-image]");
    if (!b) return;
    var panel = b.closest(".lg-votd-panel"), c = document.createElement("canvas");
    c.width = 1200; c.height = 630;
    var x = c.getContext("2d"), serif = getComputedStyle(document.documentElement).getPropertyValue("--serif").trim() || "Georgia, serif";
    var lines = function (text, width, max) {
      var out = [], line = "";
      text.split(/\s+/).forEach(function (w) {
        var t = line ? line + " " + w : w;
        if (x.measureText(t).width > width && line) { out.push(line); line = w; } else line = t;
      });
      if (line) out.push(line);
      if (out.length > max) { out = out.slice(0, max); out[max - 1] = out[max - 1].replace(/\s*\S*$/, "") + " …"; }
      return out;
    };
    x.fillStyle = "#f9f4ea"; x.fillRect(0, 0, 1200, 630);
    x.fillStyle = "#9c6f1e"; x.fillRect(0, 0, 1200, 10);
    x.fillStyle = "#2b2318"; x.font = "34px " + serif;
    var verse = lines(panel.querySelector(".votd-text").textContent.trim(), 1040, 3);
    verse.forEach(function (l, i) { x.fillText(l, 80, 90 + i * 46); });
    var y = 90 + verse.length * 46 + 4;
    x.font = "600 24px system-ui, sans-serif"; x.fillStyle = "#9c6f1e";
    x.fillText(panel.querySelector(".votd-ref").textContent.trim(), 80, y);
    [].slice.call(panel.querySelectorAll(".lg-vv > li")).slice(0, 3).forEach(function (li, i) {
      var left = 80 + i * 360, top = y + 64;
      x.fillStyle = "#2b2318"; x.font = "600 24px " + serif;
      x.fillText(li.querySelector(".lg-vv-who b").textContent.trim(), left, top);
      x.font = "21px " + serif; x.fillStyle = "#4a4034";
      lines(li.querySelector(".lg-vv-text").textContent.trim(), 320, 7).forEach(function (l, j) { x.fillText(l, left, top + 38 + j * 30); });
    });
    x.font = "24px system-ui, sans-serif"; x.fillStyle = "#6f6350";
    x.fillText("logia.faith", 1120 - x.measureText("logia.faith").width, 600);
    var ref = panel.querySelector(".votd-ref");
    c.toBlob(function (blob) {
      if (!blob) return;
      var name = "logia-" + ref.textContent.trim().replace(/[^A-Za-z0-9]+/g, "-").toLowerCase() + ".png";
      var file = window.File ? new File([blob], name, { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], url: ref.href }).catch(function () {});
        return;
      }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      say(b.getAttribute("data-votd-image"));
    }, "image/png");
  });

  // A topic as a picture to share (1200 x 630): its title, its passages
  // with their references, and the voices heard on them, from the page.
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-topic-image]");
    if (!b) return;
    var c = document.createElement("canvas"); c.width = 1200; c.height = 630;
    var x = c.getContext("2d"), serif = getComputedStyle(document.documentElement).getPropertyValue("--serif").trim() || "Georgia, serif";
    var fit = function (text, width) {
      while (x.measureText(text).width > width && text.length > 4) text = text.replace(/\s*\S+$/, "") + "…";
      return text;
    };
    x.fillStyle = "#f9f4ea"; x.fillRect(0, 0, 1200, 630);
    x.fillStyle = "#9c6f1e"; x.fillRect(0, 0, 1200, 10);
    x.fillStyle = "#2b2318"; x.font = "600 52px " + serif;
    var title = document.querySelector("h1").textContent.trim();
    x.fillText(fit(title, 1040), 80, 110);
    var items = [].slice.call(document.querySelectorAll("#items section.lg-voice")).slice(0, 6);
    items.forEach(function (sec, i) {
      var y = 180 + i * 52, h3 = sec.querySelector("h3"), ref = sec.querySelector(".lg-vmeta");
      x.font = "600 22px system-ui, sans-serif"; x.fillStyle = "#9c6f1e";
      x.fillText(String(i + 1), 80, y);
      x.font = "28px " + serif; x.fillStyle = "#2b2318";
      var label = h3 ? h3.textContent.replace(/^\s*\d+\s*/, "").trim() : "";
      x.fillText(fit(label, 640), 116, y);
      x.font = "22px system-ui, sans-serif"; x.fillStyle = "#6f6350";
      if (ref) x.fillText(fit(ref.textContent.trim(), 330), 790, y);
    });
    x.font = "21px " + serif; x.fillStyle = "#4a4034";
    var heard = fmt(b.getAttribute("data-heard"), { names: b.getAttribute("data-names") }), line = "", lines = [];
    heard.split(/\s+/).forEach(function (w) {
      var t = line ? line + " " + w : w;
      if (x.measureText(t).width > 860 && line) { lines.push(line); line = w; } else line = t;
    });
    if (line) lines.push(line);
    lines.slice(0, 2).forEach(function (l, i) { x.fillText(l, 80, 530 + i * 30); });
    x.font = "24px system-ui, sans-serif"; x.fillStyle = "#6f6350";
    x.fillText("logia.faith", 1120 - x.measureText("logia.faith").width, 600);
    c.toBlob(function (blob) {
      if (!blob) return;
      var name = "logia-" + location.pathname.replace(/^\/|\/$/g, "").replace(/[^a-z0-9]+/gi, "-") + ".png";
      var file = window.File ? new File([blob], name, { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], url: location.href }).catch(function () {});
        return;
      }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      say(b.getAttribute("data-topic-image"));
    }, "image/png");
  });

  // Two commentators across a book (book_side_page): for the two chosen,
  // each chapter's verses that only one comments on and that both do, with
  // a bar, and a link to read the chapter with the two side by side.
  (function () {
    var holder = document.getElementById("sbk-data");
    if (!holder) return;
    var D = JSON.parse(holder.textContent), U = D.ui;
    var pickA = document.getElementById("sbk-a"), pickB = document.getElementById("sbk-b");
    var body = document.querySelector(".lg-sbk-table tbody"), sum = document.querySelector(".lg-sbk-sum");
    var q = new URLSearchParams(location.search);
    if (q.get("a") && D.works[q.get("a")]) pickA.value = q.get("a");
    if (q.get("b") && D.works[q.get("b")]) pickB.value = q.get("b");
    var draw = function () {
      var a = pickA.value, b = pickB.value, na = D.names[a], nb = D.names[b], all = [0, 0, 0];
      document.querySelector(".lg-sbk-table th.lg-sbk-a").textContent = fmt(U.book_only, { name: na });
      document.querySelector(".lg-sbk-table th.lg-sbk-b").textContent = fmt(U.book_only, { name: nb });
      body.innerHTML = D.chapters.map(function (ch) {
        var x = D.works[a][ch] || "", y = D.works[b][ch] || "", n = [0, 0, 0];
        for (var i = 0; i < Math.max(x.length, y.length); i++) {
          var p = x[i] === "1", r = y[i] === "1";
          if (p && r) n[1]++; else if (p) n[0]++; else if (r) n[2]++;
        }
        all[0] += n[0]; all[1] += n[1]; all[2] += n[2];
        var len = Math.max(x.length, 1);
        var bar = '<span class="lg-sbk-bar" aria-hidden="true"><i class="lg-sbk-ia" style="width:' + (100 * n[0] / len) + '%"></i>' +
          '<i class="lg-sbk-ib2" style="width:' + (100 * n[1] / len) + '%"></i><i class="lg-sbk-ib" style="width:' + (100 * n[2] / len) + '%"></i></span>';
        return "<tr><th scope=\"row\">" + ch + "</th><td>" + n[0] + "</td><td>" + n[1] + bar + "</td><td>" + n[2] + "</td><td>" +
          ((n[0] || n[1] || n[2]) && a !== b ? '<a href="' + esc(D.side[ch]) + "?a=" + encodeURIComponent(a) + "&b=" + encodeURIComponent(b) + '">' + esc(U.open) + "</a>" : "") + "</td></tr>";
      }).join("");
      sum.textContent = fmt(U.book_sum, { both: all[1], a: na, only_a: all[0], b: nb, only_b: all[2] });
      try { history.replaceState(null, "", "?a=" + encodeURIComponent(a) + "&b=" + encodeURIComponent(b)); } catch (e) { /* file: */ }
    };
    pickA.addEventListener("change", draw);
    pickB.addEventListener("change", draw);
    draw();
  })();

  // A Sunday's page: a box for the preacher's own notes under each reading,
  // kept on this device (logia-sunday-notes: {"<page>#<reading>": text}) and
  // printed in its place with the handout.
  (function () {
    var page = document.querySelector(".lg-sunday-page[data-notes]");
    if (!page) return;
    var all = {};
    try { all = JSON.parse(localStorage.getItem("logia-sunday-notes") || "{}"); } catch (e) { return; }
    page.querySelectorAll("section.lg-voice[id]").forEach(function (sec) {
      var key = location.pathname + "#" + sec.id, id = "note-" + sec.id;
      var box = document.createElement("div");
      box.className = "lg-sn";
      box.innerHTML = '<label for="' + id + '">' + esc(page.getAttribute("data-notes")) + '</label><textarea id="' + id + '" rows="3"></textarea>' +
        '<p class="lg-quiet">' + esc(page.getAttribute("data-notes-hint")) + '</p><div class="lg-sn-print"></div>';
      var area = box.querySelector("textarea"), print = box.querySelector(".lg-sn-print");
      area.value = all[key] || ""; print.textContent = area.value;
      box.classList.toggle("lg-sn-has", !!area.value.trim());
      area.addEventListener("input", function () {
        var now = {};
        try { now = JSON.parse(localStorage.getItem("logia-sunday-notes") || "{}"); } catch (e) { /* storage blocked */ }
        if (area.value.trim()) now[key] = area.value; else delete now[key];
        try { localStorage.setItem("logia-sunday-notes", JSON.stringify(now)); } catch (e) { /* storage blocked */ }
        print.textContent = area.value;
        box.classList.toggle("lg-sn-has", !!area.value.trim());
      });
      var h2 = sec.querySelector("h2");
      var after = sec.querySelector(".lg-reading-text, .lg-reading-fold") || h2;
      after.insertAdjacentElement("afterend", box);
    });
  })();

  // "Print as a handout": the page's print layout (web/logia.css, @media print).
  document.querySelectorAll("[data-print]").forEach(function (b) {
    b.hidden = !window.print;
    b.addEventListener("click", function () { window.print(); });
  });

  // Home: on each book's card, the chapters read on this device
  // (logia-read) ticked on its line, and a link on to the last one read.
  (function () {
    var cards = document.querySelectorAll(".lg-bookcard[data-book]");
    if (!cards.length) return;
    var read = [];
    try { read = JSON.parse(localStorage.getItem("logia-read") || "[]"); } catch (e) { /* storage blocked */ }
    var holder = document.querySelector("[data-continue-in]");
    cards.forEach(function (card) {
      var pre = card.getAttribute("data-book"), cells = card.querySelectorAll(".lg-bookcard-heat i"), last = null;
      read.forEach(function (h) {
        var m = h.indexOf(pre) === 0 && h.slice(pre.length).match(/^(\d+)\/$/);
        if (!m) return;
        last = h;
        if (cells[+m[1] - 1]) cells[+m[1] - 1].classList.add("lg-was-read");
      });
      if (last && holder) {
        var go = card.querySelector(".lg-bookcard-go"), a = document.createElement("a");
        a.className = "lg-bookcard-cont"; a.href = last;
        a.textContent = fmt(holder.getAttribute("data-continue-in"), { book: card.getAttribute("data-name") });
        go.insertBefore(a, go.firstChild);
      }
    });
  })();

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
      // A returning reader: Continue leads, and the three ways in for
      // newcomers step back behind the books.
      var doors = document.querySelector(".lg-doors"), books = document.getElementById("h-read");
      if (doors && books) books.closest("section").after(doors);
      var names = JSON.parse(cont.getAttribute("data-books"));
      var main = cont.querySelector(".lg-continue-main");
      main.href = lastAt.href;
      main.querySelector("b").textContent = lastAt.voice ? fmt(cont.getAttribute("data-with"), { ref: lastAt.ref, name: lastAt.voice }) : lastAt.ref;
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

  // The Read page (read_page in scripts/build_site.py): Continue reading,
  // what has been read in each book, a label on each chapter cell, a book's
  // preview, the phone's grid of chapters, the filter, the search that
  // narrows the list, the order, this Sunday's readings, the part of the
  // Bible in view, and typing a book's name to jump to it.
  var rbar = document.querySelector(".lg-read-bar");
  if (rbar) (function () {
    var ui = JSON.parse(rbar.getAttribute("data-ui"));
    var index = document.querySelector(".lg-cov-index"), flat = document.querySelector(".lg-cov-flat");
    var rows = [].slice.call(index.querySelectorAll(".lg-cov-row"));
    var phone = window.matchMedia("(max-width: 600px)");
    var mouse = window.matchMedia("(hover: hover) and (pointer: fine)");
    var norm = function (s) { return s.toLowerCase().replace(/[^a-z0-9]/g, ""); };
    var keep = function (k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { /* storage blocked */ } return null; };
    rows.forEach(function (r) { r.lgHome = r.parentNode; });

    // Continue reading: the last verse read (logia-last), how much of its
    // book has been read, and the next chapter.
    var cont = document.querySelector(".lg-read-cont"), last = null;
    try { last = JSON.parse(localStorage.getItem("logia-last") || "null"); } catch (e) { /* storage blocked */ }
    var lm = last && last.href && String(last.href).match(/^\/([a-z0-9]{3})\/(\d+)\//);
    if (cont && lm) {
      var names = JSON.parse(cont.getAttribute("data-books")), totals = JSON.parse(cont.getAttribute("data-totals"));
      var bk = lm[1], ch = +lm[2], total = totals[bk];
      if (names[bk]) {
        var ref = last.ref || names[bk] + " " + ch;
        var done = read.filter(function (h) { return /^\/[a-z0-9]{3}\/\d+\/$/.test(h) && h.indexOf("/" + bk + "/") === 0; }).length;
        cont.querySelector(".lg-read-cont-ref").textContent = ref;
        cont.querySelector(".lg-read-cont-meta").textContent = done ? fmt(done === 1 ? ui.of_book_one : ui.of_book, { n: done, total: total, book: names[bk] }) : "";
        var go = cont.querySelector(".lg-read-cont-go");
        go.href = last.href;
        go.textContent = fmt(ui.open, { ref: ref });
        if (ch < total) {
          var nx = cont.querySelector(".lg-read-cont-next");
          nx.href = "/" + bk + "/" + (ch + 1) + "/";
          nx.textContent = fmt(ui.next, { ref: names[bk] + " " + (ch + 1) });
          nx.hidden = false;
        }
        cont.hidden = false;
      }
    }

    // How much of each book has been read, and a tick once all of it is.
    rows.forEach(function (r) {
      var cells = r.querySelectorAll(".lg-cov-bar .chap"), k = 0;
      cells.forEach(function (c) { if (c.classList.contains("lg-read")) k++; });
      if (!k) return;
      var s = document.createElement("span");
      s.className = "lg-cov-read";
      s.textContent = k === cells.length ? ui.all_read : fmt(ui.read, { n: k });
      r.querySelector(".lg-cov-n").appendChild(s);
      if (k === cells.length) r.classList.add("lg-cov-done");
    });

    // A label over the chapter under the pointer or the keyboard's focus.
    var tip = document.querySelector(".lg-cell-tip");
    document.body.appendChild(tip);
    var showTip = function (a) {
      var parts = a.getAttribute("data-tip").split(" · ");
      tip.innerHTML = "<b>" + esc(parts[0]) + "</b>" + (parts[1] ? " · " + esc(parts[1]) : "") + (parts.length > 2 ? "<br>" + esc(parts.slice(2).join(" · ")) : "");
      tip.hidden = false;
      var b = a.getBoundingClientRect(), w = tip.offsetWidth, room = document.documentElement.clientWidth;
      var x = Math.max(8, Math.min(b.left + b.width / 2 - w / 2, room - w - 8));
      tip.style.left = x + window.scrollX + "px";
      tip.style.top = b.top + window.scrollY - tip.offsetHeight - 8 + "px";
    };
    var cellOf = function (el) { return el && el.closest ? el.closest(".lg-cov-bar .chap") : null; };
    document.addEventListener("mouseover", function (e) {
      var a = cellOf(e.target);
      if (a) showTip(a); else if (!cellOf(document.activeElement)) tip.hidden = true;
    });
    document.addEventListener("focusin", function (e) { var a = cellOf(e.target); if (a) showTip(a); else tip.hidden = true; });
    window.addEventListener("scroll", function () { if (!cellOf(document.activeElement)) tip.hidden = true; }, { passive: true });

    // A wide screen: a book's commentators and its most discussed verse,
    // after a moment on its name.
    rows.forEach(function (r) {
      var pk = r.querySelector(".lg-peek"), name = r.querySelector(".lg-cov-name"), timer;
      if (!pk) return;
      var show = function (now) { clearTimeout(timer); timer = setTimeout(function () { pk.hidden = false; }, now ? 0 : 450); };
      var hide = function () { clearTimeout(timer); timer = setTimeout(function () { pk.hidden = true; }, 200); };
      name.addEventListener("mouseenter", function () { if (mouse.matches) show(); });
      name.addEventListener("mouseleave", hide);
      pk.addEventListener("mouseenter", function () { clearTimeout(timer); });
      pk.addEventListener("mouseleave", hide);
      name.addEventListener("focus", function () { if (!phone.matches) show(true); });
      r.addEventListener("focusout", function (e) { if (!r.contains(e.relatedTarget)) { clearTimeout(timer); pk.hidden = true; } });
      r.addEventListener("keydown", function (e) { if (e.key === "Escape" && !pk.hidden) { pk.hidden = true; name.focus(); } });
    });

    // A phone: the row opens a grid of numbered chapters big enough to tap.
    var toggle = function (r) {
      var btn = r.querySelector(".lg-cov-open"), g = r.querySelector(".lg-cov-grid");
      if (!g) {
        g = document.createElement("div");
        g.className = "lg-cov-grid";
        var html = "";
        r.querySelectorAll(".lg-cov-bar .chap").forEach(function (c) {
          html += '<a href="' + esc(c.getAttribute("href")) + '" class="' + (c.classList.contains("lg-has") ? "lg-has " : "") + (c.classList.contains("lg-read") ? "lg-read" : "") +
            '" aria-label="' + esc(c.getAttribute("aria-label")) + '">' + esc(c.textContent) + "</a>";
        });
        var name = r.querySelector(".lg-cov-name");
        g.innerHTML = html + '<a class="lg-cov-grid-all" href="' + esc(name.getAttribute("href")) + '">' + esc(name.textContent) + " →</a>";
        g.hidden = true;
        r.appendChild(g);
      }
      var open = btn.getAttribute("aria-expanded") !== "true";
      btn.setAttribute("aria-expanded", open);
      g.hidden = !open;
    };
    rows.forEach(function (r) {
      r.querySelector(".lg-cov-open").addEventListener("click", function () { toggle(r); });
      r.addEventListener("click", function (e) {
        if (phone.matches && !e.target.closest("a, button, .lg-cov-grid")) toggle(r);
      });
    });

    // A phone: the parts of the Bible with no commentary start folded.
    var parts = [].slice.call(index.querySelectorAll(".lg-canon-part"));
    if (phone.matches) parts.forEach(function (p) { if (p.classList.contains("lg-part-text")) p.open = false; });
    var reveal = function (id) {
      var el = id && document.getElementById(id);
      if (!el || !el.classList.contains("lg-cov-row")) return;
      if (el.hidden && only.getAttribute("aria-pressed") === "true") setOnly(false);
      var d = el.closest("details");
      if (d) d.open = true;
    };
    window.addEventListener("hashchange", function () { reveal(location.hash.slice(1)); });

    // With commentary only, the search box narrowing the list, and the order.
    var only = rbar.querySelector(".lg-read-only"), sortSel = rbar.querySelector(".lg-read-sort select");
    var input = document.getElementById("read-q"), none = document.querySelector(".lg-read-none");
    var apply = function () {
      var on = only.getAttribute("aria-pressed") === "true";
      var q = norm(input ? input.value : "").replace(/(\D)\d+$/, "$1"), shown = 0, first = null;
      rows.forEach(function (r) {
        var nm = norm(r.getAttribute("data-name"));
        var hit = !q || nm.indexOf(q) === 0 || (q.length > 2 && nm.indexOf(q) > 0);
        var vis = hit && (!on || r.classList.contains("lg-cov-has"));
        r.hidden = !vis;
        r.classList.remove("lg-jumped");
        if (vis) { shown++; if (!first) first = r; }
      });
      if (q && first) first.classList.add("lg-jumped");
      parts.forEach(function (p) { p.hidden = !p.querySelector(".lg-cov-row:not([hidden])"); if (q) p.open = true; });
      index.querySelectorAll(".lg-testament").forEach(function (tst) { tst.hidden = !tst.querySelector(".lg-cov-row:not([hidden])"); });
      none.hidden = shown > 0;
      if (!shown) none.textContent = fmt(ui.none, { q: input.value.trim() });
    };
    var setOnly = function (on) { only.setAttribute("aria-pressed", on); keep("logia-read-only", on ? "1" : "0"); apply(); };
    only.addEventListener("click", function () { setOnly(only.getAttribute("aria-pressed") !== "true"); });
    if (input) input.addEventListener("input", apply);
    var byBible = function (a, b) { return a.getAttribute("data-i") - b.getAttribute("data-i"); };
    var order = function (mode) {
      keep("logia-read-sort", mode);
      sortSel.value = mode;
      if (mode === "az" || mode === "most") {
        rows.slice().sort(mode === "az" ? function (a, b) { return a.getAttribute("data-name").localeCompare(b.getAttribute("data-name")); }
          : function (a, b) { return (b.getAttribute("data-x") - a.getAttribute("data-x")) || byBible(a, b); })
          .forEach(function (r) { flat.appendChild(r); });
        index.hidden = true;
        flat.hidden = false;
        rbar.classList.add("lg-read-flat");
      } else {
        rows.slice().sort(byBible).forEach(function (r) { r.lgHome.appendChild(r); });
        index.hidden = false;
        flat.hidden = true;
        rbar.classList.remove("lg-read-flat");
      }
    };
    sortSel.addEventListener("change", function () { order(sortSel.value); });
    rbar.querySelectorAll("nav a").forEach(function (a) { a.addEventListener("click", function () { if (!index.hidden) return; order("bible"); }); });
    document.querySelectorAll(".lg-bs").forEach(function (a) { a.addEventListener("click", function () { if (index.hidden) order("bible"); reveal(a.getAttribute("href").slice(1)); }); });
    if (keep("logia-read-only") === "1") only.setAttribute("aria-pressed", "true");
    var saved = keep("logia-read-sort");
    if (saved === "az" || saved === "most") order(saved);
    apply();
    reveal(location.hash.slice(1));

    // This Sunday's readings: a dot over their chapters.
    var suns = JSON.parse(index.getAttribute("data-sundays") || "[]"), now = new Date();
    var iso = now.getFullYear() + "-" + ("0" + (now.getMonth() + 1)).slice(-2) + "-" + ("0" + now.getDate()).slice(-2);
    var next = suns.filter(function (d) { return d[0] >= iso; })[0];
    if (next && next[1].length) {
      next[1].forEach(function (c) {
        document.querySelectorAll('a.chap[href="/' + c + '/"]').forEach(function (a) { a.classList.add("lg-sun"); });
      });
      var key = document.querySelector(".lg-sun-key"), day = next[0];
      try { day = new Date(next[0] + "T12:00:00").toLocaleDateString(document.documentElement.lang || undefined, { day: "numeric", month: "long" }); } catch (e) { /* keep the date */ }
      key.lastElementChild.textContent = fmt(ui.sunday, { day: day });
      key.hidden = false;
    }

    // The part of the Bible in view, in the bar (and the margin on a wide
    // screen); the bar's edge once it sticks.
    var links = {};
    rbar.querySelectorAll(".lg-read-parts a").forEach(function (a) { links[a.getAttribute("href").slice(1)] = a; });
    var tLinks = rbar.querySelectorAll(".lg-jump a"), partsNav = rbar.querySelector(".lg-read-parts");
    var mark = function () {
      if (index.hidden) return;
      // Side by side, each testament has its own part in view; one above the
      // other, the last part to pass the middle of the screen is the one.
      var mid = window.innerHeight * 0.4, at = {}, both = getComputedStyle(index).gridTemplateColumns.split(" ").length > 1;
      parts.forEach(function (p) {
        var tst = both ? p.closest(".lg-testament").id : "all";
        if (!p.hidden && p.getBoundingClientRect().top < mid) at[tst] = p;
      });
      // Side by side, the part that passed the line last is the one lit, so
      // the bar never shows two at once.
      var keys = Object.keys(at).sort(function (a, b) { return at[b].getBoundingClientRect().top - at[a].getBoundingClientRect().top; });
      var ids = keys.length ? [at[keys[0]].id] : [];
      Object.keys(links).forEach(function (k) { if (ids.indexOf(k) >= 0) links[k].setAttribute("aria-current", "true"); else links[k].removeAttribute("aria-current"); });
      var tst = !both && at.all ? at.all.closest(".lg-testament").id : "";
      tLinks.forEach(function (a) { if (a.getAttribute("href") === "#" + tst) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
    };
    var tick = false;
    var onScroll = function () {
      if (tick) return;
      tick = true;
      requestAnimationFrame(function () {
        tick = false;
        var top = parseFloat(getComputedStyle(rbar).top) || 0;
        rbar.classList.toggle("lg-stuck", rbar.getBoundingClientRect().top <= top + 1);
        partsNav.classList.toggle("lg-before", index.getBoundingClientRect().top > window.innerHeight * 0.6);
        mark();
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    // Type a book's name (with nothing focused) to jump to it; Enter opens it.
    var typed = "", jumped = null, idle, hint = document.querySelector(".lg-read-keys"), hintText = hint ? hint.textContent : "";
    var clear = function () { typed = ""; if (hint) hint.textContent = hintText; };
    document.addEventListener("keydown", function (e) {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
      var t = e.target;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(t.tagName))) return;
      if (document.querySelector("dialog[open]")) return;
      if (e.key === "Enter" && jumped && (t === document.body || t === jumped)) { location.href = jumped.querySelector(".lg-cov-name").href; e.preventDefault(); return; }
      if (e.key === "Escape") { if (jumped) jumped.classList.remove("lg-jumped"); jumped = null; clear(); return; }
      if (t !== document.body || !/^[a-z0-9 ]$/i.test(e.key) || (e.key === " " && !typed)) return;
      typed += e.key.toLowerCase();
      clearTimeout(idle);
      idle = setTimeout(clear, 1200);
      var q = norm(typed), hit = null;
      rows.forEach(function (r) { if (!hit && !r.hidden && norm(r.getAttribute("data-name")).indexOf(q) === 0) hit = r; });
      if (hint) hint.innerHTML = esc(fmt(ui.typed, { q: "" })) + "<b>" + esc(typed) + "</b>";
      if (!hit) return;
      e.preventDefault();
      if (jumped) jumped.classList.remove("lg-jumped");
      jumped = hit;
      hit.classList.add("lg-jumped");
      var d = hit.closest("details");
      if (d) d.open = true;
      hit.scrollIntoView({ block: "center" });
    });
    document.addEventListener("click", function () { if (jumped) { jumped.classList.remove("lg-jumped"); jumped = null; } });
  })();

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
    // Narrower screens, where the rail isn't beside the page: once the voices
    // begin, it becomes a bar under the header that scrolls sideways, the
    // voice being read marked; above the voices it stays out of the way.
    var firstVoice = document.querySelector(".lg-voice"), narrow = window.matchMedia("(max-width: 1099px)");
    if (firstVoice) {
      var place = function () {
        var on = narrow.matches && firstVoice.getBoundingClientRect().top < 120;
        vrail.classList.toggle("lg-vrail-bar", on);
        var cur = on && vrail.querySelector('[aria-current="true"]');
        if (cur && cur !== vrail._shown) {
          vrail._shown = cur;
          vrail.scrollTo({ left: cur.offsetLeft - vrail.clientWidth / 2 + cur.offsetWidth / 2, behavior: "auto" });
        }
      };
      window.addEventListener("scroll", place, { passive: true });
      narrow.addEventListener("change", place);
      place();
    }
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
        out.push('<a href="' + href + '" class="lg-chcell' + (has ? " lg-has" : "") + (read.indexOf(href) >= 0 ? " lg-read" : "") + '"' +
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

    // The Read menu: the chapters of the book pointed at, beside the books,
    // once web/site.js has fetched the header's menus.
    var readMenu = function () {
      var chapters = document.querySelector("[data-nav-chapters]");
      if (N && chapters && !chapters.hasAttribute("data-ready")) {
        chapters.setAttribute("data-ready", "");
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
    };
    readMenu();
    document.addEventListener("logia:menus", readMenu);

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
    show(tabs.filter(function (x) { return x.getAttribute("aria-selected") === "true"; })[0] || tabs[0]);
  });
  // The commentators page: book chips, era buttons (in the bar over the
  // cards and on the timeline's bands) and a name box that narrow the cards
  // together, dim the other lives on the timeline, and put the chosen book
  // first on each card, with a quotation from that book.
  document.querySelectorAll(".lg-cmtcards").forEach(function (section) {
    var pick = document.querySelector(".lg-pick"), bar = section.querySelector(".lg-findbar");
    var cards = [].slice.call(section.querySelectorAll("li.lg-cmt"));
    var rows = [].slice.call(document.querySelectorAll(".lg-tl-row[data-author]"));
    var chips = pick ? [].slice.call(pick.querySelectorAll("button[data-book]")) : [];
    var eraButtons = [].slice.call(document.querySelectorAll(".lg-findbar-eras button, .lg-tl-era[data-era]"));
    var input = bar && bar.querySelector("input"), select = bar && bar.querySelector("select");
    var count = bar && bar.querySelector(".lg-findbar-count"), reset = bar && bar.querySelector(".lg-findbar-reset");
    var none = section.querySelector(".lg-findnone");
    var state = { book: "", era: "", q: "" };
    var fold = function (s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
    // Each card's coverage rows in their first order, to put back.
    cards.forEach(function (li) {
      li._covs = [].slice.call(li.querySelectorAll(".lg-cov")).map(function (c) { return [c, c.parentNode, c.nextSibling]; });
    });
    var bookFirst = function (li) {
      li._covs.slice().reverse().forEach(function (x) { x[1].insertBefore(x[0], x[2] && x[2].parentNode === x[1] ? x[2] : null); });
      li._covs.forEach(function (x) { x[0].classList.remove("lg-cov-on"); });
      var lead = li.querySelector('.lg-pq[data-book="' + state.book + '"]');
      [].forEach.call(li.querySelectorAll(".lg-pq"), function (q) {
        q.hidden = state.book && lead ? q !== lead : q.getAttribute("data-book") !== "";
      });
      if (!state.book) return;
      var row = li.querySelector('.lg-cov[data-book="' + state.book + '"]'), list = li.querySelector(".lg-covs");
      if (row && list) { list.insertBefore(row, list.firstChild); row.classList.add("lg-cov-on"); }
    };
    var apply = function () {
      var shown = {}, n = 0, q = fold(state.q.trim());
      cards.forEach(function (li) {
        var on = (!state.book || li.getAttribute("data-books").split(" ").indexOf(state.book) >= 0) &&
          (state.era === "" || li.getAttribute("data-era") === state.era) &&
          (!q || fold(li.getAttribute("data-names")).indexOf(q) >= 0);
        li.hidden = !on;
        if (on) { shown[li.getAttribute("data-author")] = true; n++; }
        bookFirst(li);
      });
      rows.forEach(function (row) { row.classList.toggle("lg-tl-dim", !shown[row.getAttribute("data-author")]); });
      chips.forEach(function (x) { x.setAttribute("aria-pressed", String(x.getAttribute("data-book") === state.book)); });
      eraButtons.forEach(function (x) { x.setAttribute("aria-pressed", String(x.getAttribute("data-era") === state.era)); });
      if (select) select.value = state.book;
      var any = state.book || state.era !== "" || q;
      if (count) count.textContent = any ? count.getAttribute("data-of").replace("{n}", n).replace("{total}", cards.length) : "";
      if (reset) reset.hidden = !any;
      if (none) none.hidden = n > 0;
    };
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () { state.book = chip.getAttribute("data-book"); apply(); });
    });
    eraButtons.forEach(function (b) {
      if (b.tagName === "A") b.setAttribute("role", "button");
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        var era = b.getAttribute("data-era");
        state.era = state.era === era ? "" : era;
        apply();
        if (b.tagName === "A" && state.era !== "") section.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    if (input) input.addEventListener("input", function () { state.q = input.value; apply(); });
    if (select) select.addEventListener("change", function () { state.book = select.value; apply(); });
    if (reset) reset.addEventListener("click", function () {
      state = { book: "", era: "", q: "" }; if (input) input.value = ""; apply();
    });
    if (pick) pick.hidden = false;
    if (bar) bar.hidden = false;
    // On a phone each card shows its name and a line; a tap opens the rest.
    section.classList.add("lg-compact");
    cards.forEach(function (li) {
      var more = li.querySelector(".lg-card-more");
      if (!more) return;
      more.hidden = false;
      more.addEventListener("click", function () {
        var open = li.classList.toggle("lg-open");
        more.setAttribute("aria-expanded", String(open));
      });
    });
    // A link to an era's first card opens it and shows it.
    var openFromHash = function () {
      var li = location.hash && document.getElementById(location.hash.slice(1));
      if (li && li.classList.contains("lg-cmt")) {
        li.classList.add("lg-open");
        var m = li.querySelector(".lg-card-more"); if (m) m.setAttribute("aria-expanded", "true");
      }
    };
    window.addEventListener("hashchange", openFromHash); openFromHash();
  });

  // The timeline: on a page with an era strip, the chart waits behind a
  // button on a phone; and pointing at a life shows who else was alive then.
  document.querySelectorAll(".lg-tl").forEach(function (fig) {
    var toggle = fig.querySelector(".lg-tl-toggle");
    if (toggle) {
      var showText = toggle.textContent, hideText = fig.getAttribute("data-hide") || showText;
      fig.classList.add("lg-tl-folded");
      toggle.hidden = false;
      toggle.addEventListener("click", function () {
        var folded = fig.classList.toggle("lg-tl-folded");
        toggle.setAttribute("aria-expanded", String(!folded));
        toggle.textContent = folded ? showText : hideText;
      });
    }
    var rows = [].slice.call(fig.querySelectorAll(".lg-tl-row[data-born]"));
    var span = fig.querySelector(".lg-tl-span"), say = fig.querySelector(".lg-tl-alive");
    var wide = window.matchMedia("(min-width: 601px)");
    if (!span || !say || !rows.length) return;
    var clear = function () {
      span.hidden = true; say.textContent = "";
      rows.forEach(function (r) { r.classList.remove("lg-tl-far"); });
    };
    var point = function (row) {
      if (!wide.matches) return;
      var b = +row.getAttribute("data-born"), d = +row.getAttribute("data-died"), names = [];
      var life = row.querySelector(".lg-tl-life");
      rows.forEach(function (r) {
        var on = r === row || (+r.getAttribute("data-born") < d && +r.getAttribute("data-died") > b);
        r.classList.toggle("lg-tl-far", !on);
        if (on && r !== row) names.push(r.querySelector(".lg-tl-name b").textContent);
      });
      span.style.setProperty("--l", life.style.getPropertyValue("--l"));
      span.style.setProperty("--w", life.style.getPropertyValue("--w"));
      span.hidden = false;
      var name = row.querySelector(".lg-tl-name b").textContent;
      say.textContent = names.length
        ? fig.getAttribute("data-alive").replace("{name}", name).replace("{names}", names.join(", "))
        : fig.getAttribute("data-alive-none").replace("{name}", name);
    };
    rows.forEach(function (row) {
      var life = row.querySelector(".lg-tl-life");
      life.addEventListener("mouseenter", function () { point(row); });
      life.addEventListener("focus", function () { point(row); });
      life.addEventListener("mouseleave", clear);
      life.addEventListener("blur", clear);
    });
  });
  // A long verse-by-verse list keeps each closed chapter's rows in a file
  // of its own (excerpt_list in scripts/build_site.py, data-src): fetched
  // the first time the chapter opens, however it is opened.
  // Home: a book card's chapter cell names itself when pointed at.
  document.addEventListener("mouseover", function (e) {
    var cell = e.target.closest && e.target.closest(".lg-bookcard-heat i");
    if (!cell || cell.title) return;
    var card = cell.closest(".lg-bookcard");
    var ch = [].indexOf.call(cell.parentNode.children, cell) + 1;
    cell.title = fmt(card.getAttribute("data-heat-label"), { ch: ch, n: Number(cell.getAttribute("data-n")).toLocaleString("en") });
  });

  // The shape of a work: each row's squares from its string (coverage_map),
  // and, when a book's list of verses with no comment is opened, those
  // verses as linked runs ("1:5, 2:3–4").
  document.querySelectorAll(".lg-cov-map span[data-c]").forEach(function (row) {
    row.innerHTML = row.getAttribute("data-c").replace(/-/g, "").replace(/1/g, "<i></i>").replace(/0/g, '<i class="lg-nc"></i>');
  });
  document.querySelectorAll(".lg-cov-map details[data-missing]").forEach(function (d) {
    d.addEventListener("toggle", function () {
      var out = d.querySelector("p > span");
      if (!d.open || out.childNodes.length) return;
      var map = d.closest(".lg-cov-map"), book = map.getAttribute("data-book").toLowerCase(), runs = [];
      map.querySelectorAll("ol > li").forEach(function (li) {
        var ch = li.firstElementChild.textContent.trim(), bits = li.querySelector("span[data-c]").getAttribute("data-c");
        for (var i = 0; i < bits.length; i++) {
          if (bits[i] !== "0") continue;
          var last = runs[runs.length - 1];
          if (last && last.ch === ch && last.z === i) last.z = i + 1; else runs.push({ ch: ch, a: i + 1, z: i + 1 });
        }
      });
      out.innerHTML = runs.map(function (r) {
        return '<a href="/' + book + "/" + r.ch + "/#v" + r.a + '">' + r.ch + ":" + r.a + (r.z !== r.a ? "–" + r.z : "") + "</a>";
      }).join(", ");
    });
  });

  // The shape of a work: an open square (a verse with no comment) names its
  // verse when pointed at, "Genesis 1:4", from its map and row.
  document.addEventListener("mouseover", function (e) {
    var cell = e.target.closest && e.target.closest(".lg-cov-map i.lg-nc");
    if (!cell || cell.title) return;
    var map = cell.closest(".lg-cov-map"), row = cell.closest("li"), num = row && row.firstElementChild;
    var v = [].indexOf.call(cell.parentNode.children, cell) + 1;
    if (map && num) cell.title = map.getAttribute("data-name") + " " + num.textContent.trim() + ":" + v;
  });

  // A chapter kept in a file of its own (excerpt_list, data-src): its body,
  // fetched the first time it is opened.
  function loadRows(details) {
    var box = details && details.querySelector(".lg-ch-body[data-src]");
    if (!box) return Promise.resolve();
    if (!box._loading) {
      box._loading = fetch(box.getAttribute("data-src")).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }).then(function (html) {
        box.innerHTML = html;
        box.removeAttribute("data-src");
      }, function () {
        box._loading = null;
        var say = document.querySelector(".lg-chnav[data-failed]");
        box.innerHTML = '<p class="lg-quiet">' + esc(say ? say.getAttribute("data-failed") : "") + "</p>";
      });
    }
    return box._loading;
  }
  // A long book's later chapters wait behind "Show all" (excerpt_list,
  // data-fold); going to one of them, however, shows them all first.
  function unfoldBook(root, book) {
    [].forEach.call(root.querySelectorAll('details.lg-ch[data-fold][data-book="' + book + '"]'), function (d) { d.hidden = false; });
    var more = root.querySelector('.lg-vv-more button[data-book="' + book + '"]');
    if (more) more.parentNode.hidden = true;
  }
  function unfold(d) {
    if (d && d.hidden && d.matches("details.lg-ch[data-fold]")) unfoldBook(d.parentNode, d.getAttribute("data-book"));
  }
  document.querySelectorAll(".lg-vv-more button").forEach(function (btn) {
    var root = btn.closest(".lg-vv-book") || btn.parentNode.parentNode, book = btn.getAttribute("data-book");
    [].forEach.call(root.querySelectorAll('details.lg-ch[data-fold][data-book="' + book + '"]'), function (d) { d.hidden = true; });
    btn.parentNode.hidden = false;
    btn.addEventListener("click", function () {
      var first = root.querySelector('details.lg-ch[data-fold][data-book="' + book + '"]');
      unfoldBook(root, book);
      if (first) first.querySelector("summary").focus();
    });
  });
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest('a[href^="#ch-"]');
    if (a) unfold(document.getElementById(a.getAttribute("href").slice(1)));
  }, true);
  if (/^#ch-/.test(location.hash)) unfold(document.getElementById(location.hash.slice(1)));
  document.addEventListener("toggle", function (ev) {
    if (ev.target.matches && ev.target.matches("details.lg-ch") && ev.target.open) loadRows(ev.target);
  }, true);
  document.querySelectorAll("details.lg-ch[open]").forEach(loadRows);

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
      loadRows(ch).then(function () { mark(ch, m); });
    });
    function mark(ch, m) {
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
      unfold(ch);
      ch.open = true;
      row.classList.add("lg-hit");
      row.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      var link = row.querySelector("a");
      if (link) link.focus({ preventScroll: true });
    }
  });

  // A commentator's chapters: a switch that opens or closes them all, the map
  // of chapters marking those open, and "next chapter" closing the one left.
  document.querySelectorAll(".lg-ch-all").forEach(function (btn) {
    var root = btn.closest("[role=tabpanel]") || btn.closest(".lg-block") || document;
    var chs = [].slice.call(root.querySelectorAll("details.lg-ch"));
    var cells = {};
    [].forEach.call(root.querySelectorAll(".lg-chnav-cells a"), function (a) { cells[a.getAttribute("href").slice(1)] = a; });
    var sync = function () {
      var open = 0;
      chs.forEach(function (d) { if (d.open) open++; if (cells[d.id]) cells[d.id].classList.toggle("lg-on", d.open); });
      var all = open === chs.length;
      btn.textContent = btn.getAttribute(all ? "data-close" : "data-open");
      btn.setAttribute("aria-pressed", String(all));
    };
    chs.forEach(function (d) { d.addEventListener("toggle", sync); });
    btn.addEventListener("click", function () {
      var all = chs.every(function (d) { return d.open; });
      if (!all) chs.forEach(unfold);
      chs.forEach(function (d) { d.open = !all; });
    });
    // The steps to the chapters either side close this one and open that,
    // those fetched with a chapter as well as those in the page.
    root.addEventListener("click", function (e) {
      var a = e.target.closest(".lg-ch-steps a");
      if (!a) return;
      var d = a.closest("details"), next = document.getElementById(a.getAttribute("href").split("#")[1]);
      if (d) d.open = false;
      if (next) next.open = true;
    });
    btn.hidden = false;
    sync();
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

  // Two creeds side by side (/creeds/compare/): each is printed whole in a
  // hidden template; the two pickers copy the chosen ones into the columns.
  // ?a=<id> picks the left one (a creed page's "Compare" button).
  var cc = document.querySelector(".lg-cc");
  if (cc) {
    var ccShow = function () {
      ["a", "b"].forEach(function (k) {
        var id = document.getElementById("cc-" + k).value;
        var src = cc.querySelector('.lg-cc-doc[data-doc="' + id + '"]');
        var slot = cc.querySelector('[data-slot="' + k + '"]');
        slot.innerHTML = src ? src.innerHTML : "";
      });
    };
    var ccA = new URLSearchParams(location.search).get("a");
    var pickA = document.getElementById("cc-a"), pickB = document.getElementById("cc-b");
    if (ccA && pickA.querySelector('option[value="' + ccA + '"]')) {
      pickA.value = ccA;
      if (pickB.value === ccA) pickB.selectedIndex = pickB.selectedIndex ? 0 : 1;
    }
    pickA.addEventListener("change", ccShow);
    pickB.addEventListener("change", ccShow);
    ccShow();
  }

  // A short creed's "Recite": its articles one at a time, in large type
  // (a dialog; the arrow keys and the buttons move through them).
  var recite = document.querySelector("[data-recite]");
  var rd = document.querySelector(".lg-recite");
  if (recite && rd && rd.showModal) {
    var arts = Array.prototype.slice.call(document.querySelectorAll(".lg-creed-body .lg-creed-sec"));
    var at = 0;
    var rText = rd.querySelector(".lg-recite-text"), rN = rd.querySelector(".lg-recite-n");
    var rPrev = rd.querySelector("[data-recite-prev]"), rNext = rd.querySelector("[data-recite-next]");
    var rShow = function () {
      var sec = arts[at];
      var label = sec.querySelector(".lg-creed-label");
      rText.innerHTML = (label ? "<p class=\"lg-recite-label\">" + label.textContent + "</p>" : "") +
        sec.querySelector(".lg-text").innerHTML;
      rN.textContent = (at + 1) + " / " + arts.length;
      rPrev.disabled = at === 0;
      rNext.disabled = at === arts.length - 1;
    };
    var rGo = function (d) { at = Math.max(0, Math.min(arts.length - 1, at + d)); rShow(); };
    if (arts.length) {
      recite.hidden = false;
      recite.addEventListener("click", function () { at = 0; rShow(); rd.showModal(); });
      rPrev.addEventListener("click", function () { rGo(-1); });
      rNext.addEventListener("click", function () { rGo(1); });
      rd.querySelector("[data-recite-close]").addEventListener("click", function () { rd.close(); });
      rd.addEventListener("keydown", function (ev) {
        if (ev.key === "ArrowRight") { rGo(1); ev.preventDefault(); }
        if (ev.key === "ArrowLeft") { rGo(-1); ev.preventDefault(); }
      });
    }
  }

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
      // The two across the whole chapter (/<book>/<chapter>/side-by-side/).
      var side = cmp.getAttribute("data-side"), link = cmp.querySelector(".lg-cmp-side");
      if (link) link.remove();
      if (side && picked.length === 2) {
        link = document.createElement("p");
        link.className = "lg-cmp-side";
        link.innerHTML = '<a href="' + esc(side + "?a=" + encodeURIComponent(picked[0]) + "&b=" + encodeURIComponent(picked[1])) + '">' +
          esc(cmp.getAttribute("data-side-label")) + " →</a>";
        picks.after(link);
      }
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
        // A row's open first lines (the most-discussed verses) close first.
        [].slice.call(body.querySelectorAll(".lg-md-peekrow")).forEach(function (x) { x.remove(); });
        [].forEach.call(body.querySelectorAll(".lg-md-peek"), function (x) { x.setAttribute("aria-expanded", "false"); });
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

  // The most-discussed verses (/<book>/most-discussed/): rank by excerpts,
  // words or citations and count only some commentators (from the book's
  // data.json, loaded when first asked for), open a row's first lines
  // (copied from its verse page as printed there), and tick the verses whose
  // page or chapter has been read.
  var md = document.querySelector("[data-md]");
  if (md) {
    var MU = JSON.parse(md.getAttribute("data-ui"));
    var mdBody = md.querySelector("table.lg-md-table").tBodies[0];
    var mdControls = md.querySelector(".lg-md-controls");
    var mdStatus = md.querySelector(".lg-md-status");
    var mdBook = md.getAttribute("data-book");
    var mdLang = document.documentElement.lang || "en";
    var mdData = null, mdWaiting = null, metric = "excerpts";
    var num = function (n) { return Number(n).toLocaleString(mdLang); };
    var mdTicks = function () {
      if (!read.length) return;
      [].forEach.call(mdBody.rows, function (r) {
        var href = r.getAttribute("data-href");
        if (href && (read.indexOf(href) >= 0 || read.indexOf(href.replace(/\d+\/$/, "")) >= 0)) {
          r.classList.add("lg-read");
          r.cells[0].title = MU.read;
        }
      });
    };
    mdTicks();
    var mdLoad = function (then) {
      if (mdData) return then();
      if (!mdWaiting) {
        mdStatus.textContent = MU.loading;
        mdWaiting = fetch(md.getAttribute("data-md")).then(function (r) { return r.json(); })
          .then(function (d) { mdData = d; }, function () { mdWaiting = null; mdStatus.textContent = MU.failed; });
      }
      mdWaiting.then(function () { if (mdData) then(); });
    };
    var mdDraw = function () {
      var works = mdData.works;
      var on = works.map(function (w) {
        var b = mdControls.querySelector('[data-work="' + w.id + '"]');
        return !b || b.getAttribute("aria-pressed") === "true";
      });
      if (on.indexOf(true) < 0) { mdStatus.textContent = MU.none; return; }
      var key = metric === "excerpts" ? "n" : metric;
      var rows = mdData.rows.map(function (r) {
        var x = { r: r, n: 0, words: 0, all: 0, who: 0, cited: r[5] };
        r[3].forEach(function (k, i) {
          x.all += k;
          if (k) x.who += 1;
          if (on[i]) { x.n += k; x.words += r[4][i]; }
        });
        return x;
      }).filter(function (x) { return x[key] > 0; });
      rows.sort(function (a, b) { return b[key] - a[key] || a.r[0] - b.r[0] || a.r[1] - b.r[1]; });
      var first = {}, same = {};
      rows.forEach(function (x, i) {
        if (!(x[key] in first)) first[x[key]] = i + 1;
        same[x[key]] = (same[x[key]] || 0) + 1;
      });
      rows = rows.slice(0, 100);
      var peak = rows.length ? rows[0][key] : 0;
      var more = md.querySelector("[data-show-rows]");
      var cell = function (val, kind) {
        return '<td class="lg-num" data-sort="' + val + '">' + (kind === metric && peak
          ? '<span class="lg-rank-bar" aria-hidden="true"><span style="width:' + Math.round(val / peak * 100) + '%"></span></span>' : "") + num(val) + "</td>";
      };
      mdBody.innerHTML = rows.map(function (x, i) {
        var r = x.r, url = "/" + mdBook + "/" + r[0] + "/" + r[1] + "/", has = x.all > 0;
        var rank = first[x[key]], label = same[x[key]] > 1 ? fmt(MU.rank_tied, { n: rank }) : String(rank);
        var topics = r[7].map(function (id) { return '<a class="lg-md-topic" href="/topics/' + id + '/">' + esc(mdData.topics[id]) + "</a>"; }).join("");
        var dots = works.map(function (w, j) { return '<i class="lg-era-' + w.era + (r[3][j] ? " on" : "") + '" title="' + esc(w.name) + '">' + esc(w.ini) + "</i>"; }).join("");
        return '<tr' + (more && i >= 25 ? " hidden" : "") + (has ? ' data-href="' + url + '"' : "") + ' data-n="' + x.all + '">' +
          '<td class="lg-quiet lg-md-rank" data-sort="' + rank + '">' + esc(label) + "</td>" +
          '<td class="lg-md-ref" data-sort="' + (r[0] * 1000 + r[1]) + '"><a href="' + (has ? url : "/" + mdBook + "/" + r[0] + "/#v" + r[1]) + '"><b>' + esc(r[2]) + "</b></a>" + topics +
          (has ? '<button type="button" class="lg-md-peek" aria-expanded="false">' + esc(MU.peek) + "</button>" : "") + "</td>" +
          cell(x.n, "excerpts") + cell(x.words, "words") +
          '<td class="lg-num" data-sort="' + x.cited + '">' + (x.cited ? (has ? '<a href="' + url + '#cited">' + num(x.cited) + "</a>" : num(x.cited)) : "–") + "</td>" +
          '<td class="lg-md-who" data-sort="' + x.who + '"><span class="lg-dots" aria-hidden="true">' + dots + '</span><span class="sr-only">' +
          esc(fmt(MU.of, { n: x.who, total: works.length })) + "</span></td>" +
          '<td class="lg-rank-text"><span class="lg-clamp">' + esc(r[6] || MU.left_out) + "</span></td></tr>";
      }).join("");
      md.querySelectorAll("th[aria-sort]").forEach(function (th) { th.removeAttribute("aria-sort"); });
      if (more) {
        more.textContent = fmt(MU.show_all, { n: rows.length });
        more.parentNode.hidden = rows.length <= 25;
      }
      mdTicks();
      var names = works.filter(function (w, i) { return on[i]; }).map(function (w) { return w.short; });
      mdStatus.textContent = fmt(names.length === works.length ? MU.status_all : MU.status_some,
        { metric: MU["status_" + metric], names: names.join(", ") });
    };
    if (mdControls) {
      mdControls.hidden = false;
      mdControls.addEventListener("click", function (ev) {
        var b = ev.target.closest("button");
        if (!b) return;
        if (b.hasAttribute("data-metric")) {
          metric = b.getAttribute("data-metric");
          mdControls.querySelectorAll("[data-metric]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        } else {
          b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
        }
        mdLoad(mdDraw);
      });
    }
    mdBody.addEventListener("click", function (ev) {
      var clamp = ev.target.closest(".lg-clamp");
      if (clamp) { clamp.classList.toggle("lg-open"); return; }
      var btn = ev.target.closest(".lg-md-peek");
      if (!btn) return;
      var tr = btn.closest("tr"), next = tr.nextElementSibling;
      if (next && next.classList.contains("lg-md-peekrow")) {
        next.remove();
        btn.setAttribute("aria-expanded", "false");
        return;
      }
      var href = tr.getAttribute("data-href");
      var box = document.createElement("td");
      box.colSpan = tr.cells.length;
      box.textContent = MU.peek_loading;
      var pr = document.createElement("tr");
      pr.className = "lg-md-peekrow";
      pr.appendChild(box);
      tr.parentNode.insertBefore(pr, tr.nextSibling);
      btn.setAttribute("aria-expanded", "true");
      fetch(href).then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); }).then(function (text) {
        var doc = new DOMParser().parseFromString(text, "text/html");
        var lines = [];
        doc.querySelectorAll("section.lg-voice").forEach(function (s) {
          var h = s.querySelector("h3"), p = s.querySelector(".lg-text p");
          if (!h || !p) return;
          var words = p.textContent.trim().split(/\s+/);
          var line = words.slice(0, 40).join(" ") + (words.length > 40 ? " …" : "");
          lines.push('<li><a href="' + href + "#" + esc(s.id) + '"><b>' + esc(h.textContent.trim()) + "</b></a> " +
            '<span class="lg-md-line">' + esc(line) + "</span></li>");
        });
        var ref = tr.querySelector(".lg-md-ref b").textContent;
        box.innerHTML = '<ul class="lg-md-lines">' + lines.join("") + '</ul><p><a class="lg-more" href="' + href + '">' +
          esc(fmt(MU.peek_more, { n: num(tr.getAttribute("data-n")), ref: ref })) + "</a></p>";
      }).catch(function () { box.textContent = MU.peek_failed; });
    });
  }

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

  // Glossary words in the excerpts (verse, work and whole-text pages, and the
  // first words on topic and Sunday pages): the first use on the page of
  // each word in /glossary.json is marked, and pressing it shows what it
  // means, with a link to its entry. The excerpt's words are unchanged; only
  // a button is put round the first use.
  var texts = document.querySelectorAll(".lg-text, .lg-whole, .lg-collection .lg-excerpts > li > div");
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
  // next or previous chapter, n and p to the next or previous voice, c
  // compares voices, ? shows them all. Each
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
    // n and p: the next or previous voice (a section.lg-voice) below or
    // above the top of the screen, brought to the top and focused.
    function stepVoice(dir) {
      var all = [].slice.call(document.querySelectorAll("section.lg-voice")).filter(function (x) { return x.offsetParent !== null; });
      if (!all.length) return false;
      // Measured against where each would land: the page's scroll padding
      // and the section's own scroll margin.
      var pad = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
      var at = function (x) { return x.getBoundingClientRect().top - pad - (parseFloat(getComputedStyle(x).scrollMarginTop) || 0); };
      var go = dir > 0 ? all.filter(function (x) { return at(x) > 8; })[0]
        : all.filter(function (x) { return at(x) < -8; }).pop();
      if (!go) return false;
      go.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      if (!go.hasAttribute("tabindex")) go.setAttribute("tabindex", "-1");
      go.focus({ preventScroll: true });
      return true;
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
      else if (e.key === "n" || e.key === "p") done = stepVoice(e.key === "n" ? 1 : -1);
      if (done) e.preventDefault();
    });
  })();

  // A topic as a reading path: a button under each passage marks it read
  // and a link goes on to the next; how far through shows at the top, and on
  // the topics page (logia-paths: {path: [passage ids]}, on the device).
  function pathsRead() { try { return JSON.parse(localStorage.getItem("logia-paths") || "{}"); } catch (e) { return {}; } }
  var pathPage = document.querySelector(".lg-path[data-path]");
  if (pathPage) {
    var PU = JSON.parse(pathPage.getAttribute("data-ui")), pathKey = pathPage.getAttribute("data-path");
    var steps = [].slice.call(pathPage.querySelectorAll("section.lg-voice[id]"));
    var progress = pathPage.querySelector(".lg-path-progress");
    var drawPath = function () {
      var done = pathsRead()[pathKey] || [];
      steps.forEach(function (sec) {
        var b = sec.querySelector("[data-step]"), on = done.indexOf(sec.id) >= 0;
        b.setAttribute("aria-pressed", on); b.textContent = on ? PU.marked_read : PU.mark_read;
        sec.classList.toggle("lg-step-done", on);
        // The side column's entry for it is ticked too.
        var side = pathPage.querySelector('.lg-side-toc a[href="#' + sec.id + '"]');
        if (side) side.classList.toggle("lg-was-read", on);
      });
      var n = steps.filter(function (sec) { return done.indexOf(sec.id) >= 0; }).length;
      progress.hidden = !n;
      progress.querySelector(".lg-path-bar span").style.width = (100 * n / steps.length) + "%";
      progress.querySelector(".lg-path-n").textContent = fmt(n === steps.length ? PU.done : PU.progress, { n: n, total: steps.length });
    };
    steps.forEach(function (sec, i) {
      var row = document.createElement("p");
      row.className = "lg-step-row";
      row.innerHTML = '<button type="button" class="button ghost" data-step aria-pressed="false"></button>' +
        (steps[i + 1] ? '<a href="#' + esc(steps[i + 1].id) + '">' + esc(PU.next) + "</a>" : "");
      sec.appendChild(row);
      row.querySelector("[data-step]").addEventListener("click", function () {
        var all = pathsRead(), done = all[pathKey] || [], at = done.indexOf(sec.id);
        if (at >= 0) done.splice(at, 1); else done.push(sec.id);
        all[pathKey] = done;
        try { localStorage.setItem("logia-paths", JSON.stringify(all)); } catch (e) { /* storage blocked */ }
        drawPath();
      });
    });
    drawPath();
  }
  document.querySelectorAll(".lg-topic-card[data-path]").forEach(function (card) {
    var done = (pathsRead()[card.getAttribute("data-path")] || []).length, label = card.querySelector(".lg-topic-read");
    if (!done || !label) return;
    label.textContent = fmt(label.getAttribute("data-text"), { n: done, total: +card.getAttribute("data-items") });
    label.hidden = false;
  });

  // The offer to install Logia, so it reads offline: shown only from a
  // reader's second day here (logia-days), only where the browser offers to
  // install (beforeinstallprompt), and not again once declined
  // (logia-install-no). The site is installable already; this says so.
  (function () {
    var holder = document.getElementById("keys-text");
    if (!holder) return;
    var I = JSON.parse(holder.textContent).install, days = [], no = false;
    try {
      days = JSON.parse(localStorage.getItem("logia-days") || "[]");
      var today = new Date().toISOString().slice(0, 10);
      if (days.indexOf(today) < 0) { days.push(today); localStorage.setItem("logia-days", JSON.stringify(days.slice(-30))); }
      no = !!localStorage.getItem("logia-install-no");
    } catch (e) { return; }
    if (no || days.length < 2 || !I) return;
    window.addEventListener("beforeinstallprompt", function (ev) {
      ev.preventDefault();
      var bar = document.createElement("div");
      bar.className = "lg-install";
      bar.setAttribute("role", "region");
      bar.setAttribute("aria-label", I.install);
      bar.innerHTML = "<p>" + esc(I.text) + '</p><p><button type="button" class="button" data-yes>' + esc(I.install) +
        '</button> <button type="button" class="button ghost" data-no>' + esc(I.later) + "</button></p>";
      document.body.appendChild(bar);
      var close = function () { bar.remove(); };
      bar.querySelector("[data-yes]").addEventListener("click", function () { ev.prompt(); close(); });
      bar.querySelector("[data-no]").addEventListener("click", function () {
        try { localStorage.setItem("logia-install-no", "1"); } catch (e) { /* storage blocked */ }
        close();
      });
    });
  })();

  // Two commentators across a chapter (/<book>/<chapter>/side-by-side/):
  // the chapter's commentary file, the reader's own, drawn as rows of
  // verses with the two chosen side by side. ?a=<work>&b=<work> picks them.
  var sideData = document.getElementById("side-data");
  if (sideData) (function () {
    var D = JSON.parse(sideData.textContent), U = D.ui, rowsBox = document.querySelector(".lg-side-rows");
    var pickA = document.getElementById("side-a"), pickB = document.getElementById("side-b");
    var q = new URLSearchParams(location.search);
    [[pickA, q.get("a")], [pickB, q.get("b")]].forEach(function (p) {
      if (p[1] && p[0].querySelector('option[value="' + p[1] + '"]')) p[0].value = p[1];
    });
    var byWork = {};
    var paras = function (text) {
      return text.trim().split(/\n\s*\n/).map(function (x) { return "<p>" + esc(x) + "</p>"; }).join("");
    };
    var cell = function (wid, v) {
      var es = (byWork[wid] || []).filter(function (x) { return +x.start === v; });
      if (!es.length) return "";
      return es.map(function (x) {
        var span = +x.end !== +x.start ? '<p class="lg-quiet">' + esc(fmt(U.verses, { v: x.start + "–" + x.end })) + "</p>" : "";
        return '<div class="lg-side-x">' + span + (x.heading ? '<p class="lg-side-head">' + esc(x.heading) + "</p>" : "") + paras(x.excerpt) + "</div>";
      }).join("");
    };
    var draw = function () {
      var a = pickA.value, b = pickB.value, out = [], gap = [];
      var flush = function () {
        if (gap.length) out.push('<p class="lg-quiet lg-side-gap">' + esc(gap.length === 1 ? fmt(U.gap_verse, { v: gap[0] }) : fmt(U.both_none, { a: gap[0], b: gap[gap.length - 1] })) + "</p>");
        gap = [];
      };
      Object.keys(D.verses).map(Number).sort(function (x, y) { return x - y; }).forEach(function (v) {
        var l = cell(a, v), r = cell(b, v);
        if (!l && !r) { gap.push(v); return; }
        flush();
        out.push('<section class="lg-side-row" id="v' + v + '"><h2 class="lg-side-v"><a href="' + esc(D.reader) + "#v" + v + '">' +
          esc(fmt(U.verse, { v: v })) + "</a></h2><blockquote class=\"lg-side-verse\">" + esc(D.verses[v]) + "</blockquote>" +
          '<div class="lg-side-cols"><div>' + (l || '<p class="lg-quiet">' + esc(U.none) + "</p>") + "</div><div>" +
          (r || '<p class="lg-quiet">' + esc(U.none) + "</p>") + "</div></div></section>");
      });
      flush();
      var nameOf = function (pick) { return pick.options[pick.selectedIndex].textContent; };
      // The chapter's verses as a strip: which each of the two comments on
      // (an excerpt counts on every verse it covers); a verse links to its row.
      var covers = function (wid, v) { return (byWork[wid] || []).some(function (x) { return +x.start <= v && v <= +x.end; }); };
      var shown = {};
      out.forEach(function (h) { var m = /id="v(\d+)"/.exec(h); if (m) shown[m[1]] = true; });
      var strip = Object.keys(D.verses).map(Number).sort(function (x, y) { return x - y; }).map(function (v) {
        var l = covers(a, v), r = covers(b, v), cls = l && r ? "both" : l ? "left" : r ? "right" : "none";
        var row = v;
        while (row > 0 && !shown[row]) row--;
        var label = fmt(U.verse, { v: v }) + ": " + U["strip_" + cls];
        return '<a class="lg-strip-' + cls + '" href="#v' + (row || v) + '" title="' + esc(label) + '" aria-label="' + esc(label) + '">' + v + "</a>";
      }).join("");
      out.unshift('<nav class="lg-side-strip" aria-label="' + esc(U.strip_label) + '">' + strip + "</nav>" +
        '<p class="lg-side-key"><span class="lg-strip-left">' + esc(fmt(U.key_only, { name: nameOf(pickA).split(":")[0] })) + '</span> <span class="lg-strip-right">' +
        esc(fmt(U.key_only, { name: nameOf(pickB).split(":")[0] })) + '</span> <span class="lg-strip-both">' + esc(U.key_both) + "</span></p>");
      out.unshift('<div class="lg-side-cols lg-side-names"><p><b>' + esc(nameOf(pickA)) + "</b></p><p><b>" + esc(nameOf(pickB)) + "</b></p></div>");
      // On a phone the two columns would stack, one whole chapter after the
      // other; instead a switch shows one voice at a time, verse by verse,
      // and a sideways swipe on a row changes voice.
      var show = rowsBox.getAttribute("data-show") || "a";
      out.unshift('<div class="lg-side-switch" role="group" aria-label="' + esc(U.show_label) + '">' +
        '<button type="button" data-show="a" aria-pressed="' + (show === "a") + '">' + esc(nameOf(pickA).split(":")[0]) + "</button>" +
        '<button type="button" data-show="b" aria-pressed="' + (show === "b") + '">' + esc(nameOf(pickB).split(":")[0]) + "</button></div>");
      rowsBox.setAttribute("data-show", show);
      rowsBox.innerHTML = out.join("");
      history.replaceState(null, "", location.pathname + "?a=" + encodeURIComponent(a) + "&b=" + encodeURIComponent(b) + location.hash);
      // The chapters before and after keep the same two.
      document.querySelectorAll("[data-side-turn]").forEach(function (link) {
        link.href = link.getAttribute("href").split("?")[0] + "?a=" + encodeURIComponent(a) + "&b=" + encodeURIComponent(b);
      });
    };
    fetch(D.comm).then(function (r) { return r.json(); }).then(function (c) {
      c.commentaries.forEach(function (w) { byWork[w.work_id] = w.entries; });
      draw();
      pickA.addEventListener("change", draw);
      pickB.addEventListener("change", draw);
      var setShow = function (which) {
        rowsBox.setAttribute("data-show", which);
        rowsBox.querySelectorAll(".lg-side-switch button").forEach(function (x) { x.setAttribute("aria-pressed", x.dataset.show === which); });
      };
      rowsBox.addEventListener("click", function (ev) {
        var bt = ev.target.closest(".lg-side-switch button");
        if (bt) setShow(bt.dataset.show);
      });
      var sx = null, sy = 0;
      rowsBox.addEventListener("touchstart", function (ev) {
        sx = ev.target.closest(".lg-side-cols") ? ev.touches[0].clientX : null; sy = ev.touches[0].clientY;
      }, { passive: true });
      rowsBox.addEventListener("touchend", function (ev) {
        if (sx === null) return;
        var dx = ev.changedTouches[0].clientX - sx, dy = ev.changedTouches[0].clientY - sy;
        sx = null;
        if (Math.abs(dx) > 60 && Math.abs(dx) > 2 * Math.abs(dy)) setShow(dx < 0 ? "b" : "a");
      });
    });
  })();

  // Verse and homily pages on a touch screen: a firm sideways swipe goes to
  // the previous or next one (the page's own rel="prev" and rel="next"
  // links). Not from a strip, table or box that scrolls sideways itself, nor
  // while text is being selected.
  var turnPrev = document.querySelector('.lg-turns a[rel="prev"]'), turnNext = document.querySelector('.lg-turns a[rel="next"]');
  if ((turnPrev || turnNext) && "ontouchstart" in window) (function () {
    var x0 = null, y0 = 0, t0 = 0;
    var scrollsSideways = function (el) {
      for (; el && el !== document.body; el = el.parentElement) {
        if (el.scrollWidth > el.clientWidth + 2 && /(auto|scroll)/.test(getComputedStyle(el).overflowX)) return true;
        if (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.closest("dialog[open]")) return true;
      }
      return false;
    };
    document.addEventListener("touchstart", function (ev) {
      x0 = ev.touches.length === 1 && !scrollsSideways(ev.target) ? ev.touches[0].clientX : null;
      y0 = ev.touches[0].clientY; t0 = Date.now();
    }, { passive: true });
    document.addEventListener("touchend", function (ev) {
      if (x0 === null) return;
      var t = ev.changedTouches[0], dx = t.clientX - x0, dy = t.clientY - y0;
      x0 = null;
      var sel = window.getSelection && String(window.getSelection());
      if (sel || Date.now() - t0 > 700 || Math.abs(dx) < 90 || Math.abs(dy) > Math.abs(dx) * 0.5) return;
      var to = dx < 0 ? turnNext : turnPrev;
      if (to) location.href = to.href;
    }, { passive: true });
  })();

  // A link to some words (?mark=…, "Link" in web/study.js's selection bar):
  // those words marked where they stand, in the excerpt the address points
  // to or else anywhere in the text, and scrolled into view.
  (function () {
    var want = new URLSearchParams(location.search).get("mark");
    if (!want) return;
    var squash = function (x) { return x.replace(/\s+/g, " "); };
    want = squash(want).trim();
    var target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    var boxes = [].slice.call(document.querySelectorAll(".lg-text, .lg-whole"));
    if (target) boxes.sort(function (a, b) { return (target.contains(b) ? 1 : 0) - (target.contains(a) ? 1 : 0); });
    boxes.some(function (box) {
      var walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), nodes = [], text = "";
      while (walker.nextNode()) { nodes.push([walker.currentNode, text.length]); text += squash(walker.currentNode.nodeValue); }
      var at = text.indexOf(want);
      if (at < 0) return false;
      var end = at + want.length, first = null;
      nodes.forEach(function (n) {
        var node = n[0], start = n[1], len = squash(node.nodeValue).length;
        var lo = Math.max(at, start), hi = Math.min(end, start + len);
        if (lo >= hi || len !== node.nodeValue.length) return;   // a node whose spaces were squashed is left unmarked
        var r = document.createRange();
        r.setStart(node, lo - start); r.setEnd(node, hi - start);
        var m = document.createElement("mark"); m.className = "lg-hl lg-marked";
        try { r.surroundContents(m); first = first || m; } catch (e) { /* across elements */ }
      });
      if (first) {
        var fold = first.closest(".lg-folded");
        if (fold) { fold.classList.remove("lg-folded"); var more = fold.nextElementSibling; if (more && more.classList.contains("lg-unfold")) more.remove(); }
        setTimeout(function () { first.scrollIntoView({ block: "center" }); }, 60);
      }
      return !!first;
    });
  })();

  // A page opened from a search result (?hl=born again): the words searched
  // for marked in the excerpts' text, and the first in the excerpt the
  // address points to (or on the page) scrolled into view.
  (function () {
    var hl = new URLSearchParams(location.search).get("hl");
    if (!hl) return;
    var words = hl.toLowerCase().split(/\s+/).filter(function (w) { return w.length > 2; }).map(function (w) { return w.replace(/[^\p{L}\p{N}']/gu, ""); }).filter(Boolean);
    if (!words.length) return;
    var re = new RegExp("(^|[^\\p{L}])(" + words.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")[\\p{L}]*", "giu");
    var first = null, target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    document.querySelectorAll(".lg-text, .lg-text-body, .lg-whole-text").forEach(function (box) {
      var walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT), nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach(function (node) {
        var text = node.nodeValue, out = [], last = 0, m;
        re.lastIndex = 0;
        while ((m = re.exec(text))) {
          var start = m.index + m[1].length, end = m.index + m[0].length;
          out.push(document.createTextNode(text.slice(last, start)));
          var mark = document.createElement("mark");
          mark.className = "lg-hl"; mark.textContent = text.slice(start, end);
          out.push(mark);
          last = end;
        }
        if (!out.length) return;
        out.push(document.createTextNode(text.slice(last)));
        var frag = document.createDocumentFragment();
        out.forEach(function (x) { frag.appendChild(x); });
        node.parentNode.replaceChild(frag, node);
      });
    });
    var marks = [].slice.call(document.querySelectorAll("mark.lg-hl"));
    first = (target && marks.filter(function (x) { return target.contains(x); })[0]) || marks[0];
    if (!first) return;
    var fold = first.closest(".lg-folded");
    if (fold) { fold.classList.remove("lg-folded"); var more = fold.nextElementSibling; if (more && more.classList.contains("lg-unfold")) more.remove(); }
    setTimeout(function () { first.scrollIntoView({ block: "center" }); }, 60);
  })();

  // Listen (listen_button in scripts/build_site.py): a verse page read aloud,
  // the verse and then each voice, its name first; a homily paragraph by
  // paragraph. The paragraph being read is marked. Greek and Hebrew are left
  // out, as the reader's Listen does (web/reader.js).
  var listenBox = document.querySelector(".lg-listen");
  if (listenBox && "speechSynthesis" in window) (function () {
    var play = listenBox.querySelector("[data-listen]"), next = listenBox.querySelector("[data-listen-next]"), stop = listenBox.querySelector("[data-listen-stop]");
    var items = [], at = -1, on = false, run = 0;
    var collect = function () {
      var out = [];
      var verse = document.querySelector(".lg-vtext p");
      if (verse) out.push(verse);
      document.querySelectorAll("section.lg-voice").forEach(function (sec) {
        var h = sec.querySelector("h3");
        if (h) out.push(h);
        sec.querySelectorAll(".lg-text p").forEach(function (p) { out.push(p); });
      });
      document.querySelectorAll(".lg-whole p[id]").forEach(function (p) { out.push(p); });
      return out;
    };
    var spoken = function (el) {
      var copy = el.cloneNode(true);
      copy.querySelectorAll('[lang="grc"], [lang="hbo"], .lg-sec-n').forEach(function (x) { x.remove(); });
      var out = [];
      copy.textContent.replace(/\s+/g, " ").trim().split(/(?<=[.;:!?])\s+/).forEach(function (piece) {
        while (piece.length > 240) {
          var cut = piece.lastIndexOf(", ", 240); if (cut < 80) cut = piece.lastIndexOf(" ", 240);
          out.push(piece.slice(0, cut + 1)); piece = piece.slice(cut + 1).trim();
        }
        if (piece) out.push(piece);
      });
      return out;
    };
    var mark = function () {
      document.querySelectorAll(".lg-speaking").forEach(function (x) { x.classList.remove("lg-speaking"); });
      if (items[at]) {
        items[at].classList.add("lg-speaking");
        items[at].scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      }
    };
    var say = function (mine) {
      if (mine !== run) return;
      if (at >= items.length) { finish(); return; }
      mark();
      var parts = spoken(items[at]);
      var i = 0;
      var one = function () {
        if (mine !== run) return;
        if (i >= parts.length) { at++; say(mine); return; }
        var u = new SpeechSynthesisUtterance(parts[i++]);
        u.lang = document.documentElement.lang || "en";
        u.onend = one;
        // Cancelled by Next or Stop: nothing to do. Anything else (no voice): stop.
        u.onerror = function (ev) { if (mine === run && ev.error !== "interrupted" && ev.error !== "canceled") finish(); };
        speechSynthesis.speak(u);
      };
      one();
    };
    var finish = function () {
      run++; on = false; at = -1;
      speechSynthesis.cancel();
      mark();
      play.textContent = play.getAttribute("data-say-start");
      next.hidden = stop.hidden = true;
    };
    listenBox.hidden = false;
    play.addEventListener("click", function () {
      if (!on) {
        items = collect(); at = 0; on = true; run++;
        speechSynthesis.cancel();
        play.textContent = play.getAttribute("data-say-pause");
        next.hidden = stop.hidden = false;
        say(run);
      } else if (speechSynthesis.paused) {
        speechSynthesis.resume(); play.textContent = play.getAttribute("data-say-pause");
      } else {
        speechSynthesis.pause(); play.textContent = play.getAttribute("data-say-resume");
      }
    });
    next.addEventListener("click", function () {
      if (!on) return;
      run++; speechSynthesis.cancel();
      at++; play.textContent = play.getAttribute("data-say-pause");
      say(run);
    });
    stop.addEventListener("click", finish);
    window.addEventListener("pagehide", function () { speechSynthesis.cancel(); });
  })();

  // A work's contents beside a homily: the homilies already read are ticked
  // (kept on the device), and a long list can be narrowed by number or verse
  // ("24", "3:16": the homilies whose passage holds that verse).
  var readList = document.querySelector(".lg-contents[data-read-key]");
  if (readList) (function () {
    var key = readList.getAttribute("data-read-key"), read = [];
    try { read = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { read = []; }
    if (read.indexOf(location.pathname) < 0) {
      read.push(location.pathname);
      try { localStorage.setItem(key, JSON.stringify(read.slice(-3000))); } catch (e) { /* storage blocked */ }
    }
    readList.querySelectorAll("a").forEach(function (a) { if (read.indexOf(a.getAttribute("href")) >= 0) a.classList.add("lg-was-read"); });
    var find = document.querySelector(".lg-toc-find");
    if (!find) return;
    find.hidden = false;
    var span = function (text) {
      var m = /(\d+):(\d+)(?:[–-](?:(\d+):)?(\d+))?/.exec(text);
      if (!m) return null;
      var a = [+m[1], +m[2]], b = m[4] ? [m[3] ? +m[3] : +m[1], +m[4]] : a;
      return [a, b];
    };
    var le = function (x, y) { return x[0] < y[0] || (x[0] === y[0] && x[1] <= y[1]); };
    find.addEventListener("input", function () {
      var q = find.value.trim(), want = /^(\d+):(\d+)$/.exec(q);
      readList.querySelectorAll("li").forEach(function (li) {
        var text = li.textContent, show = !q;
        if (want) { var r = span(text), v = [+want[1], +want[2]]; show = !!r && le(r[0], v) && le(v, r[1]); }
        else if (q) show = text.toLowerCase().indexOf(q.toLowerCase()) >= 0;
        li.hidden = !show;
      });
    });
  })();

  // About: the section being read is marked in its contents (a sticky column on wide screens).
  var abToc = document.querySelector(".lg-ab-toc");
  if (abToc && "IntersectionObserver" in window) {
    var abLinks = {};
    abToc.querySelectorAll("a").forEach(function (a) { abLinks[a.getAttribute("href").slice(1)] = a; });
    var abIo = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting || !abLinks[en.target.id]) return;
        Object.keys(abLinks).forEach(function (id) { abLinks[id].toggleAttribute("aria-current", id === en.target.id); });
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    document.querySelectorAll(".lg-ab-sec").forEach(function (sec) { abIo.observe(sec); });
  }

  // A long passage shown in three lines first (Differ pages), with a button for the rest.
  document.querySelectorAll(".lg-clamp").forEach(function (box) {
    var more = box.nextElementSibling;
    if (!more || !more.classList.contains("lg-clamp-more")) return;
    box.classList.add("lg-clamped");
    var para = box.querySelector("p");
    if (!para || para.scrollHeight <= para.clientHeight + 4) { box.classList.remove("lg-clamped"); return; }
    more.hidden = false;
    more.addEventListener("click", function () { box.classList.remove("lg-clamped"); more.setAttribute("aria-expanded", "true"); more.remove(); });
  });

  // A side list of a page's parts ([data-spy]): the part being read is marked.
  document.querySelectorAll("nav[data-spy]").forEach(function (nav) {
    var links = [].slice.call(nav.querySelectorAll('a[href^="#"]'));
    if (!links.length || !("IntersectionObserver" in window)) return;
    var seen = {};
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (x) { seen[x.target.id] = x.isIntersecting; });
      var on = null;
      links.forEach(function (a) { if (!on && seen[a.getAttribute("href").slice(1)]) on = a; });
      if (on) links.forEach(function (a) { if (a === on) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
    }, { rootMargin: "-90px 0px -50% 0px" });
    links.forEach(function (a) { var el = document.getElementById(a.getAttribute("href").slice(1)); if (el) io.observe(el); });
  });

  // A verse page: each word of the Greek or Hebrew line (a span the build
  // marks with the rows of the word table it covers, a Hebrew prefix and its
  // word together) opens in place to those rows: dictionary form, gloss and
  // grammar, labelled by the table's own headings.
  (function () {
    var line = document.querySelector(".lg-vorig"), rows = document.querySelectorAll(".lg-words tbody tr");
    var heads = [].map.call(document.querySelectorAll(".lg-words thead th"), function (th) { return th.textContent; });
    if (!line || !rows.length) return;
    [].forEach.call(line.querySelectorAll(".lg-vword"), function (sp) {
      var b = document.createElement("button");
      b.type = "button"; b.className = "lg-vw"; b.textContent = sp.textContent;
      b.setAttribute("data-rows", sp.getAttribute("data-rows")); b.setAttribute("aria-expanded", "false");
      sp.replaceWith(b);
    });
    var card = document.createElement("div");
    card.className = "lg-vw-card"; card.hidden = true; card.setAttribute("role", "dialog");
    line.after(card);
    var open = null;
    var close = function () {
      if (open) open.setAttribute("aria-expanded", "false");
      open = null; card.hidden = true;
    };
    line.addEventListener("click", function (e) {
      var b = e.target.closest(".lg-vw");
      if (!b) return;
      if (open === b) { close(); return; }
      close();
      card.innerHTML = "";
      b.getAttribute("data-rows").split(",").forEach(function (r) {
        var row = rows[+r];
        if (!row) return;
        var part = document.createElement("div"); part.className = "lg-vw-part";
        [].forEach.call(row.children, function (td, i) {
          if (!td.textContent.trim() || td.textContent.trim() === "-") return;
          var p = document.createElement("p");
          var k = document.createElement("span"); k.className = "lg-vw-k"; k.textContent = heads[i] || "";
          var tag = document.createElement("span"); tag.className = "lg-vw-v " + td.className; tag.innerHTML = td.innerHTML;
          if (td.getAttribute("lang")) tag.setAttribute("lang", td.getAttribute("lang"));
          if (td.getAttribute("dir")) tag.setAttribute("dir", td.getAttribute("dir"));
          p.appendChild(k); p.appendChild(tag); part.appendChild(p);
        });
        // Every verse with the same dictionary form, in the word search's Bible text.
        var lemma = row.children[1] && row.children[1].textContent.trim(), table = row.closest("table");
        if (lemma && table.getAttribute("data-uses")) {
          var a = document.createElement("a");
          a.className = "lg-vw-uses";
          a.href = "/search/?q=" + encodeURIComponent(lemma) + "&source=" + encodeURIComponent(table.getAttribute("data-source"));
          a.textContent = fmt(table.getAttribute("data-uses"), { word: lemma });
          part.appendChild(a);
        }
        card.appendChild(part);
      });
      card.setAttribute("aria-label", b.textContent);
      card.hidden = false; open = b; b.setAttribute("aria-expanded", "true");
      var lr = line.getBoundingClientRect(), br = b.getBoundingClientRect();
      card.style.top = (br.bottom - lr.top + line.offsetTop + 6) + "px";
      card.style.left = Math.max(0, Math.min(br.left - lr.left + line.offsetLeft, line.offsetLeft + line.offsetWidth - card.offsetWidth)) + "px";
    });
    document.addEventListener("click", function (e) { if (open && !e.target.closest(".lg-vw, .lg-vw-card")) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && open) { var b = open; close(); b.focus(); } });
  })();

  // Verse pages on a wide screen: once the title has scrolled away, a slim
  // bar under the header keeps the verse in sight.
  (function () {
    var bar = document.querySelector(".lg-vsticky"), h1 = document.querySelector(".lg-verse h1");
    if (!bar || !h1 || !window.IntersectionObserver) return;
    new IntersectionObserver(function (es) {
      bar.hidden = es[0].isIntersecting || es[0].boundingClientRect.top > 0;
    }).observe(h1);
  })();

  // A verse shown on its own can open a speech that the next verse closes
  // ("Blessed are those who are poor in spirit: ... theirs.) or close one an
  // earlier verse opened. A muted "…" after or before the words says so; the
  // words themselves are left exactly as the Bible text has them.
  function markSpeech(box) {
    var p = box.querySelector("p");
    if (!p) return;
    p.querySelectorAll(".lg-runon").forEach(function (x) { x.remove(); });
    var text = p.textContent, open = false, unopened = false, i, c;
    for (i = 0; i < text.length; i++) {
      c = text[i];
      if (c === "\u201C") open = true;
      else if (c === "\u201D") { if (open) open = false; else unopened = true; }
      else if (c === '"') {
        var before = i ? text[i - 1] : " ";
        if (open) open = false;
        else if (/[\s(\[\u2014-]/.test(before) || i === 0) open = true;
        else unopened = true;
      }
    }
    var cue = function (title, after) {
      var s = document.createElement("span");
      s.className = "lg-runon";
      s.title = title;
      s.setAttribute("aria-label", title);
      s.textContent = after ? " \u2026" : "\u2026 ";
      if (after) p.appendChild(s); else p.insertBefore(s, p.firstChild);
    };
    if (open) cue(box.getAttribute("data-runs-on"), true);
    if (unopened) cue(box.getAttribute("data-ran-on"), false);
  }
  document.querySelectorAll("[data-runs-on]").forEach(markSpeech);

  // A verse page: the verse at the reader's level (Literal, Balanced or
  // Readable, the setting web/site.js keeps), and buttons to change it there.
  var vtext = document.querySelector(".lg-vtext[data-l]"), vlevels = document.querySelector(".lg-vlevels");
  if (vtext && vlevels) {
    var showLevel = function () {
      var lv = (window.LogiaPrefs && window.LogiaPrefs.get("level")) || document.documentElement.getAttribute("data-level") || "B";
      if (!vtext.hasAttribute("data-" + lv.toLowerCase())) lv = "B";
      vtext.querySelector("p").textContent = vtext.getAttribute("data-" + lv.toLowerCase());
      markSpeech(vtext);
      vlevels.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-level") === lv); });
    };
    vlevels.hidden = false;
    vlevels.addEventListener("click", function (ev) {
      var b = ev.target.closest("button");
      if (b && window.LogiaPrefs) window.LogiaPrefs.set("level", b.getAttribute("data-level"));
      else if (b) { document.documentElement.setAttribute("data-level", b.getAttribute("data-level")); showLevel(); }
    });
    document.addEventListener("logia:prefs", showLevel);
    showLevel();
  }

  // A work's contents beside its pages: scrolled so the page being read shows.
  var tocBox = document.querySelector(".lg-work-toc"), tocHere = tocBox && tocBox.querySelector("[aria-current]");
  if (tocHere && tocBox.scrollHeight > tocBox.clientHeight) tocBox.scrollTop = tocHere.offsetTop - tocBox.clientHeight / 3;

  // Verse pages: the strip of the chapter's verses scrolls to this one.
  var near = document.querySelector(".lg-near"), here = near && near.querySelector("[aria-current]");
  if (here) near.scrollLeft = here.offsetLeft - near.offsetLeft - (near.clientWidth - here.offsetWidth) / 2;
  // An excerpt's More menu (scripts/build_site.py, excerpt_actions) closes
  // when the reader clicks elsewhere, presses Escape, or picks an item.
  document.addEventListener("click", function (ev) {
    document.querySelectorAll(".lg-xact-more[open]").forEach(function (d) {
      if (!d.contains(ev.target) || ev.target.closest(".lg-xact-menu button, .lg-xact-menu a")) d.open = false;
    });
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    document.querySelectorAll(".lg-xact-more[open]").forEach(function (d) { d.open = false; d.querySelector("summary").focus(); });
  });

  // Verse pages: a voice with several long excerpts shows its first, folded,
  // and one "Read all of Chrysostom: 3 excerpts, 857 words" that opens them
  // all; unless the address or a search points into one of them.
  document.querySelectorAll(".lg-voice[data-all]").forEach(function (sec) {
    var arts = [].slice.call(sec.querySelectorAll("article.lg-vx[id]"));
    if (arts.length < 2) return;
    if (location.hash && arts.some(function (a) { return "#" + a.id === location.hash; })) return;
    if (sec.querySelector("mark.lg-hl")) return;
    var later = arts.slice(1);
    later.forEach(function (a) { a.hidden = true; });
    var own = arts[0].querySelector(".lg-unfold");
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lg-unfold lg-unfold-all";
    btn.textContent = sec.getAttribute("data-all");
    var fold = arts[0].querySelector(".lg-foldable");
    (own || fold || arts[0].querySelector(".lg-text")).insertAdjacentElement("afterend", btn);
    if (own) own.dataset.grouped = "1";
    btn.addEventListener("click", function () {
      later.forEach(function (a) { a.hidden = false; });
      sec.querySelectorAll(".lg-folded").forEach(function (f) { f.classList.remove("lg-folded"); });
      sec.querySelectorAll(".lg-unfold").forEach(function (b) { b.remove(); });
    });
  });

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
    btn.hidden = !!btn.dataset.grouped;   // a voice's one "Read all" stands in for it
    btn.addEventListener("click", function () {
      box.classList.remove("lg-folded");
      btn.remove();
    });
  });
  // The footer (scripts/build_site.py, build_footer).
  (function () {
    var foot = document.querySelector("footer.site");
    if (!foot) return;
    // On a phone each site-map column folds to its heading; wider, all show.
    var narrow = window.matchMedia("(max-width: 640px)");
    var folds = foot.querySelectorAll(".lg-foot-fold");
    function setFolds() {
      folds.forEach(function (b) {
        var list = document.getElementById(b.getAttribute("aria-controls"));
        b.hidden = !narrow.matches;
        b.setAttribute("aria-expanded", narrow.matches ? "false" : "true");
        if (list) list.hidden = narrow.matches;
      });
    }
    folds.forEach(function (b) {
      b.addEventListener("click", function () {
        var open = b.getAttribute("aria-expanded") !== "true";
        b.setAttribute("aria-expanded", open ? "true" : "false");
        document.getElementById(b.getAttribute("aria-controls")).hidden = !open;
      });
    });
    setFolds();
    if (narrow.addEventListener) narrow.addEventListener("change", setFolds);

    // With no place saved, a page in a book offers its next chapter, so the
    // "Start reading" link is left for the pages outside the books.
    var resume = foot.querySelector(".foot-resume");
    if (resume && foot.querySelector(".lg-foot-next")) {
      var saved = null;
      try { saved = localStorage.getItem("logia-last"); } catch (e) { /* storage blocked */ }
      if (!saved) resume.parentNode.hidden = true;
    }

    // "Sources and licences" and "All shortcuts" open what they point to.
    var map = foot.querySelector(".lg-foot-sitemap");
    foot.querySelectorAll('a[href="#foot-sources"]').forEach(function (a) {
      a.addEventListener("click", function () { if (map) map.open = true; });
    });
    var keysAll = foot.querySelector("[data-keys-help]");
    if (keysAll) keysAll.addEventListener("click", function (e) {
      e.preventDefault();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "?", bubbles: true }));
    });

    // Back to top, once the page has scrolled a screen.
    var top = foot.querySelector(".lg-top");
    if (top) {
      var showTop = function () { top.classList.toggle("on", window.scrollY > window.innerHeight); };
      window.addEventListener("scroll", showTop, { passive: true });
      showTop();
      // Once the footer's last lines are on screen, the button parks at the
      // footer's end instead of floating over its links (logia.css).
      var base = foot.querySelector(".lg-foot-base");
      if (base && "IntersectionObserver" in window) {
        new IntersectionObserver(function (seen) {
          top.classList.toggle("docked", seen[0].isIntersecting || seen[0].boundingClientRect.bottom < 0);
        }).observe(base);
      }
    }

    // While the footer is on screen, a chapter's verse sheet steps aside (logia.css).
    // It is watched on every page, since the sheet can be built after this runs.
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (seen) {
        document.body.classList.toggle("lg-at-foot", seen[0].isIntersecting);
      }, { rootMargin: "0px 0px -10% 0px" }).observe(foot);
    }

    // The next day of the church year with a Logia page, within six weeks.
    var season = foot.querySelector(".lg-foot-season");
    if (season) {
      var days = [], today = new Date(); today.setHours(0, 0, 0, 0);
      try { days = JSON.parse(season.getAttribute("data-days")); } catch (e) { /* none */ }
      var soon = null;
      days.forEach(function (d) {
        d.dates.forEach(function (iso) {
          var p = iso.split("-"), at = new Date(+p[0], +p[1] - 1, +p[2]);
          if (at >= today && at - today <= 42 * 864e5 && (!soon || at < soon.at)) soon = { at: at, day: d };
        });
      });
      if (soon) {
        var when = "";
        try { when = soon.at.toLocaleDateString(document.documentElement.lang || undefined, { weekday: "long", day: "numeric", month: "long" }); }
        catch (e) { when = soon.at.toDateString(); }
        season.innerHTML = fmt(esc(season.getAttribute("data-text")), { date: esc(when), name: "<b>" + esc(soon.day.name) + "</b>" }) +
          ' <a href="' + esc(soon.day.href) + '">' + esc(season.getAttribute("data-go")) + "</a>";
        season.hidden = false;
      }
    }
  })();
})();
