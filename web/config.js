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

  function isNativeShell() {
    if (isCapacitor()) return true;
    var loc = window.location;
    if (loc.protocol === "capacitor:") return true;
    if (loc.protocol === "file:") return true;
    // Capacitor androidScheme "https" serves as https://localhost (no port)
    if (
      loc.protocol === "https:" &&
      (loc.hostname === "localhost" || loc.hostname === "127.0.0.1") &&
      (!loc.port || loc.port === "443")
    ) {
      return true;
    }
    return false;
  }

  function apiBase() {
    if (isNativeShell()) return PRODUCTION_API;
    var loc = window.location;
    if (loc.protocol === "http:" || loc.protocol === "https:") return "";
    return "";
  }

  function appPath(name) {
    var native = isNativeShell();
    if (!name || name === "home") return native ? "./index.html" : "/";
    return native ? "./" + name + ".html" : "/" + name;
  }

  window.AGROSCAN_CONFIG = {
    API_BASE: apiBase(),
    PRODUCTION_API: PRODUCTION_API,
    appPath: appPath,
    isNative: isNativeShell,
    // Google OAuth Web Client ID (Cloud Console → Credentials).
    // Authorized JavaScript origins:
    //   http://localhost:8000
    //   https://localhost
    //   https://agroscan.mujahidulhaquejihad.com
    GOOGLE_CLIENT_ID: "145820214796-5fl72t2u8e2mnfa73n94ejk1kv3v69af.apps.googleusercontent.com",
  };

  function connLabel(on) {
    var I = window.AgroScanI18n;
    var key = on === null ? "conn_wait" : on ? "conn_on" : "conn_off";
    if (I && typeof I.t === "function") return I.t(key);
    return on === null ? "…" : on ? "Online" : "Offline";
  }

  function setConn(on) {
    var el = document.getElementById("connSign");
    if (!el) return;
    el.className = "conn-sign" + (on === null ? "" : on ? " on" : " off");
    var text = connLabel(on);
    el.setAttribute("aria-label", text);
    el.title = text;
    var lab = el.querySelector("span");
    if (lab) lab.textContent = text;
  }

  function pingConn() {
    var x = new XMLHttpRequest();
    x.timeout = 8000;
    x.onload = function () {
      setConn(x.status >= 200 && x.status < 300);
    };
    x.onerror = function () { setConn(false); };
    x.ontimeout = function () { setConn(false); };
    x.open("GET", apiBase() + "/api/status");
    x.send();
  }

  function bootConn() {
    if (document.getElementById("connSign")) return;
    var el = document.createElement("button");
    el.id = "connSign";
    el.type = "button";
    el.className = "conn-sign";
    el.innerHTML = "<span></span>";
    el.onclick = function () {
      setConn(null);
      pingConn();
    };
    var tools = document.querySelector(".header-tools");
    var authBar = document.querySelector(".auth-topbar");
    var lang = document.getElementById("langToggle");
    if (tools) {
      if (lang && lang.parentNode === tools) tools.insertBefore(el, lang);
      else tools.insertBefore(el, tools.firstChild);
    } else if (authBar) {
      if (lang && lang.parentNode === authBar) authBar.insertBefore(el, lang);
      else authBar.appendChild(el);
    } else {
      return;
    }
    setConn(null);
    pingConn();
    setInterval(pingConn, 10000);
    window.addEventListener("online", pingConn);
    window.addEventListener("offline", function () { setConn(false); });
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) pingConn();
    });
    document.addEventListener("langchange", function () {
      var on = el.classList.contains("on") ? true : el.classList.contains("off") ? false : null;
      setConn(on);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { setTimeout(bootConn, 0); });
  } else {
    setTimeout(bootConn, 0);
  }
})();
