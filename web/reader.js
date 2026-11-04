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
  // The traditions present in this chapter (library/authors "family"), in a fixed order.
  var FAMILIES = Object.keys(U.families).filter(function (f) {
    return DATA.commentaries.some(function (w) { return w.family === f; });
  });
  function hiddenFamilies() {
    try { return JSON.parse(localStorage.getItem("logia-families") || "[]"); } catch (e) { return []; }
  }
  var state = { verse: DATA.verses[0], tab: "comm", token: null, eras: new Set(ERAS), families: new Set(Object.keys(U.families)),
    marks: null, counts: {}, note: null, open: {}, unclamped: {} };
  hiddenFamilies().forEach(function (f) { state.families.delete(f); });
  // A commentator is shown when both their era and their tradition are on.
  function shown(x) { return state.eras.has(x.era) && state.families.has(x.family); }
  var Account = window.LogiaAccount;
  var CHAPTER = DATA.book + "." + DATA.chapter;
  // A comment's key: <work>.<BOOK>.<chapter>.<verse> (backend/logia/ in open-word-bible).
  var keyOf = function (w, v) { return w.work_id + "." + CHAPTER + "." + v; };
  var ICON = {
    like: '<svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.6-9.3C.9 8.2 3 4.5 6.6 4.5c2 0 3.6 1.1 4.4 2.6.8-1.5 2.4-2.6 4.4-2.6 3.6 0 5.7 3.7 4.2 7.2C19.5 16.4 12 21 12 21z"/></svg>',
    save: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M6 3.5h12v17l-6-4.2-6 4.2z"/></svg>',
    share: '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 15V3.5M7.5 8 12 3.5 16.5 8M5 12.5v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>'
  };
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
    renderStrip();
    document.querySelectorAll(".cx-levels button").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.level === lv); });
    markTokens();
  }
  // How much commentary each verse has (item 10): one bar per verse, as tall
  // as the number of commentators shown on it, with the references to it from
  // other verses in its label. A bar opens its verse.
  function renderStrip() {
    var el = $("#strip");
    if (!el) return;
    var counts = DATA.verses.map(function (v) {
      return works.filter(function (w) { return shown(w) && entriesFor(w, v).length; }).length;
    });
    var top = Math.max.apply(null, counts.concat([1]));
    if (!works.length) { el.hidden = true; return; }
    el.innerHTML = DATA.verses.map(function (v, i) {
      var n = counts[i], m = (DATA.citedBy[v] || []).filter(shown).length;
      return '<button type="button" class="cx-bar' + (v === state.verse ? " cx-on" : "") + (n ? "" : " cx-zero") + '" data-v="' + v +
        '" style="--h:' + Math.round((n / top) * 100) + '%" aria-label="' + esc(fmt(U.strip_verse, { ref: REF(v), n: n, m: m })) +
        '" title="' + esc(fmt(U.strip_verse, { ref: REF(v), n: n, m: m })) + '"><span></span></button>';
    }).join("");
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
      var on = entriesFor(w, state.verse).length > 0 && shown(w);
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
    var keep = $("#pb").scrollTop;
    $("#pb").innerHTML = ({ comm: commTab, words: wordsTab, notes: notesTab, xref: xrefTab })[state.tab]();
    $("#pb").scrollTop = state.keepScroll ? keep : 0;
    state.keepScroll = false;
  }
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
  // The topics this verse is at the centre of (library/topics).
  function topicsOn(v) {
    var ts = (DATA.topics || {})[v] || [];
    if (!ts.length) return "";
    return '<p class="cx-whole">' + esc(U.topics) + ": " + ts.map(function (tp) {
      return '<a href="/topics/' + esc(tp.id) + '/">' + esc(tp.title) + "</a>";
    }).join(" · ") + "</p>";
  }
  // Excerpts on other verses that refer to this one (the other way of a citation).
  function elsewhere(v) {
    var rows = (DATA.citedBy[v] || []).filter(shown);
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
  // Under each excerpt: Cite (item 12), How this was copied (item 14) and
  // Report a mistake (item 13). An excerpt's own link is the chapter page
  // with its id: /jhn/1/#calvin.JHN.1.1.1, opened at that excerpt.
  function permalink(e) {
    return DATA.site_url + "/" + DATA.book.toLowerCase() + "/" + DATA.chapter + "/#" + e.id;
  }
  function refOf(e) { return e.start === e.end ? REF(e.start) : REF(e.start) + "–" + e.end; }
  function citation(w, e, html) {
    var title = html ? "<i>" + esc(w.title) + "</i>" : w.title;
    var where = locusLabel(w, e.locus);
    var on = fmt(U.cite_on, { ref: refOf(e) });
    // A translation names its translator ("translated by William Pringle … (1847)"),
    // an original its year ("(1879)").
    var t = w.version.translation;
    var ed = t ? ", " + (/^[A-Z][a-z]/.test(t) ? t.charAt(0).toLowerCase() + t.slice(1) : t) : " (" + w.version.published + ")";
    var text = w.author + ", " + title + ed + ", " + (where ? where + " (" + on + ")" : on) +
      ". " + U.cite_in_logia + ": " + permalink(e) + ".";
    return html ? text.replace(permalink(e), '<a href="' + esc(permalink(e)) + '">' + esc(permalink(e)) + "</a>") : text;
  }
  function provenance(w, e) {
    var v = w.version;
    var how = v.source_kind === "scan" ? U.from_scan : U.from_ccel;
    var src = '<a href="' + esc(e.source_url) + '" target="_blank" rel="noopener">' + esc(e.sources[0]) + "</a> (" + esc(how) + ")";
    var lang = U.languages[v.language] || v.language;
    var kind = fmt(v.kind === "original" ? U.version_original : U.version_translation, { language: lang });
    var fixes = e.fixed.length
      ? "<p>" + esc(U.fixes) + "</p><ul>" + e.fixed.map(function (f) {
          return "<li><s>" + esc(f[0]) + "</s> → " + esc(f[1]) + "</li>";
        }).join("") + "</ul>"
      : "<p>" + esc(U.no_fixes) + "</p>";
    return "<p>" + fmt(esc(U.copied_from), { source: src }) + "</p>" + fixes +
      "<p>" + esc(fmt(U.version_label, { kind: kind, edition: v.edition })) + " " +
      esc(v.status === "reviewed" ? fmt(U.review_done, { name: v.reviewer }) : U.review_draft) + "</p>" +
      '<p><a href="' + esc(w.work_url) + '#versions">' + esc(U.all_versions) + "</a></p>";
  }
  function reportUrl(w, e) {
    var body = fmt(U.report_body, { id: e.id, ref: refOf(e), url: permalink(e), source: e.source_url });
    return DATA.issues_url + "?title=" + encodeURIComponent(fmt(U.report_title, { id: e.id })) + "&body=" + encodeURIComponent(body);
  }
  function tools(w, e) {
    var open = state.open[e.id];
    var panel = "";
    if (open === "cite") {
      panel = '<div class="cx-tool-panel"><p class="cx-citation">' + citation(w, e, true) + "</p>" +
        '<button type="button" data-copy="' + esc(citation(w, e, false)) + '">' + esc(U.copy) + "</button> " +
        '<button type="button" data-copy="' + esc(permalink(e)) + '">' + esc(U.permalink) + "</button></div>";
    } else if (open === "source") {
      panel = '<div class="cx-tool-panel">' + provenance(w, e) + "</div>";
    }
    return '<div class="cx-tools">' +
      '<button type="button" data-tool="cite" data-id="' + esc(e.id) + '" aria-expanded="' + (open === "cite") + '">' + esc(U.cite) + "</button>" +
      '<button type="button" data-tool="source" data-id="' + esc(e.id) + '" aria-expanded="' + (open === "source") + '">' + esc(U.source) + "</button>" +
      '<a href="' + esc(reportUrl(w, e)) + '" target="_blank" rel="noopener">' + esc(U.report) + "</a></div>" + panel;
  }

  function commTab() {
    var v = state.verse;
    var h = '<div class="cx-chips" role="group" aria-label="' + esc(U.show_eras) + '">' + ERAS.map(function (e) {
      return '<button class="cx-chip" data-era="' + esc(e) + '" aria-pressed="' + state.eras.has(e) + '">' + esc(U.eras[e]) + "</button>";
    }).join("") + "</div>";
    if (FAMILIES.length > 1) {
      h += '<div class="cx-chips" role="group" aria-label="' + esc(U.show_families) + '" title="' + esc(U.families_note) + '">' +
        FAMILIES.map(function (f) {
          return '<button class="cx-chip" data-family="' + f + '" aria-pressed="' + state.families.has(f) + '">' + esc(U.families[f]) + "</button>";
        }).join("") + "</div>";
    }
    var any = false;
    ERAS.forEach(function (era) {
      if (!state.eras.has(era)) return;
      var ws = works.filter(function (w) { return w.era === era && state.families.has(w.family) && entriesFor(w, v).length; });
      if (!ws.length) return;
      any = true;
      h += '<div class="cx-era">' + esc(U.eras[era]) + "</div>";
      ws.forEach(function (w) {
        var es = entriesFor(w, v);
        var body = es.map(function (e) {
          var where = [e.start === e.end ? "" : fmt(U.on_verses, { a: e.start, b: e.end }), locusLabel(w, e.locus)]
            .filter(Boolean).join(" · ");
          var range = where ? '<div class="cx-range">' + esc(where) + "</div>" : "";
          var lemma = e.heading && e.excerpt.replace(/^\s*\d+\.\s*/, "").toLowerCase().indexOf(e.heading.toLowerCase()) !== 0
            ? '<div class="cx-lemma">' + esc(e.heading) + "</div>" : "";
          return '<div class="cx-entry" id="x-' + esc(e.id) + '">' + range + lemma + paras(linked(e.excerpt, e.cites)) + traced(e) +
            tools(w, e) + "</div>";
        }).join("");
        var words = es.reduce(function (n, e) { return n + e.excerpt.split(/\s+/).length; }, 0);
        // Opened in full by "Read all", by a panel open under one of its
        // excerpts, or by a link to one of them.
        var opened = state.unclamped[w.work_id] || es.some(function (e) { return state.open[e.id]; });
        var long = words > 140 && !fullExcerpts() && !opened;
        h += '<section class="cx-card" id="c-' + w.work_id + '">' +
          '<div class="cx-who"><a href="' + w.author_url + '"><b>' + esc(w.author) + "</b></a>" +
          '<span class="cx-d">' + esc(w.author_dates) + '</span><span class="cx-tag">' + esc(w.tradition) + "</span></div>" +
          '<div class="cx-work"><a href="' + w.work_url + '"><i>' + esc(w.title) + "</i></a> · " + esc(w.edition_short) + "</div>" +
          '<div class="cx-ex' + (long ? " cx-clamp" : "") + '">' + body + "</div>" +
          '<div class="cx-more">' + (long ? '<button type="button" data-expand>' + esc(fmt(U.read_all, { n: words.toLocaleString() })) + "</button>" : "") +
          (es[0].inFull ? '<a href="' + esc(es[0].inFull) + '">' +
            esc(fmt(U.read_in_full, { where: locusLabel(w, es[0].locus.split(".")[0]) })) + "</a>" : "") +
          '<a href="' + esc(es[0].source_url) + '" target="_blank" rel="noopener">' + esc(U.full_text) + " ↗</a></div>" +
          actions(w, v) + "</section>";
      });
    });
    if (!any) {
      h += '<p class="cx-empty">' + esc(works.some(function (w) { return entriesFor(w, v).length; }) ? U.none_in_eras : U.none_yet_long) + "</p>";
    }
    return h + wholeTexts(v) + topicsOn(v) + elsewhere(v);
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
    state.note = null;
    document.querySelectorAll(".cx-verse").forEach(function (el) { el.classList.toggle("cx-on", +el.dataset.v === state.verse); });
    document.querySelectorAll(".cx-bar").forEach(function (el) { el.classList.toggle("cx-on", +el.dataset.v === state.verse); });
    markTokens();
    renderPanel();
    if (opts.keepHash) return;
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
  if ($("#strip")) $("#strip").addEventListener("click", function (e) {
    var b = e.target.closest(".cx-bar"); if (!b) return;
    state.tab = "comm"; go(+b.dataset.v);
  });
  $("#grab").addEventListener("click", function () { $("#panel").classList.toggle("cx-min"); });
  if (window.innerWidth <= 880 && !location.hash) $("#panel").classList.add("cx-min");
  $("#prev").addEventListener("click", function () { go(state.verse - 1); });
  $("#next").addEventListener("click", function () { go(state.verse + 1); });
  $("#pb").addEventListener("click", function (e) {
    var actButton = e.target.closest("[data-act]");
    if (actButton) { act(actButton); return; }
    var tool = e.target.closest("[data-tool]");
    if (tool) {
      var id = tool.dataset.id;
      state.open[id] = state.open[id] === tool.dataset.tool ? null : tool.dataset.tool;
      refresh(); return;
    }
    var copy = e.target.closest("[data-copy]");
    if (copy) {
      var label = copy.textContent;
      var done = function () { copy.textContent = U.copied_citation; setTimeout(function () { copy.textContent = label; }, 1500); };
      if (navigator.clipboard) navigator.clipboard.writeText(copy.dataset.copy).then(done, function () { /* blocked */ });
      return;
    }
    var fam = e.target.closest("[data-family]");
    if (fam) {
      var f = fam.dataset.family;
      if (state.families.has(f)) state.families.delete(f); else state.families.add(f);
      try {
        localStorage.setItem("logia-families", JSON.stringify(Object.keys(U.families).filter(function (x) { return !state.families.has(x); })));
      } catch (err) { /* storage blocked: the choice lasts for this page */ }
      renderPanel(); renderStrip(); return;
    }
    var chip = e.target.closest(".cx-chip");
    if (chip) {
      var era = chip.dataset.era;
      if (state.eras.has(era)) state.eras.delete(era); else state.eras.add(era);
      try {
        localStorage.setItem("logia-eras", JSON.stringify(ERAS.filter(function (x) { return !state.eras.has(x); })));
      } catch (err) { /* storage blocked: the choice lasts for this page */ }
      renderPanel(); renderStrip(); return;
    }
    var ex = e.target.closest("[data-expand]");
    if (ex) {
      var card = ex.closest(".cx-card");
      state.unclamped[card.id.slice(2)] = true;
      card.querySelector(".cx-ex").classList.remove("cx-clamp"); ex.remove(); return;
    }
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
  // #v14 opens verse 14; #v14-calvin opens it at Calvin's comment (a shared link).
  var HASH = /^#v(\d+)(?:-([a-z][a-z0-9-]*))?$/;
  function showCard(work) {
    var card = document.getElementById("c-" + work);
    if (!card) return;
    card.scrollIntoView({ block: "start" });
    card.classList.remove("cx-flash"); void card.offsetWidth; card.classList.add("cx-flash");
  }
  // #calvin.JHN.1.1.1 opens that excerpt: its verse, its card, the excerpt itself.
  function excerptAt(hash) {
    var id = decodeURIComponent(hash.slice(1));
    for (var i = 0; i < works.length; i++) {
      var e = works[i].entries.filter(function (x) { return x.id === id; })[0];
      if (e) return e;
    }
    return null;
  }
  function showExcerpt(e) {
    state.tab = "comm";
    state.unclamped[e.id.split(".")[0]] = true;
    if (state.verse !== e.start) go(e.start, { keepHash: true }); else renderPanel();
    $("#panel").classList.remove("cx-min");
    var el = document.getElementById("x-" + e.id);
    if (!el) return;
    el.scrollIntoView({ block: "start" });
    el.classList.remove("cx-flash"); void el.offsetWidth; el.classList.add("cx-flash");
  }
  window.addEventListener("hashchange", function () {
    var x = excerptAt(location.hash);
    if (x) { showExcerpt(x); return; }
    var m = location.hash.match(HASH);
    if (!m) return;
    if (+m[1] !== state.verse) { state.tab = "comm"; go(+m[1]); }
    if (m[2]) { $("#panel").classList.remove("cx-min"); showCard(m[2]); }
  });

  var m0 = location.hash.match(HASH), x0 = excerptAt(location.hash);
  if (x0) state.verse = x0.start;
  else if (m0) state.verse = Math.max(FIRST, Math.min(LAST, +m0[1]));
  else {
    // With no verse asked for, open at the first verse that has commentary.
    var firstWith = DATA.verses.filter(function (v) { return works.some(function (w) { return entriesFor(w, v).length; }); })[0];
    if (firstWith) state.verse = firstWith;
  }
  renderText(); go(state.verse, { keepHash: !!x0 });
  if (x0) showExcerpt(x0);
  if (m0 && m0[2]) { $("#panel").classList.remove("cx-min"); showCard(m0[2]); }

  // Likes for this chapter (public), and the reader's own likes and saves.
  if (Account && works.length) {
    Account.likeCounts(CHAPTER).then(function (counts) { state.counts = counts || {}; if (state.tab === "comm") refresh(); });
    Account.marks().then(function (m) { if (m) { state.marks = m; if (state.tab === "comm") refresh(); } });
  }
})();
