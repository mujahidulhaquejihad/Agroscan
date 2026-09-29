/** App icons + Android permissions. Scan/chat use the hosted web app (no local models). */
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.join(__dirname, "..", "android");
const repo = path.join(__dirname, "..", "..");
const manifest = path.join(root, "app", "src", "main", "AndroidManifest.xml");

if (!fs.existsSync(manifest)) {
  console.error("No android/ project yet. Run: npx cap add android");
  process.exit(1);
}

const icons = spawnSync("python", [path.join(repo, "scripts", "make_app_icons.py")], {
  cwd: repo,
  stdio: "inherit",
  shell: true,
});
if (icons.status !== 0) {
  console.error("make_app_icons.py failed");
  process.exit(icons.status || 1);
}

let xml = fs.readFileSync(manifest, "utf8");
if (!xml.includes("ACCESS_NETWORK_STATE")) {
  xml = xml.replace(
    '<uses-permission android:name="android.permission.INTERNET" />',
    '<uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />'
  );
}
if (!xml.includes("ACCESS_FINE_LOCATION")) {
  xml = xml.replace(
    '<uses-permission android:name="android.permission.INTERNET" />',
    '<uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />\n    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />'
  );
}
if (!xml.includes("RECORD_AUDIO")) {
  xml = xml.replace(
    '<uses-permission android:name="android.permission.INTERNET" />',
    '<uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.RECORD_AUDIO" />\n    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />'
  );
}
fs.writeFileSync(manifest, xml);
console.log("patched AndroidManifest");
