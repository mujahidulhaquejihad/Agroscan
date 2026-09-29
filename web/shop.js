/* AgroScan shop: browse → cart → checkout (ecommerce-style, ES5) */
(function () {
  var API = "";
  if (window.AGROSCAN_CONFIG && window.AGROSCAN_CONFIG.API_BASE) {
    API = window.AGROSCAN_CONFIG.API_BASE;
  }

  var CART_KEY = "agroscan_cart";
  var PLACE_KEY = "agroscan_place_v1";
  var loc = { district: "", upazila: "", lat: null, lng: null };
  try {
    var savedPlace = JSON.parse(localStorage.getItem(PLACE_KEY) || "null");
    if (savedPlace && (savedPlace.district || savedPlace.upazila)) {
      loc.district = savedPlace.district || "";
      loc.upazila = savedPlace.upazila || "";
      loc.lat = savedPlace.lat != null ? savedPlace.lat : null;
      loc.lng = savedPlace.lng != null ? savedPlace.lng : null;
    }
  } catch (e) {}
  var cart = [];
  var productCache = {};
  var currentCat = "pesticide";
  var currentView = "browse";
  var drawerStep = "cart";
  var searchTimer = null;
  var toastTimer = null;
  var allUpazilas = [];
  var pendingNearest = null;
  var profileLoaded = false;

  function $(id) { return document.getElementById(id); }

  function T(key, vars) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key, vars) : key;
  }

  function isBn() {
    var lang = window.AgroScanI18n ? window.AgroScanI18n.lang : "en";
    return String(lang || "").indexOf("bn") === 0;
  }

  function districtLabel(row) {
    if (!row) return "";
    if (isBn()) return row.district_bn || row.district || "";
    return row.district || "";
  }

  function upazilaLabel(row) {
    if (!row) return "";
    if (isBn()) return row.name_bn || row.name || "";
    return row.name || "";
  }

  function placeDisplay(districtEn, upazilaEn) {
    var dLabel = districtEn || "";
    var uLabel = upazilaEn || "";
    var i;
    for (i = 0; i < allUpazilas.length; i++) {
      var row = allUpazilas[i];
      if (districtEn && row.district === districtEn) {
        dLabel = districtLabel(row);
        if (upazilaEn && row.name === upazilaEn) {
          uLabel = upazilaLabel(row);
          break;
        }
      }
    }
    if (uLabel && dLabel) return uLabel + ", " + dLabel;
    return uLabel || dLabel || "";
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function xhrGet(url, ok, fail) {
    var x = new XMLHttpRequest();
    x.open("GET", url, true);
    x.onload = function () {
      if (x.status >= 200 && x.status < 300) {
        try { ok(JSON.parse(x.responseText)); } catch (e) { fail(e); }
      } else fail(x.status);
    };
    x.onerror = function () { fail("network"); };
    x.send();
  }

  function xhrJson(method, url, body, ok, fail, auth) {
    var x = new XMLHttpRequest();
    x.open(method, url, true);
    x.setRequestHeader("Content-Type", "application/json");
    if (auth) x.setRequestHeader("Authorization", "Bearer " + auth);
    x.onload = function () {
      try {
        var data = x.responseText ? JSON.parse(x.responseText) : {};
        if (x.status >= 200 && x.status < 300) ok(data);
        else fail(data.detail || x.status);
      } catch (e) { fail(x.status); }
    };
    x.onerror = function () { fail("network"); };
    x.send(body != null ? JSON.stringify(body) : null);
  }

  function getSession() {
    try { return JSON.parse(localStorage.getItem("agroscan_session") || "null"); }
    catch (e) { return null; }
  }

  function authToken() {
    var s = getSession();
    return s && s.token ? s.token : "";
  }

  function sessionUser() {
    var s = getSession();
    return s && s.user ? s.user : null;
  }

  function isLoggedIn() {
    return !!authToken();
  }

  function isBn() {
    var lang = (window.AgroScanI18n && window.AgroScanI18n.lang) || "bn";
    return String(lang).indexOf("bn") === 0;
  }

  function productName(p) {
    if (!p) return "";
    return isBn() ? (p.name_bn || p.name) : (p.name || p.name_bn);
  }

  function loadCart() {
    try {
      var raw = JSON.parse(localStorage.getItem(CART_KEY) || "[]");
      cart = Array.isArray(raw) ? raw : [];
    } catch (e) { cart = []; }
  }

  function saveCart() {
    try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch (e) {}
  }

  function cartCount() {
    var n = 0, i;
    for (i = 0; i < cart.length; i++) n += Number(cart[i].qty) || 1;
    return n;
  }

  function updateCartBadge() {
    var badge = $("shopCartBadge");
    var n = cartCount();
    var go = $("shopGoCheckout");
    if (badge) {
      if (n > 0) {
        badge.textContent = String(n);
        badge.className = "shop-cart-badge";
      } else {
        badge.className = "shop-cart-badge hidden";
      }
    }
    if (go) go.disabled = n < 1;
  }

  function playAddToCartAnim(qty) {
    var fab = $("shopCartToggle");
    var badge = $("shopCartBadge");
    var n = qty || 1;
    updateCartBadge();
    if (badge) {
      badge.classList.remove("shop-cart-badge-bump");
      // reflow so animation can replay
      void badge.offsetWidth;
      badge.classList.add("shop-cart-badge-bump");
    }
    if (fab) {
      fab.classList.remove("shop-cart-fab-pulse");
      void fab.offsetWidth;
      fab.classList.add("shop-cart-fab-pulse");
      var plus = document.createElement("span");
      plus.className = "shop-cart-plus-fly";
      plus.textContent = "+" + n;
      plus.setAttribute("aria-hidden", "true");
      fab.appendChild(plus);
      setTimeout(function () {
        if (plus.parentNode) plus.parentNode.removeChild(plus);
      }, 900);
    }
  }

  function showToast(msg) {
    var el = $("shopToast");
    if (!el) return;
    el.textContent = msg;
    el.className = "shop-toast";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.className = "shop-toast hidden";
    }, 1800);
  }

  function setDrawerStep(step) {
    drawerStep = step || "cart";
    var cartStep = $("shopCartStep");
    var checkoutStep = $("shopCheckoutStep");
    var title = $("shopDrawerTitle");
    var steps = document.querySelectorAll(".shop-step");
    var i;
    if (cartStep) cartStep.className = drawerStep === "cart" ? "shop-cart-step" : "shop-cart-step hidden";
    if (checkoutStep) checkoutStep.className = drawerStep === "checkout" ? "shop-cart-step" : "shop-cart-step hidden";
    if (title) title.textContent = drawerStep === "checkout" ? T("shop_step_checkout") : T("shop_cart");
    for (i = 0; i < steps.length; i++) {
      var on = steps[i].getAttribute("data-step") === drawerStep;
      steps[i].className = on ? "shop-step active" : "shop-step";
    }
  }

  function openCart() {
    setDrawerStep("cart");
    renderCart();
    var drawer = $("shopCartDrawer");
    var backdrop = $("shopCartBackdrop");
    if (drawer) {
      drawer.classList.add("open");
      drawer.setAttribute("aria-hidden", "false");
    }
    if (backdrop) {
      backdrop.className = "shop-cart-backdrop";
      backdrop.setAttribute("aria-hidden", "false");
    }
    document.body.classList.add("shop-cart-open");
  }

  function closeCart() {
    var drawer = $("shopCartDrawer");
    var backdrop = $("shopCartBackdrop");
    if (drawer) {
      drawer.classList.remove("open");
      drawer.setAttribute("aria-hidden", "true");
    }
    if (backdrop) {
      backdrop.className = "shop-cart-backdrop hidden";
      backdrop.setAttribute("aria-hidden", "true");
    }
    document.body.classList.remove("shop-cart-open");
    setDrawerStep("cart");
  }

  function setView(view) {
    currentView = view || "browse";
    var tabs = document.querySelectorAll(".shop-view");
    var panels = document.querySelectorAll(".shop-view-panel");
    var i;
    for (i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute("data-view") === currentView;
      tabs[i].className = on ? "shop-view active" : "shop-view";
    }
    for (i = 0; i < panels.length; i++) {
      var show = panels[i].getAttribute("data-panel") === currentView;
      panels[i].className = show ? "shop-view-panel" : "shop-view-panel hidden";
    }
  }

  function applyShopWarnings() {
    xhrGet(API + "/api/safety", function (data) {
      var boxes = data.ui_warning_boxes || [];
      var want = ["warn_find_licensed_dealer", "warn_price_indicative", "warn_fake_product"];
      var bn = isBn();
      var items = [];
      var i, j;
      for (j = 0; j < want.length; j++) {
        for (i = 0; i < boxes.length; i++) {
          if (boxes[i].id === want[j]) {
            items.push(boxes[i]);
            break;
          }
        }
      }
      var el = $("shopSafetyNote");
      if (!el) return;
      if (!items.length) {
        el.innerHTML = "";
        return;
      }
      var html = "<details class='shop-safety-box'>" +
        "<summary>" + esc(T("shop_safety_summary")) + "</summary><div class='shop-safety-list'>";
      for (i = 0; i < items.length; i++) {
        html += "<div class='shop-safety-item'><strong>" +
          esc(bn ? items[i].title_bn : items[i].title_en) +
          "</strong><p>" + esc(bn ? items[i].body_bn : items[i].body_en) + "</p></div>";
      }
      html += "</div></details>";
      el.innerHTML = html;
    }, function () {});
  }

  function setLocationStatus(msg, isErr) {
    var el = $("shopLocationStatus");
    if (!el) return;
    if (!msg) {
      el.className = "muted small shop-locate-status hidden";
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.className = isErr
      ? "muted small shop-locate-status shop-locate-err"
      : "muted small shop-locate-status";
  }

  function applyNearestUpazila(u) {
    if (!u) return;
    if (!allUpazilas.length) {
      pendingNearest = u;
      return;
    }
    pendingNearest = null;
    var district = u.district || "";
    var name = u.name || "";
    loc.district = district;
    loc.upazila = name;
    try {
      localStorage.setItem(PLACE_KEY, JSON.stringify({
        district: loc.district,
        upazila: loc.upazila,
        lat: loc.lat,
        lng: loc.lng,
      }));
    } catch (e) {}
    var dist = $("shopDistrict");
    var upa = $("shopUpazila");
    if (dist) {
      dist.value = district;
      fillBrowseUpazila(district);
    }
    if (upa) upa.value = name;
    fillDistrictSelect("shopCheckoutDistrict", district);
    fillCheckoutUpazila(district, name);
    var farm = $("farmDistrict");
    if (farm && district) farm.value = district;
    loadSuppliers();
    var km = u.distance_km != null ? u.distance_km : "?";
    var label = isBn() ? (u.name_bn || name) : name;
    var distLabel = isBn() ? (u.district_bn || district) : district;
    setLocationStatus(T("shop_location_ok", { place: label, district: distLabel, km: km }));
    showToast(T("shop_location_ok_short", { place: label }));
  }

  function fetchNearest(lat, lng) {
    loc.lat = lat;
    loc.lng = lng;
    var q = "/api/shop/nearest-upazila?lat=" + encodeURIComponent(lat) +
      "&lng=" + encodeURIComponent(lng);
    xhrGet(API + q, function (data) {
      var btn = $("shopUseLocation");
      if (btn) {
        btn.disabled = false;
        btn.textContent = T("shop_use_location");
      }
      applyNearestUpazila(data.upazila);
    }, function () {
      var btn = $("shopUseLocation");
      if (btn) {
        btn.disabled = false;
        btn.textContent = T("shop_use_location");
      }
      loadSuppliers();
      setLocationStatus(T("shop_location_no_match"), true);
    });
  }

  function detectLocation(fromButton) {
    var btn = $("shopUseLocation");
    if (fromButton && btn) {
      btn.disabled = true;
      btn.textContent = T("shop_location_finding");
      setLocationStatus(T("shop_location_finding"));
    }
    function onErr(err) {
      if (btn) {
        btn.disabled = false;
        btn.textContent = T("shop_use_location");
      }
      var code = err && err.code;
      if (code === 1) setLocationStatus(T("shop_location_denied"), true);
      else if (code === 3) setLocationStatus(T("shop_location_timeout"), true);
      else setLocationStatus(T("shop_location_fail"), true);
    }
    if (window.AgroScanGeo && window.AgroScanGeo.locate) {
      window.AgroScanGeo.locate(function (pos) {
        if (pos && pos.lat != null) fetchNearest(pos.lat, pos.lng);
      }, onErr);
      return;
    }
    if (!navigator.geolocation) {
      setLocationStatus(T("shop_location_unsupported"), true);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        fetchNearest(pos.coords.latitude, pos.coords.longitude);
      },
      onErr,
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
    );
  }

  function typeLabel(type) {
    if (type === "government_office") return T("shop_type_dae");
    if (type === "government_supplier") return T("shop_type_badc");
    if (type === "brand_distributor") return T("shop_type_brand");
    return type || "";
  }

  function loadSuppliers() {
    var q = "/api/shop/suppliers?limit=12";
    if (loc.district) q += "&district=" + encodeURIComponent(loc.district);
    if (loc.upazila) q += "&upazila=" + encodeURIComponent(loc.upazila);
    if (loc.lat != null && loc.lng != null) {
      q += "&lat=" + encodeURIComponent(loc.lat) + "&lng=" + encodeURIComponent(loc.lng);
    }
    xhrGet(API + q, function (data) {
      var el = $("shopSuppliers");
      if (!el) return;
      var html = "";
      var list = data.suppliers || [];
      var i;
      for (i = 0; i < list.length; i++) {
        var s = list[i];
        var name = isBn() ? (s.name_bn || s.name) : (s.name || s.name_bn);
        var links = "";
        if (s.phone) links += "<a class='shop-link' href='tel:" + esc(s.phone) + "'>" + esc(s.phone) + "</a>";
        if (s.website) links += "<a class='shop-link' href='" + esc(s.website) + "' target='_blank' rel='noopener'>" + T("shop_website") + "</a>";
        var distLine = "";
        if (s.distance_km != null) {
          distLine = "<div class='shop-meta'>" + esc(T("shop_distance_km", { km: s.distance_km })) + "</div>";
        }
        html += "<article class='shop-supplier'>" +
          "<div class='shop-supplier-top'>" +
          "<strong>" + esc(name) + "</strong>" +
          "<span class='shop-rank'>#" + esc(s.rank_in_upazila || "") + "</span></div>" +
          "<div class='shop-meta'>" + esc(placeDisplay(s.district, s.upazila)) + "</div>" +
          "<div class='shop-meta'>" + esc(typeLabel(s.supplier_type)) + "</div>" +
          distLine +
          (links ? "<div class='shop-links'>" + links + "</div>" : "") +
          (s.supplier_type === "government_office"
            ? "<p class='muted small'>" + esc(T("shop_dae_note")) + "</p>" : "") +
          "</article>";
      }
      el.innerHTML = html || ("<p class='muted'>" + T("shop_no_suppliers") + "</p>");
    }, function () {
      var el = $("shopSuppliers");
      if (el) el.innerHTML = "<p class='muted'>" + T("shop_no_suppliers") + "</p>";
    });
  }

  function rememberProduct(p) {
    if (p && p.id != null) productCache[String(p.id)] = p;
  }

  function loadProducts(cat, search) {
    if (cat == null) cat = currentCat;
    currentCat = cat || "";
    var q = "/api/shop/products?limit=48";
    if (currentCat) q += "&category=" + encodeURIComponent(currentCat);
    if (search) q += "&search=" + encodeURIComponent(search);
    var el = $("shopProducts");
    if (el) el.innerHTML = "<p class='muted small shop-loading'>" + T("shop_loading") + "</p>";
    xhrGet(API + q, function (data) {
      if (!el) return;
      var list = data.products || [];
      var html = "";
      var i;
      for (i = 0; i < list.length; i++) {
        var p = list[i];
        rememberProduct(p);
        var price = "";
        if (p.price_bdt != null && Number(p.price_bdt) > 0) {
          price = T("shop_price_bdt", { price: Math.round(Number(p.price_bdt)) });
        }
        var tags = "";
        if (p.hhp) tags += "<span class='shop-tag warn'>" + T("shop_hhp_short") + "</span>";
        if (!p.registration_verified && p.category === "pesticide") {
          tags += "<span class='shop-tag muted-tag'>" + T("shop_reg_short") + "</span>";
        }
        html += "<article class='shop-product'>" +
          "<div class='shop-product-media'>" +
          (p.image_url
            ? ("<img class='shop-product-img' src='" + esc(p.image_url) + "' alt='" + esc(productName(p)) + "' loading='lazy' decoding='async' onerror=\"this.onerror=null;this.classList.add('broken');\" />")
            : "<div class='shop-product-ph' aria-hidden='true'></div>") +
          "</div>" +
          "<div class='shop-product-top'>" +
          "<span class='shop-cat-pill'>" + esc(p.category || "") + "</span>" +
          "</div>" +
          "<div class='shop-product-body'>" +
          "<strong>" + esc(productName(p)) + "</strong>" +
          "<div class='shop-meta'>" + esc([p.brand, p.pack_size || p.unit].filter(Boolean).join(" · ")) + "</div>" +
          (p.description ? "<p class='shop-desc'>" + esc(String(p.description).slice(0, 140)) + "</p>" : "") +
          (p.active_ingredient ? "<div class='shop-meta shop-ai'>" + esc(p.active_ingredient) + "</div>" : "") +
          (price ? "<div class='shop-price'>" + esc(price) + "</div>" : "") +
          (tags ? "<div class='shop-tags'>" + tags + "</div>" : "") +
          "</div>" +
          "<button type='button' class='btn btn-primary btn-sm shop-add' data-id='" + p.id + "'>" +
          T("shop_add") + "</button></article>";
      }
      el.innerHTML = html || ("<div class='shop-empty'><p>" + T("shop_empty") + "</p></div>");
      var count = $("shopProductCount");
      if (count) count.textContent = list.length ? T("shop_showing", { n: list.length }) : "";
      var btns = el.getElementsByClassName("shop-add");
      for (i = 0; i < btns.length; i++) {
        if (productInCart(parseInt(btns[i].getAttribute("data-id"), 10))) {
          markAddButton(btns[i]);
        }
        btns[i].onclick = function () {
          addToCart(parseInt(this.getAttribute("data-id"), 10), 1, false);
          markAddButton(this);
        };
      }
    }, function () {
      if (el) el.innerHTML = "<div class='shop-empty'><p>" + T("shop_empty") + "</p></div>";
    });
  }

  function productInCart(productId) {
    var id = Number(productId);
    var i;
    for (i = 0; i < cart.length; i++) {
      if (Number(cart[i].product_id) === id) return true;
    }
    return false;
  }

  function markAddButton(btn) {
    if (!btn) return;
    btn.textContent = T("shop_btn_added");
    btn.classList.add("is-added");
    btn.setAttribute("aria-pressed", "true");
  }

  function addToCart(productId, qty, openDrawer) {
    if (!productId) return;
    var addQty = qty || 1;
    var i, found = false;
    for (i = 0; i < cart.length; i++) {
      if (cart[i].product_id === productId) {
        cart[i].qty = (Number(cart[i].qty) || 1) + addQty;
        found = true;
        break;
      }
    }
    if (!found) cart.push({ product_id: productId, qty: addQty });
    saveCart();
    renderCart();
    playAddToCartAnim(addQty);
    if (openDrawer) openCart();
  }

  function setQty(productId, qty) {
    var next = [], i;
    for (i = 0; i < cart.length; i++) {
      if (cart[i].product_id === productId) {
        if (qty > 0) next.push({ product_id: productId, qty: qty });
      } else next.push(cart[i]);
    }
    cart = next;
    saveCart();
    renderCart();
  }

  function renderCart() {
    var el = $("shopCart");
    updateCartBadge();
    if (!el) return;
    if (!cart.length) {
      el.innerHTML = "<div class='shop-empty shop-empty-sm'><p>" + T("shop_cart_empty") + "</p></div>";
      return;
    }
    var html = "<ul class='shop-cart-list'>";
    var i;
    for (i = 0; i < cart.length; i++) {
      var item = cart[i];
      var p = productCache[String(item.product_id)] || {};
      var name = productName(p) || ("#" + item.product_id);
      var line = "";
      if (p.price_bdt != null && Number(p.price_bdt) > 0) {
        line = T("shop_line_total", {
          total: Math.round(Number(p.price_bdt) * (item.qty || 1))
        });
      }
      html += "<li class='shop-cart-item'>" +
        (p.image_url
          ? ("<img class='shop-cart-thumb' src='" + esc(p.image_url) + "' alt='' loading='lazy' onerror=\"this.style.display='none'\" />")
          : "<div class='shop-cart-thumb shop-cart-thumb-ph' aria-hidden='true'></div>") +
        "<div class='shop-cart-info'><strong>" + esc(name) + "</strong>" +
        (p.sku ? "<div class='shop-meta'>" + esc(p.sku) + "</div>" : "") +
        (line ? "<div class='shop-meta'>" + esc(line) + "</div>" : "") +
        "</div>" +
        "<div class='shop-qty'>" +
        "<button type='button' class='shop-qty-btn' data-id='" + item.product_id + "' data-d='-1' aria-label='-'>-</button>" +
        "<span>" + (item.qty || 1) + "</span>" +
        "<button type='button' class='shop-qty-btn' data-id='" + item.product_id + "' data-d='1' aria-label='+'>+</button>" +
        "</div></li>";
    }
    html += "</ul>";
    el.innerHTML = html;
    var qtyBtns = el.getElementsByClassName("shop-qty-btn");
    for (i = 0; i < qtyBtns.length; i++) {
      qtyBtns[i].onclick = function () {
        var id = parseInt(this.getAttribute("data-id"), 10);
        var d = parseInt(this.getAttribute("data-d"), 10);
        var cur = 1, j;
        for (j = 0; j < cart.length; j++) {
          if (cart[j].product_id === id) { cur = Number(cart[j].qty) || 1; break; }
        }
        setQty(id, cur + d);
      };
    }
  }

  function fillDistrictSelect(selectId, selected) {
    var el = $(selectId);
    if (!el) return;
    var html = "<option value=''>" + T("shop_pick_district") + "</option>";
    var seen = {}, list = [], i;
    for (i = 0; i < allUpazilas.length; i++) {
      var d = allUpazilas[i].district;
      if (!d || seen[d]) continue;
      seen[d] = 1;
      list.push(allUpazilas[i]);
    }
    list.sort(function (a, b) {
      return districtLabel(a).localeCompare(districtLabel(b), isBn() ? "bn" : "en");
    });
    for (i = 0; i < list.length; i++) {
      var row = list[i];
      var val = row.district || "";
      html += "<option value='" + esc(val) + "'" + (selected === val ? " selected" : "") + ">" +
        esc(districtLabel(row)) + "</option>";
    }
    el.innerHTML = html;
  }

  function fillCheckoutUpazila(district, selected) {
    var upa = $("shopCheckoutUpazila");
    if (!upa) return;
    var html = "<option value=''>—</option>";
    var rows = [], i;
    for (i = 0; i < allUpazilas.length; i++) {
      if (!district || allUpazilas[i].district === district) rows.push(allUpazilas[i]);
    }
    rows.sort(function (a, b) {
      return upazilaLabel(a).localeCompare(upazilaLabel(b), isBn() ? "bn" : "en");
    });
    for (i = 0; i < rows.length; i++) {
      var n = rows[i].name || "";
      html += "<option value='" + esc(n) + "'" + (selected === n ? " selected" : "") + ">" +
        esc(upazilaLabel(rows[i])) + "</option>";
    }
    upa.innerHTML = html;
  }

  function fillBrowseUpazila(district) {
    var upa = $("shopUpazila");
    if (!upa) return;
    var selected = upa.value || loc.upazila || "";
    var html = "<option value=''>—</option>";
    var rows = [], i;
    for (i = 0; i < allUpazilas.length; i++) {
      if (!district || allUpazilas[i].district === district) rows.push(allUpazilas[i]);
    }
    rows.sort(function (a, b) {
      return upazilaLabel(a).localeCompare(upazilaLabel(b), isBn() ? "bn" : "en");
    });
    for (i = 0; i < rows.length; i++) {
      var n = rows[i].name || "";
      html += "<option value='" + esc(n) + "'" + (selected === n ? " selected" : "") + ">" +
        esc(upazilaLabel(rows[i])) + "</option>";
    }
    upa.innerHTML = html;
  }

  function refillLocationSelects() {
    var browseDist = ($("shopDistrict") && $("shopDistrict").value) || loc.district || "";
    var browseUpa = ($("shopUpazila") && $("shopUpazila").value) || loc.upazila || "";
    var checkDist = ($("shopCheckoutDistrict") && $("shopCheckoutDistrict").value) || loc.district || "";
    var checkUpa = ($("shopCheckoutUpazila") && $("shopCheckoutUpazila").value) || loc.upazila || "";
    fillDistrictSelect("shopDistrict", browseDist);
    fillBrowseUpazila(browseDist);
    if ($("shopUpazila") && browseUpa) $("shopUpazila").value = browseUpa;
    fillDistrictSelect("shopCheckoutDistrict", checkDist);
    fillCheckoutUpazila(checkDist, checkUpa);
  }

  function profileComplete(u) {
    return !!(u && u.phone && u.address && u.district && u.upazila && u.name);
  }

  function setFormValues(u) {
    u = u || {};
    if ($("shopName")) $("shopName").value = u.name || "";
    if ($("shopPhone")) $("shopPhone").value = u.phone || "";
    if ($("shopAddress")) $("shopAddress").value = u.address || "";
    fillDistrictSelect("shopCheckoutDistrict", u.district || loc.district || "");
    fillCheckoutUpazila(u.district || loc.district || "", u.upazila || loc.upazila || "");
  }

  function renderDeliverySummary(u) {
    var box = $("shopDeliverySummary");
    var form = $("shopCheckoutForm");
    if (!box) return;
    if (isLoggedIn() && profileComplete(u)) {
      box.className = "shop-delivery-summary";
      box.innerHTML =
        "<div class='shop-summary-card'>" +
        "<strong>" + esc(T("shop_deliver_to")) + "</strong>" +
        "<p>" + esc(u.name) + "<br>" + esc(u.phone) + "<br>" + esc(u.address) + "<br>" +
        esc(placeDisplay(u.district, u.upazila)) + "</p>" +
        "<button type='button' id='shopEditDelivery' class='btn btn-secondary btn-sm'>" +
        T("shop_edit_delivery") + "</button></div>";
      if (form) form.className = "shop-checkout-form hidden";
      var edit = $("shopEditDelivery");
      if (edit) edit.onclick = function () {
        box.className = "shop-delivery-summary hidden";
        if (form) form.className = "shop-checkout-form";
      };
    } else {
      box.className = "shop-delivery-summary hidden";
      box.innerHTML = "";
      if (form) form.className = "shop-checkout-form";
    }
  }

  function refreshProfile(done) {
    var token = authToken();
    var wrap = $("shopSaveProfileWrap");
    if (!token) {
      profileLoaded = true;
      if (wrap) wrap.className = "shop-check hidden";
      var guest = sessionUser() || {};
      setFormValues({
        name: guest.name && guest.provider !== "guest" ? guest.name : "",
        phone: "",
        address: "",
        district: loc.district,
        upazila: loc.upazila
      });
      renderDeliverySummary(null);
      if (done) done(null);
      return;
    }
    if (wrap) wrap.className = "shop-check";
    xhrJson("GET", API + "/api/auth/me", null, function (data) {
      var u = data.user || {};
      var s = getSession() || {};
      s.user = u;
      try { localStorage.setItem("agroscan_session", JSON.stringify(s)); } catch (e) {}
      profileLoaded = true;
      setFormValues({
        name: u.name || "",
        phone: u.phone || "",
        address: u.address || "",
        district: u.district || loc.district || "",
        upazila: u.upazila || loc.upazila || ""
      });
      renderDeliverySummary(u);
      if (done) done(u);
    }, function () {
      profileLoaded = true;
      var u = sessionUser() || {};
      setFormValues(u);
      renderDeliverySummary(u);
      if (done) done(u);
    }, token);
  }

  function goCheckout() {
    if (!cart.length) return;
    setDrawerStep("checkout");
    refreshProfile();
  }

  function readCheckoutFields() {
    var u = sessionUser() || {};
    var summaryVisible = $("shopDeliverySummary") &&
      $("shopDeliverySummary").className.indexOf("hidden") < 0 &&
      profileComplete(u);
    if (summaryVisible) {
      return {
        user_name: u.name || "",
        user_phone: u.phone || "",
        address: u.address || "",
        district: u.district || "",
        upazila: u.upazila || ""
      };
    }
    return {
      user_name: ($("shopName") && $("shopName").value.trim()) || "",
      user_phone: ($("shopPhone") && $("shopPhone").value.trim()) || "",
      address: ($("shopAddress") && $("shopAddress").value.trim()) || "",
      district: ($("shopCheckoutDistrict") && $("shopCheckoutDistrict").value) || "",
      upazila: ($("shopCheckoutUpazila") && $("shopCheckoutUpazila").value) || ""
    };
  }

  function checkout() {
    if (!cart.length) {
      alert(T("shop_cart_empty"));
      setDrawerStep("cart");
      return;
    }
    var fields = readCheckoutFields();
    if (!fields.user_name) {
      alert(T("shop_need_name"));
      return;
    }
    if (!fields.user_phone) {
      alert(T("shop_need_phone"));
      return;
    }
    if (!fields.address) {
      alert(T("shop_need_address"));
      return;
    }
    if (!fields.district || !fields.upazila) {
      alert(T("shop_need_location"));
      return;
    }

    var body = {
      items: cart,
      user_name: fields.user_name,
      user_phone: fields.user_phone,
      district: fields.district,
      upazila: fields.upazila,
      address: fields.address,
      lat: loc.lat,
      lng: loc.lng
    };

    var btn = $("shopPlaceOrder");
    if (btn) { btn.disabled = true; btn.textContent = T("shop_placing"); }

    function place() {
      xhrJson("POST", API + "/api/shop/orders", body, function (data) {
        cart = [];
        saveCart();
        renderCart();
        closeCart();
        setView("orders");
        var el = $("shopOrders");
        if (el && data.order) {
          el.innerHTML = "<div class='shop-order ok-line'>" +
            esc(T("shop_order_ok", { code: data.order.order_code })) + "</div>" + el.innerHTML;
        }
        loadOrders();
        showToast(T("shop_order_ok", { code: data.order && data.order.order_code }));
        if (btn) { btn.disabled = false; btn.textContent = T("shop_checkout"); }
      }, function (msg) {
        if (btn) { btn.disabled = false; btn.textContent = T("shop_checkout"); }
        alert(typeof msg === "string" ? msg : T("shop_order_fail"));
      }, authToken());
    }

    var token = authToken();
    var saveProfile = $("shopSaveProfile") && $("shopSaveProfile").checked;
    if (token && saveProfile) {
      xhrJson("PATCH", API + "/api/auth/profile", {
        name: fields.user_name,
        phone: fields.user_phone,
        address: fields.address,
        district: fields.district,
        upazila: fields.upazila
      }, function (data) {
        var s = getSession() || {};
        if (data.user) s.user = data.user;
        try { localStorage.setItem("agroscan_session", JSON.stringify(s)); } catch (e) {}
        place();
      }, function () { place(); }, token);
    } else {
      place();
    }
  }

  function loadOrders() {
    var token = authToken();
    var el = $("shopOrders");
    if (!token) {
      if (el) el.innerHTML = "<div class='shop-empty shop-empty-sm'><p>" + T("shop_sign_in_orders") + "</p></div>";
      return;
    }
    xhrJson("GET", API + "/api/shop/orders", null, function (data) {
      if (!el) return;
      var html = "";
      var list = data.orders || [];
      var i;
      for (i = 0; i < list.length; i++) {
        var o = list[i];
        html += "<div class='shop-order'>" +
          "<div><strong>" + esc(o.order_code) + "</strong>" +
          "<div class='shop-meta'>" + esc(o.total_bdt || 0) + " BDT</div></div>" +
          "<span class='shop-status'>" + esc(o.status) + "</span></div>";
      }
      el.innerHTML = html || ("<div class='shop-empty shop-empty-sm'><p>" + T("shop_no_orders") + "</p>" +
        "<p class='muted small'><a href='/account#orders'>" + T("account_orders_title") + "</a></p></div>");
      if (html) {
        el.innerHTML += "<p class='muted small' style='margin-top:10px'><a href='/account#orders'>" +
          T("account_orders_title") + " →</a></p>";
      }
    }, function () {
      if (el) el.innerHTML = "<div class='shop-empty shop-empty-sm'><p>" + T("shop_sign_in_orders") + "</p></div>";
    }, token);
  }

  function loadRecommendations(diseaseClass, opts) {
    if (!diseaseClass) return;
    opts = opts || {};
    var q = "/api/shop/recommend?disease_class=" + encodeURIComponent(diseaseClass);
    if (loc.district) q += "&district=" + encodeURIComponent(loc.district);
    if (loc.upazila) q += "&upazila=" + encodeURIComponent(loc.upazila);
    xhrGet(API + q, function (data) {
      var list = data.products || [];
      renderRecommendInto($("shopRecommend"), list, opts.stay !== true);
      renderRecommendInto($("adviceShopRec"), list, false);
    }, function () {});
  }

  function renderRecommendInto(el, list, jumpToShopOnAdd) {
    if (!el) return;
    if (!list || !list.length) {
      el.className = (el.id === "adviceShopRec" ? "advice-shop-rec" : "shop-recommend") + " hidden";
      el.innerHTML = "";
      return;
    }
    var html = "<div class='shop-rec-head'><h4>" + T("shop_recommend_title") + "</h4>" +
      "<p class='muted small'>" + T("shop_recommend_hint") + "</p></div>" +
      "<div class='shop-rec-grid'>";
    var i;
    for (i = 0; i < list.length; i++) {
      var p = list[i];
      rememberProduct(p);
      html += "<div class='shop-rec-item'>" +
        (p.image_url
          ? ("<img class='shop-rec-thumb' src='" + esc(p.image_url) + "' alt='' loading='lazy' onerror=\"this.style.display='none'\" />")
          : "<div class='shop-rec-thumb shop-rec-thumb-ph' aria-hidden='true'></div>") +
        "<strong>" + esc(productName(p)) + "</strong>" +
        "<button type='button' class='btn btn-secondary btn-sm shop-rec-add' data-id='" + p.id + "'>" +
        T("shop_add") + "</button></div>";
    }
    html += "</div>";
    el.innerHTML = html;
    el.className = el.id === "adviceShopRec" ? "advice-shop-rec" : "shop-recommend";
    var btns = el.getElementsByClassName("shop-rec-add");
    for (i = 0; i < btns.length; i++) {
      if (productInCart(parseInt(btns[i].getAttribute("data-id"), 10))) {
        markAddButton(btns[i]);
      }
      btns[i].onclick = function () {
        addToCart(parseInt(this.getAttribute("data-id"), 10), 1, false);
        markAddButton(this);
        if (jumpToShopOnAdd) {
          if (window.agroscanShowPane) window.agroscanShowPane("shop");
          setView("browse");
        }
      };
    }
  }

  function setActiveCat(cat) {
    currentCat = cat || "";
    var wrap = $("shopCategoryFilter");
    if (!wrap) return;
    var btns = wrap.getElementsByClassName("shop-cat");
    var i;
    for (i = 0; i < btns.length; i++) {
      var on = (btns[i].getAttribute("data-cat") || "") === currentCat;
      btns[i].className = on ? "shop-cat active" : "shop-cat";
    }
  }

  function addSku(sku) {
    if (!sku) return;
    xhrGet(API + "/api/shop/products?search=" + encodeURIComponent(sku) + "&limit=5", function (data) {
      var list = data.products || [];
      var i;
      for (i = 0; i < list.length; i++) {
        rememberProduct(list[i]);
        if (list[i].sku === sku) {
          addToCart(list[i].id, 1, false);
          return;
        }
      }
      if (list[0]) {
        rememberProduct(list[0]);
        addToCart(list[0].id, 1, false);
      }
    }, function () {});
  }

  function hydrateCartProducts() {
    if (!cart.length) return;
    var missing = [], i;
    for (i = 0; i < cart.length; i++) {
      if (!productCache[String(cart[i].product_id)]) missing.push(cart[i].product_id);
    }
    for (i = 0; i < missing.length; i++) {
      (function (id) {
        xhrGet(API + "/api/shop/products/" + id, function (data) {
          if (data && data.product) rememberProduct(data.product);
          else if (data && data.id) rememberProduct(data);
          renderCart();
        }, function () {});
      })(missing[i]);
    }
  }

  function init() {
    var dist = $("shopDistrict");
    var upa = $("shopUpazila");
    var search = $("shopSearch");
    var cats = $("shopCategoryFilter");
    var cartToggle = $("shopCartToggle");
    var cartClose = $("shopCartClose");
    var backdrop = $("shopCartBackdrop");
    var goCheckoutBtn = $("shopGoCheckout");
    var backCart = $("shopBackToCart");
    var placeOrder = $("shopPlaceOrder");
    var coDist = $("shopCheckoutDistrict");
    var views = document.querySelectorAll(".shop-view");

    loadCart();

    if (dist) dist.onchange = function () {
      loc.district = dist.value;
      loc.upazila = "";
      fillBrowseUpazila(dist.value);
      loadSuppliers();
      loadProducts(currentCat, search && search.value);
    };
    if (upa) upa.onchange = function () {
      loc.upazila = upa.value;
      loadSuppliers();
    };
    if (search) {
      search.oninput = function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          loadProducts(currentCat, search.value.trim());
        }, 280);
      };
    }
    if (cats) {
      cats.onclick = function (e) {
        var t = e.target;
        while (t && t !== cats && !(t.className && String(t.className).indexOf("shop-cat") >= 0)) {
          t = t.parentNode;
        }
        if (!t || t === cats) return;
        var cat = t.getAttribute("data-cat") || "";
        setActiveCat(cat);
        loadProducts(cat, search && search.value.trim());
      };
    }
    var vi;
    for (vi = 0; vi < views.length; vi++) {
      views[vi].onclick = function () {
        setView(this.getAttribute("data-view"));
      };
    }
    if (cartToggle) cartToggle.onclick = function () { openCart(); };
    if (cartClose) cartClose.onclick = closeCart;
    if (backdrop) backdrop.onclick = closeCart;
    if (goCheckoutBtn) goCheckoutBtn.onclick = goCheckout;
    if (backCart) backCart.onclick = function () { setDrawerStep("cart"); };
    if (placeOrder) placeOrder.onclick = checkout;
    if (coDist) coDist.onchange = function () {
      fillCheckoutUpazila(coDist.value, "");
    };
    var locateBtn = $("shopUseLocation");
    if (locateBtn) locateBtn.onclick = function () { detectLocation(true); };
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeCart();
    });

    xhrGet(API + "/api/shop/upazilas", function (data) {
      allUpazilas = data.upazilas || [];
      fillDistrictSelect("shopDistrict", loc.district || "");
      fillDistrictSelect("shopCheckoutDistrict", loc.district || "");
      if (loc.district) fillBrowseUpazila(loc.district);
      if (loc.upazila && $("shopUpazila")) $("shopUpazila").value = loc.upazila;
      if (pendingNearest) applyNearestUpazila(pendingNearest);
      var g = window.AgroScanGeo && window.AgroScanGeo.get && window.AgroScanGeo.get();
      if (g && g.lat != null) fetchNearest(g.lat, g.lng);
    }, function () {
      var g = window.AgroScanGeo && window.AgroScanGeo.get && window.AgroScanGeo.get();
      if (g && g.lat != null) fetchNearest(g.lat, g.lng);
    });
    document.addEventListener("agroscan-geo", function (ev) {
      var d = ev.detail || {};
      if (d.lat != null && d.lng != null) fetchNearest(d.lat, d.lng);
    });

    document.addEventListener("langchange", function () {
      applyShopWarnings();
      refillLocationSelects();
      loadProducts(currentCat, search && search.value.trim());
      loadSuppliers();
      renderCart();
      loadOrders();
      if (drawerStep === "checkout") refreshProfile();
    });

    setActiveCat(currentCat);
    setView("browse");
    setDrawerStep("cart");
    applyShopWarnings();
    loadProducts(currentCat);
    loadSuppliers();
    loadOrders();
    renderCart();
    hydrateCartProducts();
    if (isLoggedIn()) refreshProfile();
  }

  window.AgroScanShop = {
    init: init,
    recommendForDisease: loadRecommendations,
    addToCart: function (id, qty) { addToCart(id, qty, false); },
    getPlace: function () {
      return { district: loc.district, upazila: loc.upazila, lat: loc.lat, lng: loc.lng };
    },
    openCart: openCart,
    closeCart: closeCart
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
