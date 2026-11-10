// Draws the app icons in web/icons/ from Logia's mark (MARK_INNER in
// scripts/build_site.py), for the web app manifest and iOS home screens.
//
//   npm install --no-save playwright@1.49.1 && node scripts/make_icons.js
//
// Run it again only when the mark changes; the PNGs are committed.

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { chromium } = require("playwright");

const OUT = path.join(__dirname, "..", "web", "icons");
const MARK = execFileSync("python3", ["-c", "import sys; sys.path.insert(0, 'scripts'); import build_site; print(build_site.MARK_INNER)"],
  { cwd: path.join(__dirname, ".."), encoding: "utf8" }).trim();
const GOLD = "#9a6a1c";
// name, size, and whether the tile fills the square (maskable and iOS icons
// are cut to shape by the system, so the book sits in the middle 70%).
const ICONS = [["icon-192.png", 192, false], ["icon-512.png", 512, false],
  ["maskable-512.png", 512, true], ["apple-touch-icon.png", 180, true]];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  for (const [name, size, full] of ICONS) {
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    const inner = full ? MARK.replace(/<rect[^>]*\/>/, "") : MARK;
    const svg = full
      ? `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 64 64"><rect width="64" height="64" fill="${GOLD}"/><g transform="translate(9.6 9.6) scale(.7)">${inner}</g></svg>`
      : `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 64 64">${inner}</svg>`;
    await page.setContent(`<style>html,body{margin:0;background:transparent}</style>${svg}`);
    await page.screenshot({ path: path.join(OUT, name), omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
    await page.close();
  }
  await browser.close();
})();
