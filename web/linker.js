/* Logia's linker: a script any website can add, which turns the Bible
   references in its pages ("John 1:14", "Rom. 5:1-2") into links to Logia,
   with a small card showing the verse and who comments on it.

     <script src="https://logia.faith/linker.js" defer></script>

   The book names, the words on the card and the site's address are filled in
   when Logia builds (linker_js in scripts/build_site.py). Each card reads
   /linker/<BOOK>.<chapter>.json, one small file per chapter, numbered as
   English Bibles number it. A page can leave a part of itself alone by giving
   it the class "logia-skip". */
(function () {
  "use strict";
  var CONFIG = /*LOGIA*/ { site: "https://logia.faith", books: {}, numbered: {}, ui: {} } /*END*/;
  if (window.__logiaLinker) return;
  window.__logiaLinker = true;

  var SKIP = /^(A|SCRIPT|STYLE|NOSCRIPT|TEXTAREA|INPUT|SELECT|OPTION|CODE|PRE|BUTTON|SVG|MATH|IFRAME|TEMPLATE)$/;
  var names = Object.keys(CONFIG.books).sort(function (a, b) { return b.length - a.length; });
  var numbered = Object.keys(CONFIG.numbered).sort(function (a, b) { return b.length - a.length; });
  if (!names.length) return;
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); };
  // "1 Cor. 13:4", "I John 4:8", "John 3:16", "Ps. 23:1-3", "Rom 5:1–2"
  var RE = new RegExp("(?:\\b([1-3]|I{1,3})\\s?(" + numbered.map(esc).join("|") + ")|\\b(" + names.map(esc).join("|") +
                      "))\\.?\\s+(\\d{1,3}):(\\d{1,3})(?:\\s?[-\\u2013]\\s?(\\d{1,3}))?(?![\\d:])", "g");
  var ROMAN = { I: 1, II: 2, III: 3 };

  function code(m) {
    if (m[2]) {
      var n = ROMAN[m[1]] || +m[1];
      return CONFIG.numbered[m[2]][n - 1] || null;
    }
    return CONFIG.books[m[3]] || null;
  }

  function walk(root) {
    var found = [];
    var tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        for (var el = node.parentNode; el && el !== root.parentNode; el = el.parentNode) {
          if (el.nodeType !== 1) continue;
          if (SKIP.test(el.nodeName.toUpperCase()) || el.isContentEditable ||
              (el.classList && (el.classList.contains("logia-skip") || el.classList.contains("logia-card")))) return NodeFilter.FILTER_REJECT;
        }
        RE.lastIndex = 0;
        return RE.test(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
    });
    while (tw.nextNode()) found.push(tw.currentNode);
    found.forEach(link);
  }

  function link(node) {
    var text = node.nodeValue, last = 0, frag = document.createDocumentFragment(), m, any = false;
    RE.lastIndex = 0;
    while ((m = RE.exec(text))) {
      var book = code(m);
      if (!book) continue;
      var ch = +m[4], v = +m[5], ev = m[6] ? +m[6] : v;
      if (ev < v) continue;
      frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      var a = document.createElement("a");
      a.className = "logia-ref";
      a.textContent = m[0];
      a.href = CONFIG.site + "/" + book.toLowerCase() + "/" + ch + "/";
      a.setAttribute("data-logia", book + "." + ch + "." + v + (ev !== v ? "-" + ev : ""));
      a.target = "_blank";
      a.rel = "noopener";
      frag.appendChild(a);
      last = m.index + m[0].length;
      any = true;
    }
    if (!any) return;
    frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }

  // The card -------------------------------------------------------------
  var cache = {}, card = null, current = null, hideTimer = null;

  function chapter(key) {
    if (!cache[key]) {
      cache[key] = fetch(CONFIG.site + "/linker/" + key + ".json").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      });
    }
    return cache[key];
  }

  function el(tag, cls, text) {
    var x = document.createElement(tag);
    if (cls) x.className = cls;
    if (text != null) x.textContent = text;
    return x;
  }

  function fill(a, data, v, ev) {
    card.textContent = "";
    var verses = [], voices = [], href = null, n = 0;
    for (var i = v; i <= ev; i++) {
      var x = data.verses[String(i)];
      if (!x) continue;
      verses.push((ev > v ? i + " " : "") + x.text);
      (x.voices || []).forEach(function (name) { if (voices.indexOf(name) < 0) voices.push(name); });
      n += x.n || 0;
      if (!href) href = x.href;
    }
    if (!verses.length) { hide(); return; }
    card.appendChild(el("p", "logia-card-ref", data.name + " " + data.chapter + ":" + v + (ev > v ? "–" + ev : "")));
    card.appendChild(el("p", "logia-card-text", verses.join(" ")));
    card.appendChild(el("p", "logia-card-bible", CONFIG.ui.bible));
    if (voices.length) {
      var shown = voices.slice(0, 6).join(", ") + (voices.length > 6 ? CONFIG.ui.more.replace("{n}", voices.length - 6) : "");
      card.appendChild(el("p", "logia-card-voices", CONFIG.ui.voices.replace("{n}", voices.length).replace("{names}", shown)));
    } else {
      card.appendChild(el("p", "logia-card-voices", CONFIG.ui.none));
    }
    var go = el("a", "logia-card-go", voices.length ? CONFIG.ui.read : CONFIG.ui.read_verse);
    go.href = CONFIG.site + (href || ("/" + data.book.toLowerCase() + "/" + data.chapter + "/"));
    go.target = "_blank";
    go.rel = "noopener";
    card.appendChild(go);
    a.href = go.href;
    place(a);
  }

  function place(a) {
    var r = a.getBoundingClientRect(), w = Math.min(340, window.innerWidth - 24);
    card.style.width = w + "px";
    var left = Math.max(12, Math.min(r.left + window.scrollX, window.scrollX + window.innerWidth - w - 12));
    card.style.left = left + "px";
    card.style.top = (r.bottom + window.scrollY + 8) + "px";
    card.hidden = false;
    var cr = card.getBoundingClientRect();
    if (cr.bottom > window.innerHeight && r.top > cr.height + 16) card.style.top = (r.top + window.scrollY - cr.height - 8) + "px";
  }

  function show(a) {
    clearTimeout(hideTimer);
    if (current === a && !card.hidden) return;
    current = a;
    var m = /^([1-3]?[A-Z]{2,3})\.(\d+)\.(\d+)(?:-(\d+))?$/.exec(a.getAttribute("data-logia"));
    if (!m) return;
    chapter(m[1] + "." + m[2]).then(function (data) {
      if (current === a) fill(a, data, +m[3], m[4] ? +m[4] : +m[3]);
    }).catch(function () { delete cache[m[1] + "." + m[2]]; });
  }

  function hide() {
    hideTimer = setTimeout(function () { if (card) card.hidden = true; current = null; }, 200);
  }

  function style() {
    var css = ".logia-ref{text-decoration:underline dotted;text-underline-offset:3px}" +
      ".logia-card{position:absolute;z-index:2147483000;box-sizing:border-box;padding:12px 14px;border-radius:10px;" +
      "background:#fffdf8;color:#221c15;border:1px solid #d9ccb4;box-shadow:0 8px 28px rgba(0,0,0,.16);" +
      "font:14px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;text-align:left}" +
      ".logia-card p{margin:0 0 6px}.logia-card-ref{font-weight:700}" +
      ".logia-card-text{font-family:Georgia,'Times New Roman',serif;font-size:15px}" +
      ".logia-card-bible,.logia-card-voices{font-size:12.5px;color:#6e6358}" +
      ".logia-card-go{display:inline-block;margin-top:2px;font-weight:600;color:#3f3d9a}" +
      "@media (prefers-color-scheme:dark){.logia-card{background:#201b15;color:#ece3d4;border-color:#3a3127}" +
      ".logia-card-bible,.logia-card-voices{color:#ab9f8b}.logia-card-go{color:#9c9af2}}";
    var s = document.createElement("style");
    s.textContent = css;
    document.head.appendChild(s);
  }

  function start() {
    style();
    card = el("div", "logia-card");
    card.hidden = true;
    card.setAttribute("role", "tooltip");
    document.body.appendChild(card);
    card.addEventListener("mouseenter", function () { clearTimeout(hideTimer); });
    card.addEventListener("mouseleave", hide);
    var target = function (ev) { return ev.target.closest && ev.target.closest("a.logia-ref"); };
    document.addEventListener("mouseover", function (ev) { var a = target(ev); if (a) show(a); });
    document.addEventListener("mouseout", function (ev) { if (target(ev)) hide(); });
    document.addEventListener("focusin", function (ev) { var a = target(ev); if (a) show(a); });
    document.addEventListener("focusout", function (ev) { if (target(ev)) hide(); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && card) card.hidden = true; });
    walk(document.body);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
