/* Logia linker: turns Bible references on any web page ("John 3:16",
 * "1 Cor. 13:4-7", "Rom 8:28") into links to that verse on Logia, with a
 * preview of the verse and of what the church has said about it.
 *
 *   <script src="https://logia.faith/linker.js" defer></script>
 *
 * Options, on the script tag:
 *   data-logia-scope="article, .post"   only look inside these elements
 *   data-logia-preview="off"            links only, no preview cards
 * Leave an element alone with data-logia-skip.
 *
 * The verse text and commentary come from Logia's read-only API
 * (/api/v1/chapters/<BOOK>.<chapter>.json, docs/api.md). Book names,
 * chapter counts and the site's address are filled in when the site is
 * built (scripts/build_site.py); this file's own copy has placeholders.
 * Logia's data and this script are free to use (CC0 and MIT).
 */
(function () {
  "use strict";
  if (window.LogiaLinker) return;
  var SITE = "/*SITE*/";
  var NAMES = /*NAMES*/{};
  var CHAPTERS = /*CHAPTERS*/{};
  // English verse numbers -> Logia's (the Open Word Bible's source text counts
  // a psalm's title as verse 1): {"PSA.19": [[1, 14, 19, 1]]} is English
  // Psalm 19:1-14 -> Psalm 19, each verse plus one.
  var RENUMBER = /*RENUMBER*/{};
  function own(book, ch, v) {
    var runs = RENUMBER[book + "." + ch] || [];
    for (var i = 0; i < runs.length; i++) {
      if (v >= runs[i][0] && v <= runs[i][1]) return [runs[i][2], v + runs[i][3]];
    }
    return [ch, v];
  }
  var me = document.currentScript || document.querySelector('script[src*="linker.js"]');
  var opt = function (k) { return me ? me.getAttribute("data-logia-" + k) : null; };
  var SKIP = "a,script,style,noscript,textarea,input,select,button,code,pre,kbd,samp,svg,math,[contenteditable],[data-logia-skip],.logia-card";

  // "1 Cor. 13:4–7": a name (longest first, capitalised or numbered), a full
  // stop if abbreviated, then chapter:verse with an optional range.
  var names = Object.keys(NAMES).sort(function (a, b) { return b.length - a.length; });
  var alt = names.map(function (n) {
    return n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s?");
  }).join("|");
  var REF = new RegExp("(^|[^\\w])(" + alt + ")\\.?\\s?(\\d{1,3}):(\\d{1,3})(?:\\s?[-–]\\s?(\\d{1,3})(?!:))?(?![\\w:])", "gi");

  function code(name) { return NAMES[name.toLowerCase().replace(/\s+/g, " ")] || NAMES[name.toLowerCase().replace(/\s+/g, "")]; }

  function link(text) {
    var out = [], last = 0, m, any = false;
    REF.lastIndex = 0;
    while ((m = REF.exec(text))) {
      // A book's name starts with a capital ("Is 53:5", not "is 9:30").
      var letter = m[2].match(/[A-Za-z]/);
      if (letter && letter[0] !== letter[0].toUpperCase()) continue;
      var book = code(m[2]), ch = +m[3], v = +m[4], to = m[5] ? +m[5] : null;
      if (!book || !CHAPTERS[book] || ch < 1 || v < 1 || (to && to < v)) continue;
      var at = own(book, ch, v), end = to ? own(book, ch, to) : at;
      if (at[0] > CHAPTERS[book] || end[0] !== at[0]) { if (at[0] > CHAPTERS[book]) continue; end = [at[0], at[1]]; }
      ch = at[0]; v = at[1]; to = to ? end[1] : null;
      var start = m.index + m[1].length, words = text.slice(start, REF.lastIndex);
      if (start > last) out.push(document.createTextNode(text.slice(last, start)));
      var a = document.createElement("a");
      a.className = "logia-ref";
      a.href = SITE + "/" + book.toLowerCase() + "/" + ch + "/#v" + v;
      a.textContent = words;
      a.setAttribute("data-logia", book + "." + ch + "." + v + (to ? "-" + to : ""));
      out.push(a);
      last = REF.lastIndex;
      any = true;
    }
    if (!any) return null;
    if (last < text.length) out.push(document.createTextNode(text.slice(last)));
    return out;
  }

  function scan(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!/\d:\d/.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        return n.parentElement && n.parentElement.closest(SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(function (n) {
      var parts = link(n.nodeValue);
      if (!parts) return;
      var frag = document.createDocumentFragment();
      parts.forEach(function (p) { frag.appendChild(p); });
      n.parentNode.replaceChild(frag, n);
    });
  }

  // The preview card: the verse (or the first verses of a range), and how
  // many commentators Logia has on it, with their names.
  var cache = {}, card = null, hideTimer = null;
  function chapter(book, ch) {
    var key = book + "." + ch;
    if (!cache[key]) {
      cache[key] = fetch(SITE + "/api/v1/chapters/" + key + ".json").then(function (r) {
        if (!r.ok) throw new Error(r.status); return r.json();
      });
    }
    return cache[key];
  }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function style() {
    if (document.getElementById("logia-linker-style")) return;
    var s = document.createElement("style");
    s.id = "logia-linker-style";
    s.textContent =
      ".logia-card{position:absolute;z-index:2147483000;max-width:min(380px,calc(100vw - 24px));box-sizing:border-box;" +
      "background:#fffdf8;color:#221c15;border:1px solid #e8dfcf;border-radius:12px;box-shadow:0 10px 30px rgba(34,28,21,.18);" +
      "padding:14px 16px;font:15px/1.5 Georgia,'Times New Roman',serif;text-align:left}" +
      ".logia-card b.lr{display:block;font:600 13px/1.3 system-ui,sans-serif;letter-spacing:.04em;text-transform:uppercase;color:#9a6a1c;margin-bottom:4px}" +
      ".logia-card p{margin:0 0 8px}.logia-card .lv{font-size:12px;color:#9a6a1c;font-family:system-ui,sans-serif;vertical-align:super;margin-right:3px}" +
      ".logia-card .lc{font:13.5px/1.45 system-ui,sans-serif;color:#6e6358;border-top:1px solid #e8dfcf;padding-top:8px;margin:0}" +
      ".logia-card a{color:#3f3d9a;font-weight:600;text-decoration:none}.logia-card a:hover{text-decoration:underline}" +
      ".logia-card .lf{font:11.5px/1.4 system-ui,sans-serif;color:#968462;margin:6px 0 0}" +
      "@media (prefers-color-scheme:dark){.logia-card{background:#201b15;color:#ece3d4;border-color:#2d261d}" +
      ".logia-card .lc{color:#ab9f8b;border-color:#2d261d}.logia-card a{color:#9c9af2}}";
    document.head.appendChild(s);
  }
  function place(a) {
    var r = a.getBoundingClientRect();
    var left = Math.max(12, Math.min(r.left + window.scrollX, window.scrollX + document.documentElement.clientWidth - card.offsetWidth - 12));
    var top = r.bottom + window.scrollY + 6;
    if (r.bottom + card.offsetHeight + 12 > window.innerHeight && r.top > card.offsetHeight + 12) top = r.top + window.scrollY - card.offsetHeight - 6;
    card.style.left = left + "px"; card.style.top = top + "px";
  }
  function show(a) {
    clearTimeout(hideTimer);
    var ref = a.getAttribute("data-logia").split(/[.-]/);
    var book = ref[0], ch = +ref[1], v = +ref[2], to = ref[3] ? +ref[3] : v;
    style();
    if (!card) {
      card = document.createElement("div");
      card.className = "logia-card"; card.setAttribute("role", "tooltip"); card.id = "logia-card";
      card.addEventListener("mouseenter", function () { clearTimeout(hideTimer); });
      card.addEventListener("mouseleave", hide);
      document.body.appendChild(card);
    }
    card.hidden = false;
    card.innerHTML = '<b class="lr">' + esc(a.textContent) + "</b><p>…</p>";
    a.setAttribute("aria-describedby", "logia-card");
    place(a);
    chapter(book, ch).then(function (d) {
      if (a.getAttribute("aria-describedby") !== "logia-card" || card.hidden) return;
      var verses = d.verses.filter(function (x) { return x.verse >= v && x.verse <= Math.min(to, v + 2); });
      if (!verses.length) { card.innerHTML = '<b class="lr">' + esc(a.textContent) + "</b><p>—</p>"; return; }
      var first = verses[0], people = [];
      first.excerpts.forEach(function (id) {
        var name = d.excerpts[id] && d.excerpts[id].author_name;
        if (name && people.indexOf(name) < 0) people.push(name);
      });
      var text = verses.map(function (x) {
        return (verses.length > 1 ? '<span class="lv">' + x.verse + "</span>" : "") + esc(x.text);
      }).join(" ") + (to > v + 2 ? " …" : "");
      var more = people.length
        ? esc(people.length + (people.length === 1 ? " commentator" : " commentators") + ": " +
              people.slice(0, 4).join(", ") + (people.length > 4 ? "…" : "")) + ' · <a href="' + esc(a.href) + '">Read what they say</a>'
        : '<a href="' + esc(a.href) + '">Read it on Logia</a>' +
          (first.cited_by.length ? esc(" · cited in " + first.cited_by.length + " commentar" + (first.cited_by.length === 1 ? "y" : "ies")) : "");
      card.innerHTML = '<b class="lr">' + esc(a.textContent) + "</b>" +
        "<p>" + text + '</p><p class="lc">' + more + '</p><p class="lf">Open Word Bible · Logia</p>';
      place(a);
    }).catch(function () { card.innerHTML = '<b class="lr">' + esc(a.textContent) + '</b><p class="lc"><a href="' + esc(a.href) + '">Read it on Logia</a></p>'; });
  }
  function hide() {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function () {
      if (card) card.hidden = true;
      document.querySelectorAll('[aria-describedby="logia-card"]').forEach(function (x) { x.removeAttribute("aria-describedby"); });
    }, 200);
  }

  function start() {
    var scope = opt("scope");
    var roots = scope ? Array.prototype.slice.call(document.querySelectorAll(scope)) : [document.body];
    roots.forEach(scan);
    if (opt("preview") === "off" || !window.fetch) return;
    var over = function (e) { var a = e.target.closest && e.target.closest("a.logia-ref"); if (a) show(a); };
    var out = function (e) { var a = e.target.closest && e.target.closest("a.logia-ref"); if (a) hide(); };
    document.addEventListener("mouseover", over);
    document.addEventListener("mouseout", out);
    document.addEventListener("focusin", over);
    document.addEventListener("focusout", out);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") hide(); });
  }
  window.LogiaLinker = { scan: scan };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
