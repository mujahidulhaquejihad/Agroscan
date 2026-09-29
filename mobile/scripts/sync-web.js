/**
 * Copy ../web → ./www and rewrite /static/... paths for Capacitor file serving.
 * No on-device models — scan/chat hit https://agroscan.mujahidulhaquejihad.com
 */
const fs = require("fs");
const path = require("path");

const MOBILE = path.resolve(__dirname, "..");
const WEB = path.join(MOBILE, "..", "web");
const WWW = path.join(MOBILE, "www");

function rmrf(dir) {
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
}

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    if (name === "sw.js") continue; // SW is for hosted PWA only
    const from = path.join(src, name);
    const to = path.join(dest, name);
    let st;
    try {
      st = fs.statSync(from);
    } catch (e) {
      console.warn("Skipping missing path:", from);
      continue;
    }
    if (st.isDirectory()) copyDir(from, to);
    else fs.copyFileSync(from, to);
  }
}

function rewriteFile(filePath) {
  let text = fs.readFileSync(filePath, "utf8");
  text = text.replace(/(["'`])\/static\//g, "$1./");
  text = text.replace(/href="\/static\//g, 'href="./');
  text = text.replace(/src="\/static\//g, 'src="./');
  text = text.replace(/<script[^>]*pwa\.js[^>]*><\/script>\s*/g, "");
  text = text.replace(/navigator\.serviceWorker\.register\([^)]*\);?/g, "");
  fs.writeFileSync(filePath, text);
}

function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p);
    else if (/\.(html|js|css|json)$/i.test(name)) rewriteFile(p);
  }
}

console.log("Syncing", WEB, "->", WWW);
rmrf(WWW);
copyDir(WEB, WWW);
walk(WWW);

const manifestPath = path.join(WWW, "manifest.json");
if (fs.existsSync(manifestPath)) {
  const m = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  m.start_url = "./index.html";
  m.scope = "./";
  m.icons = (m.icons || []).map((icon) => ({
    ...icon,
    src: icon.src.replace(/^\.?\/?static\//, "./").replace(/^\//, "./"),
  }));
  fs.writeFileSync(manifestPath, JSON.stringify(m, null, 2));
}

console.log("Done. www ready for Capacitor (no local models).");
