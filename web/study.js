// Logia's study tools, on every page beside web/logia.js. All of it is kept
// in this browser only (localStorage), apart from the commentary, and works
// without an account:
//
// - Select words in an excerpt or a whole homily: copy them as a quote with
//   their citation, highlight them, or add the excerpt to a study sheet.
// - A note of the reader's own under any excerpt, always marked as theirs.
// - Share an excerpt as an image (a card drawn here, never sent anywhere).
// - Whole homilies remember the section last read and offer to pick up there.
// - The pages read lately, and the notes, listed on the Saved page.
// - The next chapter is fetched while the reader is near the end of this one.
// - /random/ opens a verse at random; /quiz/ plays "Who said it?".
//
// The words come from the catalog (study.ui, <script id="study-text">).
(function () {
  "use strict";
  var T = {};
  try { T = JSON.parse((document.getElementById("study-text") || {}).textContent || "{}"); } catch (e) { T = {}; }
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  };
  var fmt = function (s, o) { return String(s || "").replace(/\{(\w+)\}/g, function (_m, k) { return o[k] != null ? o[k] : ""; }); };
  function get(key, empty) {
    try { var v = JSON.parse(localStorage.getItem(key) || "null"); return v == null ? empty : v; } catch (e) { return empty; }
  }
  function put(key, v) { try { localStorage.setItem(key, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function title() { return document.title.replace(/ · Logia$/, ""); }

  // The device asks for more contrast and the reader picks the paper mode on
  // purpose: remember it, so the boot script stops choosing contrast for them.
  document.addEventListener("logia:prefs", function (ev) {
    var d = ev.detail || {};
    if (d.pref === "theme" && d.value === "light" && window.matchMedia && matchMedia("(prefers-contrast: more)").matches) {
      try { localStorage.setItem("logia-theme", "light"); } catch (e) { /* storage blocked */ }
    }
  });

  // An excerpt's article (id "<work>.<BOOK>.<chapter>.<verse>.<n>") and its actions box.
  function excerptOf(node) {
    var a = node && node.closest ? node.closest("article.lg-excerpt[id]") : null;
    return a && /^[a-z0-9-]+\.[1-3]?[A-Z]{2,3}\.\d+\.\d+\.\d+$/.test(a.id) ? a : null;
  }
  function citeOf(article) {
    var box = article && article.querySelector(".lg-xact");
    if (box) return box.getAttribute("data-cite");
    return title() + ". " + location.origin + location.pathname;
  }
  function sheetKey(article) { return article.id.split(".").slice(0, 4).join("."); }
  function addToSheet(key) {
    if (window.LogiaSheets) return window.LogiaSheets.add(key).ok;
    var x = get("logia.sheets", { sheets: [], current: null });
    if (!x.sheets) x = { sheets: [], current: null };
    var s = x.sheets.filter(function (y) { return y.id === x.current; })[0];
    if (!s) {
      s = { id: Date.now().toString(36), title: T.untitled || "My study sheet", items: [] };
      x.sheets.unshift(s); x.current = s.id;
    }
    if (!s.items.some(function (i) { return i.k === key; })) s.items.push({ k: key });
    return put("logia.sheets", x);
  }
  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (ok, no) {
      var area = document.createElement("textarea");
      area.value = text; area.style.position = "fixed"; area.style.opacity = "0";
      document.body.appendChild(area); area.select();
      try { document.execCommand("copy") ? ok() : no(); } catch (e) { no(e); }
      area.remove();
    });
  }
  var toast = (function () {
    var el = null, timer = null;
    return function (text) {
      if (!el) { el = document.createElement("p"); el.className = "lg-toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
      el.textContent = text; el.hidden = false;
      clearTimeout(timer); timer = setTimeout(function () { el.hidden = true; }, 2600);
    };
  })();

  // Highlights ----------------------------------------------------------------
  // Kept as character offsets into the excerpt's text (logia-highlights,
  // {excerpt id: [[start, end]]}) and drawn as <mark>s.
  var HL = "logia-highlights";
  function textNodes(root) {
    var out = [], w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    while (w.nextNode()) out.push(w.currentNode);
    return out;
  }
  function offsetOf(root, node, off) {
    var n = 0, nodes = textNodes(root);
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i] === node) return n + off;
      n += nodes[i].nodeValue.length;
    }
    return -1;
  }
  function paint(root, a, b) {
    var n = 0;
    textNodes(root).forEach(function (t) {
      var len = t.nodeValue.length, lo = Math.max(a, n), hi = Math.min(b, n + len);
      if (lo < hi) {
        var r = document.createRange();
        r.setStart(t, lo - n); r.setEnd(t, hi - n);
        var m = document.createElement("mark"); m.className = "lg-hl";
        try { r.surroundContents(m); } catch (e) { /* across elements: skip this piece */ }
      }
      n += len;
    });
  }
  function drawHighlights() {
    var all = get(HL, {});
    Object.keys(all).forEach(function (id) {
      var art = document.getElementById(id);
      var text = art && art.querySelector(".lg-text");
      if (!text) return;
      all[id].forEach(function (p) { paint(text, p[0], p[1]); });
    });
  }

  // The bar over a selection ---------------------------------------------------
  var bar = null, picked = null;
  function hideBar() { if (bar) bar.hidden = true; picked = null; }
  function showBar(range, article, inText) {
    if (!bar) {
      bar = document.createElement("div");
      bar.className = "lg-selbar"; bar.setAttribute("role", "toolbar");
      bar.innerHTML = '<button type="button" data-do="quote">' + esc(T.quote) + "</button>" +
        '<button type="button" data-do="hl">' + esc(T.highlight || "Highlight") + "</button>" +
        '<button type="button" data-do="sheet">' + esc(T.to_sheet) + "</button>";
      document.body.appendChild(bar);
      bar.addEventListener("mousedown", function (e) { e.preventDefault(); });
      bar.addEventListener("click", function (e) {
        var b = e.target.closest("button");
        if (!b || !picked) return;
        var what = b.getAttribute("data-do"), p = picked;
        if (what === "quote") {
          var said = p.text.replace(/\s+/g, " ").trim();
          var where = p.article ? citeOf(p.article) : title() + ". " + location.origin + location.pathname + (p.anchor ? "#" + p.anchor : "");
          copy("“" + said + "”\n— " + where).then(function () { toast(T.quote_done); }, function () { toast(said); });
        } else if (what === "hl" && p.article && p.inText) {
          var all = get(HL, {});
          (all[p.article.id] = all[p.article.id] || []).push([p.start, p.end]);
          put(HL, all);
          paint(p.inText, p.start, p.end);
          window.getSelection().removeAllRanges();
        } else if (what === "sheet" && p.article) {
          if (addToSheet(sheetKey(p.article))) toast(T.to_sheet_done);
        }
        hideBar();
      });
    }
    bar.querySelector('[data-do="hl"]').hidden = !(article && inText);
    bar.querySelector('[data-do="sheet"]').hidden = !article;
    var r = range.getBoundingClientRect();
    bar.hidden = false;
    var w = bar.offsetWidth;
    bar.style.top = (r.top + window.scrollY - bar.offsetHeight - 8) + "px";
    bar.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + window.scrollX + r.width / 2 - w / 2)) + "px";
  }
  document.addEventListener("mouseup", function (ev) { if (!bar || !bar.contains(ev.target)) setTimeout(checkSelection, 0); });
  document.addEventListener("keyup", function (ev) { if (ev.shiftKey) checkSelection(); });
  document.addEventListener("touchend", function () { setTimeout(checkSelection, 300); });
  function checkSelection() {
    var sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) { hideBar(); return; }
    var range = sel.getRangeAt(0), node = range.commonAncestorContainer;
    var el = node.nodeType === 1 ? node : node.parentElement;
    var inText = el && el.closest(".lg-text, .lg-whole");
    if (!inText) { hideBar(); return; }
    var article = excerptOf(el);
    var textBox = article ? article.querySelector(".lg-text") : null;
    var text = sel.toString();
    if (text.trim().length < 3) { hideBar(); return; }
    var para = el.closest("p[id]");
    picked = { text: text, article: article, anchor: para ? para.id : "", inText: textBox && textBox.contains(range.startContainer) ? textBox : null };
    if (picked.inText) {
      picked.start = offsetOf(textBox, range.startContainer, range.startOffset);
      picked.end = offsetOf(textBox, range.endContainer, range.endOffset);
      if (picked.start < 0 || picked.end <= picked.start) picked.inText = null;
    }
    showBar(range, article, !!picked.inText);
  }

  // Notes and "Share as image", beside each excerpt's own actions ----------------
  var NOTES = "logia-notes";
  function noteBox(article, open) {
    var notes = get(NOTES, {}), mine = notes[article.id];
    var box = article.querySelector(".lg-mynote");
    if (!mine && !open) { if (box) box.remove(); return; }
    if (!box) {
      box = document.createElement("div");
      box.className = "lg-mynote";
      var actions = article.querySelector(".lg-xact");
      article.insertBefore(box, actions ? actions.nextSibling : null);
    }
    box.innerHTML = '<p class="lg-mynote-who">' + esc(T.note_who) + "</p>" +
      '<textarea rows="3" aria-label="' + esc(T.note_label) + '">' + esc(mine ? mine.t : "") + "</textarea>" +
      '<p class="lg-mynote-tools"><span class="lg-quiet" role="status"></span> <button type="button" class="lg-linkish">' + esc(T.note_delete) + "</button></p>";
    var area = box.querySelector("textarea"), said = box.querySelector("[role=status]");
    var info = article.querySelector(".lg-xact");
    area.addEventListener("input", function () {
      var all = get(NOTES, {});
      if (area.value.trim()) {
        all[article.id] = { t: area.value, at: new Date().toISOString().slice(0, 10), w: info ? info.getAttribute("data-title") : title(),
          h: location.pathname + "#" + article.id };
      } else delete all[article.id];
      put(NOTES, all);
      said.textContent = T.note_save;
    });
    box.querySelector("button").addEventListener("click", function () {
      var all = get(NOTES, {}); delete all[article.id]; put(NOTES, all); box.remove();
    });
    if (open) area.focus();
  }

  function wrap(ctx, text, width) {
    var words = text.split(/\s+/), lines = [], line = "";
    words.forEach(function (w) {
      var tryLine = line ? line + " " + w : w;
      if (ctx.measureText(tryLine).width > width && line) { lines.push(line); line = w; } else line = tryLine;
    });
    if (line) lines.push(line);
    return lines;
  }
  function shareImage(article) {
    var info = article.querySelector(".lg-xact");
    var who = info ? info.getAttribute("data-title") : title();
    var text = (article.querySelector(".lg-text") || article).textContent.replace(/\s+/g, " ").trim();
    var sel = window.getSelection && window.getSelection().toString().trim();
    if (sel && article.contains(window.getSelection().anchorNode)) text = sel;
    var c = document.createElement("canvas"); c.width = 1200; c.height = 630;
    var x = c.getContext("2d");
    var css = getComputedStyle(document.documentElement);
    x.fillStyle = "#f9f4ea"; x.fillRect(0, 0, 1200, 630);
    x.fillStyle = "#9c6f1e"; x.fillRect(0, 0, 14, 630);
    var serif = (css.getPropertyValue("--serif") || "").trim() || "Georgia, serif";
    var size = 40, lines;
    do {
      x.font = size + "px " + serif;
      lines = wrap(x, "“" + text, 1040);
      size -= 2;
    } while (lines.length * size * 1.4 > 400 && size > 24);
    var max = Math.floor(400 / (size * 1.4));
    if (lines.length > max) { lines = lines.slice(0, max); lines[max - 1] = lines[max - 1].replace(/[\s,;:.]*\S*$/, "") + " …"; }
    lines[lines.length - 1] += "”";
    x.fillStyle = "#2b2318";
    lines.forEach(function (l, i) { x.fillText(l, 80, 110 + i * size * 1.4); });
    x.font = "600 30px system-ui, sans-serif"; x.fillStyle = "#2b2318";
    x.fillText(who, 80, 555);
    x.font = "26px system-ui, sans-serif"; x.fillStyle = "#6f6350";
    x.fillText("logia.faith", 1120 - x.measureText("logia.faith").width, 555);
    c.toBlob(function (blob) {
      if (!blob) return;
      var name = article.id + ".png";
      var file = window.File ? new File([blob], name, { type: "image/png" }) : null;
      if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], title: who, url: location.origin + location.pathname + "#" + article.id }).catch(function () {});
        return;
      }
      var a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
      toast(T.image_done);
    }, "image/png");
  }

  document.querySelectorAll("article.lg-excerpt .lg-xact").forEach(function (box) {
    var article = excerptOf(box);
    if (!article) return;
    var note = document.createElement("button");
    note.type = "button"; note.className = "lg-xact-extra";
    note.textContent = T.note;
    note.addEventListener("click", function () { noteBox(article, true); });
    var img = document.createElement("button");
    img.type = "button"; img.className = "lg-xact-extra";
    img.textContent = T.image;
    img.addEventListener("click", function () { shareImage(article); });
    var report = box.querySelector("a");
    box.insertBefore(note, report);
    box.insertBefore(img, report);
    noteBox(article, false);
  });
  drawHighlights();

  // "See the printed page": the scan's page, loaded only when asked ---------------
  document.querySelectorAll(".lg-scan-show").forEach(function (b) {
    b.hidden = false;
    b.addEventListener("click", function () {
      var art = b.closest("article") || b.parentElement;
      var fig = art.querySelector(".lg-scan-fig");
      if (fig) { fig.hidden = !fig.hidden; b.textContent = fig.hidden ? T.scan_show || b.dataset.show : b.getAttribute("data-hide"); return; }
      b.dataset.show = b.textContent;
      fig = document.createElement("figure");
      fig.className = "lg-scan-fig";
      fig.innerHTML = '<a href="' + esc(b.getAttribute("data-href")) + '" rel="noopener"><img loading="lazy" src="' + esc(b.getAttribute("data-img")) +
        '" alt="' + esc(b.getAttribute("data-alt")) + '"></a>';
      b.parentElement.insertAdjacentElement("afterend", fig);
      b.textContent = b.getAttribute("data-hide");
    });
  });

  // Whole homilies: remember the section last read ------------------------------
  var whole = document.querySelector(".lg-whole");
  if (whole && "IntersectionObserver" in window) {
    var places = get("logia-place", {}), path = location.pathname, sections = whole.querySelectorAll("section.lg-section[id]");
    var was = places[path];
    var first = sections.length ? sections[0].id : null;
    if (was && was !== first && !location.hash && document.getElementById(was)) {
      var num = document.querySelector("#" + CSS.escape(was) + " .lg-sec-n");
      var go = document.createElement("p");
      go.className = "lg-pickup";
      go.innerHTML = '<a class="button ghost" href="#' + esc(was) + '">' + esc(fmt(T.pick_up, { where: num ? num.textContent : was })) + "</a>";
      whole.parentElement.insertBefore(go, whole);
    }
    var seen = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        var all = get("logia-place", {});
        all[path] = en.target.id;
        var keys = Object.keys(all);
        if (keys.length > 100) delete all[keys[0]];
        put("logia-place", all);
      });
    }, { rootMargin: "0px 0px -70% 0px" });
    sections.forEach(function (s) { seen.observe(s); });
  }

  // Recently read: chapters, verses, passages, homilies and a work's chapters ---
  var READABLE = /^\/(?:[0-9a-z]{3}\/\d+\/(?:\d+(?:-[\d.]+)?\/)?|works\/[a-z0-9-]+\/(?:\d+|[0-9a-z]{3}\/\d+)\/)$/;
  if (READABLE.test(location.pathname)) {
    var recent = get("logia-recent", []).filter(function (r) { return r.p !== location.pathname; });
    recent.unshift({ p: location.pathname, t: title(), at: new Date().toISOString().slice(0, 10) });
    put("logia-recent", recent.slice(0, 20));
  }

  // The Saved page: notes and recently read ------------------------------------------
  var noteList = document.querySelector('[data-study="notes"]');
  if (noteList) {
    var all = get(NOTES, {}), ids = Object.keys(all).sort(function (a, b) { return (all[b].at || "").localeCompare(all[a].at || ""); });
    noteList.innerHTML = "<h2>" + esc(T.notes_heading) + "</h2>" + (ids.length ? '<ul class="lg-mynotes">' + ids.map(function (id) {
      var n = all[id];
      return '<li><p><a href="' + esc(n.h) + '"><b>' + esc(n.w || id) + '</b></a> <span class="lg-quiet">' + esc(n.at || "") + "</span></p>" +
        '<p class="lg-mynote-text">' + esc(n.t) + "</p></li>";
    }).join("") + "</ul>" : '<p class="lg-quiet">' + esc(T.notes_none) + "</p>");
  }
  var recentList = document.querySelector('[data-study="recent"]');
  if (recentList) {
    var draw = function () {
      var rs = get("logia-recent", []);
      recentList.innerHTML = "<h2>" + esc(T.recent_heading) + "</h2>" + (rs.length
        ? '<ol class="lg-recent">' + rs.map(function (r) {
          return '<li><a href="' + esc(r.p) + '">' + esc(r.t) + '</a> <span class="lg-quiet">' + esc(r.at) + "</span></li>";
        }).join("") + '</ol><p><button type="button" class="button ghost" data-clear>' + esc(T.recent_clear) + "</button></p>"
        : '<p class="lg-quiet">' + esc(T.recent_none) + "</p>");
    };
    draw();
    recentList.addEventListener("click", function (e) {
      if (!e.target.closest("[data-clear]")) return;
      try { localStorage.removeItem("logia-recent"); } catch (err) { /* storage blocked */ }
      draw();
    });
  }

  // Fetch the next chapter while the reader is near the end of this one ----------
  var next = document.querySelector('.lg-turns a[rel="next"], a[rel="next"]');
  if (next && "IntersectionObserver" in window) {
    var once = false, foot = document.querySelector(".lg-turns, footer");
    if (foot) {
      new IntersectionObserver(function (es, obs) {
        if (once || !es.some(function (en) { return en.isIntersecting; })) return;
        once = true; obs.disconnect();
        var l = document.createElement("link");
        l.rel = "prefetch"; l.href = next.getAttribute("href");
        document.head.appendChild(l);
      }, { rootMargin: "800px" }).observe(foot);
    }
  }

  // /random/: a verse with commentary at random, then one of its excerpts ---------
  var go = document.getElementById("random-go");
  if (go) {
    fetch("/random.json").then(function (r) { return r.json(); }).then(function (all) {
      var keys = Object.keys(all), total = 0;
      keys.forEach(function (k) { total += all[k].length; });
      function pick() {
        var n = Math.floor(Math.random() * total);
        for (var i = 0; i < keys.length; i++) {
          if (n < all[keys[i]].length) return "/" + keys[i] + "/" + all[keys[i]][n] + "/#random";
          n -= all[keys[i]].length;
        }
        return "/";
      }
      var href = pick();
      go.href = href;
      var st = document.getElementById("random-status");
      if (st) st.textContent = fmt(T.random_go, { ref: href.split("#")[0] });
      location.replace(href);
      go.addEventListener("click", function (e) { e.preventDefault(); location.href = pick(); });
    }).catch(function () {});
  }
  if (location.hash === "#random") {
    var arts = document.querySelectorAll("article.lg-vx[id]");
    if (arts.length) {
      var art = arts[Math.floor(Math.random() * arts.length)];
      history.replaceState(null, "", location.pathname + "#" + art.id);
      art.scrollIntoView();
      art.classList.add("lg-picked");
    }
  }

  // /quiz/: "Who said it?" ----------------------------------------------------------
  var quiz = document.getElementById("quiz-app");
  if (quiz) {
    var Q = JSON.parse(quiz.getAttribute("data-ui")), score = get("logia-quiz", { right: 0, played: 0 });
    var chapters = JSON.parse(quiz.getAttribute("data-chapters"));
    var round = function () {
      quiz.innerHTML = '<p class="lg-quiet">' + esc(Q.loading) + "</p>";
      var ch = chapters[Math.floor(Math.random() * chapters.length)];
      fetch("/data/" + ch + ".json").then(function (r) { return r.json(); }).then(function (d) {
        var pool = [];
        d.commentaries.forEach(function (w) {
          w.entries.forEach(function (en) {
            var words = en.excerpt.split(/\s+/).length;
            if (words >= 40 && words <= 220) pool.push({ w: w, e: en });
          });
        });
        if (!pool.length) return round();
        var p = pool[Math.floor(Math.random() * pool.length)];
        var ref = d.bookName + " " + d.chapter + ":" + p.e.start + (p.e.end !== p.e.start ? "–" + p.e.end : "");
        quiz.innerHTML = '<p class="lg-quiz-ref">' + esc(fmt(Q.on, { ref: ref })) + '</p><blockquote class="lg-quiz-text">' +
          p.e.excerpt.split(/\n\s*\n/).map(function (x) { return "<p>" + esc(x.trim()) + "</p>"; }).join("") + "</blockquote>" +
          '<p class="lg-quiz-ask">' + esc(Q.ask) + '</p><p class="lg-quiz-eras">' + Q.eras.map(function (x) {
            return '<button type="button" class="cx-chip" data-era="' + esc(x[0]) + '">' + esc(x[1]) + "</button>";
          }).join("") + '</p><p class="lg-quiz-said" role="status"></p>';
        quiz.querySelectorAll("[data-era]").forEach(function (b) {
          b.addEventListener("click", function () {
            var right = b.getAttribute("data-era") === p.w.era;
            score.played++; if (right) score.right++;
            put("logia-quiz", score);
            quiz.querySelectorAll("[data-era]").forEach(function (x) {
              x.disabled = true;
              if (x.getAttribute("data-era") === p.w.era) x.setAttribute("aria-pressed", "true");
            });
            var href = "/" + d.book.toLowerCase() + "/" + d.chapter + "/#v" + p.e.start + "-" + p.w.work_id;
            quiz.querySelector(".lg-quiz-said").innerHTML = "<b>" + esc(right ? Q.right : Q.wrong) + "</b> " +
              esc(fmt(Q.was, { name: p.w.author, dates: p.w.dates || "", title: p.w.title })) + ' <a href="' + esc(href) + '">' + esc(Q.read) + "</a>" +
              '<br><span class="lg-quiet">' + esc(fmt(Q.score, { right: score.right, played: score.played })) + '</span> <button type="button" class="button" data-next>' + esc(Q.next) + "</button>";
            quiz.querySelector("[data-next]").addEventListener("click", round);
          });
        });
      }).catch(function () { quiz.innerHTML = '<p class="lg-quiet">' + esc(Q.failed) + "</p>"; });
    };
    round();
  }
})();
