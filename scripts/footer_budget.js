// The footer's height budget: on a sample of pages, the footer (with its
// site map folded, as it first shows) must fit in about one laptop screen
// and two phone screens, so that adding books never makes it grow again.
//
//   python3 scripts/build_site.py
//   npm install --no-save playwright@1.49.1 && npx playwright install chromium
//   node scripts/footer_budget.js
//
// It serves site/ itself, so nothing else need be running.

const http = require("http");
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const SITE = path.join(__dirname, "..", "site");
// Home, a book, a chapter, a verse, a commentator and About.
const PAGES = ["/", "/rom/", "/jhn/3/", "/jhn/3/16/", "/commentators/calvin/", "/about/"];
// [width, most pixels the footer may take]
const BUDGETS = [[1280, 800], [390, 1500]];
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };

function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const p = decodeURIComponent(req.url.split("?")[0]);
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
  for (const [width, most] of BUDGETS) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => route.abort());
    for (const p of PAGES) {
      if (!fs.existsSync(path.join(SITE, p, "index.html"))) continue;
      await page.goto(base + p, { waitUntil: "load" });
      await page.waitForTimeout(300);
      const h = Math.round(await page.evaluate(() => document.querySelector("footer.site").getBoundingClientRect().height));
      const ok = h <= most;
      if (!ok) failed++;
      console.log(`${ok ? "ok  " : "FAIL"} ${width}px ${p}: footer ${h}px (budget ${most}px)`);
    }
    await page.close();
  }
  await browser.close();
  server.close();
  if (failed) {
    console.error(`${failed} page(s) over the footer's height budget`);
    process.exit(1);
  }
})();
