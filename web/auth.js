/* AgroVet auth: login, signup, guest, Google, session header UI */
(function () {
  var cfg = window.AGROVET_CONFIG || {};
  var API = cfg.API_BASE || "";
  var KEY = "agrovet_session";

  function $(id) { return document.getElementById(id); }

  function T(key, vars) {
    return window.AgrovetI18n ? window.AgrovetI18n.t(key, vars) : key;
  }

  function getSession() {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); }
    catch (e) { return null; }
  }

  function setSession(data) {
    localStorage.setItem(KEY, JSON.stringify(data));
    renderHeader();
  }

  function clearSession() {
    localStorage.removeItem(KEY);
    renderHeader();
  }

  function authHeaders() {
    var s = getSession();
    if (s && s.token) return { Authorization: "Bearer " + s.token };
    return {};
  }

  function xhrJson(method, path, body, ok, fail) {
    var x = new XMLHttpRequest();
    x.open(method, API + path, true);
    x.setRequestHeader("Content-Type", "application/json");
    var h = authHeaders();
    if (h.Authorization) x.setRequestHeader("Authorization", h.Authorization);
    x.timeout = 20000;
    x.onload = function () {
      try {
        var data = x.responseText ? JSON.parse(x.responseText) : {};
        if (x.status >= 200 && x.status < 300) ok(data);
        else fail((data.detail && (typeof data.detail === "string" ? data.detail : data.detail.msg || JSON.stringify(data.detail))) || ("HTTP " + x.status));
      } catch (e) { fail("Bad response"); }
    };
    x.onerror = function () { fail("Network error"); };
    x.ontimeout = function () { fail("Request timed out"); };
    x.send(body ? JSON.stringify(body) : null);
  }

  function renderHeader() {
    var area = $("authArea");
    if (!area) return;
    var s = getSession();
    if (!s || !s.user) {
      area.innerHTML =
        '<a href="/login" class="btn btn-outline btn-sm">' + T("auth_login") + '</a>' +
        '<a href="/signup" class="btn btn-primary btn-sm">' + T("auth_signup") + '</a>';
      return;
    }
    var u = s.user;
    var pic = u.picture ? '<img src="' + u.picture + '" alt="" class="avatar">' : '<span class="avatar avatar-text">' + (u.name || "U").charAt(0).toUpperCase() + "</span>";
    var displayName = u.provider === "guest" ? T("auth_guest") : (u.name || T("auth_user"));
    var badge = u.provider === "guest" ? '<span class="user-badge">' + T("auth_guest") + '</span>' : "";
    area.innerHTML =
      '<div class="user-menu">' + pic +
      '<a class="user-name user-account-link" href="/account" title="' + T("account_kicker") + '">' + displayName + "</a>" + badge +
      '<a href="/account" class="btn btn-secondary btn-sm account-link-btn">' + T("account_kicker") + "</a>" +
      '<a href="/logout" class="btn btn-ghost btn-sm auth-logout-btn" title="' + T("auth_logout") + '" aria-label="' + T("auth_logout") + '">' +
      '<span class="auth-logout-icon" aria-hidden="true">&#128682;</span>' +
      '<span class="auth-logout-label">' + T("auth_logout") + "</span></a></div>";
  }

  function logout() {
    var s = getSession();
    if (s && s.token) {
      xhrJson("POST", "/api/auth/logout", {}, function () {}, function () {});
    }
    clearSession();
    if (window.location.pathname !== "/") window.location.href = "/login";
  }

  function loginGuest() {
    setSession({
      token: null,
      user: { name: "Guest", email: null, provider: "guest", picture: null },
    });
    window.location.href = "/";
  }

  function saveAuthResponse(data) {
    setSession({ token: data.token, user: data.user });
    window.location.href = "/";
  }

  function loginEmail(email, password, errEl) {
    xhrJson("POST", "/api/auth/login", { email: email, password: password }, saveAuthResponse, function (m) {
      if (errEl) { errEl.textContent = m; errEl.className = "auth-error"; }
    });
  }

  function signupEmail(name, email, password, profile, errEl) {
    var body = {
      name: name,
      email: email,
      password: password,
      phone: (profile && profile.phone) || "",
      address: (profile && profile.address) || "",
      district: (profile && profile.district) || "",
      upazila: (profile && profile.upazila) || ""
    };
    xhrJson("POST", "/api/auth/signup", body, saveAuthResponse, function (m) {
      if (errEl) { errEl.textContent = m; errEl.className = "auth-error"; }
    });
  }

  function initPasswordToggles() {
    var btns = document.querySelectorAll(".password-toggle");
    var i;
    for (i = 0; i < btns.length; i++) {
      btns[i].onclick = function () {
        var id = this.getAttribute("data-target");
        var input = id ? $(id) : null;
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        var showIcon = this.querySelector(".pw-icon-show");
        var hideIcon = this.querySelector(".pw-icon-hide");
        if (showIcon) showIcon.className = show ? "pw-icon-show hidden" : "pw-icon-show";
        if (hideIcon) hideIcon.className = show ? "pw-icon-hide" : "pw-icon-hide hidden";
        this.setAttribute("aria-label", show ? T("hide_password") : T("show_password"));
        this.setAttribute("title", show ? T("hide_password") : T("show_password"));
      };
    }
  }

  function decodeJwt(token) {
    try { return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); }
    catch (e) { return null; }
  }

  function googleCredential(response) {
    var p = decodeJwt(response.credential);
    if (!p) return;
    if (cfg.GOOGLE_CLIENT_ID) {
      xhrJson("POST", "/api/auth/google", {
        id_token: response.credential,
        client_id: cfg.GOOGLE_CLIENT_ID,
      }, saveAuthResponse, function () {
        setSession({
          token: null,
          user: { name: p.name, email: p.email, picture: p.picture, provider: "google" },
        });
        window.location.href = "/";
      });
    } else {
      setSession({
        token: null,
        user: { name: p.name, email: p.email, picture: p.picture, provider: "google" },
      });
      window.location.href = "/";
    }
  }

  function initGoogleButton(containerId) {
    var el = $(containerId);
    if (!el) return;
    if (!cfg.GOOGLE_CLIENT_ID) {
      el.innerHTML = '<button type="button" class="btn btn-google" id="googleSetupBtn">' +
        '<span class="g-icon">G</span> ' + T("google_signin") + '</button>' +
        '<p class="auth-hint">' + T("google_hint") + '</p>';
      var b = $("googleSetupBtn");
      if (b) b.onclick = function () {
        alert("1. Go to Google Cloud Console\n2. Create OAuth Web Client ID\n3. Add http://localhost:8000 to Authorized origins\n4. Paste ID in web/config.js as GOOGLE_CLIENT_ID");
      };
      return;
    }
    function tryRender(n) {
      if (window.google && google.accounts && google.accounts.id) {
        google.accounts.id.initialize({ client_id: cfg.GOOGLE_CLIENT_ID, callback: googleCredential });
        google.accounts.id.renderButton(el, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "pill",
          width: 320,
        });
      } else if (n < 30) {
        setTimeout(function () { tryRender(n + 1); }, 200);
      }
    }
    tryRender(0);
  }

  function initAuthPage() {
    var guestBtn = $("guestBtn");
    if (guestBtn) guestBtn.onclick = loginGuest;
    initPasswordToggles();

    var loginForm = $("loginForm");
    if (loginForm) {
      loginForm.onsubmit = function (e) {
        e.preventDefault();
        var err = $("authError");
        if (err) err.className = "auth-error hidden";
        loginEmail($("email").value, $("password").value, err);
      };
    }

    var signupForm = $("signupForm");
    if (signupForm) {
      signupForm.onsubmit = function (e) {
        e.preventDefault();
        var err = $("authError");
        if (err) err.className = "auth-error hidden";
        var p1 = $("password").value, p2 = $("password2").value;
        if (p1.length < 6) { if (err) { err.textContent = T("auth_err_password_len"); err.className = "auth-error"; } return; }
        if (p1 !== p2) { if (err) { err.textContent = T("auth_err_password_match"); err.className = "auth-error"; } return; }
        signupEmail($("name").value, $("email").value, p1, {
          phone: ($("phone") && $("phone").value) || "",
          address: ($("address") && $("address").value) || "",
          district: ($("district") && $("district").value) || "",
          upazila: ($("upazila") && $("upazila").value) || ""
        }, err);
      };
    }

    initGoogleButton("googleBtn");
  }

  window.AgrovetAuth = {
    getSession: getSession,
    setSession: setSession,
    clearSession: clearSession,
    logout: logout,
    renderHeader: renderHeader,
    initAuthPage: initAuthPage,
    loginGuest: loginGuest,
  };

  function boot() {
    renderHeader();
    if ($("loginForm") || $("signupForm")) initAuthPage();
  }

  document.addEventListener("langchange", function () {
    renderHeader();
    if ($("googleBtn")) initGoogleButton("googleBtn");
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
