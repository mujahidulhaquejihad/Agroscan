(function (w) {
  var API = (w.AGROSCAN_CONFIG && w.AGROSCAN_CONFIG.API_BASE) || "";

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function toast(msg) {
    var el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "toast show";
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.className = "toast"; }, 2600);
  }

  function formatDetail(detail) {
    if (detail == null || detail === "") return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map(function (d) {
        if (!d) return "";
        if (typeof d === "string") return d;
        if (d.msg) return d.msg;
        try { return JSON.stringify(d); } catch (e) { return String(d); }
      }).filter(Boolean).join("; ") || "Request failed";
    }
    if (typeof detail === "object" && detail.msg) return detail.msg;
    try { return JSON.stringify(detail); } catch (e) { return String(detail); }
  }

  function xhr(method, path, body, token, ok, fail) {
    var x = new XMLHttpRequest();
    x.open(method, API + path, true);
    if (token) x.setRequestHeader("Authorization", "Bearer " + token);
    if (body != null) x.setRequestHeader("Content-Type", "application/json");
    x.onload = function () {
      var data = {};
      try { data = x.responseText ? JSON.parse(x.responseText) : {}; }
      catch (e) {
        if (x.status >= 200 && x.status < 300) return fail("Invalid JSON response");
      }
      if (x.status >= 200 && x.status < 300) ok(data);
      else fail(formatDetail(data.detail) || ("HTTP " + x.status));
    };
    x.onerror = function () { fail("Network error"); };
    x.send(body != null ? JSON.stringify(body) : null);
  }

  function money(n) {
    return Math.round(Number(n) || 0).toLocaleString();
  }

  function bindPasswordToggles() {
    var toggles = document.querySelectorAll(".password-toggle");
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].onclick = function () {
        var input = $(this.getAttribute("data-target"));
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        var a = this.querySelector(".pw-icon-show");
        var b = this.querySelector(".pw-icon-hide");
        if (a) a.className = show ? "pw-icon-show hidden" : "pw-icon-show";
        if (b) b.className = show ? "pw-icon-hide" : "pw-icon-hide hidden";
      };
    }
  }

  function authFail(msg) {
    var s = String(msg || "").toLowerCase();
    return s.indexOf("token") >= 0 || s.indexOf("sign-in") >= 0 || s.indexOf("401") >= 0 || s.indexOf("password") >= 0 || s.indexOf("admin") >= 0 || s.indexOf("vendor") >= 0;
  }

  w.AgroOps = {
    API: API,
    $: $,
    esc: esc,
    toast: toast,
    xhr: xhr,
    money: money,
    bindPasswordToggles: bindPasswordToggles,
    authFail: authFail,
    t: function (key, vars) {
      return (w.AgroScanI18n && w.AgroScanI18n.t) ? w.AgroScanI18n.t(key, vars) : key;
    },
    st: function (status) {
      var key = "ops_st_" + String(status || "");
      var v = (w.AgroScanI18n && w.AgroScanI18n.t) ? w.AgroScanI18n.t(key) : key;
      return v === key ? String(status || "") : v;
    }
  };

  function bootChrome() {
    var btn = document.getElementById("langToggle");
    if (btn && w.AgroScanI18n) {
      btn.onclick = function () { w.AgroScanI18n.toggleLang(); };
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootChrome);
  else bootChrome();
})(window);
