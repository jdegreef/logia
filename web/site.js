// Logia's site script, taken from the Open Word Bible's web/site.js (MIT) so
// the two sites behave alike: the settings menu and the header's menus.
//
// The settings menu behind the gear in the header (see prefs_menu in
// scripts/build_site.py): the colour mode, the reading text's size, typeface
// and line spacing, motion, and Logia's own settings: which translation level
// the Bible text opens in and whether commentary excerpts show in full. Each
// radiogroup is one setting (data-pref); a
// choice is kept in localStorage as logia-<pref> and applied as data-<pref> on
// <html>, and the default (data-default; "light", Paper, for the colour mode)
// removes both. "auto" is a choice like any other: it follows the device. The inline boot script in each page
// applies saved choices before paint.
(function () {
  "use strict";
  var MODES = ["auto", "light", "sepia", "dark", "night", "contrast"];
  var root = document.documentElement;
  var button = document.querySelector(".prefs-btn");
  var menu = document.getElementById("colour-menu");
  if (!button || !menu) return;
  var groups = Array.prototype.slice.call(menu.querySelectorAll("[data-pref]"));

  function optionsOf(group) {
    return Array.prototype.slice.call(group.querySelectorAll("[data-value]"));
  }

  function current(group) {
    var pref = group.getAttribute("data-pref");
    var v = root.getAttribute("data-" + pref);
    var known = pref === "theme" ? MODES.indexOf(v) >= 0
      : optionsOf(group).some(function (o) { return o.getAttribute("data-value") === v; });
    return known ? v : group.getAttribute("data-default");
  }

  function mark(group) {
    var value = current(group);
    optionsOf(group).forEach(function (o) {
      var on = o.getAttribute("data-value") === value;
      o.setAttribute("aria-checked", on ? "true" : "false");
      o.tabIndex = on ? 0 : -1;
    });
  }

  function choose(group, value) {
    var pref = group.getAttribute("data-pref");
    var isDefault = value === group.getAttribute("data-default");
    if (isDefault) root.removeAttribute("data-" + pref);
    else root.setAttribute("data-" + pref, value);
    try {
      if (isDefault) localStorage.removeItem("logia-" + pref);
      else localStorage.setItem("logia-" + pref, value);
    } catch (e) { /* storage blocked: the choice lasts for this page only */ }
    mark(group);
    document.dispatchEvent(new CustomEvent("logia:prefs", { detail: { pref: pref, value: value } }));
  }

  function open(show) {
    menu.hidden = !show;
    button.setAttribute("aria-expanded", show ? "true" : "false");
    if (show) {
      var on = optionsOf(groups[0]).filter(function (o) { return o.tabIndex === 0; })[0] || optionsOf(groups[0])[0];
      on.focus();
    }
  }

  // For other scripts (web/reader.js): read a setting, or change one as the
  // menu would.
  window.LogiaPrefs = {
    get: function (pref) {
      var group = groups.filter(function (g) { return g.getAttribute("data-pref") === pref; })[0];
      return group ? current(group) : null;
    },
    set: function (pref, value) {
      var group = groups.filter(function (g) { return g.getAttribute("data-pref") === pref; })[0];
      if (group) choose(group, value);
    }
  };

  button.addEventListener("click", function () { groups.forEach(mark); open(menu.hidden); });
  groups.forEach(function (group) {
    var options = optionsOf(group);
    options.forEach(function (o, i) {
      o.addEventListener("click", function () { choose(group, o.getAttribute("data-value")); });
      o.addEventListener("keydown", function (e) {
        var step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
        if (!step) return;
        e.preventDefault();
        var next = options[(i + step + options.length) % options.length];
        choose(group, next.getAttribute("data-value"));
        next.focus();
      });
    });
    mark(group);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !menu.hidden) { open(false); button.focus(); }
  });
  document.addEventListener("click", function (e) {
    if (!menu.hidden && !menu.contains(e.target) && !button.contains(e.target)) open(false);
  });
})();

// The header's section dropdowns (Read, Commentators, About), and the menu
// button that shows the links on narrow screens, where each dropdown opens
// in place (see site_header in scripts/build_site.py). One dropdown is open
// at a time; Escape, a click elsewhere or tabbing away closes it.
(function () {
  "use strict";
  var nav = document.getElementById("site-nav");
  var menuBtn = document.querySelector(".menu-btn");
  if (!nav) return;
  var triggers = Array.prototype.slice.call(nav.querySelectorAll(".nav-trigger"));

  function panel(t) { return document.getElementById(t.getAttribute("aria-controls")); }

  function setOpen(t, show) {
    var p = panel(t);
    p.hidden = !show;
    t.setAttribute("aria-expanded", show ? "true" : "false");
    if (show) keepOnScreen(p);
  }

  // A panel is centred under its trigger; nudge it back inside the window
  // (16px clear of each edge) when that would run off one side.
  function keepOnScreen(p) {
    p.style.setProperty("--dd-shift", "0px");
    if (getComputedStyle(p).position !== "absolute") return;
    var r = p.getBoundingClientRect();
    var room = document.documentElement.clientWidth - 16;
    var shift = r.left < 16 ? 16 - r.left : r.right > room ? room - r.right : 0;
    p.style.setProperty("--dd-shift", shift + "px");
  }

  function openOne(t) {
    triggers.forEach(function (o) { if (o !== t) setOpen(o, false); });
    setOpen(t, true);
  }

  function closeAll() { triggers.forEach(function (t) { setOpen(t, false); }); }

  function openTrigger() {
    return triggers.filter(function (t) { return t.getAttribute("aria-expanded") === "true"; })[0];
  }

  function showMenu(show) {
    nav.classList.toggle("open", show);
    if (menuBtn) menuBtn.setAttribute("aria-expanded", show ? "true" : "false");
    if (!show) closeAll();
  }

  triggers.forEach(function (t) {
    t.addEventListener("click", function () {
      if (t.getAttribute("aria-expanded") === "true") setOpen(t, false);
      else openOne(t);
    });
    // Down arrow on a closed trigger opens it and moves into the panel.
    t.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowDown") return;
      e.preventDefault();
      openOne(t);
      var first = panel(t).querySelector("a");
      if (first) first.focus();
    });
    // Leaving an open item by keyboard closes its panel.
    t.parentNode.addEventListener("focusout", function (e) {
      var to = e.relatedTarget;
      if (to && !t.parentNode.contains(to)) setOpen(t, false);
    });
  });

  if (menuBtn) {
    menuBtn.addEventListener("click", function () {
      var show = !nav.classList.contains("open");
      showMenu(show);
      if (show) nav.querySelector(".nav-link").focus();
    });
  }

  // Following a link closes the menus, so one to a place on this page
  // isn't left under them.
  nav.addEventListener("click", function (e) {
    if (e.target.closest("a")) showMenu(false);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var t = openTrigger();
    if (t) { setOpen(t, false); t.focus(); }
    else if (nav.classList.contains("open")) { showMenu(false); menuBtn.focus(); }
  });
  document.addEventListener("click", function (e) {
    if (nav.contains(e.target) || (menuBtn && menuBtn.contains(e.target))) return;
    closeAll();
    if (nav.classList.contains("open")) showMenu(false);
  });
  // Tabbing out of the open narrow-screen menu closes it too.
  nav.addEventListener("focusout", function (e) {
    var to = e.relatedTarget;
    if (to && nav.classList.contains("open") && !nav.contains(to) && !(menuBtn && menuBtn.contains(to))) showMenu(false);
  });
})();
