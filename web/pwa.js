/* PWA install prompt + service worker registration */
(function () {
  var deferredPrompt = null;
  var banner = null;

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  function dismissKey() {
    return "agroscan_pwa_dismissed";
  }

  function hideBanner() {
    if (banner) banner.classList.add("hidden");
  }

  function showBanner() {
    if (isStandalone()) return;
    if (sessionStorage.getItem(dismissKey())) return;
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "pwaInstallBanner";
      banner.className = "pwa-install-banner";
      banner.innerHTML =
        '<div class="pwa-install-text">' +
        "<strong>Install AgroScan</strong>" +
        "<span>Add to your home screen for faster access</span>" +
        "</div>" +
        '<div class="pwa-install-actions">' +
        '<button type="button" class="btn btn-primary btn-sm" id="pwaInstallBtn">Install</button>' +
        '<button type="button" class="btn btn-ghost btn-sm" id="pwaDismissBtn">Not now</button>' +
        "</div>";
      document.body.appendChild(banner);
      document.getElementById("pwaDismissBtn").onclick = function () {
        sessionStorage.setItem(dismissKey(), "1");
        hideBanner();
      };
      document.getElementById("pwaInstallBtn").onclick = function () {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.finally(function () {
          deferredPrompt = null;
          hideBanner();
        });
      };
    }
    banner.classList.remove("hidden");
  }

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showBanner();
  });

  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    hideBanner();
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function (err) {
        console.warn("SW register failed", err);
      });
    });
  }
})();
