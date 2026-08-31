/* Farmer UX helpers: season tips, sticky helpline, offline last advice, PHI, scout, feedback */
(function () {
  var ADVICE_KEY = "agrovet_last_advice_v1";
  var SCOUT_KEY = "agrovet_last_scout_v1";
  var FEEDBACK_KEY = "agrovet_feedback_log_v1";

  function $(id) { return document.getElementById(id); }
  function T(key, vars) {
    return window.AgrovetI18n ? window.AgrovetI18n.t(key, vars) : key;
  }
  function isBn() {
    var lang = window.AgrovetI18n ? window.AgrovetI18n.lang : "bn";
    return String(lang || "").indexOf("bn") === 0;
  }

  /* ---- Season tips (BD crop calendar, top diseases) ---- */
  var SEASON_TIPS = [
    { months: [11, 12, 1, 2], en: "Foggy Rabi: watch potato & tomato late blight. Spray before fog if possible.", bn: "কুয়াশা মৌসুম: আলু ও টমেটোর নাবি ধ্বসায় নজর রাখুন। সম্ভব হলে কুয়াশার আগেই স্প্রে করুন।", keys: ["Potato___Late_blight", "Tomato___Late_blight"] },
    { months: [6, 7, 8, 9, 10], en: "Wet season: rice blast, BLB and sheath blight risk is high. Scout weekly.", bn: "বর্ষা মৌসুম: ধানের ব্লাস্ট, BLB ও খোলপোড়ার ঝুঁকি বেশি। সপ্তাহে একবার জমি দেখুন।", keys: ["Rice___Blast", "Rice___Bacterial_leaf_blight", "Rice___Sheath_blight"] },
    { months: [2, 3, 4], en: "Wheat season: watch wheat blast and leaf rust in northern districts.", bn: "গম মৌসুম: উত্তরাঞ্চলে গমের ব্লাস্ট ও পাতার মরিচা দেখুন।", keys: ["Wheat___Blast", "Wheat___Leaf_rust"] },
    { months: [3, 4, 5, 6], en: "Summer vegetables: chilli leaf curl and brinjal shoot & fruit borer peak.", bn: "গ্রীষ্মকালীন সবজি: মরিচের পাতা কোঁকড়ানো ও বেগুনের ডগা/ফল ছিদ্রকারী পোকা বাড়ে।", keys: ["Chilli___Leaf_curl", "Brinjal___Shoot_and_fruit_borer"] },
    { months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], en: "Any month: upload a clear leaf photo for advice, or call 16123.", bn: "যেকোনো মাস: পরিষ্কার পাতার ছবি দিয়ে পরামর্শ নিন, অথবা ১৬১২৩-এ কল করুন।", keys: [] },
  ];

  function currentSeasonTip() {
    var m = new Date().getMonth() + 1;
    var i;
    for (i = 0; i < SEASON_TIPS.length; i++) {
      if (SEASON_TIPS[i].months.indexOf(m) >= 0) return SEASON_TIPS[i];
    }
    return SEASON_TIPS[SEASON_TIPS.length - 1];
  }

  function renderSeasonTip() {
    var el = $("seasonTip");
    if (!el) return;
    var tip = currentSeasonTip();
    el.innerHTML = "<strong>" + T("season_tip_title") + "</strong> " +
      (isBn() ? tip.bn : tip.en);
    el.className = "season-tip";
  }

  /* ---- Scout reminder (every 7 days) ---- */
  function renderScoutReminder() {
    var el = $("scoutReminder");
    if (!el) return;
    var last = 0;
    try { last = parseInt(localStorage.getItem(SCOUT_KEY) || "0", 10) || 0; } catch (e) {}
    var week = 7 * 24 * 60 * 60 * 1000;
    if (last && (Date.now() - last) < week) {
      el.className = "scout-reminder hidden";
      return;
    }
    el.className = "scout-reminder";
    el.innerHTML = "<span>" + T("scout_reminder_text") + "</span> " +
      "<button type='button' class='btn btn-secondary btn-sm' id='scoutDoneBtn'>" + T("scout_done") + "</button>";
    var btn = $("scoutDoneBtn");
    if (btn) {
      btn.onclick = function () {
        try { localStorage.setItem(SCOUT_KEY, String(Date.now())); } catch (e) {}
        el.className = "scout-reminder hidden";
      };
    }
  }

  /* ---- Cache last advice offline ---- */
  function cacheAdvice(payload) {
    try {
      localStorage.setItem(ADVICE_KEY, JSON.stringify({
        saved_at: Date.now(),
        disease: payload.disease || "",
        title: payload.title || "",
        summary: payload.summary || "",
        steps: payload.steps || [],
        treatment: payload.treatment || [],
        phi_days: payload.phi_days,
        helpline: payload.helpline || "",
      }));
    } catch (e) {}
  }

  function loadCachedAdvice() {
    try {
      var raw = localStorage.getItem(ADVICE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }

  function showOfflineAdvice() {
    var box = $("offlineAdviceBox");
    if (!box) return;
    // Prefer multi-card offline pack when available
    if (window.AgrovetField && window.AgrovetField.getPack) {
      var pack = window.AgrovetField.getPack() || [];
      if (pack.length) {
        var html = "<h3>" + T("offline_pack_title") + "</h3><p class='muted small'>" +
          T("offline_pack_hint") + "</p><div class='offline-pack-list'>";
        var i;
        for (i = 0; i < Math.min(8, pack.length); i++) {
          var c = pack[i];
          html += "<button type='button' class='offline-pack-item' data-idx='" + i + "'>" +
            "<strong>" + (c.title || c.disease || "") + "</strong>" +
            "<span class='muted small'>" + (c.summary ? String(c.summary).slice(0, 80) : "") +
            "</span></button>";
        }
        html += "</div><p><a class='btn btn-primary btn-sm' href='tel:16123'>16123</a> " +
          "<a class='btn btn-secondary btn-sm' href='tel:16358'>16358</a> " +
          "<button type='button' class='btn btn-ghost btn-sm' id='offlineGoField'>" +
          T("nav_field") + "</button></p>";
        box.innerHTML = html;
        box.className = "offline-advice";
        var items = box.getElementsByClassName("offline-pack-item");
        for (i = 0; i < items.length; i++) {
          items[i].onclick = function () {
            var idx = parseInt(this.getAttribute("data-idx"), 10);
            if (window.agroscanShowPane) window.agroscanShowPane("field");
            if (window.AgrovetField && window.AgrovetField.showOfflineDetail) {
              var detailPack = window.AgrovetField.getPack();
              // switch offline tab then show detail
              var tabs = document.querySelectorAll(".field-tab");
              var t;
              for (t = 0; t < tabs.length; t++) {
                if (tabs[t].getAttribute("data-tab") === "offline") tabs[t].click();
              }
              setTimeout(function () {
                window.AgrovetField.showOfflineDetail(detailPack[idx]);
              }, 50);
            }
          };
        }
        var go = $("offlineGoField");
        if (go) {
          go.onclick = function () {
            if (window.agroscanShowPane) window.agroscanShowPane("field");
          };
        }
        box.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return;
      }
    }
    var data = loadCachedAdvice();
    if (!data) {
      box.className = "offline-advice";
      box.innerHTML = "<p>" + T("offline_no_advice") + "</p>" +
        "<p><a href='tel:16123'>16123</a> · <a href='tel:16358'>16358</a></p>";
      return;
    }
    var html = "<h3>" + T("offline_last_advice") + "</h3>" +
      "<p><strong>" + (data.title || data.disease || "") + "</strong></p>" +
      "<p>" + (data.summary || "") + "</p>";
    if (data.steps && data.steps.length) {
      html += "<ol>";
      var j;
      for (j = 0; j < Math.min(6, data.steps.length); j++) {
        html += "<li>" + data.steps[j] + "</li>";
      }
      html += "</ol>";
    }
    if (data.treatment && data.treatment.length) {
      html += "<p><strong>" + T("treatment") + ":</strong> " + data.treatment.slice(0, 3).join("; ") + "</p>";
    }
    if (data.phi_days != null) {
      html += "<p class='phi-line'>" + T("phi_offline", { days: data.phi_days }) + "</p>";
    }
    html += "<p><a class='btn btn-primary btn-sm' href='tel:16123'>16123</a> " +
      "<a class='btn btn-secondary btn-sm' href='tel:16358'>16358</a></p>";
    box.innerHTML = html;
    box.className = "offline-advice";
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  /* ---- PHI reminder from advice ---- */
  function showPhiReminder(advice) {
    var el = $("phiReminder");
    if (!el) return;
    var phi = null;
    var tp = advice && advice.treatment_plan;
    if (tp && tp.chemical_treatments) {
      var i;
      for (i = 0; i < tp.chemical_treatments.length; i++) {
        var d = tp.chemical_treatments[i].phi_days;
        if (d != null && (phi == null || d > phi)) phi = d;
      }
    }
    if (phi == null) {
      el.className = "phi-reminder hidden";
      return;
    }
    el.className = "phi-reminder";
    el.innerHTML = "<strong>" + T("phi_title") + "</strong> " + T("phi_body", { days: phi });
  }

  /* ---- Action strip ---- */
  function showActionStrip(show) {
    var strip = $("farmerActionStrip");
    if (!strip) return;
    strip.className = show ? "farmer-action-strip" : "farmer-action-strip hidden";
  }

  function wireActionStrip() {
    var listen = $("farmerActListen");
    var buy = $("farmerActBuy");
    if (listen) {
      listen.onclick = function () {
        if ($("listenBtn")) $("listenBtn").click();
        else if (window.AgrovetFeatures && window.AgrovetFeatures.speakAdvice) {
          window.AgrovetFeatures.speakAdvice();
        }
      };
    }
    if (buy) {
      buy.onclick = function () {
        if (window.AgrovetShop && window.AgrovetShop.recommendForDisease) {
          window.AgrovetShop.recommendForDisease(window.AgroScanLastDisease || "", { stay: false });
        }
        if (window.agroscanShowPane) window.agroscanShowPane("shop");
      };
    }
  }

  /* ---- Feedback ---- */
  function wireFeedback(disease) {
    var box = $("adviceFeedback");
    if (!box) return;
    box.className = "advice-feedback";
    var thanks = $("feedbackThanks");
    if (thanks) thanks.className = "muted small hidden";
    var btns = box.querySelectorAll("[data-fb]");
    var i;
    for (i = 0; i < btns.length; i++) {
      btns[i].onclick = function () {
        var vote = this.getAttribute("data-fb");
        try {
          var log = JSON.parse(localStorage.getItem(FEEDBACK_KEY) || "[]");
          log.push({ at: Date.now(), disease: disease || "", vote: vote });
          if (log.length > 50) log = log.slice(-50);
          localStorage.setItem(FEEDBACK_KEY, JSON.stringify(log));
        } catch (e) {}
        // Attach vote onto the latest matching history scan
        try {
          if (window.AgrovetFeatures && window.AgrovetFeatures.attachFeedback) {
            window.AgrovetFeatures.attachFeedback(disease || "", vote);
          }
        } catch (e2) {}
        if (thanks) thanks.className = "muted small";
      };
    }
  }

  /* ---- Called after diagnosis render ---- */
  function onDiagnosis(data) {
    var d = data && (data.stage3_disease || data.stage2_disease);
    var b = d && d.best_answer;
    if (!b) {
      showActionStrip(false);
      return;
    }
    showActionStrip(true);
    showPhiReminder(b.advice);
    wireFeedback(b.prediction);

    var a = b.advice || {};
    var steps = [];
    var i;
    if (a.next_steps) {
      for (i = 0; i < a.next_steps.length; i++) {
        var s = a.next_steps[i] || {};
        steps.push((s.title || "") + (s.detail ? (": " + s.detail) : ""));
      }
    }
    var phi = null;
    var tp = a.treatment_plan;
    if (tp && tp.chemical_treatments) {
      for (i = 0; i < tp.chemical_treatments.length; i++) {
        var pd = tp.chemical_treatments[i].phi_days;
        if (pd != null && (phi == null || pd > phi)) phi = pd;
      }
    }
    cacheAdvice({
      disease: b.prediction || "",
      title: (b.plant || "") + " — " + (b.condition || ""),
      summary: a.description || a.summary || "",
      steps: steps,
      treatment: a.treatment || [],
      phi_days: phi,
      helpline: a.when_to_call_helpline || "",
    });

    if (window.AgrovetField && window.AgrovetField.onDiagnosis) {
      window.AgrovetField.onDiagnosis(data);
    }

    // Auto-read once for simple UI (short delay so UI paints)
    if (document.body.classList.contains("simple-ui") && window.speechSynthesis) {
      setTimeout(function () {
        if ($("listenBtn") && !window.__agrovetAutoSpoke) {
          window.__agrovetAutoSpoke = true;
          $("listenBtn").click();
        }
      }, 900);
    }
  }

  function init() {
    wireActionStrip();
    renderSeasonTip();
    renderScoutReminder();
    var showBtn = $("showOfflineAdviceBtn");
    if (showBtn) showBtn.onclick = showOfflineAdvice;
    document.addEventListener("langchange", function () {
      renderSeasonTip();
      renderScoutReminder();
      if (window.AgrovetI18n) window.AgrovetI18n.applyI18n();
    });
  }

  window.AgrovetFarmerUX = {
    init: init,
    onDiagnosis: onDiagnosis,
    showOfflineAdvice: showOfflineAdvice,
    cacheAdvice: cacheAdvice,
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
