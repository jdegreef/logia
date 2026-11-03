// The chapter reader: the Bible text on the left and, beside it, the panel
// of what the church has said about the chosen verse (see chapter_page in
// scripts/build_site.py). The page carries its chapter as JSON in
// #chapter-data: the Open Word Bible text, Greek words, translation notes,
// cross-references, the commentaries on this chapter and the interface text
// in the page's language (ui). Settings come from the gear menu through
// window.LogiaPrefs (web/site.js): the translation level and how much of
// each excerpt to show; the eras shown are kept here, as logia-eras.
(function () {
  "use strict";
  var holder = document.getElementById("chapter-data");
  if (!holder) return;
  var DATA = JSON.parse(holder.textContent);
  var U = DATA.ui;
  var ERAS = DATA.eras;
  var Prefs = window.LogiaPrefs;
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (s) {
    return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  };
  var fmt = function (s, vals) { return s.replace(/\{(\w+)\}/g, function (_, k) { return vals[k] !== undefined ? vals[k] : ""; }); };

  function hiddenEras() {
    try { return JSON.parse(localStorage.getItem("logia-eras") || "[]"); } catch (e) { return []; }
  }
  var state = { verse: DATA.verses[0], tab: "comm", token: null, eras: new Set(ERAS) };
  hiddenEras().forEach(function (e) { state.eras.delete(e); });
  function level() { return Prefs ? Prefs.get("level") : "B"; }
  function fullExcerpts() { return Prefs && Prefs.get("excerpt") === "full"; }

  var works = DATA.commentaries;
  var FIRST = DATA.verses[0], LAST = DATA.verses[DATA.verses.length - 1];
  var REF = function (v) { return DATA.bookName + " " + DATA.chapter + ":" + v; };
  var recFor = function (v) { return DATA.records.filter(function (r) { return r.verses.indexOf(v) >= 0; })[0]; };
  var entriesFor = function (w, v) { return w.entries.filter(function (e) { return e.start <= v && v <= e.end; }); };

  function verseText(v) {
    var r = recFor(v), lv = level();
    if (lv === "B") return r.pieces.filter(function (p) { return p[0] === v; }).map(function (p) { return p[1]; }).join("").trim();
    return r[lv][v] || "";
  }

  function renderText() {
    var out = [], lv = level();
    DATA.records.forEach(function (r) {
      if (r.heading && r.verses[0] !== FIRST) out.push('<h2 class="cx-head">' + esc(r.heading) + "</h2>");
      r.verses.forEach(function (v) {
        var inner;
        if (lv === "B") {
          inner = r.pieces.filter(function (p) { return p[0] === v; }).map(function (p) {
            return p[2] ? '<span class="cx-w" data-tok="' + p[2].join(" ") + '">' + esc(p[1]) + "</span>" : esc(p[1]);
          }).join("");
        } else inner = esc(r[lv][v] || "");
        var has = works.some(function (w) { return entriesFor(w, v).length; });
        out.push('<span class="cx-verse' + (v === state.verse ? " cx-on" : "") + (has ? " cx-has" : "") + '" data-v="' + v +
          '" tabindex="0" role="button" aria-label="' + esc(REF(v)) + '"><span class="cx-vn">' + v + "</span>" + inner + "</span> ");
      });
    });
    $("#text").innerHTML = out.join("");
    document.querySelectorAll(".cx-levels button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.level === lv); });
    markTokens();
  }
  function markTokens() {
    document.querySelectorAll(".cx-w").forEach(function (el) {
      el.classList.toggle("cx-on", !!state.token && el.dataset.tok.split(" ").indexOf(state.token) >= 0);
    });
  }

  function renderRail() {
    var lo = 200, hi = 1950, pos = function (y) { return ((y - lo) / (hi - lo)) * 100; };
    var h = '<div class="cx-rail-line"></div>';
    [300, 600, 900, 1200, 1500, 1800].forEach(function (t) { h += '<span class="cx-tick" style="left:' + pos(t) + '%">' + t + "</span>"; });
    var last = -99, lift = false;
    works.slice().sort(function (a, b) { return a.died - b.died; }).forEach(function (w) {
      var on = entriesFor(w, state.verse).length > 0 && state.eras.has(w.era);
      var x = pos(w.died);
      lift = x - last < 2.5 ? !lift : false; last = x;
      h += '<button class="cx-dot' + (on ? "" : " cx-off") + '" style="left:' + x + "%;" + (lift ? "top:1px" : "") +
        '" data-work="' + w.work_id + '" data-name="' + esc(w.author) + '" aria-label="' + esc(w.author) + '"></button>';
    });
    $("#rail").innerHTML = h;
  }

  function renderPanel() {
    var v = state.verse;
    $("#ref").textContent = REF(v);
    $("#ph-text").textContent = verseText(v);
    $("#prev").disabled = v === FIRST; $("#next").disabled = v === LAST;
    var voices = works.filter(function (w) { return entriesFor(w, v).length; });
    var eras = new Set(voices.map(function (w) { return w.era; }));
    $("#summary").textContent = voices.length
      ? fmt(voices.length === 1 ? U.summary_one : U.summary, {
          n: voices.length, eras: eras.size,
          first: voices[0].short_name, last: voices[voices.length - 1].short_name })
      : U.none_yet;
    var r = recFor(v);
    $("#n-comm").textContent = voices.length;
    $("#n-words").textContent = (DATA.greek[v] || []).length;
    $("#n-notes").textContent = r.decisions.length;
    $("#n-xref").textContent = (DATA.crossrefs[v] || []).length;
    document.querySelectorAll(".cx-tabs button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.tab === state.tab); });
    renderRail();
    $("#pb").innerHTML = ({ comm: commTab, words: wordsTab, notes: notesTab, xref: xrefTab })[state.tab]();
    $("#pb").scrollTop = 0;
  }

  function paras(t) { return t.split(/\n\s*\n/).map(function (p) { return "<p>" + esc(p.trim()) + "</p>"; }).join(""); }
  function commTab() {
    var v = state.verse;
    var h = '<div class="cx-chips" role="group" aria-label="' + esc(U.show_eras) + '">' + ERAS.map(function (e) {
      return '<button class="cx-chip" data-era="' + esc(e) + '" aria-pressed="' + state.eras.has(e) + '">' + esc(U.eras[e]) + "</button>";
    }).join("") + "</div>";
    var any = false;
    ERAS.forEach(function (era) {
      if (!state.eras.has(era)) return;
      var ws = works.filter(function (w) { return w.era === era && entriesFor(w, v).length; });
      if (!ws.length) return;
      any = true;
      h += '<div class="cx-era">' + esc(U.eras[era]) + "</div>";
      ws.forEach(function (w) {
        var es = entriesFor(w, v);
        var body = es.map(function (e) {
          var range = e.start === e.end ? "" : '<div class="cx-range">' + esc(fmt(U.on_verses, { a: e.start, b: e.end })) + "</div>";
          var lemma = e.heading && e.excerpt.replace(/^\s*\d+\.\s*/, "").toLowerCase().indexOf(e.heading.toLowerCase()) !== 0
            ? '<div class="cx-lemma">' + esc(e.heading) + "</div>" : "";
          return range + lemma + paras(e.excerpt);
        }).join("");
        var words = es.reduce(function (n, e) { return n + e.excerpt.split(/\s+/).length; }, 0);
        var long = words > 140 && !fullExcerpts();
        h += '<section class="cx-card" id="c-' + w.work_id + '">' +
          '<div class="cx-who"><a href="' + w.author_url + '"><b>' + esc(w.author) + "</b></a>" +
          '<span class="cx-d">' + esc(w.author_dates) + '</span><span class="cx-tag">' + esc(w.tradition) + "</span></div>" +
          '<div class="cx-work"><a href="' + w.work_url + '"><i>' + esc(w.title) + "</i></a> · " + esc(w.edition_short) + "</div>" +
          '<div class="cx-ex' + (long ? " cx-clamp" : "") + '">' + body + "</div>" +
          '<div class="cx-more">' + (long ? '<button type="button" data-expand>' + esc(fmt(U.read_all, { n: words.toLocaleString() })) + "</button>" : "") +
          '<a href="' + esc(es[0].source_url) + '" target="_blank" rel="noopener">' + esc(U.full_text) + " ↗</a></div></section>";
      });
    });
    if (!any) {
      h += '<p class="cx-empty">' + esc(works.some(function (w) { return entriesFor(w, v).length; }) ? U.none_in_eras : U.none_yet_long) + "</p>";
    }
    return h;
  }

  function wordsTab() {
    var v = state.verse, toks = DATA.greek[v] || [];
    var h = '<div class="cx-greek" lang="grc">' + toks.map(function (t) {
      return '<span class="cx-g' + (t.id === state.token ? " cx-on" : "") + '" data-gid="' + t.id + '" role="button" tabindex="0">' +
        esc(t.text) + "</span>" + esc((t.after || " ").replace(/(\S)$/, "$1 "));
    }).join("") + "</div>";
    var t = toks.filter(function (x) { return x.id === state.token; })[0];
    if (!t) return h + '<p class="cx-empty">' + esc(U.tap_word) + "</p>";
    h += '<div class="cx-word"><div class="cx-big cx-gk" lang="grc">' + esc(t.text) + "</div><dl>" +
      "<dt>" + esc(U.lemma) + '</dt><dd class="cx-gk" lang="grc">' + esc(t.lemma) + "</dd>" +
      "<dt>" + esc(U.grammar) + "</dt><dd>" + esc(t.parse) + "</dd>" +
      "<dt>" + esc(U.gloss) + "</dt><dd>" + esc(t.gloss) + "</dd>" +
      "<dt>" + esc(U.strong) + "</dt><dd>G" + esc(t.strong) + "</dd></dl></div>";
    var decs = recFor(v).decisions.filter(function (d) { return (d.tokens || []).indexOf(t.id) >= 0; });
    if (decs.length) h += '<div class="cx-era cx-gap">' + esc(U.how_translated) + "</div>" + decs.map(noteHtml).join("");
    return h;
  }

  function noteHtml(d) {
    var kind = d.layer === "meaning" ? U.meaning
      : fmt(U.english_levels, { levels: (d.levels || []).map(function (l) { return U.levels[l]; }).join(", ") });
    return '<div class="cx-note"><h4>' + esc(d.choice) + ' <span class="cx-tag">' + esc(U.categories[d.category] || d.category) +
      '</span><span class="cx-tag">' + esc(kind) + "</span>" + (d.uncertain ? '<span class="cx-tag">' + esc(U.uncertain) + "</span>" : "") + "</h4>" +
      (d.alternatives && d.alternatives.length ? '<div class="cx-alt">' + esc(U.not_) + " " + d.alternatives.map(esc).join(" · ") + "</div>" : "") +
      "<p>" + esc(d.reason) + "</p></div>";
  }
  function notesTab() {
    var r = recFor(state.verse);
    var span = r.verses.length > 1
      ? '<div class="cx-range">' + esc(fmt(U.sentence_spans, { a: r.verses[0], b: r.verses[r.verses.length - 1] })) + "</div>" : "";
    return span + '<div class="cx-src" lang="grc">' + esc(r.greek) + '</div><div class="cx-gloss">' + esc(U.word_for_word) + " " +
      esc(r.gloss) + "</div>" + r.decisions.map(noteHtml).join("");
  }
  function xrefTab() {
    var xs = DATA.crossrefs[state.verse] || [];
    if (!xs.length) return '<p class="cx-empty">' + esc(U.no_xrefs) + "</p>";
    return '<div class="cx-xr">' + xs.map(function (x) {
      var p = x.split("."), key = p[0] + "." + p[1];
      var verse = (p[2] || "").split("-")[0];
      var href = DATA.available.indexOf(key) >= 0
        ? "/" + p[0].toLowerCase() + "/" + p[1] + "/" + (verse ? "#v" + verse : "")
        : DATA.owb_site + "/" + p[0].toLowerCase() + "/" + p[1] + "/";
      var ext = href.indexOf("http") === 0 ? ' target="_blank" rel="noopener"' : "";
      return '<a href="' + href + '"' + ext + ">" + esc((DATA.books[p[0]] || p[0]) + " " + p[1] + (p[2] ? ":" + p[2] : "")) + "</a>";
    }).join("") + '</div><p class="cx-hint">' + esc(U.xref_credit) + "</p>";
  }

  function go(v, opts) {
    opts = opts || {};
    state.verse = Math.max(FIRST, Math.min(LAST, v));
    if (!opts.keepToken) state.token = null;
    document.querySelectorAll(".cx-verse").forEach(function (el) { el.classList.toggle("cx-on", +el.dataset.v === state.verse); });
    markTokens();
    renderPanel();
    if (location.hash !== "#v" + state.verse) history.replaceState(null, "", "#v" + state.verse);
  }

  $("#text").addEventListener("click", function (e) {
    var w = e.target.closest(".cx-w"), vs = e.target.closest(".cx-verse");
    if (!vs) return;
    var v = +vs.dataset.v;
    if (w && v === state.verse) {
      var ids = w.dataset.tok.split(" ");
      state.token = ids[ids.length - 1];
      state.tab = "words";
      go(v, { keepToken: true });
    } else go(v);
    $("#panel").classList.remove("cx-min");
  });
  $("#text").addEventListener("keydown", function (e) {
    var vs = e.target.closest(".cx-verse");
    if (vs && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); go(+vs.dataset.v); }
  });
  document.querySelector(".cx-levels").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    if (Prefs) Prefs.set("level", b.dataset.level);   // fires logia:prefs, which re-renders
  });
  document.addEventListener("logia:prefs", function () { state.token = null; renderText(); renderPanel(); });
  document.querySelector(".cx-tabs").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    state.tab = b.dataset.tab; renderPanel();
  });
  $("#grab").addEventListener("click", function () { $("#panel").classList.toggle("cx-min"); });
  if (window.innerWidth <= 880 && !location.hash) $("#panel").classList.add("cx-min");
  $("#prev").addEventListener("click", function () { go(state.verse - 1); });
  $("#next").addEventListener("click", function () { go(state.verse + 1); });
  $("#pb").addEventListener("click", function (e) {
    var chip = e.target.closest(".cx-chip");
    if (chip) {
      var era = chip.dataset.era;
      if (state.eras.has(era)) state.eras.delete(era); else state.eras.add(era);
      try {
        localStorage.setItem("logia-eras", JSON.stringify(ERAS.filter(function (x) { return !state.eras.has(x); })));
      } catch (err) { /* storage blocked: the choice lasts for this page */ }
      renderPanel(); return;
    }
    var ex = e.target.closest("[data-expand]");
    if (ex) { ex.closest(".cx-card").querySelector(".cx-ex").classList.remove("cx-clamp"); ex.remove(); return; }
    var g = e.target.closest(".cx-g");
    if (g) { state.token = g.dataset.gid; markTokens(); renderPanel(); }
  });
  $("#pb").addEventListener("keydown", function (e) {
    var g = e.target.closest(".cx-g");
    if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); state.token = g.dataset.gid; markTokens(); renderPanel(); }
  });
  $("#rail").addEventListener("click", function (e) {
    var d = e.target.closest(".cx-dot"); if (!d || d.classList.contains("cx-off")) return;
    if (state.tab !== "comm") { state.tab = "comm"; renderPanel(); }
    var card = document.getElementById("c-" + d.dataset.work);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "start" });
      card.classList.remove("cx-flash"); void card.offsetWidth; card.classList.add("cx-flash");
    }
  });
  window.addEventListener("hashchange", function () {
    var m = location.hash.match(/^#v(\d+)$/);
    if (m && +m[1] !== state.verse) go(+m[1]);
  });

  var m0 = location.hash.match(/^#v(\d+)$/);
  if (m0) state.verse = Math.max(FIRST, Math.min(LAST, +m0[1]));
  else {
    // With no verse asked for, open at the first verse that has commentary.
    var firstWith = DATA.verses.filter(function (v) { return works.some(function (w) { return entriesFor(w, v).length; }); })[0];
    if (firstWith) state.verse = firstWith;
  }
  renderText(); go(state.verse);
})();
