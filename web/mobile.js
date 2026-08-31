/* App navigation: one pane at a time (no long single-page scroll). */
(function () {
  function $(id) { return document.getElementById(id); }

  var PANES = ["diagnose", "field", "notifications", "shop", "emergency", "library"];
  var currentPane = "diagnose";

  function mapPane(id) {
    if (id === "resources" || id === "help" || id === "more") return "library";
    return id;
  }

  function setupUpload() {
    var cameraBtn = $("cameraBtn");
    var galleryBtn = $("galleryBtn");
    var cameraInput = $("cameraInput");
    var fileInput = $("fileInput");

    if (cameraBtn && cameraInput) {
      cameraBtn.onclick = function (e) {
        e.preventDefault();
        cameraInput.click();
      };
    }
    if (galleryBtn && fileInput) {
      galleryBtn.onclick = function (e) {
        e.preventDefault();
        fileInput.click();
      };
    }
  }

  function setActiveNav(id) {
    var items = document.querySelectorAll(".mob-nav-item");
    for (var i = 0; i < items.length; i++) {
      var on = items[i].getAttribute("data-section") === id;
      items[i].className = on ? "mob-nav-item active" : "mob-nav-item";
      items[i].setAttribute("aria-current", on ? "page" : "false");
    }
    var links = document.querySelectorAll(".nav a[href^='#'], .site-footer a[href^='#']");
    for (var j = 0; j < links.length; j++) {
      var href = (links[j].getAttribute("href") || "").replace(/^#/, "");
      if (href === "top") href = "diagnose";
      if (PANES.indexOf(href) < 0) continue;
      if (href === id) links[j].classList.add("nav-active");
      else links[j].classList.remove("nav-active");
    }
  }

  function showPane(id, opts) {
    id = mapPane(id);
    if (PANES.indexOf(id) < 0) id = "diagnose";
    currentPane = id;
    opts = opts || {};

    document.body.classList.add("app-panes");
    document.body.classList.add("mobile-tabs"); // keep legacy class for existing CSS
    document.body.setAttribute("data-mobile-pane", id);
    document.body.setAttribute("data-app-pane", id);
    setActiveNav(id);

    var shell = document.querySelector(".app-scroll") || document.querySelector(".mobile-scroll");
    if (shell && !opts.keepScroll) shell.scrollTop = 0;

    if (opts.focusResults) {
      var results = $("results");
      if (results && shell) {
        setTimeout(function () {
          shell.scrollTop = Math.max(0, results.offsetTop - 12);
        }, 50);
      }
    }
  }

  function bindPaneLink(el) {
    el.addEventListener("click", function (e) {
      var href = (this.getAttribute("href") || "").replace(/^#/, "");
      if (href === "top" || href === "results" || href === "dropzone") href = "diagnose";
      href = mapPane(href);
      if (PANES.indexOf(href) < 0) return;
      e.preventDefault();
      showPane(href);
      if (history.replaceState) history.replaceState(null, "", "#" + href);
    });
  }

  function setupBottomNav() {
    var items = document.querySelectorAll(".mob-nav-item");
    for (var i = 0; i < items.length; i++) {
      items[i].addEventListener("click", function (e) {
        e.preventDefault();
        var id = this.getAttribute("data-section") || "diagnose";
        showPane(id);
        if (history.replaceState) history.replaceState(null, "", "#" + id);
      });
    }
  }

  function setupHeaderNav() {
    var links = document.querySelectorAll(".nav a[href^='#'], .brand[href^='#'], .site-footer a[href^='#']");
    for (var i = 0; i < links.length; i++) bindPaneLink(links[i]);
  }

  function paneFromHash() {
    var h = (location.hash || "").replace(/^#/, "");
    if (h === "results" || h === "top" || h === "dropzone") h = "diagnose";
    if (PANES.indexOf(h) >= 0) return h;
    return "diagnose";
  }

  function wrapScrollShell() {
    var existing = document.querySelector(".mobile-scroll") || document.querySelector(".app-scroll");
    if (existing) {
      existing.classList.add("app-scroll");
      existing.classList.add("mobile-scroll");
      return;
    }
    var layout = document.querySelector(".layout");
    var footer = document.querySelector(".site-footer");
    if (!layout) return;

    var shell = document.createElement("div");
    shell.className = "app-scroll mobile-scroll";
    layout.parentNode.insertBefore(shell, layout);
    shell.appendChild(layout);
    if (footer) shell.appendChild(footer);
  }

  function init() {
    wrapScrollShell();
    setupUpload();
    setupBottomNav();
    setupHeaderNav();
    currentPane = paneFromHash();
    showPane(currentPane, { keepScroll: true });

    window.addEventListener("hashchange", function () {
      showPane(paneFromHash());
    });
  }

  window.agroscanShowPane = showPane;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
