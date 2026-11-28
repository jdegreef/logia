// Accessibility audit of the built site: axe-core on a sample of pages, in
// each colour theme, in Chromium. It fails on any violation axe rates
// serious or critical, and lists the moderate ones.
//
//   python3 scripts/build_site.py
//   npm install --no-save playwright@1.49.1 axe-core@4.10.2 && npx playwright install chromium
//   node scripts/a11y_audit.js
//
// It serves site/ itself, so nothing else need be running.

const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const SITE = path.join(__dirname, "..", "site");
const AXE = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
// One page of each kind: home, the book list, a book, chapters with and
// without commentary and with verses left out, the commentators, a
// commentator, a work, one of its chapters, a verse, a passage the churches
// read differently, About, the open data and the word search.
const PAGES = ["/", "/read/", "/jhn/", "/jhn/3/", "/jhn/8/", "/rom/8/", "/gen/1/", "/commentators/",
  "/commentators/calvin/", "/works/chrysostom/", "/works/chrysostom/jhn/1/", "/jhn/1/1/", "/differ/matthew-16-rock/",
  "/about/", "/open-data/", "/topics/", "/topics/baptism/", "/search/", "/who-names-whom/", "/jhn/3/side-by-side/",
  // Every other kind of page: creeds, the glossary, the readings, Saved, a homily, the most-discussed
  // verses, the plans, the quiz, what's new, Explore, and a search with its results.
  "/creeds/", "/creeds/apostles/", "/creeds/compare/", "/glossary/", "/readings/", "/saved/", "/works/chrysostom/24/",
  "/most-discussed/", "/jhn/most-discussed/", "/differ/", "/plans/", "/quiz/", "/new/", "/explore/", "/search/?q=grace",
  // Two commentators across a book, and a Sunday's page (built for every day the lectionary data holds).
  "/jhn/side-by-side/", "/readings/2026-12-20/"];
const THEMES = ["light", "sepia", "dark", "night"];
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };

function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split("?")[0]);
      let file = path.join(SITE, p);
      if (p.endsWith("/")) file = path.join(file, "index.html");
      if (!file.startsWith(SITE) || !fs.existsSync(file)) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

(async () => {
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  let failed = 0;
  for (const theme of THEMES) {
    const page = await browser.newPage();
    // The theme the settings menu would keep (web/site.js); the API is offline here.
    await page.addInitScript((t) => { try { localStorage.setItem("logia-theme", t); } catch (e) { /* blocked */ } }, theme);
    await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => route.abort());
    for (const p of PAGES) {
      if (!fs.existsSync(path.join(SITE, p.split("?")[0], "index.html"))) continue;
      await page.goto(base + p, { waitUntil: "load" });
      await page.waitForTimeout(p.includes("?") ? 2500 : 400);   // a search's results arrive after the page
      await page.addScriptTag({ content: AXE });
      const found = await page.evaluate(async () => (await window.axe.run(document, { resultTypes: ["violations"] })).violations
        .map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map((n) => n.target.join(" ")) })));
      for (const v of found) {
        const serious = v.impact === "serious" || v.impact === "critical";
        if (serious) failed++;
        console.log(`${serious ? "FAIL" : "note"} ${theme} ${p} ${v.id} (${v.impact}): ${v.help}`);
        v.nodes.slice(0, 3).forEach((n) => console.log(`       ${n}`));
      }
    }
    await page.close();
  }
  await browser.close();
  server.close();
  console.log(failed ? `${failed} serious or critical accessibility problems` : "No serious or critical accessibility problems");
  process.exit(failed ? 1 : 0);
})();
