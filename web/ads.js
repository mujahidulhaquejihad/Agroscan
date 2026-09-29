/* Permanent banner under the top bar + one popup on first open. */
(function () {
  var BANNERS = [
    "/static/ads/ad6.jpg?v=3",
    "/static/ads/ad7.jpg?v=3",
    "/static/ads/ad8.jpg?v=3"
  ];
  var POP_KEY = "agroscan_ad_popup_seen";
  var ROTATE_MS = 4000;
  var i = 0;
  var timer = 0;

  function t(key, fallback) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key) : fallback;
  }

  function $(id) { return document.getElementById(id); }

  function setStrip(idx, instant) {
    var img = $("adStripImg");
    if (!img) return;
    i = ((idx % BANNERS.length) + BANNERS.length) % BANNERS.length;
    var src = BANNERS[i];
    img.alt = t("ads_label", "Ad");
    if (instant) {
      img.src = src;
      img.style.opacity = "1";
      return;
    }
    img.style.opacity = "0";
    var preload = new Image();
    preload.onload = function () {
      img.src = src;
      img.style.opacity = "1";
    };
    preload.onerror = function () { img.src = src; img.style.opacity = "1"; };
    preload.src = src;
  }

  function nextStrip() {
    if (document.hidden) return;
    setStrip(i + 1);
  }

  function startRotate() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    stopRotate();
    timer = window.setInterval(nextStrip, ROTATE_MS);
  }

  function stopRotate() {
    if (timer) {
      clearInterval(timer);
      timer = 0;
    }
  }

  function closePopup() {
    var back = $("adPopup");
    if (back) back.classList.add("hidden");
    sessionStorage.setItem(POP_KEY, "1");
  }

  function showPopup() {
    if (sessionStorage.getItem(POP_KEY)) return;
    var back = $("adPopup");
    var img = $("adPopupImg");
    if (!back || !img) return;
    img.src = BANNERS[Math.floor(Math.random() * BANNERS.length)];
    img.alt = t("ads_label", "Ad");
    back.classList.remove("hidden");
  }

  function boot() {
    var strip = $("adStrip");
    if (!strip) return;
    strip.classList.remove("hidden");

    var badge = $("adStripBadge");
    if (badge) badge.textContent = t("ads_label", "Ad");

    var popClose = $("adPopupClose");
    if (popClose) {
      popClose.setAttribute("aria-label", t("close", "Close"));
      popClose.onclick = closePopup;
    }
    var back = $("adPopup");
    if (back) {
      back.onclick = function (e) {
        if (e.target === back) closePopup();
      };
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePopup();
    });

    setStrip(0, true);
    startRotate();
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stopRotate();
      else startRotate();
    });

    window.setTimeout(showPopup, 900);
  }

  document.addEventListener("langchange", function () {
    var badge = $("adStripBadge");
    if (badge) badge.textContent = t("ads_label", "Ad");
    var img = $("adStripImg");
    if (img) img.alt = t("ads_label", "Ad");
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
