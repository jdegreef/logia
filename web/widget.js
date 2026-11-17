// Logia's "This Sunday" box for church websites (/widget/). A page adds
//   <div data-logia-sunday></div><script src="https://logia.faith/widget.js" defer></script>
// and the box shows the coming Sunday's Gospel (Revised Common Lectionary)
// with up to three voices from different traditions, each its own opening
// words and a link to Logia. It reads /widget/sundays.json (scripts/build_more.py),
// takes its fonts and colours from the page around it, and sends nothing about
// the page's visitors. Its words are filled in from the catalog (widget.ui)
// when scripts/build_more.py publishes it.
(function () {
  "use strict";
  var UI = /*UI*/{};
  var me = document.currentScript;
  var SITE = "https://logia.faith";
  try { if (me && me.src) SITE = new URL(me.src).origin; } catch (e) { /* keep the default */ }
  var boxes = document.querySelectorAll("[data-logia-sunday]");
  if (!boxes.length) return;
  var esc = function (s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  };
  if (!document.getElementById("logia-sunday-style")) {
    var st = document.createElement("style");
    st.id = "logia-sunday-style";
    st.textContent = ".logia-sunday{border:1px solid rgba(127,127,127,.35);border-radius:12px;padding:16px 18px;max-width:30rem;font:inherit;line-height:1.5}" +
      ".logia-sunday .ls-eyebrow{font-size:.75em;letter-spacing:.1em;text-transform:uppercase;opacity:.7;margin:0}" +
      ".logia-sunday .ls-ref{font-size:1.25em;font-weight:600;margin:.1em 0 .1em}.logia-sunday .ls-day{opacity:.75;margin:0 0 .6em;font-size:.9em}" +
      ".logia-sunday ul{list-style:none;margin:.4em 0;padding:0}.logia-sunday li{margin:.55em 0;padding-left:.7em;border-left:3px solid rgba(156,111,30,.6)}" +
      ".logia-sunday li b{display:block;font-size:.9em}.logia-sunday .ls-more{font-size:.9em;font-weight:600}";
    document.head.appendChild(st);
  }
  function today() {
    var d = new Date();
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function day(iso) {
    try { return new Date(iso + "T12:00:00").toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }); }
    catch (e) { return iso; }
  }
  fetch(SITE + "/widget/sundays.json").then(function (r) { return r.json(); }).then(function (all) {
    var now = today();
    var s = all.filter(function (x) { return x.d >= now; })[0] || all[all.length - 1];
    if (!s) return;
    var voices = s.v.length
      ? '<p class="ls-day">' + esc(UI.voices) + "</p><ul>" + s.v.map(function (v) {
        return '<li><b>' + esc(v.a) + "</b>" + esc(v.x) + ' <a href="' + esc(v.h) + '" rel="noopener">→</a></li>';
      }).join("") + "</ul>"
      : "<p>" + esc(UI.none) + "</p>";
    var html = '<div class="logia-sunday"><p class="ls-eyebrow">' + esc(UI.eyebrow) + " · Logia</p>" +
      '<p class="ls-ref"><a href="' + esc(s.h) + '" rel="noopener">' + esc(s.g) + "</a></p>" +
      '<p class="ls-day">' + esc(day(s.d)) + " · " + esc(s.n) + "</p>" + voices +
      '<p><a class="ls-more" href="' + esc(s.h) + '" rel="noopener">' + esc(UI.more) + " ›</a></p></div>";
    boxes.forEach(function (b) { b.innerHTML = html; });
  }).catch(function () { /* the page around it stays as it was */ });
})();
