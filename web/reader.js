// The chapter reader: the Bible text on the left and, beside it, the panel
// of what the church has said about the chosen verse (see chapter_page in
// scripts/build_site.py). The page carries its chapter as JSON in
// #chapter-data: the Open Word Bible text, its Greek or Hebrew words,
// translation notes, cross-references, the commentaries on this chapter and
// the interface text in the page's language (ui). Settings come from the gear
// menu through window.LogiaPrefs (web/site.js): the translation level, the
// Open Word Bible's wording settings and how much of each excerpt to show;
// the eras shown are kept here, as logia-eras.
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
  var state = { verse: DATA.verses[0], tab: "comm", token: null, eras: new Set(ERAS), marks: null, counts: {}, note: null, open: {} };
  var Account = window.LogiaAccount;
  var CHAPTER = DATA.book + "." + DATA.chapter;
  // A comment's key: <work>.<BOOK>.<chapter>.<verse> (backend/logia/ in open-word-bible).
  var keyOf = function (w, v) { return w.work_id + "." + CHAPTER + "." + v; };
  var ICON = {
    like: '<svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2 0 3.6 1.1 4.4 2.6.8-1.5 2.4-2.6 4.4-2.6 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z"/></svg>',
    save: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></svg>',
    share: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V3.5M7.5 8 12 3.5 16.5 8M5 12.5v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>'
  };
  ICON.chevron = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
  ICON.flag = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 21V4m0 0h11l-2 4 2 4H5"/></svg>';
  ICON.copy = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg>';
  ICON.columns = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/></svg>';
  hiddenEras().forEach(function (e) { state.eras.delete(e); });
  // Whether a voice's card is open on the chosen verse (see commTab).
  // A voice with nothing new since the verse before starts closed, while
  // another voice has something new.
  function isOpen(work) {
    if (work in state.open) return state.open[work];
    if (fullExcerpts()) return true;
    var shown = works.filter(function (w) { return state.eras.has(w.era) && entriesFor(w, state.verse).length; });
    var fresh = shown.filter(function (w) { return !alsoBefore(w, state.verse); });
    if (fresh.length && fresh.length < shown.length && alsoBefore(byId(work), state.verse)) return false;
    return (fresh.length || shown.length) <= 2;
  }
  var byId = function (id) { return works.filter(function (w) { return w.work_id === id; })[0]; };
  // The verse before this one in the text (past any the Bible leaves out).
  function before(v) { var i = DATA.verses.indexOf(v); return i > 0 ? DATA.verses[i - 1] : null; }
  // Whether everything a voice says on this verse was on the verse before:
  // it comments on a passage the reader is stepping through (Calvin on 1:1-17).
  function alsoBefore(w, v) {
    var p = before(v), es = w ? entriesFor(w, v) : [];
    return p !== null && es.length > 0 && es.every(function (e) { return e.start <= p; });
  }
  function level() { return Prefs ? Prefs.get("level") : "B"; }

  // The Open Word Bible writes its reader settings into the text as spans,
  // {{gender:all people|men}}, and its poetry lines as "\q" (owb/markup.py).
  // DATA.wording lists each setting's values in the order of its options;
  // the menu's choice picks the option, and a missing one keeps the default
  // (the first, or "He" for pronouns for God).
  var SPAN = /\{\{([a-z_]+):([^{}]*)\}\}/g;
  var LINES = / ?\\q ?/g, LINE = / ?\\q ?/;
  var DEFAULT_OPTION = { deity_pronoun: 1 };
  function wording(text) {
    return String(text || "").replace(SPAN, function (_, name, opts) {
      var options = opts.split("|"), values = DATA.wording[name];
      var i = values && Prefs ? values.indexOf(Prefs.get(name)) : -1;
      if (i < 0) i = DEFAULT_OPTION[name] || 0;
      return i < options.length ? options[i] : options[0];
    });
  }
  // On one line (the panel, notes): a poetic line break reads as a space.
  function flat(text) { return wording(text).replace(LINES, " "); }
  // In the passage: each poetic line on its own line.
  function lined(text) { return esc(wording(text)).replace(LINES, '<br class="cx-q">'); }
  var HEBREW = DATA.source === "hbo";
  var SOURCE_LANG = HEBREW ? "hbo" : "grc";
  var DIR = HEBREW ? ' dir="rtl"' : "";
  function fullExcerpts() { return Prefs && Prefs.get("excerpt") === "full"; }

  var works = DATA.commentaries;
  // A chapter with no commentary yet opens on its translation notes, with
  // the commentary tab last; the timeline and the era filter stay hidden.
  var EMPTY = !works.length;
  var FIRST = DATA.verses[0], LAST = DATA.verses[DATA.verses.length - 1];
  var REF = function (v) { return DATA.bookName + " " + DATA.chapter + ":" + v; };
  // A verse of two sentences is in two records (one per sentence).
  var recsFor = function (v) { return DATA.records.filter(function (r) { return r.verses.indexOf(v) >= 0; }); };
  var entriesFor = function (w, v) { return w.entries.filter(function (e) { return e.start <= v && v <= e.end; }); };

  // A verse of two sentences is in two records: its text is all of them.
  function verseText(v) {
    var lv = level();
    return recsFor(v).map(function (r) {
      if (lv === "B") return flat(r.pieces.filter(function (p) { return p[0] === v; }).map(function (p) { return p[1]; }).join("")).trim();
      return flat(r[lv][v] || "").trim();
    }).join(" ");
  }

  function renderText() {
    var out = [], lv = level(), seen = {};
    DATA.records.forEach(function (r) {
      if (r.heading && r.verses[0] !== FIRST) out.push('<h2 class="cx-head">' + esc(flat(r.heading)) + "</h2>");
      // A sentence set as poetry at any level starts each verse on its own line.
      var poem = ["L", "R"].some(function (l) { return Object.keys(r[l]).some(function (k) { return LINE.test(r[l][k]); }); }) ||
        r.pieces.some(function (p) { return LINE.test(p[1]); });
      r.verses.forEach(function (v) {
        var inner;
        if (lv === "B") {
          inner = r.pieces.filter(function (p) { return p[0] === v; }).map(function (p) {
            return p[2] ? '<span class="cx-w" data-tok="' + p[2].join(" ") + '">' + lined(p[1]) + "</span>" : lined(p[1]);
          }).join("");
        } else inner = lined(r[lv][v] || "");
        // The verse's next sentence, in a later record: it carries on the
        // verse already begun, without its number again.
        if (seen[v]) {
          out.push('<span class="cx-verse cx-cont' + (v === state.verse ? " cx-on" : "") + (poem ? " cx-poem" : "") + '" data-v="' + v + '">' + inner + "</span> ");
          return;
        }
        seen[v] = true;
        // Verses the Open Word Bible leaves out, just before the verse after them.
        if ((DATA.gaps || {})[v]) out.push(DATA.gaps[v]);
        // The gold count beside a verse number: how many voices comment on it.
        var n = works.filter(function (w) { return entriesFor(w, v).length; }).length;
        var label = n ? fmt(n === 1 ? U.verse_voices_one : U.verse_voices, { ref: REF(v), n: n }) : REF(v);
        out.push('<span class="cx-verse' + (v === state.verse ? " cx-on" : "") + (n ? " cx-has" : "") + (poem ? " cx-poem" : "") + '" data-v="' + v +
          '" tabindex="0" role="button" aria-label="' + esc(label) + '" title="' + esc(heatTitle(v)) + '"><span class="cx-vn">' + v + "</span>" +
          inner + "</span> ");
      });
    });
    $("#text").innerHTML = out.join("") + '<div class="cx-gutter" id="gutter"></div>';
    $("#text").classList.add("cx-ready");
    drawGutter();
    document.querySelectorAll(".cx-levels button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.level === lv); });
    markTokens();
  }
  // How much is written on a verse: every voice's excerpts that cover it.
  function wordsOn(v) {
    return works.reduce(function (n, w) {
      return n + entriesFor(w, v).reduce(function (m, e) { return m + (e.words || 0); }, 0);
    }, 0);
  }
  function heatTitle(v) {
    var n = works.filter(function (w) { return entriesFor(w, v).length; }).length;
    return n ? fmt(n === 1 ? U.heat_title_one : U.heat_title, { ref: REF(v), n: n, words: wordsOn(v).toLocaleString() }) : REF(v);
  }
  // Beside the text, a gold line darker where more is written on a verse
  // and, further out, a bracket for each comment on a passage of three
  // verses or more (Calvin, Henry and Ryle on Matthew 1:1-17); a bracket
  // goes to its first verse. Drawn from where the verses fall on the page,
  // so again when the text reflows.
  function drawGutter() {
    var g = $("#gutter"), box = $("#text");
    if (!g || EMPTY) return;
    var top0 = box.getBoundingClientRect().top;
    var span = function (a, b) {
      var first = box.querySelector('.cx-verse[data-v="' + a + '"]');
      var lasts = box.querySelectorAll('.cx-verse[data-v="' + b + '"]');
      if (!first || !lasts.length) return null;
      var r1 = first.getClientRects(), r2 = lasts[lasts.length - 1].getClientRects();
      if (!r1.length || !r2.length) return null;
      return { top: r1[0].top - top0 + 3, bottom: r2[r2.length - 1].bottom - top0 - 3 };
    };
    var max = Math.max.apply(null, DATA.verses.map(wordsOn).concat([1]));
    var h = "";
    DATA.verses.forEach(function (v) {
      var words = wordsOn(v), s = span(v, v);
      if (!words || !s) return;
      var r = words / max, lvl = r > 0.66 ? 3 : r > 0.33 ? 2 : 1;
      h += '<i class="cx-heat cx-heat' + lvl + '" style="top:' + s.top + "px;height:" + Math.max(6, s.bottom - s.top) + 'px"></i>';
    });
    // One bracket for each passage, naming every voice that comments on it.
    var spans = {};
    works.forEach(function (w) {
      w.entries.forEach(function (e) {
        if (e.end - e.start < 2) return;
        var k = e.start + "-" + e.end;
        spans[k] = spans[k] || { a: e.start, b: e.end, names: [] };
        var nm = w.short_name || w.author;
        if (spans[k].names.indexOf(nm) < 0) spans[k].names.push(nm);
      });
    });
    var lanes = [];
    Object.keys(spans).map(function (k) { return spans[k]; })
      .sort(function (x, y) { return x.a - y.a || (y.b - y.a) - (x.b - x.a); })
      .forEach(function (p) {
        var lane = 0;
        while (lane < lanes.length && lanes[lane] >= p.a) lane++;
        if (lane > 2) return;
        lanes[lane] = p.b;
        var s = span(p.a, p.b);
        if (!s) return;
        var label = fmt(U.passage, { names: p.names.join(", "), a: DATA.chapter + ":" + p.a, b: p.b });
        h += '<button type="button" class="cx-brk cx-brk' + lane + '" data-v="' + p.a + '" style="top:' + s.top + "px;height:" +
          (s.bottom - s.top) + 'px" title="' + esc(label) + '" aria-label="' + esc(label) + '"></button>';
      });
    g.innerHTML = h;
  }
  if (window.ResizeObserver) {
    var lastW = 0;
    new ResizeObserver(function (rs) {
      var w = Math.round(rs[0].contentRect.width);
      if (w !== lastW) { lastW = w; drawGutter(); }
    }).observe($("#text"));
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { drawGutter(); });
  function markTokens() {
    document.querySelectorAll(".cx-w").forEach(function (el) {
      el.classList.toggle("cx-on", !!state.token && el.dataset.tok.split(" ").indexOf(state.token) >= 0);
    });
  }

  // The commentators on a line of centuries, each a labelled pill at the year
  // they died: tap one to open what they say. Pills that would overlap stack
  // in lanes; a voice with nothing on this verse is faded.
  function renderRail() {
    var lo = 200, hi = 1950, pos = function (y) { return ((y - lo) / (hi - lo)) * 100; };
    var width = $("#rail").offsetWidth || 480, PILL = 40;
    var h = "";
    [300, 600, 900, 1200, 1500, 1800].forEach(function (t) { h += '<span class="cx-tick" style="left:' + pos(t) + '%">' + t + "</span>"; });
    var lanes = [];
    works.slice().sort(function (a, b) { return a.died - b.died; }).forEach(function (w) {
      var on = entriesFor(w, state.verse).length > 0 && state.eras.has(w.era);
      var x = pos(w.died), px = x / 100 * width;
      var lane = 0;
      while (lanes[lane] !== undefined && px - lanes[lane] < PILL + 3) lane++;
      lanes[lane] = px;
      var label = (w.short_name || w.author).slice(0, 3);
      h += '<button type="button" class="cx-dot cx-lane' + Math.min(lane, 2) + (on ? "" : " cx-off") +
        (on && state.open[w.work_id] ? " cx-cur" : "") + '" style="left:' + x + '%" data-work="' + w.work_id +
        '" title="' + esc(w.author + ", " + w.author_dates) + '" aria-label="' + esc(w.author) + '"' + (on ? "" : " disabled") + ">" +
        esc(label) + "</button>";
    });
    $("#rail").style.setProperty("--lanes", Math.min(lanes.length, 3));
    $("#rail").innerHTML = '<div class="cx-rail-line"></div>' + h;
  }
  window.addEventListener("resize", function () { if ($("#rail").offsetWidth) renderRail(); });

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
      : EMPTY ? fmt(U.none_book, { book: DATA.bookName }) : U.none_yet;
    $("#rail").hidden = EMPTY;
    // A verse with commentary has a page of its own (verse_page in scripts/build_site.py).
    $("#vpage").hidden = !voices.length;
    if (voices.length) {
      $("#vpage").href = "/" + DATA.book.toLowerCase() + "/" + DATA.chapter + "/" + v + "/";
      $("#vpage").textContent = fmt(U.verse_page, { ref: REF(v) }) + " →";
    }
    var rs = recsFor(v);
    $("#n-comm").textContent = voices.length;
    $("#n-words").textContent = DATA.wordCounts[v] || 0;
    $("#n-notes").textContent = rs.reduce(function (sum, r) { return sum + r.notes; }, 0);
    $("#n-xref").textContent = (DATA.crossrefs[v] || []).length;
    document.querySelectorAll(".cx-tabs button").forEach(function (b) { b.setAttribute("aria-selected", b.dataset.tab === state.tab); });
    renderRail();
    var keep = $("#pb").scrollTop;
    $("#pb").innerHTML = state.tab === "comm" && !COMM ? waiting(commFailed, "comm")
      : needsPanel() && !PANEL ? panelWaiting()
      : ({ comm: commTab, words: wordsTab, notes: notesTab, xref: xrefTab })[state.tab]();
    $("#pb").scrollTop = state.keepScroll ? keep : 0;
    state.keepScroll = false;
  }
  // The words and notes tabs read the chapter's panel file (DATA.panel:
  // /panel/<BOOK>.<chapter>.json, see panel_file in scripts/build_site.py),
  // fetched the first time one of them is opened.
  var PANEL = null, panelLoad = null, panelFailed = false;
  function needsPanel() { return state.tab === "words" || state.tab === "notes"; }
  function loadPanel() {
    if (!panelLoad) {
      panelFailed = false;
      panelLoad = fetch(DATA.panel).then(function (res) {
        if (!res.ok) throw new Error(res.status);
        return res.json();
      }).then(function (p) { PANEL = p; refresh(); }, function () {
        panelLoad = null; panelFailed = true; refresh();
      });
    }
    return panelLoad;
  }
  function waiting(failed, what) {
    if (failed) {
      return '<p class="cx-empty">' + esc(U.panel_failed) + ' <button type="button" class="lg-linkish" data-retry="' + what + '">' +
        esc(U.try_again) + "</button></p>";
    }
    return '<p class="cx-empty" role="status">' + esc(U.loading) + "</p>";
  }
  function panelWaiting() {
    if (!panelFailed) loadPanel();
    return waiting(panelFailed, "panel");
  }

  // The commentary's text and the excerpts elsewhere that cite this
  // chapter (DATA.comm: /comm/<BOOK>.<chapter>.json, see comm_file in
  // scripts/build_site.py), preloaded by the page's head and read at once.
  // Until it arrives, works holds the page's index: who comments on which
  // verses, enough for the timeline, the summary and the verse numbers.
  var COMM = DATA.comm ? null : { commentaries: [], citedBy: {} }, commLoad = null, commFailed = false, pendingCard = null;
  DATA.citedBy = {};
  function loadComm() {
    if (COMM || commLoad) return;
    commFailed = false;
    commLoad = fetch(DATA.comm).then(function (res) {
      if (!res.ok) throw new Error(res.status);
      return res.json();
    }).then(function (c) {
      COMM = c; works = c.commentaries; DATA.citedBy = c.citedBy;
      commLoad = null; refresh();
      if (pendingCard) { var card = pendingCard; pendingCard = null; showCard(card); }
    }, function () { commLoad = null; commFailed = true; refresh(); });
  }
  var notesOf = function (r) { return PANEL.records[r.id]; };

  // Re-render the panel where the reader is, after likes or saves arrive.
  function refresh() { state.keepScroll = true; renderPanel(); }

  // Paragraphs of an excerpt already made into HTML (by linked()).
  function paras(h) { return h.split(/\n\s*\n/).map(function (p) { return "<p>" + p.trim() + "</p>"; }).join(""); }
  // An excerpt's text with the Scripture it cites made into links
  // (library/citations, docs/references.md).
  // In a Catena excerpt, the name that opens each quotation (speakers, from
  // catena_speakers in scripts/build_site.py) is set apart as it is printed.
  function linked(text, cites, speakers) {
    var h = "", pos = 0;
    (speakers || []).forEach(function (s) {
      cites = (cites || []).filter(function (c) { return c.at + c.text.length <= s.at || c.at >= s.at + s.len; });
    });
    var marks = (cites || []).concat((speakers || []).map(function (s) { return { at: s.at, len: s.len, who: s.who }; }));
    marks.sort(function (a, b) { return a.at - b.at; }).forEach(function (c) {
      if (c.at < pos) return;
      if (c.who) {
        var name = (U.fathers || {})[c.who] || "";
        h += esc(text.slice(pos, c.at)) + '<span class="cx-speaker" title="' + esc(name) + '">' + esc(text.slice(c.at, c.at + c.len)) + "</span>";
        pos = c.at + c.len;
        return;
      }
      var same = cites.filter(function (x) { return x.at === c.at; }).map(function (x) { return x.label; }).join(", ");
      var words = esc(text.slice(c.at, c.at + c.text.length));
      var ext = c.href && c.href.indexOf("http") === 0 ? ' target="_blank" rel="noopener"' : "";
      h += esc(text.slice(pos, c.at)) + (c.href
        ? '<a class="cx-cite" href="' + esc(c.href) + '"' + ext + ' title="' + esc(same) + '">' + words + "</a>"
        : '<span class="cx-cite" title="' + esc(same) + '">' + words + "</span>");
      pos = c.at + c.text.length;
    });
    return h + esc(text.slice(pos));
  }
  // "Homily 2, section 8" from a work's divisions and an excerpt's locus.
  function locusLabel(w, locus) {
    if (!locus || !Array.isArray(w.divisions)) return "";
    return locus.split(".").map(function (n, i) {
      return (i ? w.divisions[i].toLowerCase() : w.divisions[i]) + " " + n;
    }).join(", ");
  }
  // The Catena's quotations, both ways: under a Catena excerpt, the Father's
  // passage each comes from; under that passage, that the Catena quotes it.
  function traced(e) {
    var unchecked = function (q) {
      return q.status === "reviewed" ? "" : ' <span title="' + esc(U.unchecked_title) + '">' + esc(U.unchecked) + "</span>";
    };
    var rows = (e.quotes || []).map(function (q) {
      return "<div><b>" + esc(q.label) + "</b> " + esc(q.author) + ", " + esc(q.where) +
        (q.exact ? "" : " " + esc(U.not_pinned)) + ": " +
        (q.href ? '<a href="' + esc(q.href) + '">' + esc(fmt(U.read_it_on, { ref: q.ref })) + "</a> · " : "") +
        '<a href="' + esc(q.url) + '" target="_blank" rel="noopener">' + esc(U.full_text_short) + " ↗</a>" + unchecked(q) + "</div>";
    }).concat((e.quotedIn || []).map(function (q) {
      var label = esc(fmt(U.quoted_by, { name: q.author, title: q.title, ref: q.ref }));
      return "<div>" + (q.href ? '<a href="' + esc(q.href) + '">' + label + "</a>" : label) + unchecked(q) + "</div>";
    }));
    return rows.length ? '<div class="cx-qs">' + rows.join("") + "</div>" : "";
  }
  // Whole homilies and tractates on this verse: the works' second structure,
  // by the verse they expound (library/texts), even where Logia has no excerpt.
  function wholeTexts(v) {
    var rows = DATA.wholeTexts[v] || [];
    if (!rows.length) return "";
    return '<p class="cx-whole">' + esc(U.whole_texts) + ": " + rows.map(function (r) {
      return '<a href="' + esc(r.href) + '">' + esc(r.short) + ", " + esc(r.where) + "</a>";
    }).join(" · ") + "</p>";
  }
  // Excerpts on other verses that refer to this one (the other way of a citation).
  function elsewhere(v) {
    var rows = (DATA.citedBy[v] || []).filter(function (r) { return state.eras.has(r.era); });
    if (!rows.length) return "";
    return '<section class="cx-elsewhere"><div class="cx-era">' + esc(U.elsewhere) + "</div>" +
      '<p class="cx-hint">' + esc(fmt(U.elsewhere_hint, { ref: REF(v) })) + "</p>" + rows.map(function (r) {
        var i = r.snippet.indexOf(r.text);
        var q = i < 0 ? esc(r.snippet)
          : esc(r.snippet.slice(0, i)) + "<mark>" + esc(r.text) + "</mark>" + esc(r.snippet.slice(i + r.text.length));
        return '<div class="cx-cb"><div class="cx-who"><b>' + esc(r.author) + '</b><span class="cx-d">' + esc(r.author_dates) +
          '</span><span class="cx-tag">' + esc(r.tradition) + "</span></div><q>" + q + '</q><div><a href="' + esc(r.href) + '">' +
          esc(fmt(U.read_it_on, { ref: r.ref })) + "</a></div></div>";
      }).join("") + "</section>";
  }
  // A voice's excerpts on a verse: where each sits, its lemma, its text.
  function excerptsHtml(w, es) {
    return es.map(function (e) {
      var where = [e.start === e.end ? "" : fmt(U.on_verses, { a: e.start, b: e.end }), locusLabel(w, e.locus)]
        .filter(Boolean).join(" · ");
      var range = where ? '<div class="cx-range">' + esc(where) + "</div>" : "";
      var lemma = e.heading && e.excerpt.replace(/^\s*\d+\.\s*/, "").toLowerCase().indexOf(e.heading.toLowerCase()) !== 0
        ? '<div class="cx-lemma">' + esc(e.heading) + "</div>" : "";
      return range + lemma + paras(linked(e.excerpt, e.cites, e.speakers)) + traced(e);
    }).join("");
  }
  // Under a voice's name: how much it says here and where in the work, and
  // for a Catena, the Fathers it quotes.
  function facts(w, es, words) {
    var bits = [fmt(es.length === 1 ? U.facts_one : U.facts, {
      n: es.length, words: words.toLocaleString(), min: Math.max(1, Math.round(words / 230)) })];
    var firsts = es.map(function (e) { return e.locus ? +e.locus.split(".")[0] : NaN; }).filter(function (n) { return !isNaN(n); });
    if (firsts.length && Array.isArray(w.divisions) && w.divisions.length) {
      var a = Math.min.apply(null, firsts), b = Math.max.apply(null, firsts);
      bits.push(fmt(a === b ? U.facts_where : U.facts_where_range, { div: w.divisions[0], a: a, b: b }));
    }
    var who = [];
    es.forEach(function (e) { (e.speakers || []).forEach(function (s) { if (who.indexOf(s.who) < 0) who.push(s.who); }); });
    var names = who.map(function (k) { return (U.fathers || {})[k]; }).filter(Boolean);
    var quoting = names.length ? '<div class="cx-quoting">' + esc(fmt(U.quoting, { names: names.join(", ") })) + "</div>" : "";
    return '<div class="cx-facts">' + esc(bits.join(" · ")) + "</div>" + quoting;
  }
  function commTab() {
    var v = state.verse;
    var onVerse = works.some(function (w) { return entriesFor(w, v).length; });
    var h = !onVerse ? "" : '<div class="cx-chips" role="group" aria-label="' + esc(U.show_eras) + '">' + ERAS.map(function (e) {
      return '<button class="cx-chip" data-era="' + esc(e) + '" aria-pressed="' + state.eras.has(e) + '">' + esc(U.eras[e]) + "</button>";
    }).join("") + "</div>";
    var shown = works.filter(function (w) { return state.eras.has(w.era) && entriesFor(w, v).length; });
    if (COMM && shown.length > 1) {
      h += '<button type="button" class="cx-compare-btn" data-compare>' + ICON.columns + esc(U.compare) + "</button>";
    }
    var shownOn = shown, fresh = shown.filter(function (w) { return !alsoBefore(w, v); });
    var any = false;
    ERAS.forEach(function (era) {
      if (!state.eras.has(era)) return;
      var ws = works.filter(function (w) { return w.era === era && entriesFor(w, v).length; });
      if (!ws.length) return;
      any = true;
      h += '<div class="cx-era">' + esc(U.eras[era]) + "</div>";
      ws.forEach(function (w) {
        var es = entriesFor(w, v);
        var body = excerptsHtml(w, es);
        var words = es.reduce(function (n, e) { return n + e.excerpt.split(/\s+/).length; }, 0);
        var long = words > 140 && !fullExcerpts();
        // A voice opens as two lines of its excerpt; the reader opens the ones
        // they want. With one or two voices, or "In full" chosen, all are open.
        var open = isOpen(w.work_id);
        var peek = es[0].excerpt.split(/\n\s*\n/)[0].split(/\s+/).slice(0, 48).join(" ");
        var badge = fresh.length && fresh.length < shownOn.length
          ? (alsoBefore(w, v)
            ? '<span class="cx-also" title="' + esc(fmt(U.also_on_title, { ref: REF(before(v)) })) + '">' + esc(fmt(U.also_on, { ref: REF(before(v)) })) + "</span>"
            : '<span class="cx-new">' + esc(U.new_here) + "</span>")
          : "";
        h += '<section class="cx-card' + (open ? "" : " cx-shut") + '" id="c-' + w.work_id + '">' +
          '<div class="cx-who"><a href="' + w.author_url + '"><b>' + esc(w.author) + "</b></a>" +
          '<span class="cx-d">' + esc(w.author_dates) + '</span><span class="cx-tag">' + esc(w.tradition) + "</span>" + badge +
          '<button type="button" class="cx-toggle" data-toggle="' + w.work_id + '" aria-expanded="' + open + '" aria-controls="cb-' + w.work_id +
          '" aria-label="' + esc(fmt(open ? U.hide_voice : U.show_voice, { name: w.author })) + '">' + ICON.chevron + "</button></div>" +
          facts(w, es, words) +
          (open ? "" : '<button type="button" class="cx-peek" data-toggle="' + w.work_id + '">' + esc(peek) + "</button>") +
          '<div class="cx-body" id="cb-' + w.work_id + '"' + (open ? "" : " hidden") + ">" +
          '<div class="cx-work"><a href="' + w.work_url + '"><i>' + esc(w.title) + "</i></a> · " + esc(w.edition_short) + "</div>" +
          '<div class="cx-ex' + (long ? " cx-clamp" : "") + '">' + body + "</div>" +
          '<div class="cx-more">' + (long ? '<button type="button" data-expand>' + esc(fmt(U.read_all, { n: words.toLocaleString() })) + "</button>" : "") +
          (es[0].inFull ? '<a href="' + esc(es[0].inFull) + '">' +
            esc(fmt(U.read_in_full, { where: locusLabel(w, es[0].locus.split(".")[0]) })) + "</a>" : "") +
          '<a href="' + esc(es[0].source_url) + '" target="_blank" rel="noopener">' + esc(U.full_text) + " ↗</a></div>" +
          actions(w, v) + "</div></section>";
      });
    });
    if (!any) {
      h += '<p class="cx-empty' + (onVerse ? "" : " cx-empty-box") + '">' + esc(onVerse ? U.none_in_eras : EMPTY ? fmt(U.none_book_long, { book: DATA.bookName }) : U.none_yet_long) + "</p>";
    }
    return h + related(v) + wholeTexts(v) + elsewhere(v);
  }
  // Where no one comments on a verse: the verses it cross-references that
  // have commentary, with one voice's first words on each.
  function related(v) {
    var rows = (DATA.related || {})[v] || [];
    if (!rows.length) return "";
    return '<section class="cx-related"><div class="cx-era">' + esc(U.related) + "</div>" + rows.map(function (r) {
      return '<div class="cx-rel"><a class="cx-rel-verse" href="' + esc(r.href) + '"><span class="cx-rel-ref">' + esc(r.ref) +
        '</span><span class="cx-vc">' + r.n + "</span><span class=\"cx-rel-text\">" + esc(r.text) + "</span></a>" +
        '<div class="cx-who"><b>' + esc(r.author) + '</b><span class="cx-d">' + esc(U.eras[r.era]) + "</span></div>" +
        '<p class="cx-rel-snip">' + esc(r.snippet) + '</p><a class="cx-rel-all" href="' + esc(r.href) + '">' +
        esc(fmt(U.related_all, { n: r.n, ref: r.ref })) + " \u2192</a></div>";
    }).join("") + "</section>";
  }

  // Like, save and share under a card. Likes and saves need an account
  // (web/account.js); sharing does not.
  function actions(w, v) {
    var key = keyOf(w, v);
    var liked = !!(state.marks && state.marks.liked[key]);
    var isSaved = !!(state.marks && state.marks.saved[key]);
    // The public counts are cached for a minute, so a like of the reader's
    // own may be newer than them: it always counts.
    var n = Math.max(state.counts[key] || 0, liked ? 1 : 0);
    var note = state.note && state.note.key === key
      ? '<p class="cx-act-note" role="status">' + state.note.html + "</p>" : "";
    return '<div class="cx-actions" data-key="' + key + '" data-work="' + w.work_id + '">' +
      '<button type="button" class="cx-act cx-like" data-act="like" aria-pressed="' + liked + '" aria-label="' +
      esc(liked ? U.unlike : U.like) + '" title="' + esc(liked ? U.unlike : U.like) + '">' + ICON.like + '<span class="cx-count">' + (n ? n : "") + "</span>" +
      '<span class="cx-act-label">' + esc(liked ? U.liked : U.like) + "</span></button>" +
      '<button type="button" class="cx-act cx-save" data-act="save" aria-pressed="' + isSaved + '" title="' + esc(isSaved ? U.saved : U.save) + '">' + ICON.save +
      '<span class="cx-act-label">' + esc(isSaved ? U.saved : U.save) + "</span></button>" +
      '<button type="button" class="cx-act" data-act="cite" title="' + esc(U.copy_cite) + '">' + ICON.copy + '<span class="cx-act-label">' + esc(U.copy_cite) +
      "</span></button>" +
      '<button type="button" class="cx-act" data-act="share" title="' + esc(U.share) + '">' + ICON.share + '<span class="cx-act-label">' + esc(U.share) +
      "</span></button>" +
      '<a class="cx-act" href="' + esc(reportUrl(w, v)) + '" target="_blank" rel="noopener" title="' + esc(U.report) + '">' + ICON.flag +
      '<span class="cx-act-label">' + esc(U.report) + "</span></a></div>" + note;
  }

  // "Report a mistake": a new issue on GitHub, filled in with which excerpt,
  // where it was copied from and this page, so a misreading can be checked
  // against the printed page and fixed in library/corrections/.
  function reportUrl(w, v) {
    var es = entriesFor(w, v);
    var page = location.origin + location.pathname + "#v" + v + "-" + w.work_id;
    var title = fmt(U.report_title, { name: w.author, ref: REF(v) });
    var body = fmt(U.report_body, {
      ids: es.map(function (e) { return e.id; }).join(", "), title: w.title, edition: w.edition_short, ref: REF(v),
      sources: es.map(function (e) { return e.source_url; }).filter(function (u, i, all) { return u && all.indexOf(u) === i; }).join(" "), url: page });
    return DATA.issues + "?title=" + encodeURIComponent(title) + "&body=" + encodeURIComponent(body);
  }

  function signInNote(key) {
    state.note = { key: key, html: esc(U.sign_in_to) + ' <a href="' + esc(Account ? Account.signInUrl() : "#") + '">' +
      esc(U.sign_in) + "</a>" };
    refresh();
  }

  function act(button) {
    var box = button.closest(".cx-actions");
    var key = box.getAttribute("data-key");
    var w = works.filter(function (x) { return x.work_id === box.getAttribute("data-work"); })[0];
    var kind = button.getAttribute("data-act");
    if (kind === "share") return share(w, key);
    if (kind === "cite") return cite(w, key);
    if (!Account || !Account.user()) return signInNote(key);
    var mark = kind === "like" ? "liked" : "saved";
    var on = !(state.marks && state.marks[mark][key]);
    if (!state.marks) state.marks = { saved: {}, liked: {} };
    // Show it at once; put it back if the API says no.
    if (on) state.marks[mark][key] = true; else delete state.marks[mark][key];
    if (kind === "like") state.counts[key] = Math.max(0, (state.counts[key] || 0) + (on ? 1 : -1));
    state.note = null;
    refresh();
    Account.setMark(mark, key, on).catch(function (err) {
      if (on) delete state.marks[mark][key]; else state.marks[mark][key] = true;
      if (kind === "like") state.counts[key] = Math.max(0, (state.counts[key] || 0) + (on ? -1 : 1));
      if (err.signedOut) return signInNote(key);
      state.note = { key: key, html: esc(err.message) };
      refresh();
    });
  }

  // A link to this comment (/jhn/1/#v14-calvin), through the device's share
  // sheet where there is one, else copied.
  function share(w, key) {
    var v = +key.split(".").pop();
    var url = location.origin + location.pathname + "#v" + v + "-" + w.work_id;
    var title = fmt(U.share_title, { name: w.author, ref: REF(v) });
    if (navigator.share) {
      navigator.share({ title: title, text: title, url: url }).catch(function () { /* closed */ });
      return;
    }
    var done = function (ok) {
      state.note = { key: key, html: ok ? esc(U.copied) : esc(U.copy_this) + ' <input class="cx-copy" readonly value="' + esc(url) + '">' };
      refresh();
    };
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
    else done(false);
  }

  // The excerpt with its citation, for a sermon or a paper: the words as
  // Logia has them, then who, which work and edition, the verse, and a link.
  function cite(w, key) {
    var v = +key.split(".").pop();
    var url = location.origin + location.pathname + "#v" + v + "-" + w.work_id;
    var words = entriesFor(w, v).map(function (e) { return e.excerpt.trim(); }).join("\n\n");
    var text = "\u201c" + words + "\u201d\n\n" + fmt(U.citation, { name: w.author, title: w.title, edition: w.edition_short, ref: REF(v), url: url });
    var done = function (ok) {
      state.note = { key: key, html: ok ? esc(U.copied_cite) : esc(U.copy_this) + ' <textarea class="cx-copy" readonly rows="4">' + esc(text) + "</textarea>" };
      refresh();
    };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); });
    else done(false);
  }

  function wordsTab() {
    var v = state.verse, toks = PANEL.words[v] || [];
    var h = '<div class="cx-greek" lang="' + SOURCE_LANG + '"' + DIR + ">" + toks.map(function (t) {
      return '<span class="cx-g' + (t.id === state.token ? " cx-on" : "") + '" data-gid="' + t.id + '" role="button" tabindex="0">' +
        esc(t.text) + "</span>" + esc((t.after || " ").replace(/(\S)$/, "$1 "));
    }).join("") + "</div>";
    var t = toks.filter(function (x) { return x.id === state.token; })[0];
    if (!t) return h + '<p class="cx-empty">' + esc(U.tap_word) + "</p>";
    var lang = HEBREW && t.lang === "A" ? "arc" : SOURCE_LANG;
    h += '<div class="cx-word"><div class="cx-big cx-gk" lang="' + lang + '"' + DIR + ">" + esc(t.text) + "</div><dl>" +
      (t.transliteration ? "<dt>" + esc(U.transliteration) + "</dt><dd><i>" + esc(t.transliteration) + "</i></dd>" : "") +
      "<dt>" + esc(U.lemma) + '</dt><dd class="cx-gk" lang="' + lang + '"' + DIR + ">" + esc(t.lemma) + "</dd>" +
      (t.parse ? "<dt>" + esc(U.grammar) + "</dt><dd>" + esc(t.parse) + "</dd>" : "") +
      "<dt>" + esc(U.gloss) + "</dt><dd>" + esc(t.gloss) + "</dd>" +
      (t.strong ? "<dt>" + esc(U.strong) + "</dt><dd>" + (HEBREW ? "H" + esc(t.strong.replace(/^0+/, "")) : "G" + esc(t.strong)) + "</dd>" : "") +
      "</dl></div>";
    var decs = [].concat.apply([], recsFor(v).map(function (r) { return notesOf(r).decisions; })).filter(function (d) { return (d.tokens || []).indexOf(t.id) >= 0; });
    if (decs.length) h += '<div class="cx-era cx-gap">' + esc(U.how_translated) + "</div>" + decs.map(noteHtml).join("");
    return h;
  }

  function noteHtml(d) {
    var kind = d.layer === "meaning" ? U.meaning
      : fmt(U.english_levels, { levels: (d.levels || []).map(function (l) { return U.levels[l]; }).join(", ") });
    return '<div class="cx-note"><h4>' + esc(flat(d.choice)) + ' <span class="cx-tag">' + esc(U.categories[d.category] || d.category) +
      '</span><span class="cx-tag">' + esc(kind) + "</span>" + (d.uncertain ? '<span class="cx-tag">' + esc(U.uncertain) + "</span>" : "") + "</h4>" +
      (d.alternatives && d.alternatives.length ? '<div class="cx-alt">' + esc(U.not_) + " " +
        d.alternatives.map(function (a) { return esc(flat(a)); }).join(" · ") + "</div>" : "") +
      "<p>" + esc(flat(d.reason)) + "</p></div>";
  }
  function notesTab() {
    return recsFor(state.verse).map(function (r) {
      var n = notesOf(r);
      var span = r.verses.length > 1
        ? '<div class="cx-range">' + esc(fmt(U.sentence_spans, { a: r.verses[0], b: r.verses[r.verses.length - 1] })) + "</div>" : "";
      return span + '<div class="cx-src" lang="' + SOURCE_LANG + '"' + DIR + ">" + esc(n.source) + '</div><div class="cx-gloss">' + esc(U.word_for_word) + " " +
        esc(n.gloss) + "</div>" + n.decisions.map(noteHtml).join("");
    }).join("");
  }
  function xrefTab() {
    var xs = DATA.crossrefs[state.verse] || [];
    if (!xs.length) return '<p class="cx-empty">' + esc(U.no_xrefs) + "</p>";
    return '<div class="cx-xr">' + xs.map(function (x) {
      // Every chapter of the Bible is in Logia, so a reference opens here.
      var p = x.split(".");
      var verse = (p[2] || "").split("-")[0];
      var href = "/" + p[0].toLowerCase() + "/" + p[1] + "/" + (verse ? "#v" + verse : "");
      return '<a href="' + href + '">' + esc((DATA.books[p[0]] || p[0]) + " " + p[1] + (p[2] ? ":" + p[2] : "")) + "</a>";
    }).join("") + '</div><p class="cx-hint">' + esc(U.xref_credit) + "</p>";
  }

  // Compare: two or three voices on the chosen verse in columns, in a
  // dialog over the page (#compare, chapter_page in scripts/build_site.py).
  var cmp = { picked: [] };
  function voicesHere() {
    return works.filter(function (w) { return entriesFor(w, state.verse).length; });
  }
  function openCompare() {
    var vs = voicesHere();
    var ids = vs.map(function (w) { return w.work_id; });
    cmp.picked = cmp.picked.filter(function (id) { return ids.indexOf(id) >= 0; });
    if (cmp.picked.length < 2) {
      // The earliest, the latest and one between: the widest spread of the eras.
      var pick = vs.length <= 3 ? vs : [vs[0], vs[Math.floor((vs.length - 1) / 2)], vs[vs.length - 1]];
      cmp.picked = pick.map(function (w) { return w.work_id; });
    }
    renderCompare();
    var d = $("#compare");
    if (d.showModal && !d.open) d.showModal(); else d.setAttribute("open", "");
  }
  function renderCompare() {
    var v = state.verse, vs = voicesHere();
    var chips = vs.map(function (w) {
      var on = cmp.picked.indexOf(w.work_id) >= 0;
      return '<button type="button" class="cx-chip" data-pick="' + w.work_id + '" aria-pressed="' + on + '"' +
        (!on && cmp.picked.length >= 3 ? " disabled" : "") + ">" + esc(w.short_name) + "</button>";
    }).join("");
    var cols = vs.filter(function (w) { return cmp.picked.indexOf(w.work_id) >= 0; }).map(function (w) {
      return '<section class="cx-col"><div class="cx-who"><a href="' + w.author_url + '"><b>' + esc(w.author) + "</b></a>" +
        '<span class="cx-d">' + esc(w.author_dates) + "</span></div>" +
        '<div class="cx-work">' + esc(U.eras[w.era]) + " · <i>" + esc(w.title) + "</i></div>" +
        '<div class="cx-ex">' + excerptsHtml(w, entriesFor(w, v)) + "</div></section>";
    }).join("");
    $("#compare-ref").textContent = fmt(U.compare_on, { ref: REF(v) });
    $("#compare-text").textContent = verseText(v);
    $("#compare-picks").innerHTML = '<span class="cx-picks-label">' + esc(U.compare_pick) + "</span>" + chips;
    $("#compare-cols").innerHTML = cols;
    $("#compare-cols").style.setProperty("--cols", cmp.picked.length);
  }
  (function () {
    var d = $("#compare");
    if (!d) return;
    d.addEventListener("click", function (e) {
      if (e.target === d || e.target.closest("[data-close]")) { if (d.close) d.close(); else d.removeAttribute("open"); return; }
      var p = e.target.closest("[data-pick]");
      if (!p) return;
      var id = p.getAttribute("data-pick"), i = cmp.picked.indexOf(id);
      if (i >= 0) { if (cmp.picked.length > 1) cmp.picked.splice(i, 1); } else if (cmp.picked.length < 3) cmp.picked.push(id);
      renderCompare();
    });
  })();

  function go(v, opts) {
    opts = opts || {};
    var to = Math.max(FIRST, Math.min(LAST, v));
    if (to !== state.verse) state.open = {};
    state.verse = to;
    if (!opts.keepToken) state.token = null;
    state.note = null;
    document.querySelectorAll(".cx-verse").forEach(function (el) { el.classList.toggle("cx-on", +el.dataset.v === state.verse); });
    markTokens();
    renderPanel();
    // The last verse read, for "Continue reading" (web/logia.js).
    try { localStorage.setItem("logia-last", JSON.stringify({ href: location.pathname + "#v" + state.verse, ref: REF(state.verse) })); }
    catch (err) { /* storage blocked */ }
    var cur = location.hash.match(/^#v(\d+)/);
    if (!cur || +cur[1] !== state.verse) history.replaceState(null, "", "#v" + state.verse);
    // Moving to another verse while listening reads from there.
    if (listen && listen.on && !listen.moving) listenFrom(state.verse);
  }

  $("#text").addEventListener("click", function (e) {
    var brk = e.target.closest(".cx-brk");
    if (brk) {
      go(+brk.dataset.v); sheet("half");
      keepInView(document.querySelector('.cx-verse[data-v="' + brk.dataset.v + '"]'));
      return;
    }
    var w = e.target.closest(".cx-w"), vs = e.target.closest(".cx-verse");
    if (!vs) return;
    var v = +vs.dataset.v;
    if (w && v === state.verse) {
      var ids = w.dataset.tok.split(" ");
      state.token = ids[ids.length - 1];
      state.tab = "words";
      go(v, { keepToken: true });
    } else go(v);
    sheet("half");
    keepInView(vs);
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
  // On a phone the panel is a sheet over the text: a peek, half the screen
  // or nearly all of it. The handle steps through them; dragging the sheet's
  // head up or down moves one step.
  var PHONE = window.matchMedia("(max-width: 880px)");
  function sheetState() {
    var p = $("#panel");
    return p.classList.contains("cx-min") ? "min" : p.classList.contains("cx-full") ? "full" : "half";
  }
  function sheet(to) {
    var p = $("#panel");
    p.classList.toggle("cx-min", to === "min");
    p.classList.toggle("cx-full", to === "full");
    $("#grab").setAttribute("aria-expanded", to !== "min");
  }
  // Scroll the chosen verse into the space above a half-height sheet.
  function keepInView(el) {
    if (!PHONE.matches || !el) return;
    var top = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--header-h")) || 64;
    var r = el.getBoundingClientRect(), room = window.innerHeight * 0.5;
    if (r.top < top + 8 || r.bottom > room - 8) {
      var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollBy({ top: r.top - top - 16, behavior: reduce ? "auto" : "smooth" });
    }
  }
  $("#grab").addEventListener("click", function () {
    sheet({ min: "half", half: "full", full: "min" }[sheetState()]);
  });
  (function () {
    var head = document.querySelector(".cx-ph"), y0 = null;
    [head, $("#grab")].forEach(function (el) {
      el.addEventListener("touchstart", function (e) { y0 = e.touches[0].clientY; }, { passive: true });
      el.addEventListener("touchend", function (e) {
        if (y0 === null) return;
        var dy = e.changedTouches[0].clientY - y0; y0 = null;
        if (Math.abs(dy) < 40) return;
        var order = ["min", "half", "full"], i = order.indexOf(sheetState());
        sheet(order[Math.max(0, Math.min(2, i + (dy < 0 ? 1 : -1)))]);
      });
    });
  })();
  if (window.innerWidth <= 880 && !location.hash) $("#panel").classList.add("cx-min");
  // The verse before or after this one, past any the Bible text leaves out (John 5:4).
  function step(d) {
    var i = DATA.verses.indexOf(state.verse) + d;
    if (i >= 0 && i < DATA.verses.length) go(DATA.verses[i]);
  }
  $("#prev").addEventListener("click", function () { step(-1); });
  $("#next").addEventListener("click", function () { step(1); });
  // The left and right arrow keys move a verse, when nothing else uses them:
  // not while typing, in a menu, the panel's tabs or the compare dialog.
  document.addEventListener("keydown", function (e) {
    if ((e.key !== "ArrowLeft" && e.key !== "ArrowRight") || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var el = document.activeElement;
    if (el && (/input|textarea|select/i.test(el.tagName) || el.isContentEditable ||
        el.closest('[role="tablist"], [role="radiogroup"], [role="menu"], dialog, .dropdown, .prefs-menu, .account-pop'))) return;
    if ($("#compare").open) return;
    e.preventDefault();
    step(e.key === "ArrowLeft" ? -1 : 1);
    var on = document.querySelector('.cx-verse[data-v="' + state.verse + '"]');
    if (on) on.scrollIntoView({ block: "nearest" });
  });
  $("#pb").addEventListener("click", function (e) {
    var actButton = e.target.closest("[data-act]");
    if (actButton) { act(actButton); return; }
    if (e.target.closest("[data-compare]")) { openCompare(); return; }
    var toggle = e.target.closest("[data-toggle]");
    if (toggle) {
      var wid = toggle.getAttribute("data-toggle");
      state.open[wid] = !isOpen(wid);
      refresh();
      var again = document.querySelector('[data-toggle="' + wid + '"].cx-toggle');
      if (again) again.focus();
      return;
    }
    var chip = e.target.closest(".cx-chip");
    if (chip) {
      var era = chip.dataset.era;
      if (state.eras.has(era)) state.eras.delete(era); else state.eras.add(era);
      try {
        localStorage.setItem("logia-eras", JSON.stringify(ERAS.filter(function (x) { return !state.eras.has(x); })));
      } catch (err) { /* storage blocked: the choice lasts for this page */ }
      renderPanel(); return;
    }
    var retry = e.target.closest("[data-retry]");
    if (retry) {
      if (retry.getAttribute("data-retry") === "comm") loadComm(); else panelFailed = false;
      refresh(); return;
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
    state.open[d.dataset.work] = true;
    state.tab = "comm"; renderPanel();
    var card = document.getElementById("c-" + d.dataset.work);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "start" });
      card.classList.remove("cx-flash"); void card.offsetWidth; card.classList.add("cx-flash");
    }
  });
  // #v14 opens verse 14; #v14-calvin opens it at Calvin's comment (a shared link).
  var HASH = /^#v(\d+)(?:-([a-z][a-z0-9-]*))?$/;
  function showCard(work) {
    if (!COMM) { pendingCard = work; return; }
    if (!isOpen(work)) { state.open[work] = true; renderPanel(); }
    var card = document.getElementById("c-" + work);
    if (!card) return;
    card.scrollIntoView({ block: "start" });
    card.classList.remove("cx-flash"); void card.offsetWidth; card.classList.add("cx-flash");
  }
  window.addEventListener("hashchange", function () {
    var m = location.hash.match(HASH);
    if (!m) return;
    if (+m[1] !== state.verse) { if (!EMPTY) state.tab = "comm"; go(+m[1]); }
    if (m[2]) { sheet("half"); showCard(m[2]); }
  });

  // The chapter bar: once the chapter's title has scrolled away, a slim bar
  // under the header with the chapters before and after, a list of the
  // book's chapters, and how far through the text the reader is.
  (function () {
    var bar = $("#cx-bar"), title = document.querySelector(".cx-passage h1"), text = $("#text");
    if (!bar || !title || !window.IntersectionObserver) return;
    new IntersectionObserver(function (es) { bar.hidden = es[0].isIntersecting || es[0].boundingClientRect.top > 0; }).observe(title);
    var tick = false;
    window.addEventListener("scroll", function () {
      if (tick) return;
      tick = true;
      requestAnimationFrame(function () {
        tick = false;
        var r = text.getBoundingClientRect(), span = r.height - window.innerHeight * 0.5;
        var done = span > 0 ? Math.min(1, Math.max(0, -r.top / span)) : 1;
        $("#cx-progress").style.width = (done * 100).toFixed(1) + "%";
      });
    }, { passive: true });
    document.addEventListener("click", function (e) {
      var pick = bar.querySelector(".cx-pick");
      if (pick.open && !pick.contains(e.target)) pick.open = false;
    });
  })();

  if (EMPTY) {
    // ... unless the verse cross-references one the church comments on.
    var hv = location.hash.match(/^#v(\d+)/);
    state.tab = (DATA.related || {})[hv ? hv[1] : DATA.verses[0]] ? "comm" : "notes";
    var commTabButton = $("#tab-comm");
    commTabButton.parentNode.appendChild(commTabButton);
    commTabButton.classList.add("cx-zero");
  }
  var m0 = location.hash.match(HASH);
  // A verse the Open Word Bible leaves out (#v1 on John 8): open at the verse
  // after it, and show the note that stands in its place.
  var gapAsked = m0 && DATA.verses.indexOf(+m0[1]) < 0 && (DATA.verses.filter(function (v) { return v > +m0[1]; })[0] || 0);
  if (gapAsked) state.verse = gapAsked;
  else if (m0) state.verse = Math.max(FIRST, Math.min(LAST, +m0[1]));
  else {
    // With no verse asked for, open at the first verse that has commentary.
    var firstWith = DATA.verses.filter(function (v) { return works.some(function (w) { return entriesFor(w, v).length; }); })[0];
    if (firstWith) state.verse = firstWith;
  }
  // This chapter, read: kept for the dot on its chip (web/logia.js).
  try {
    var read = JSON.parse(localStorage.getItem("logia-read") || "[]");
    if (read.indexOf(location.pathname) < 0) { read.push(location.pathname); localStorage.setItem("logia-read", JSON.stringify(read.slice(-2000))); }
  } catch (err) { /* storage blocked */ }
  loadComm();
  renderText(); go(state.verse);
  if (m0 && m0[2]) { sheet("half"); showCard(m0[2]); }
  if (gapAsked) {
    var gapNote = [].filter.call(document.querySelectorAll(".lg-gap"), function (el) { return +el.dataset.a <= +m0[1] && +m0[1] <= +el.dataset.b; })[0];
    if (gapNote) gapNote.scrollIntoView({ block: "center" });
  }

  // Likes for this chapter (public), and the reader's own likes and saves.
  if (Account && works.length) {
    Account.likeCounts(CHAPTER).then(function (counts) { state.counts = counts || {}; if (state.tab === "comm") refresh(); });
    Account.marks().then(function (m) { if (m) { state.marks = m; if (state.tab === "comm") refresh(); } });
  }
  // Listen: the browser's own speech reads the verse, then each voice the
  // panel shows on it (in its era order, within the eras chosen), then goes
  // on to the next verse until the chapter ends or the reader presses Stop.
  // An excerpt already read for an earlier verse is not read again.
  var listen = { on: false, moving: false, run: 0, said: {} };
  function listenFrom(v) { listen.run++; speechSynthesis.cancel(); listenVerse(v, listen.run); }
  function speakable(text) {
    // Short pieces: some browsers stop an utterance after about 15 seconds.
    var out = [];
    flat(text).replace(/\s+/g, " ").trim().split(/(?<=[.;:!?])\s+/).forEach(function (s) {
      while (s.length > 240) {
        var cut = s.lastIndexOf(", ", 240); if (cut < 80) cut = s.lastIndexOf(" ", 240);
        out.push(s.slice(0, cut + 1)); s = s.slice(cut + 1).trim();
      }
      if (!s) return;
      // "Ver." or "16." alone would be read as a sentence of its own.
      if (out.length && out[out.length - 1].length < 40) out[out.length - 1] += " " + s;
      else out.push(s);
    });
    return out;
  }
  function listenVerse(v, run) {
    if (!COMM) { loadComm(); if (commLoad) commLoad.then(function () { if (run === listen.run) listenVerse(v, run); }); return; }
    if (state.tab !== "comm") { state.tab = "comm"; refresh(); }
    var queue = speakable(REF(v) + ". " + verseText(v)).map(function (t) { return { text: t }; });
    ERAS.forEach(function (era) {
      if (!state.eras.has(era)) return;
      works.filter(function (w) { return w.era === era; }).forEach(function (w) {
        var es = entriesFor(w, v).filter(function (e) { return !listen.said[w.work_id + ":" + e.start + ":" + e.excerpt.length]; });
        if (!es.length) return;
        queue.push({ text: w.author + ", " + w.title + ".", work: w.work_id });
        es.forEach(function (e) {
          listen.said[w.work_id + ":" + e.start + ":" + e.excerpt.length] = 1;
          speakable(e.excerpt).forEach(function (t) { queue.push({ text: t, work: w.work_id }); });
        });
      });
    });
    var lang = document.documentElement.lang || "en";
    var voice = speechSynthesis.getVoices().filter(function (x) { return x.lang && x.lang.indexOf(lang) === 0; })
      .sort(function (a, b) { return (b.localService ? 1 : 0) - (a.localService ? 1 : 0); })[0];
    var i = 0, card = null;
    var mark = function (work) {
      if (card) card.classList.remove("cx-speaking");
      card = work ? document.getElementById("c-" + work) : null;
      if (!card) return;
      card.classList.add("cx-speaking");
      if (card.classList.contains("cx-shut")) { var tg = card.querySelector("[data-toggle]"); if (tg) tg.click(); card = document.getElementById("c-" + work); card.classList.add("cx-speaking"); }
      card.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    var next = function () {
      if (run !== listen.run) return;
      if (i >= queue.length) {
        mark(null);
        var at = DATA.verses.indexOf(v);
        if (at >= 0 && at < DATA.verses.length - 1) {
          listen.moving = true; go(DATA.verses[at + 1]); listen.moving = false;
          keepInView(document.querySelector('.cx-verse[data-v="' + state.verse + '"]'));
          listenVerse(state.verse, run);
        } else listenStop();
        return;
      }
      var item = queue[i++];
      if (item.work !== (card && card.id.slice(2))) mark(item.work);
      var u = new SpeechSynthesisUtterance(item.text);
      u.lang = lang; if (voice) u.voice = voice;
      u.onend = next;
      u.onerror = function (ev) { if (ev.error !== "interrupted" && ev.error !== "canceled") next(); };
      speechSynthesis.speak(u);
    };
    next();
  }
  function listenShow() {
    var b = $("#listen");
    b.setAttribute("aria-pressed", listen.on);
    b.querySelector("span").textContent = listen.on ? U.listen_stop : U.listen;
  }
  function listenStop() {
    listen.on = false; listen.run++; listen.said = {};
    speechSynthesis.cancel();
    document.querySelectorAll(".cx-speaking").forEach(function (el) { el.classList.remove("cx-speaking"); });
    listenShow();
  }
  if ("speechSynthesis" in window && $("#listen")) {
    $("#listen").hidden = false;
    $("#listen").addEventListener("click", function () {
      if (listen.on) { listenStop(); return; }
      listen.on = true; listen.said = {}; listenShow(); listenFrom(state.verse);
    });
    window.addEventListener("pagehide", function () { speechSynthesis.cancel(); });
  }
})();
