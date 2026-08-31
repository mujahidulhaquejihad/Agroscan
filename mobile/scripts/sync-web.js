/**
 * Copy ../web → ./www and rewrite /static/... paths for Capacitor file serving.
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
  // HTML/CSS/JS/manifest references served as /static/foo on the server
  text = text.replace(/(["'`])\/static\//g, "$1./");
  text = text.replace(/href="\/static\//g, 'href="./');
  text = text.replace(/src="\/static\//g, 'src="./');
  // Capacitor does not use root /sw.js
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

function injectCapacitor(htmlPath) {
  let html = fs.readFileSync(htmlPath, "utf8");
  if (!html.includes("capacitor.js")) {
    html = html.replace(
      "</head>",
      '  <script src="capacitor.js"></script>\n</head>'
    );
    // Capacitor CLI injects capacitor.js on sync; keep a stub comment if missing
    html = html.replace(
      '<script src="capacitor.js"></script>',
      "<!-- capacitor.js injected by `npx cap sync` -->"
    );
  }
  // Ensure config loads first and production API works in native shell
  fs.writeFileSync(htmlPath, html);
}

console.log("Syncing", WEB, "->", WWW);
rmrf(WWW);
copyDir(WEB, WWW);
walk(WWW);

// Fix manifest icon paths already rewritten to ./icons/...
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

["index.html", "login.html", "signup.html", "logout.html"].forEach((f) => {
  const p = path.join(WWW, f);
  if (fs.existsSync(p)) injectCapacitor(p);
});

console.log("Done. www ready for Capacitor.");
