/* AgroScan account page: profile + order tracking */
(function () {
  var API = (window.AGROSCAN_CONFIG && window.AGROSCAN_CONFIG.API_BASE) || "";
  var STEPS = ["pending", "confirmed", "processing", "shipped", "delivered"];

  function $(id) { return document.getElementById(id); }
  function T(key, vars) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key, vars) : key;
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function session() {
    return window.AgroScanAuth ? window.AgroScanAuth.getSession() : null;
  }
  function token() {
    var s = session();
    return s && s.token ? s.token : "";
  }
  function isRealUser() {
    var s = session();
    return !!(s && s.user && s.token && s.user.provider !== "guest");
  }

  function xhr(method, path, body, ok, fail) {
    var x = new XMLHttpRequest();
    x.open(method, API + path, true);
    x.setRequestHeader("Content-Type", "application/json");
    var t = token();
    if (t) x.setRequestHeader("Authorization", "Bearer " + t);
    x.onload = function () {
      var data = {};
      try { data = x.responseText ? JSON.parse(x.responseText) : {}; } catch (e) {}
      if (x.status >= 200 && x.status < 300) ok(data);
      else {
        var d = data.detail;
        fail(typeof d === "string" ? d : (d && d.msg) || ("HTTP " + x.status));
      }
    };
    x.onerror = function () { fail("Network error"); };
    x.send(body != null ? JSON.stringify(body) : null);
  }

  function fmtWhen(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso);
      return d.toLocaleString();
    } catch (e) {
      return String(iso);
    }
  }

  function statusLabel(st) {
    var key = "order_status_" + st;
    var t = T(key);
    return t === key ? st : t;
  }

  function timelineHtml(order) {
    var cur = order.status || "pending";
    var cancelled = cur === "cancelled";
    var idx = STEPS.indexOf(cur);
    if (cancelled) {
      return "<div class='order-timeline cancelled'><span class='badge off'>" +
        esc(statusLabel("cancelled")) + "</span></div>";
    }
    var html = "<ol class='order-timeline'>";
    for (var i = 0; i < STEPS.length; i++) {
      var done = idx >= i;
      var active = idx === i;
      html += "<li class='" + (done ? "done" : "") + (active ? " active" : "") + "'>" +
        "<span class='dot'></span><span class='lab'>" + esc(statusLabel(STEPS[i])) + "</span></li>";
    }
    html += "</ol>";
    return html;
  }

  function renderOrderCard(o, open) {
    return "<article class='account-order" + (open ? " open" : "") + "' data-code='" + esc(o.order_code) + "'>" +
      "<button type='button' class='account-order-summary' data-code='" + esc(o.order_code) + "'>" +
      "<div><strong>" + esc(o.order_code) + "</strong>" +
      "<div class='meta'>" + Math.round(o.total_bdt || 0) + " BDT · " +
      esc([o.upazila, o.district].filter(Boolean).join(", ") || "—") +
      (o.created_at ? (" · " + esc(fmtWhen(o.created_at))) : "") +
      "</div></div>" +
      "<span class='badge " + esc(o.status || "") + "'>" + esc(statusLabel(o.status || "")) + "</span>" +
      "</button></article>";
  }

  function renderDetail(order, into) {
    var items = order.items || [];
    var events = order.events || [];
    var html = "<div class='order-detail-inner'>" +
      "<div class='order-detail-top'>" +
      "<strong>" + esc(order.order_code) + "</strong>" +
      "<span class='badge " + esc(order.status || "") + "'>" + esc(statusLabel(order.status || "")) + "</span>" +
      "</div>" +
      timelineHtml(order) +
      "<div class='order-block'><h3>" + esc(T("account_delivery")) + "</h3>" +
      "<p>" + esc(order.user_name || "") +
      (order.user_phone ? (" · " + esc(order.user_phone)) : "") + "<br/>" +
      esc(order.address || "") + "<br/>" +
      esc([order.upazila, order.district].filter(Boolean).join(", ")) +
      "</p></div>" +
      "<div class='order-block'><h3>" + esc(T("account_items")) + "</h3><ul class='order-items'>";
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      html += "<li><span>" + esc(it.product_name || ("#" + it.product_id)) +
        " × " + esc(it.qty) + "</span><span>" + Math.round(it.line_total_bdt || 0) + " BDT</span></li>";
    }
    html += "</ul><p class='order-total'><strong>" + esc(T("account_total")) +
      ":</strong> " + Math.round(order.total_bdt || 0) + " BDT</p></div>";
    if (events.length) {
      html += "<div class='order-block'><h3>" + esc(T("account_updates")) + "</h3><ul class='order-events'>";
      for (var j = events.length - 1; j >= 0; j--) {
        var ev = events[j];
        html += "<li><strong>" + esc(statusLabel(ev.status || "")) + "</strong> — " +
          esc(ev.message || "") +
          "<div class='meta'>" + esc(fmtWhen(ev.created_at)) + "</div></li>";
      }
      html += "</ul></div>";
    }
    html += "</div>";
    into.className = "account-order-detail";
    into.innerHTML = html;
  }

  function loadOrderDetail(code, into, after) {
    if (!code) return;
    into.className = "account-order-detail";
    into.innerHTML = "<p class='muted'>" + esc(T("account_loading")) + "</p>";
    xhr("GET", "/api/shop/orders/" + encodeURIComponent(code), null, function (data) {
      renderDetail(data, into);
      if (after) after(data);
    }, function (m) {
      into.innerHTML = "<p class='error'>" + esc(m) + "</p>";
    });
  }

  function setTab(tab) {
    $("tabProfile").className = tab === "profile" ? "account-card" : "account-card hidden";
    $("tabOrders").className = tab === "orders" ? "account-card" : "account-card hidden";
    var tabs = document.querySelectorAll(".account-tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].className = tabs[i].getAttribute("data-tab") === tab ? "account-tab active" : "account-tab";
    }
    if (tab === "orders") loadOrders();
    if (location.hash !== "#" + tab && history.replaceState) {
      history.replaceState(null, "", "#" + tab);
    }
  }

  function dash(v) {
    var s = (v == null ? "" : String(v)).trim();
    return s || "—";
  }

  var editing = false;
  var savedProfile = null;

  function fillProfile(u) {
    savedProfile = {
      name: u.name || "",
      email: u.email || "",
      phone: u.phone || "",
      district: u.district || "",
      upazila: u.upazila || "",
      address: u.address || ""
    };
    $("accountHello").textContent = T("account_hello", { name: savedProfile.name || T("auth_user") });
    $("accountEmail").textContent = savedProfile.email || "";
    $("viewName").textContent = dash(savedProfile.name);
    $("viewEmail").textContent = dash(savedProfile.email);
    $("viewPhone").textContent = dash(savedProfile.phone);
    $("viewDistrict").textContent = dash(savedProfile.district);
    $("viewUpazila").textContent = dash(savedProfile.upazila);
    $("viewAddress").textContent = dash(savedProfile.address);
    $("accName").value = savedProfile.name;
    $("accEmail").value = savedProfile.email;
    $("accPhone").value = savedProfile.phone;
    $("accDistrict").value = savedProfile.district;
    $("accUpazila").value = savedProfile.upazila;
    $("accAddress").value = savedProfile.address;
    setEditMode(false);
  }

  function setEditMode(on) {
    editing = !!on;
    $("profileView").className = editing ? "account-profile-view hidden" : "account-profile-view";
    $("profileForm").className = editing ? "account-form" : "account-form hidden";
    $("profileEditBtn").className = editing ? "btn btn-primary btn-sm hidden" : "btn btn-primary btn-sm";
    var msg = $("profileMsg");
    var viewMsg = $("profileViewMsg");
    if (!editing) {
      if (msg) msg.className = "account-msg hidden";
    } else if (viewMsg) {
      viewMsg.className = "account-msg hidden";
    }
    if (editing) {
      $("accName").focus();
    }
  }

  function cancelEdit() {
    if (savedProfile) {
      $("accName").value = savedProfile.name;
      $("accEmail").value = savedProfile.email;
      $("accPhone").value = savedProfile.phone;
      $("accDistrict").value = savedProfile.district;
      $("accUpazila").value = savedProfile.upazila;
      $("accAddress").value = savedProfile.address;
    }
    setEditMode(false);
  }

  function saveProfile(e) {
    e.preventDefault();
    var msg = $("profileMsg");
    var body = {
      name: $("accName").value.trim(),
      phone: $("accPhone").value.trim(),
      district: $("accDistrict").value.trim(),
      upazila: $("accUpazila").value.trim(),
      address: $("accAddress").value.trim()
    };
    if (!body.name) {
      msg.textContent = T("account_name_required");
      msg.className = "account-msg error";
      return;
    }
    xhr("PATCH", "/api/auth/profile", body, function (data) {
      var s = session() || {};
      if (data.user) s.user = data.user;
      try { localStorage.setItem("agroscan_session", JSON.stringify(s)); } catch (err) {}
      fillProfile(data.user || Object.assign({}, savedProfile || {}, body));
      var viewMsg = $("profileViewMsg");
      viewMsg.textContent = T("account_saved");
      viewMsg.className = "account-msg ok";
      if (window.AgroScanAuth && window.AgroScanAuth.renderHeader) window.AgroScanAuth.renderHeader();
    }, function (m) {
      msg.textContent = m;
      msg.className = "account-msg error";
    });
  }

  function loadOrders() {
    var el = $("accountOrders");
    el.innerHTML = "<p class='muted'>" + esc(T("account_loading")) + "</p>";
    xhr("GET", "/api/shop/orders", null, function (data) {
      var list = data.orders || [];
      var active = 0;
      for (var i = 0; i < list.length; i++) {
        var st = list[i].status || "";
        if (st && st !== "delivered" && st !== "cancelled") active++;
      }
      $("statOrderCount").textContent = String(list.length);
      $("statActiveCount").textContent = String(active);
      if (!list.length) {
        el.innerHTML = "<div class='account-empty'><p>" + esc(T("shop_no_orders")) + "</p>" +
          "<a class='btn btn-primary btn-sm' href='/#shop'>" + esc(T("nav_shop")) + "</a></div>";
        return;
      }
      var html = "";
      for (var j = 0; j < list.length; j++) html += renderOrderCard(list[j], false);
      el.innerHTML = html;
      var btns = el.querySelectorAll(".account-order-summary");
      for (var k = 0; k < btns.length; k++) {
        btns[k].onclick = function () {
          var code = this.getAttribute("data-code");
          loadOrderDetail(code, $("accountOrderDetail"));
          var cards = el.querySelectorAll(".account-order");
          for (var n = 0; n < cards.length; n++) {
            cards[n].className = cards[n].getAttribute("data-code") === code
              ? "account-order open" : "account-order";
          }
        };
      }
    }, function (m) {
      el.innerHTML = "<p class='error'>" + esc(m) + "</p>";
    });
  }

  function showApp() {
    $("accountGate").className = "account-card hidden";
    $("accountApp").className = "";
    xhr("GET", "/api/auth/me", null, function (data) {
      var u = data.user || {};
      var s = session() || {};
      s.user = u;
      try { localStorage.setItem("agroscan_session", JSON.stringify(s)); } catch (e) {}
      fillProfile(u);
      loadOrders();
      var hash = (location.hash || "").replace(/^#/, "");
      setTab(hash === "orders" ? "orders" : "profile");
    }, function () {
      showGate();
    });
  }

  function showGate() {
    $("accountGate").className = "account-card";
    $("accountApp").className = "hidden";
  }

  function init() {
    var tabs = document.querySelectorAll(".account-tab");
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].onclick = function () { setTab(this.getAttribute("data-tab")); };
    }
    $("profileForm").onsubmit = saveProfile;
    $("profileEditBtn").onclick = function () { setEditMode(true); };
    $("profileCancelBtn").onclick = cancelEdit;
    $("ordersRefresh").onclick = loadOrders;

    $("guestTrackForm").onsubmit = function (e) {
      e.preventDefault();
      var code = ($("guestOrderCode").value || "").trim();
      loadOrderDetail(code, $("guestTrackResult"));
    };
    $("userTrackForm").onsubmit = function (e) {
      e.preventDefault();
      var code = ($("userOrderCode").value || "").trim();
      if (!code) return;
      loadOrderDetail(code, $("accountOrderDetail"));
      setTab("orders");
    };

    if (isRealUser()) showApp();
    else showGate();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
