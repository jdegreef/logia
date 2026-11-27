// /search/ only (search_page in scripts/build_site.py): the word search over
// Pagefind's index, its filters, sorting, grouping and export. It runs after
// web/logia.js, whose helpers it takes from window.LogiaSearch.
(function () {
  "use strict";
  var L = window.LogiaSearch;
  if (!L) return;
  var esc = L.esc, fmt = L.fmt, withData = L.withData, parseRef = L.parseRef, suggest = L.suggest, distance = L.distance;

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
    var src = form.getAttribute("data-pagefind"), srcBible = form.getAttribute("data-pagefind-bible");
    if (!src) return;
    // The Bible's verses are an index of their own, loaded only when "Bible
    // text" is chosen (build_search_index in scripts/build_site.py).
    var pfBible = null, srcCounts = {};
    function sources() {
      var names = Object.keys(allCounts.source || {}), comm = names[0], bible = names[1], s = chosen.source;
      return { comm: !s.length || s.indexOf(comm) >= 0, bible: !!bible && s.indexOf(bible) >= 0, names: names };
    }
    function bibleIndex() {
      if (!pfBible) pfBible = import(srcBible).then(function (m) { return m.options({ excerptLength: 36 }).then(function () { return m; }); });
      return pfBible;
    }
    var pf = null, allCounts = {}, chosen = { source: [], era: [], tradition: [], book: [], commentator: [], work: [] }, results = [], shown = 0, run = 0, timer = null;
    var params = new URLSearchParams(location.search);
    input.value = params.get("q") || "";
    // As the query is typed (and from the address bar, /opensearch.xml),
    // what it could name besides words: a reference offers its page as a
    // button, and up to three books or commentators follow as links, above
    // the word search's results.
    var goto = document.createElement("p");
    goto.className = "lg-fts-goto"; goto.hidden = true;
    status.parentNode.insertBefore(goto, status);
    function showGoto() {
      var q = input.value.trim();
      if (!q) { goto.hidden = true; return; }
      withData(function () {
        var hits = suggest(input.value).filter(function (x) { return x.href.indexOf("/search/") !== 0; }).slice(0, 3);
        if (!hits.length) { goto.hidden = true; return; }
        goto.innerHTML = hits.map(function (x, i) {
          return i === 0 && parseRef(q)
            ? '<a class="button" href="' + esc(x.href) + '">' + esc(fmt(U.goto, { ref: x.title })) + " →</a>"
            : '<a class="lg-fts-goto-link" href="' + esc(x.href) + '"><b>' + esc(x.title) + "</b> <span>" + esc(x.note) + "</span></a>";
        }).join(" ");
        goto.hidden = false;
      });
    }
    var gotoTimer = null;
    input.addEventListener("input", function () { clearTimeout(gotoTimer); gotoTimer = setTimeout(showGoto, 150); });
    if (input.value.trim()) showGoto();
    Object.keys(chosen).forEach(function (k) { chosen[k] = params.getAll(k); });
    function filters(but) {
      var f = {};
      Object.keys(chosen).forEach(function (k) { if (k !== but && chosen[k].length) f[k] = { any: chosen[k] }; });
      return f;
    }
    // Each group's counts as if nothing were chosen in it, so its other
    // values stay offered: one more search for each group with a choice.
    // Counting the filters costs Pagefind time on every search once their
    // data is loaded (20 seconds for "Word"), so the results come from an
    // instance that never loads it, and the chips' counts from a second
    // instance, asked only when a search has at most COUNT_UP_TO results.
    // A bigger search shows the chips without counts.
    var COUNT_UP_TO = 1500, pfCount = null;
    function counter() {
      if (!pfCount) pfCount = import(src + "?counts").then(function (m) { return m.filters().then(function () { return m; }); });
      return pfCount;
    }
    function facetCounts(q) {
      return counter().then(function (m) {
        return m.search(q || null, { filters: filters() }).then(function (s) {
          var counts = {};
          Object.keys(s.filters).forEach(function (k) { counts[k] = s.filters[k]; });
          var groups = Object.keys(chosen).filter(function (k) { return chosen[k].length; });
          return Promise.all(groups.map(function (k) {
            return m.search(q || null, { filters: filters(k) }).then(function (s2) { counts[k] = s2.filters[k] || {}; });
          })).then(function () { return counts; });
        });
      });
    }
    function keep() {
      var p = new URLSearchParams();
      if (input.value.trim()) p.set("q", input.value.trim());
      if (sortBy.value) p.set("sort", sortBy.value);
      Object.keys(chosen).forEach(function (k) { chosen[k].forEach(function (v) { p.append(k, v); }); });
      var qs = p.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
    }
    function chips(counts, bare) {
      form.querySelectorAll(".lg-fts-group[data-filter]").forEach(function (g) {
        var k = g.getAttribute("data-filter"), c = bare ? allCounts[k] || {} : counts[k] || {};
        var names = Object.keys(c).filter(function (v) { return c[v] || chosen[k].indexOf(v) >= 0; });
        // Both sources are always offered; a count shows once that index is searched.
        if (k === "source") { names = Object.keys(allCounts.source || {}); c = input.value.trim() || Object.keys(filters()).length ? srcCounts : allCounts.source || {}; }
        if (k === "era" || k === "book" || k === "source") {
          var order = Object.keys(allCounts[k] || {});
          names.sort(function (a, b) { return order.indexOf(a) - order.indexOf(b); });
        } else names.sort();
        if (k === "commentator") {
          who.innerHTML = '<option value="">' + esc(who.options[0].text) + "</option>" + names.map(function (v) {
            return '<option value="' + esc(v) + '"' + (chosen[k].indexOf(v) >= 0 ? " selected" : "") + ">" + esc(v) + (bare ? "" : " (" + (c[v] || 0) + ")") + "</option>";
          }).join("");
        } else {
          g.querySelector(".lg-fts-chips").innerHTML = names.map(function (v) {
            return '<button type="button" class="cx-chip" data-k="' + k + '" data-v="' + esc(v) + '" aria-pressed="' + (chosen[k].indexOf(v) >= 0) + '">' +
              esc(v) + ((bare && k !== "source") || c[v] == null ? "" : ' <span class="cx-chip-n">' + c[v] + "</span>") + "</button>";
          }).join("");
        }
        g.hidden = !names.length;
      });
    }
    // A result is named from its code (x: work~book~chapter~verse~end chapter~end
    // verse, or b~book~chapter~verse for a verse of the Bible), and its
    // address is its record's path with the .html made a #fragment
    // (search_records in scripts/build_site.py).
    function card(d) {
      var x = (d.meta.x || "").split("~"), bible = x[0] === "b";
      var link = d.url.replace(/\/v(\d+)\.html$/, "/#v$1").replace(/\/([^/]+)\.html$/, "/#$1");
      // The words searched for go along (?hl=), to be marked where the result opens.
      var words = input.value.trim().replace(/\b[a-z]+:\S+/gi, "").trim();
      if (words && !bible) link = link.replace("#", "?hl=" + encodeURIComponent(words) + "#");
      var book = U.books[+x[1]] || "", ch = x[2], v = x[3];
      var ref = book + " " + ch + ":" + v;
      if (!bible && (x[4] !== ch || x[5] !== v)) ref += "–" + (x[4] !== ch ? x[4] + ":" : "") + x[5];
      var w = bible ? null : U.works[+x[0]];
      var title = bible ? ref : fmt(U.result_title, { name: w ? w[1] : "", ref: ref });
      var sub = bible ? "<i>" + esc(U.owb) + "</i>" : esc(w ? w[2] : "") + " · <i>" + esc(w ? w[0] : "") + "</i>";
      // A stripe in the commentator's era colour down the result's edge.
      return '<li class="lg-fts-hit' + (bible ? " lg-fts-verse" : " lg-era-" + (w ? w[3] : 0)) + '"><p class="lg-fts-head"><a href="' + esc(link) + '"><b>' + esc(title) + "</b></a>" +
        ' <span class="lg-quiet">' + sub + "</span></p>" +
        '<p class="lg-fts-text">' + d.excerpt + "</p>" +
        (!bible && d.content && d.content.length > d.excerpt.replace(/<[^>]+>/g, "").length + 80
          ? '<button type="button" class="lg-linkish lg-fts-open" data-open="' + (opened.push(d.content) - 1) + '">' + esc(U.more_text) + "</button>" : "") + "</li>";
    }
    // "Show more": the excerpt's text around the first word searched for, up
    // to about 200 words, the words searched for marked, in place.
    var opened = [];
    list.addEventListener("click", function (e) {
      var b = e.target.closest("[data-open]");
      if (!b) return;
      var text = opened[+b.getAttribute("data-open")] || "", low = text.toLowerCase();
      var words = input.value.trim().replace(/\b[a-z]+:\S+/gi, "").replace(/["']/g, "").split(/\s+/).filter(function (w) { return w.length > 1; });
      var at = words.reduce(function (best, w) { var i = low.indexOf(w.toLowerCase()); return i >= 0 && (best < 0 || i < best) ? i : best; }, -1);
      var from = Math.max(0, (at < 0 ? 0 : at) - 400);
      from = from ? text.indexOf(" ", from) + 1 : 0;
      var part = text.slice(from, from + 1300), cut = part.lastIndexOf(" ");
      if (from + 1300 < text.length && cut > 0) part = part.slice(0, cut);
      var html = esc(part);
      words.forEach(function (w) {
        var re = new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
        html = html.replace(re, "<mark>$1</mark>");
      });
      var p = b.parentNode.querySelector(".lg-fts-text");
      p.innerHTML = (from ? "… " : "") + html + (from + part.length < text.length ? " …" : "");
      b.remove();
    });
    // "Group by passage": the best U.group_top results gathered by the verse
    // each begins at, the verse with most first, each with its voices' lines.
    var grouping = document.getElementById("fts-group"), view = document.querySelector(".lg-fts-view");
    function showGroups(mine) {
      more.hidden = true;
      return Promise.all(results.slice(0, U.group_top).map(function (r) { return r.data(); })).then(function (ds) {
        if (mine !== run) return;
        var groups = {}, order = [];
        ds.forEach(function (d) {
          var x = (d.meta.x || "").split("~");
          var key = x[1] + "~" + x[2] + "~" + x[3];
          if (!groups[key]) { groups[key] = []; order.push(key); }
          groups[key].push(d);
        });
        order.sort(function (a, b) { return groups[b].length - groups[a].length || order.indexOf(a) - order.indexOf(b); });
        list.innerHTML = order.map(function (key) {
          var ds2 = groups[key], k = key.split("~"), ref = (U.books[+k[0]] || "") + " " + k[1] + ":" + k[2];
          var first = card(ds2[0]).match(/href="([^"]+)"/)[1].replace(/&amp;/g, "&");
          var href = first.indexOf("/#v") >= 0 ? first : first.split("#")[0];
          return '<li class="lg-fts-hit lg-fts-grouped"><p class="lg-fts-head"><a href="' + esc(href) + '"><b>' + esc(ref) + "</b></a> " +
            '<span class="lg-quiet">' + esc(ds2.length === 1 ? U.group_head_one : fmt(U.group_head, { n: ds2.length })) + "</span></p><ul>" +
            ds2.map(function (d) {
              var x = (d.meta.x || "").split("~"), w = x[0] === "b" ? null : U.works[+x[0]];
              var link = card(d).match(/href="([^"]+)"/)[1];
              return '<li><a href="' + link + '"><b>' + esc(w ? w[1] : U.owb) + "</b></a> " + '<span class="lg-fts-text">' + d.excerpt + "</span></li>";
            }).join("") + "</ul></li>";
        }).join("");
      });
    }
    // "Did you mean…": when a search finds little, each word not in the
    // excerpts' word list (/search-words.txt, commonest first) is offered
    // as the commonest word within a letter or two of it.
    var wordList = null;
    function didYouMean(q, mine) {
      if (!wordList) wordList = fetch("/search-words.txt").then(function (r) { return r.text(); }).then(function (t) {
        var list = t.trim().split(" "), set = {};
        list.forEach(function (w, i) { set[w] = i + 1; });
        return { list: list, set: set };
      });
      wordList.then(function (W) {
        if (mine !== run) return;
        var changed = false;
        var fixed = q.split(/\s+/).map(function (w) {
          var low = w.toLowerCase();
          if (low.length < 4 || /[^a-z]/.test(low)) return w;
          // A word in the list is offered another only twenty times commoner.
          var rank = W.set[low], max = low.length > 6 ? 2 : 1, upto = rank ? Math.floor(rank / 20) : W.list.length;
          for (var i = 0; i < upto; i++) {
            if (distance(low, W.list[i], max) <= max) { changed = true; return W.list[i]; }
          }
          return w;
        }).join(" ");
        if (!changed) return;
        var p = document.createElement("span");
        p.className = "lg-fts-dym";
        p.innerHTML = " " + esc(U.did_you_mean) + ' <a href="?q=' + encodeURIComponent(fixed) + '">' + esc(fixed) + "</a>?";
        status.appendChild(p);
        p.querySelector("a").addEventListener("click", function (ev) { ev.preventDefault(); input.value = fixed; search(); });
      });
    }
    // The results as a file or a list (data-export): the best U.export_top,
    // each with its reference, commentator, work, address and opening words.
    function exportRows() {
      return Promise.all(results.slice(0, U.export_top).map(function (r) { return r.data(); })).then(function (ds) {
        return ds.map(function (d) {
          var x = (d.meta.x || "").split("~"), bible = x[0] === "b", w = bible ? null : U.works[+x[0]];
          var ref = (U.books[+x[1]] || "") + " " + x[2] + ":" + x[3];
          if (!bible && (x[4] !== x[2] || x[5] !== x[3])) ref += "–" + (x[4] !== x[2] ? x[4] + ":" : "") + x[5];
          var link = location.origin + card(d).match(/href="([^"]+)"/)[1].replace(/&amp;/g, "&").replace(/\?hl=[^#]*/, "");
          var words = d.excerpt.replace(/<[^>]+>/g, "").replace(/&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
          return [ref, w ? w[1] : U.owb, w ? w[0] : "", link, words];
        });
      });
    }
    document.querySelectorAll("[data-export]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var kind = btn.getAttribute("data-export"), label = btn.textContent;
        btn.textContent = U.exporting;
        exportRows().then(function (rows) {
          var q = input.value.trim(), text;
          if (kind === "csv") {
            var cell = function (v) { return '"' + String(v).replace(/"/g, '""') + '"'; };
            text = [U.export_head.split("|")].concat(rows).map(function (r) { return r.map(cell).join(","); }).join("\r\n") + "\r\n";
            var a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob(["\ufeff" + text], { type: "text/csv;charset=utf-8" }));
            a.download = "logia-search-" + (q || "results").replace(/[^\w-]+/g, "-").slice(0, 40) + ".csv";
            document.body.appendChild(a); a.click(); a.remove();
            btn.textContent = label;
          } else {
            text = rows.map(function (r) { return r[0] + " — " + r[1] + (r[2] ? ", " + r[2] : "") + "\n" + r[3]; }).join("\n\n");
            (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () {
              btn.textContent = fmt(U.exported, { n: rows.length });
              setTimeout(function () { btn.textContent = label; }, 2500);
            }, function () { btn.textContent = label; });
          }
        });
      });
    });
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
    // One index's results for q and its old spellings, merged, best first.
    function findIn(m, q, f, more2) {
      return Promise.all([m.search(q || null, f)].concat(more2.queries.map(function (v) { return m.search(v, f); }))).then(function (all) {
        var seen = {}, merged = [];
        all.forEach(function (s) { s.results.forEach(function (r) { if (!seen[r.id]) { seen[r.id] = true; merged.push(r); } }); });
        return { results: merged, extra: all.slice(1).some(function (s) { return s.results.length; }) };
      });
    }
    // The chosen sources' results together, best first; srcCounts holds each one's number.
    // Sorted by date (the commentator's death, data-pagefind-sort="died"),
    // the old spellings are left out, so the order holds; the Bible's verses follow.
    var sortBy = document.getElementById("fts-sort");
    function find(q, f) {
      var order = sortBy.value;
      if (order) f = Object.assign({}, f, { sort: { died: order } });
      var on = sources(), more2 = q && !order ? variants(q) : { queries: [], words: [] };
      var jobs = [on.comm ? findIn(pf, q, f, more2) : Promise.resolve(null),
        on.bible && srcBible ? bibleIndex().then(function (m) { return findIn(m, q, f, more2); }) : Promise.resolve(null)];
      return Promise.all(jobs).then(function (two) {
        srcCounts = {};
        var merged = [], extra = false;
        two.forEach(function (x, i) {
          if (!x) return;
          srcCounts[on.names[i]] = x.results.length;
          merged = merged.concat(x.results);
          extra = extra || x.extra;
        });
        if (!order) merged.sort(function (a, b) { return b.score - a.score; });
        return { results: merged, oldWords: extra ? more2.words : [], bibleOff: !on.bible };
      });
    }
    // The examples and recent searches show only while the box is empty; a
    // search the reader submits is kept (five, newest first) in this browser.
    var tryBox = document.getElementById("fts-try");
    function recent() {
      try { return JSON.parse(localStorage.getItem("logia-fts-recent") || "[]"); } catch (err) { return []; }
    }
    if (tryBox) {
      var mine0 = recent(), box0 = tryBox.querySelector(".lg-fts-recent");
      if (mine0.length) {
        box0.querySelector("ul").innerHTML = mine0.map(function (q) {
          return '<li><a class="lg-fts-ex" href="/search/?q=' + encodeURIComponent(q) + '"><b>' + esc(q) + "</b></a></li>";
        }).join("");
        box0.hidden = false;
      }
      form.addEventListener("submit", function () {
        var q = input.value.trim();
        if (!q) return;
        var keepIt = [q].concat(recent().filter(function (x) { return x !== q; })).slice(0, 5);
        try { localStorage.setItem("logia-fts-recent", JSON.stringify(keepIt)); } catch (err) { /* storage blocked */ }
      });
    }
    function search() {
      var q = operators(), mine = ++run, any = Object.keys(filters()).length;
      if (tryBox) tryBox.hidden = !!(q || any);
      keep();
      if (!q && !any) { list.innerHTML = ""; more.hidden = true; view.hidden = true; status.textContent = U.start; chips(allCounts); return; }
      status.textContent = U.searching;
      find(q, { filters: filters() }).then(function (s) {
        if (mine !== run) return;
        results = s.results; shown = 0; list.innerHTML = "";
        chips({}, true);
        if (results.length <= COUNT_UP_TO && sources().comm) facetCounts(q).then(function (c) { if (mine === run) chips(c); }, function () { /* keep them bare */ });
        if (results.length < 20 && q) didYouMean(q, mine);
        status.innerHTML = esc(!results.length ? fmt(U.none, { q: q })
          : any ? fmt(U.count_filtered, { n: results.length.toLocaleString() })
          : fmt(results.length === 1 ? U.count_one : U.count, { n: results.length.toLocaleString(), q: q })) +
          (any ? ' <button type="button" class="cx-chip-all" data-clear>' + esc(U.clear) + "</button>" : "") +
          (s.oldWords && s.oldWords.length ? ' <span class="lg-quiet">' + esc(fmt(U.spelling_note, { words: s.oldWords.join(", ") })) + "</span>" : "") +
          (s.bibleOff && q && srcBible && !["era", "tradition", "commentator", "work"].some(function (k) { return chosen[k].length; }) ? ' <button type="button" class="cx-chip-all" data-also-bible>' + esc(U.also_bible) + "</button>" : "");
        view.hidden = results.length < 2;
        return grouping.checked && results.length > 1 ? showGroups(mine) : showMore();
      }).catch(function () { if (mine === run) status.textContent = U.failed; });
    }
    // Before anything is typed, the chips show the whole library's counts,
    // worked out when the site is built (search_page in scripts/build_site.py).
    allCounts = U.counts || {};
    import(src).then(function (m) {
      pf = m;
      return pf.options({ excerptLength: 36 });
    }).then(function () {
      search();
    }).catch(function () { status.textContent = U.failed; });
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { if (pf) search(); }, 250); });
    form.addEventListener("submit", function (e) { e.preventDefault(); if (pf) search(); });
    try { grouping.checked = localStorage.getItem("logia-search-group") === "1"; } catch (e) { /* storage blocked */ }
    sortBy.value = params.get("sort") || "";
    sortBy.addEventListener("change", function () { if (pf) search(); });
    grouping.addEventListener("change", function () {
      try { localStorage.setItem("logia-search-group", grouping.checked ? "1" : "0"); } catch (e) { /* storage blocked */ }
      if (pf) search();
    });
    form.addEventListener("click", function (e) {
      var b = e.target.closest("[data-k]");
      if (!b || !pf) return;
      var k = b.getAttribute("data-k"), v = b.getAttribute("data-v"), i = chosen[k].indexOf(v);
      if (i >= 0) chosen[k].splice(i, 1); else chosen[k].push(v);
      search();
    });
    who.addEventListener("change", function () { chosen.commentator = who.value ? [who.value] : []; if (pf) search(); });
    status.addEventListener("click", function (e) {
      if (e.target.closest("[data-also-bible]")) { chosen.source = sources().names.slice(); search(); return; }
      if (!e.target.closest("[data-clear]")) return;
      Object.keys(chosen).forEach(function (k) { chosen[k] = []; });
      search();
    });
    more.addEventListener("click", showMore);
  })();
})();
