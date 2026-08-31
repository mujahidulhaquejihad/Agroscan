/* Farmer notifications: pack news + local field/PHI alerts */
(function () {
  var READ_KEY = "agroscan_news_read_v1";
  var CACHE_KEY = "agroscan_news_cache_v1";
  var cfg = window.AGROSCAN_CONFIG || {};
  var API = cfg.API_BASE || "";

  function $(id) { return document.getElementById(id); }
  function T(key, vars) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key, vars) : key;
  }
  function isBn() {
    var lang = window.AgroScanI18n ? window.AgroScanI18n.lang : "bn";
    return String(lang || "").indexOf("bn") === 0;
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function loadRead() {
    try {
      var raw = JSON.parse(localStorage.getItem(READ_KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (e) { return []; }
  }
  function saveRead(ids) {
    try { localStorage.setItem(READ_KEY, JSON.stringify(ids.slice(-200))); } catch (e) {}
  }
  function isRead(id, readSet) {
    return readSet.indexOf(id) >= 0;
  }
  function markRead(id) {
    var read = loadRead();
    if (read.indexOf(id) < 0) {
      read.push(id);
      saveRead(read);
    }
    updateBadge();
  }
  function markAllRead(items) {
    var read = loadRead();
    var i;
    for (i = 0; i < items.length; i++) {
      if (items[i].id && read.indexOf(items[i].id) < 0) read.push(items[i].id);
    }
    saveRead(read);
    updateBadge();
    renderList(items);
  }

  function localAlerts() {
    var out = [];
    var today = new Date().toISOString().slice(0, 10);

    // PHI / spray alerts from Field module
    try {
      var sprays = JSON.parse(localStorage.getItem("agroscan_sprays_v1") || "[]");
      var i;
      for (i = 0; i < (sprays || []).length; i++) {
        var s = sprays[i];
        if (!s || s.done || !s.harvest_ok_at) continue;
        var left = Math.ceil((s.harvest_ok_at - Date.now()) / (24 * 60 * 60 * 1000));
        var title, body, pri;
        if (left > 0) {
          pri = left <= 2 ? "high" : "normal";
          title = T("notif_phi_title");
          body = T("field_phi_countdown", {
            days: left,
            date: new Date(s.harvest_ok_at).toLocaleDateString(),
            name: s.title || s.disease || s.plot_name || ""
          });
        } else {
          pri = "high";
          title = T("notif_phi_ready_title");
          body = T("field_phi_ready", { name: s.title || s.disease || "" });
        }
        out.push({
          id: "local-phi-" + s.id,
          date: today,
          priority: pri,
          category: "field",
          title: title,
          body: body,
          link: "#field",
          source: "local"
        });
      }
    } catch (e) {}

    // Scout reminder
    try {
      var last = parseInt(localStorage.getItem("agroscan_last_scout_v1") || "0", 10) || 0;
      var week = 7 * 24 * 60 * 60 * 1000;
      if (!last || (Date.now() - last) >= week) {
        out.push({
          id: "local-scout-" + today,
          date: today,
          priority: "normal",
          category: "tip",
          title: T("notif_scout_title"),
          body: T("scout_reminder_text"),
          link: "#diagnose",
          source: "local"
        });
      }
    } catch (e) {}

    return out;
  }

  function cacheNews(payload) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        saved_at: Date.now(),
        lang: isBn() ? "bn" : "en",
        payload: payload
      }));
    } catch (e) {}
  }

  function loadCachedNews() {
    try {
      var raw = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
      if (!raw || !raw.payload) return null;
      return raw.payload;
    } catch (e) { return null; }
  }

  function mergeFeed(remoteItems) {
    var local = localAlerts();
    var seen = {};
    var all = [];
    var i;
    for (i = 0; i < local.length; i++) {
      if (!seen[local[i].id]) {
        seen[local[i].id] = 1;
        all.push(local[i]);
      }
    }
    for (i = 0; i < (remoteItems || []).length; i++) {
      var it = remoteItems[i];
      if (!it || !it.id || seen[it.id]) continue;
      seen[it.id] = 1;
      all.push(it);
    }
    all.sort(function (a, b) {
      var pa = a.priority === "high" ? 0 : 1;
      var pb = b.priority === "high" ? 0 : 1;
      if (pa !== pb) return pa - pb;
      return String(b.date || "").localeCompare(String(a.date || ""));
    });
    return all;
  }

  function catLabel(cat) {
    var key = "notif_cat_" + (cat || "tip");
    var t = T(key);
    return t === key ? (cat || "tip") : t;
  }

  function renderList(items) {
    var el = $("notifList");
    if (!el) return;
    var read = loadRead();
    if (!items.length) {
      el.innerHTML = "<p class='muted'>" + T("notif_empty") + "</p>";
      updateBadge();
      return;
    }
    el.innerHTML = items.map(function (it) {
      var unread = !isRead(it.id, read);
      var link = it.link
        ? (String(it.link).indexOf("tel:") === 0 || String(it.link).indexOf("http") === 0
          ? ("<a class='btn btn-secondary btn-sm' href='" + esc(it.link) + "' target='_blank' rel='noopener'>" +
            T("notif_open") + "</a>")
          : ("<button type='button' class='btn btn-secondary btn-sm notif-goto' data-href='" +
            esc(it.link) + "'>" + T("notif_open") + "</button>"))
        : "";
      return "<article class='notif-card" + (unread ? " is-unread" : "") +
        "' data-id='" + esc(it.id) + "'>" +
        "<div class='notif-meta'>" +
        "<span class='notif-cat'>" + esc(catLabel(it.category)) + "</span>" +
        (it.priority === "high" ? "<span class='notif-pri'>" + T("notif_priority_high") + "</span>" : "") +
        (unread ? "<span class='notif-new'>" + T("notif_new") + "</span>" : "") +
        "</div>" +
        "<h3>" + esc(it.title || "") + "</h3>" +
        "<p>" + esc(it.body || "") + "</p>" +
        "<div class='notif-foot'>" +
        "<span class='muted small'>" + esc(it.date || "") + "</span>" +
        "<div class='notif-actions'>" + link +
        (unread
          ? ("<button type='button' class='btn btn-ghost btn-sm notif-read' data-id='" +
            esc(it.id) + "'>" + T("notif_mark_read") + "</button>")
          : "") +
        "</div></div></article>";
    }).join("");

    var readBtns = el.getElementsByClassName("notif-read");
    var i;
    for (i = 0; i < readBtns.length; i++) {
      readBtns[i].onclick = function () {
        markRead(this.getAttribute("data-id"));
        var card = this.closest ? this.closest(".notif-card") : null;
        if (card) {
          card.classList.remove("is-unread");
          var neu = card.querySelector(".notif-new");
          if (neu) neu.parentNode.removeChild(neu);
          this.parentNode.removeChild(this);
        }
        updateBadge();
      };
    }
    var goBtns = el.getElementsByClassName("notif-goto");
    for (i = 0; i < goBtns.length; i++) {
      goBtns[i].onclick = function () {
        var href = (this.getAttribute("data-href") || "").replace(/^#/, "");
        var card = this.closest ? this.closest(".notif-card") : null;
        if (card) markRead(card.getAttribute("data-id"));
        if (window.agroscanShowPane && href) window.agroscanShowPane(href);
        else if (href) location.hash = "#" + href;
      };
    }
    // Opening a card marks read
    var cards = el.getElementsByClassName("notif-card");
    for (i = 0; i < cards.length; i++) {
      cards[i].addEventListener("click", function (ev) {
        if (ev.target && (ev.target.tagName === "A" || ev.target.tagName === "BUTTON" ||
            (ev.target.closest && ev.target.closest("a,button")))) return;
        markRead(this.getAttribute("data-id"));
        this.classList.remove("is-unread");
        var neu = this.querySelector(".notif-new");
        if (neu) neu.parentNode.removeChild(neu);
        var rb = this.querySelector(".notif-read");
        if (rb) rb.parentNode.removeChild(rb);
        updateBadge();
      });
    }
    updateBadge();
  }

  function unreadCount(items) {
    var read = loadRead();
    var n = 0;
    var i;
    for (i = 0; i < items.length; i++) {
      if (items[i].id && !isRead(items[i].id, read)) n += 1;
    }
    return n;
  }

  function updateBadge(items) {
    if (!items) {
      var cached = loadCachedNews();
      items = mergeFeed((cached && cached.items) || []);
    }
    var n = unreadCount(items);
    var badges = document.querySelectorAll(".notif-badge");
    var i;
    for (i = 0; i < badges.length; i++) {
      if (n > 0) {
        badges[i].textContent = n > 9 ? "9+" : String(n);
        badges[i].classList.remove("hidden");
      } else {
        badges[i].textContent = "";
        badges[i].classList.add("hidden");
      }
    }
  }

  var lastItems = [];

  function showFeed(payload) {
    var items = mergeFeed((payload && payload.items) || []);
    lastItems = items;
    renderList(items);
    var meta = $("notifMeta");
    if (meta) {
      meta.textContent = T("notif_count", { n: items.length });
    }
  }

  function fetchNews() {
    var lang = isBn() ? "bn" : "en";
    var status = $("notifStatus");
    if (status) status.textContent = T("notif_loading");

    // Show cache immediately for offline-first
    var cached = loadCachedNews();
    if (cached) showFeed(cached);

    var x = new XMLHttpRequest();
    x.open("GET", API + "/api/news?lang=" + encodeURIComponent(lang) + "&limit=40", true);
    x.timeout = 20000;
    x.onload = function () {
      try {
        var data = JSON.parse(x.responseText || "{}");
        if (x.status >= 200 && x.status < 300) {
          cacheNews(data);
          showFeed(data);
          if (status) status.textContent = "";
          return;
        }
      } catch (e) {}
      if (!cached) showFeed({ items: [] });
      if (status) status.textContent = T("notif_offline_cache");
    };
    x.onerror = x.ontimeout = function () {
      if (!cached) showFeed({ items: [] });
      if (status) status.textContent = T("notif_offline_cache");
    };
    x.send();
  }

  function init() {
    var refresh = $("notifRefresh");
    var markAll = $("notifMarkAll");
    if (refresh) refresh.onclick = fetchNews;
    if (markAll) {
      markAll.onclick = function () {
        markAllRead(lastItems.length ? lastItems : mergeFeed([]));
      };
    }
    fetchNews();
    document.addEventListener("langchange", fetchNews);

    // Refresh badge when opening the pane
    document.addEventListener("click", function (e) {
      var t = e.target;
      if (!t) return;
      var a = t.closest ? t.closest("[data-section='notifications'], a[href='#notifications']") : null;
      if (a) setTimeout(fetchNews, 30);
    });
  }

  window.AgroScanNotifications = {
    init: init,
    refresh: fetchNews,
    updateBadge: updateBadge
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
