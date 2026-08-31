// AgroScan web config.
(function () {
  // Must match the hostname you open in the browser (Cloudflare Tunnel).
  var PRODUCTION_API = "https://agroscan.mujahidulhaquejihad.com";

  function isCapacitor() {
    try {
      if (!window.Capacitor) return false;
      if (typeof window.Capacitor.isNativePlatform === "function") {
        return window.Capacitor.isNativePlatform();
      }
      return true;
    } catch (e) {
      return false;
    }
  }

  function apiBase() {
    // Native Android/iOS shell → always use the hosted API
    if (isCapacitor()) return PRODUCTION_API;

    var loc = window.location;
    if (loc.protocol === "capacitor:") return PRODUCTION_API;
    // Capacitor androidScheme "https" serves as https://localhost (no port)
    if (
      loc.protocol === "https:" &&
      (loc.hostname === "localhost" || loc.hostname === "127.0.0.1") &&
      (!loc.port || loc.port === "443")
    ) {
      return PRODUCTION_API;
    }
    if (loc.protocol === "file:") return "http://127.0.0.1:8000";
    // Browser / PWA on the real site: same origin
    if (loc.protocol === "http:" || loc.protocol === "https:") return "";
    return "";
  }

  window.AGROSCAN_CONFIG = {
    API_BASE: apiBase(),
    PRODUCTION_API: PRODUCTION_API,
    // Google OAuth Web Client ID (Cloud Console → Credentials).
    // Add http://localhost:8000 and https://agroscan.mujahidulhaquejihad.com
    // to Authorized JavaScript origins.
    GOOGLE_CLIENT_ID: "145820214796-5fl72t2u8e2mnfa73n94ejk1kv3v69af.apps.googleusercontent.com",
  };
})();
