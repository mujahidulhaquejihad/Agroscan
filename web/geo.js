/* One GPS read on app open. Shop, weather, and chat all reuse this. */
(function () {
  var KEY = "agroscan_geo_v1";
  var cached = null;
  var inflight = null;

  try {
    cached = JSON.parse(localStorage.getItem(KEY) || "null");
    if (!cached || cached.lat == null || cached.lng == null) cached = null;
  } catch (e) {
    cached = null;
  }

  function save(lat, lng) {
    cached = { lat: lat, lng: lng, ts: Date.now() };
    try { localStorage.setItem(KEY, JSON.stringify(cached)); } catch (e) {}
    document.dispatchEvent(new CustomEvent("agroscan-geo", { detail: cached }));
    return cached;
  }

  function capGeo() {
    try {
      var C = window.Capacitor;
      if (!C) return null;
      if (C.Plugins && C.Plugins.Geolocation) return C.Plugins.Geolocation;
      if (typeof C.registerPlugin === "function") return C.registerPlugin("Geolocation");
    } catch (e) {}
    return null;
  }

  function fromBrowser(ok, fail) {
    if (!navigator.geolocation) {
      if (fail) fail({ code: 0 });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        ok(save(pos.coords.latitude, pos.coords.longitude));
      },
      function (err) { if (fail) fail(err); },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 300000 }
    );
  }

  function locate(ok, fail) {
    if (inflight) {
      inflight.then(function (p) { if (ok) ok(p); }).catch(function (e) { if (fail) fail(e); });
      return inflight;
    }
    inflight = new Promise(function (resolve, reject) {
      function done(p) {
        inflight = null;
        resolve(p);
        if (ok) ok(p);
      }
      function boom(err) {
        inflight = null;
        reject(err || {});
        if (fail) fail(err);
      }
      var geo = capGeo();
      if (geo && typeof geo.getCurrentPosition === "function") {
        var run = function () {
          geo.getCurrentPosition({ enableHighAccuracy: true, timeout: 15000 }).then(function (pos) {
            var c = pos && pos.coords;
            if (!c) {
              fromBrowser(done, boom);
              return;
            }
            done(save(c.latitude, c.longitude));
          }).catch(function () { fromBrowser(done, boom); });
        };
        if (typeof geo.requestPermissions === "function") {
          geo.requestPermissions().then(run).catch(run);
        } else {
          run();
        }
        return;
      }
      fromBrowser(done, boom);
    });
    return inflight;
  }

  function boot() {
    if (cached) {
      document.dispatchEvent(new CustomEvent("agroscan-geo", { detail: cached }));
    }
    locate(function () {}, function () {});
  }

  window.AgroScanGeo = {
    locate: locate,
    get: function () { return cached; },
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
