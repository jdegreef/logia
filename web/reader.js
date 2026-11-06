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
  ICON.columns = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/></svg>';
  hiddenEras().forEach(function (e) { state.eras.delete(e); });
  // Whether a voice's card is open on the chosen verse (see commTab).
  function isOpen(work) {
    if (work in state.open) return state.open[work];
    if (fullExcerpts()) return true;
    return works.filter(function (w) { return state.eras.has(w.era) && entriesFor(w, state.verse).length; }).length <= 2;
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
  var FIRST = DATA.verses[0], LAST = DATA.verses[DATA.verses.length - 1];
  var REF = function (v) { return DATA.bookName + " " + DATA.chapter + ":" + v; };
  var recFor = function (v) { return DATA.records.filter(function (r) { return r.verses.indexOf(v) >= 0; })[0]; };
  var entriesFor = function (w, v) { return w.entries.filter(function (e) { return e.start <= v && v <= e.end; }); };

  function verseText(v) {
    var r = recFor(v), lv = level();
    if (lv === "B") return flat(r.pieces.filter(function (p) { return p[0] === v; }).map(function (p) { return p[1]; }).join("")).trim();
    return flat(r[lv][v] || "");
  }

  function renderText() {
    var out = [], lv = level();
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
        // The gold count beside a verse number: how many voices comment on it.
        var n = works.filter(function (w) { return entriesFor(w, v).length; }).length;
        var label = n ? fmt(n === 1 ? U.verse_voices_one : U.verse_voices, { ref: REF(v), n: n }) : REF(v);
        out.push('<span class="cx-verse' + (v === state.verse ? " cx-on" : "") + (n ? " cx-has" : "") + (poem ? " cx-poem" : "") + '" data-v="' + v +
          '" tabindex="0" role="button" aria-label="' + esc(label) + '"><span class="cx-vn">' + v + "</span>" +
          (n ? '<span class="cx-vc" aria-hidden="true">' + n + "</span>" : "") + inner + "</span> ");
      });
    });
    $("#text").innerHTML = out.join("");
    $("#text").classList.add("cx-ready");
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
    $("#n-words").textContent = DATA.wordCounts[v] || 0;
    $("#n-notes").textContent = r.notes;
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
  function linked(text, cites) {
    var h = "", pos = 0;
    (cites || []).slice().sort(function (a, b) { return a.at - b.at; }).forEach(function (c) {
      if (c.at < pos) return;
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
      return range + lemma + paras(linked(e.excerpt, e.cites)) + traced(e);
    }).join("");
  }
  function commTab() {
    var v = state.verse;
    var h = '<div class="cx-chips" role="group" aria-label="' + esc(U.show_eras) + '">' + ERAS.map(function (e) {
      return '<button class="cx-chip" data-era="' + esc(e) + '" aria-pressed="' + state.eras.has(e) + '">' + esc(U.eras[e]) + "</button>";
    }).join("") + "</div>";
    var shown = works.filter(function (w) { return state.eras.has(w.era) && entriesFor(w, v).length; });
    if (COMM && shown.length > 1) {
      h += '<button type="button" class="cx-compare-btn" data-compare>' + ICON.columns + esc(U.compare) + "</button>";
    }
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
        h += '<section class="cx-card' + (open ? "" : " cx-shut") + '" id="c-' + w.work_id + '">' +
          '<div class="cx-who"><a href="' + w.author_url + '"><b>' + esc(w.author) + "</b></a>" +
          '<span class="cx-d">' + esc(w.author_dates) + '</span><span class="cx-tag">' + esc(w.tradition) + "</span>" +
          '<button type="button" class="cx-toggle" data-toggle="' + w.work_id + '" aria-expanded="' + open + '" aria-controls="cb-' + w.work_id +
          '" aria-label="' + esc(fmt(open ? U.hide_voice : U.show_voice, { name: w.author })) + '">' + ICON.chevron + "</button></div>" +
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
      h += '<p class="cx-empty">' + esc(works.some(function (w) { return entriesFor(w, v).length; }) ? U.none_in_eras : U.none_yet_long) + "</p>";
    }
    return h + wholeTexts(v) + elsewhere(v);
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
      esc(liked ? U.unlike : U.like) + '">' + ICON.like + '<span class="cx-count">' + (n ? n : "") + "</span>" +
      '<span class="cx-act-label">' + esc(liked ? U.liked : U.like) + "</span></button>" +
      '<button type="button" class="cx-act cx-save" data-act="save" aria-pressed="' + isSaved + '">' + ICON.save +
      '<span class="cx-act-label">' + esc(isSaved ? U.saved : U.save) + "</span></button>" +
      '<button type="button" class="cx-act" data-act="share">' + ICON.share + '<span class="cx-act-label">' + esc(U.share) +
      "</span></button></div>" + note;
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
    var decs = notesOf(recFor(v)).decisions.filter(function (d) { return (d.tokens || []).indexOf(t.id) >= 0; });
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
    var r = recFor(state.verse), n = notesOf(r);
    var span = r.verses.length > 1
      ? '<div class="cx-range">' + esc(fmt(U.sentence_spans, { a: r.verses[0], b: r.verses[r.verses.length - 1] })) + "</div>" : "";
    return span + '<div class="cx-src" lang="' + SOURCE_LANG + '"' + DIR + ">" + esc(n.source) + '</div><div class="cx-gloss">' + esc(U.word_for_word) + " " +
      esc(n.gloss) + "</div>" + n.decisions.map(noteHtml).join("");
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
    var cur = location.hash.match(/^#v(\d+)/);
    if (!cur || +cur[1] !== state.verse) history.replaceState(null, "", "#v" + state.verse);
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
  $("#prev").addEventListener("click", function () { go(state.verse - 1); });
  $("#next").addEventListener("click", function () { go(state.verse + 1); });
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
    if (+m[1] !== state.verse) { state.tab = "comm"; go(+m[1]); }
    if (m[2]) { sheet("half"); showCard(m[2]); }
  });

  var m0 = location.hash.match(HASH);
  if (m0) state.verse = Math.max(FIRST, Math.min(LAST, +m0[1]));
  else {
    // With no verse asked for, open at the first verse that has commentary.
    var firstWith = DATA.verses.filter(function (v) { return works.some(function (w) { return entriesFor(w, v).length; }); })[0];
    if (firstWith) state.verse = firstWith;
  }
  loadComm();
  renderText(); go(state.verse);
  if (m0 && m0[2]) { sheet("half"); showCard(m0[2]); }

  // Likes for this chapter (public), and the reader's own likes and saves.
  if (Account && works.length) {
    Account.likeCounts(CHAPTER).then(function (counts) { state.counts = counts || {}; if (state.tab === "comm") refresh(); });
    Account.marks().then(function (m) { if (m) { state.marks = m; if (state.tab === "comm") refresh(); } });
  }
})();
