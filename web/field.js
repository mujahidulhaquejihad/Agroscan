/* My Field: plots + scan history, spray/PHI calendar, offline diagnosis pack */
(function () {
  var PLOTS_KEY = "agroscan_plots_v1";
  var ACTIVE_PLOT_KEY = "agroscan_active_plot_v1";
  var SPRAYS_KEY = "agroscan_sprays_v1";
  var PACK_KEY = "agroscan_offline_pack_v1";
  var PACK_MAX = 12;
  var DAY_MS = 24 * 60 * 60 * 1000;

  function $(id) { return document.getElementById(id); }
  function T(key, vars) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key, vars) : key;
  }
  function uid() {
    return "f" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }
  function loadJson(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      if (!raw) return fallback;
      var v = JSON.parse(raw);
      return v == null ? fallback : v;
    } catch (e) { return fallback; }
  }
  function saveJson(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {}
  }
  function fmtDate(ms) {
    try {
      return new Date(ms).toLocaleDateString(undefined, {
        year: "numeric", month: "short", day: "numeric"
      });
    } catch (e) { return ""; }
  }
  function daysLeft(untilMs) {
    return Math.ceil((untilMs - Date.now()) / DAY_MS);
  }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* ---------- Plots ---------- */
  function getPlots() { return loadJson(PLOTS_KEY, []); }
  function setPlots(list) { saveJson(PLOTS_KEY, list || []); }
  function getActivePlotId() { return localStorage.getItem(ACTIVE_PLOT_KEY) || ""; }
  function setActivePlotId(id) {
    try {
      if (id) localStorage.setItem(ACTIVE_PLOT_KEY, id);
      else localStorage.removeItem(ACTIVE_PLOT_KEY);
    } catch (e) {}
  }
  function getActivePlot() {
    var id = getActivePlotId();
    var plots = getPlots();
    var i;
    for (i = 0; i < plots.length; i++) {
      if (plots[i].id === id) return plots[i];
    }
    return plots[0] || null;
  }

  function addPlot(name, crop, landSize, landUnit) {
    var plots = getPlots();
    var p = {
      id: uid(),
      name: (name || "").trim() || T("field_plot_default"),
      crop: (crop || "").trim(),
      land_size: landSize || null,
      land_unit: landUnit || "decimal",
      created_at: Date.now(),
      updated_at: Date.now(),
      scans: []
    };
    plots.unshift(p);
    setPlots(plots);
    setActivePlotId(p.id);
    return p;
  }

  function deletePlot(id) {
    var plots = getPlots().filter(function (p) { return p.id !== id; });
    setPlots(plots);
    if (getActivePlotId() === id) setActivePlotId(plots[0] ? plots[0].id : "");
  }

  function appendScanToPlot(plotId, scan) {
    var plots = getPlots();
    var i;
    for (i = 0; i < plots.length; i++) {
      if (plots[i].id === plotId) {
        plots[i].scans = plots[i].scans || [];
        plots[i].scans.unshift(scan);
        if (plots[i].scans.length > 40) plots[i].scans = plots[i].scans.slice(0, 40);
        if (scan.plant && !plots[i].crop) plots[i].crop = scan.plant;
        plots[i].updated_at = Date.now();
        setPlots(plots);
        return plots[i];
      }
    }
    return null;
  }

  /* ---------- Sprays / PHI ---------- */
  function getSprays() { return loadJson(SPRAYS_KEY, []); }
  function setSprays(list) { saveJson(SPRAYS_KEY, list || []); }

  function logSpray(opts) {
    opts = opts || {};
    var phi = opts.phi_days != null ? Number(opts.phi_days) : null;
    if (phi == null || !(phi > 0)) phi = 7;
    var sprayedAt = opts.sprayed_at || Date.now();
    var entry = {
      id: uid(),
      plot_id: opts.plot_id || (getActivePlot() && getActivePlot().id) || "",
      plot_name: opts.plot_name || (getActivePlot() && getActivePlot().name) || "",
      disease: opts.disease || "",
      title: opts.title || "",
      product_note: opts.product_note || "",
      sprayed_at: sprayedAt,
      phi_days: phi,
      harvest_ok_at: sprayedAt + phi * DAY_MS,
      done: false
    };
    var list = getSprays();
    list.unshift(entry);
    if (list.length > 60) list = list.slice(0, 60);
    setSprays(list);
    maybeNotifyPhi(entry);
    return entry;
  }

  function markSprayDone(id) {
    var list = getSprays();
    var i;
    for (i = 0; i < list.length; i++) {
      if (list[i].id === id) {
        list[i].done = true;
        setSprays(list);
        return;
      }
    }
  }

  function activePhiSprays() {
    return getSprays().filter(function (s) {
      return !s.done && s.harvest_ok_at;
    });
  }

  function maybeNotifyPhi(entry) {
    if (!entry || !("Notification" in window)) return;
    if (Notification.permission !== "granted") return;
    try {
      new Notification(T("phi_title"), {
        body: T("phi_notify_body", {
          days: entry.phi_days,
          date: fmtDate(entry.harvest_ok_at),
          crop: entry.title || entry.disease || ""
        }),
        tag: "agroscan-phi-" + entry.id
      });
    } catch (e) {}
  }

  function requestNotifyPermission() {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      try { Notification.requestPermission(); } catch (e) {}
    }
  }

  /* ---------- Offline pack ---------- */
  function getPack() { return loadJson(PACK_KEY, []); }
  function setPack(list) { saveJson(PACK_KEY, list || []); }

  function pushOfflineCard(card) {
    if (!card || !card.disease) return;
    var pack = getPack().filter(function (c) { return c.disease !== card.disease; });
    pack.unshift(Object.assign({ saved_at: Date.now() }, card));
    if (pack.length > PACK_MAX) pack = pack.slice(0, PACK_MAX);
    setPack(pack);
    // Keep single last-advice key in sync for existing offline banner button
    try {
      localStorage.setItem("agroscan_last_advice_v1", JSON.stringify(pack[0]));
    } catch (e) {}
  }

  function cardFromDiagnosis(b, advice) {
    advice = advice || {};
    var steps = [];
    var i;
    if (advice.next_steps) {
      for (i = 0; i < advice.next_steps.length; i++) {
        var s = advice.next_steps[i] || {};
        steps.push((s.title || "") + (s.detail ? (": " + s.detail) : ""));
      }
    }
    var phi = null;
    var tp = advice.treatment_plan;
    if (tp && tp.chemical_treatments) {
      for (i = 0; i < tp.chemical_treatments.length; i++) {
        var pd = tp.chemical_treatments[i].phi_days;
        if (pd != null && (phi == null || pd > phi)) phi = pd;
      }
    }
    var plot = getActivePlot();
    return {
      disease: b.prediction || "",
      plant: b.plant || "",
      condition: b.condition || "",
      confidence: b.confidence,
      title: (b.plant || "") + " — " + (b.condition || ""),
      summary: advice.description || advice.summary || "",
      steps: steps,
      treatment: advice.treatment || [],
      prevention: advice.prevention || [],
      phi_days: phi,
      helpline: advice.when_to_call_helpline || "",
      plot_id: plot ? plot.id : "",
      plot_name: plot ? plot.name : ""
    };
  }

  /* ---------- Called after diagnosis ---------- */
  var lastCard = null;

  function onDiagnosis(data) {
    var d = data && (data.stage3_disease || data.stage2_disease);
    var b = d && d.best_answer;
    if (!b || !b.prediction) {
      lastCard = null;
      renderPhiBanner();
      return;
    }
    var card = cardFromDiagnosis(b, b.advice || {});
    lastCard = card;
    pushOfflineCard(card);

    var plot = getActivePlot();
    if (!plot) {
      plot = addPlot(T("field_plot_default"), card.plant || "", null, "decimal");
    }
    if (plot) {
      appendScanToPlot(plot.id, {
        id: uid(),
        at: Date.now(),
        disease: card.disease,
        plant: card.plant,
        condition: card.condition,
        confidence: card.confidence,
        title: card.title,
        summary: card.summary,
        steps: card.steps,
        treatment: card.treatment,
        phi_days: card.phi_days
      });
    }

    renderAll();
    showPostScanActions(card);
  }

  function showPostScanActions(card) {
    var el = $("fieldPostScan");
    if (!el || !card) return;
    var plot = getActivePlot();
    var plotLabel = plot ? esc(plot.name) : T("field_no_active_plot");
    el.className = "field-post-scan";
    el.innerHTML =
      "<p class='muted small'>" + T("field_saved_hint", { plot: plotLabel }) + "</p>" +
      "<div class='field-post-actions'>" +
      "<button type='button' class='btn btn-primary btn-sm' id='fieldLogSprayBtn'>" +
      T("field_log_spray") + "</button>" +
      "<button type='button' class='btn btn-secondary btn-sm' id='fieldOpenBtn'>" +
      T("nav_field") + "</button>" +
      "</div>";
    var sprayBtn = $("fieldLogSprayBtn");
    var openBtn = $("fieldOpenBtn");
    if (sprayBtn) {
      sprayBtn.onclick = function () {
        requestNotifyPermission();
        logSpray({
          disease: card.disease,
          title: card.title,
          phi_days: card.phi_days,
          plot_id: plot ? plot.id : "",
          plot_name: plot ? plot.name : ""
        });
        renderAll();
        el.innerHTML = "<p class='field-ok'>" + T("field_spray_logged", {
          days: card.phi_days != null ? card.phi_days : 7,
          date: fmtDate(Date.now() + (card.phi_days != null ? card.phi_days : 7) * DAY_MS)
        }) + "</p>";
      };
    }
    if (openBtn) {
      openBtn.onclick = function () {
        if (window.agroscanShowPane) window.agroscanShowPane("field");
        else location.hash = "#field";
      };
    }
  }

  /* ---------- Render ---------- */
  var currentTab = "plots";

  function setTab(tab) {
    currentTab = tab || "plots";
    var tabs = document.querySelectorAll(".field-tab");
    var i;
    for (i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute("data-tab") === currentTab;
      tabs[i].className = on ? "field-tab active" : "field-tab";
    }
    var panels = ["fieldPlotsPanel", "fieldCalendarPanel", "fieldOfflinePanel"];
    var map = { plots: "fieldPlotsPanel", calendar: "fieldCalendarPanel", offline: "fieldOfflinePanel" };
    for (i = 0; i < panels.length; i++) {
      var el = $(panels[i]);
      if (!el) continue;
      el.className = panels[i] === map[currentTab] ? "field-panel" : "field-panel hidden";
    }
  }

  function renderPhiBanner() {
    var el = $("fieldPhiBanner");
    if (!el) return;
    var active = activePhiSprays().filter(function (s) {
      return daysLeft(s.harvest_ok_at) >= 0;
    });
    var ready = activePhiSprays().filter(function (s) {
      return daysLeft(s.harvest_ok_at) < 0 && !s.done;
    });
    if (!active.length && !ready.length) {
      el.className = "field-phi-banner hidden";
      el.innerHTML = "";
      return;
    }
    var html = "";
    if (active.length) {
      var soon = active.slice().sort(function (a, b) {
        return a.harvest_ok_at - b.harvest_ok_at;
      })[0];
      var left = daysLeft(soon.harvest_ok_at);
      html += "<strong>" + T("phi_title") + "</strong> " +
        T("field_phi_countdown", {
          days: Math.max(0, left),
          date: fmtDate(soon.harvest_ok_at),
          name: soon.title || soon.disease || soon.plot_name || ""
        });
    }
    if (ready.length) {
      html += (html ? "<br/>" : "") + T("field_phi_ready", {
        name: ready[0].title || ready[0].disease || ""
      });
    }
    html += " <button type='button' class='btn btn-ghost btn-sm' id='fieldPhiOpen'>" +
      T("field_view_calendar") + "</button>";
    el.innerHTML = html;
    el.className = "field-phi-banner";
    var btn = $("fieldPhiOpen");
    if (btn) {
      btn.onclick = function () {
        if (window.agroscanShowPane) window.agroscanShowPane("field");
        setTab("calendar");
      };
    }
  }

  function applyPlotLand(plot) {
    if (!plot || !(Number(plot.land_size) > 0)) return;
    var sizeEl = $("adviceLandSize") || $("farmLandSize");
    var unitEl = $("adviceLandUnit") || $("farmLandUnit");
    if (sizeEl) sizeEl.value = String(plot.land_size);
    if (unitEl) unitEl.value = plot.land_unit || "decimal";
    try {
      localStorage.setItem("agroscan_land", JSON.stringify({
        size: Number(plot.land_size),
        unit: plot.land_unit || "decimal"
      }));
    } catch (e) {}
  }

  function renderDiagnoseFieldPicker() {
    var selectEl = $("diagnoseFieldSelect");
    var quick = $("diagnoseFieldQuickAdd");
    if (!selectEl) return;
    var plots = getPlots();
    var activeId = getActivePlotId();
    if (!activeId && plots[0]) {
      activeId = plots[0].id;
      setActivePlotId(activeId);
    }
    if (!plots.length) {
      selectEl.innerHTML = "<option value=''>" + T("diagnose_no_field") + "</option>";
      if (quick) quick.className = "diagnose-field-quick";
    } else {
      selectEl.innerHTML = plots.map(function (p) {
        return "<option value='" + esc(p.id) + "'" +
          (p.id === activeId ? " selected" : "") + ">" +
          esc(p.name) + (p.crop ? (" · " + esc(p.crop)) : "") +
          "</option>";
      }).join("");
      if (quick && !quick.classList.contains("force-open")) {
        quick.className = "diagnose-field-quick hidden";
      }
    }
    selectEl.onchange = function () {
      var id = selectEl.value;
      if (!id) return;
      setActivePlotId(id);
      applyPlotLand(getActivePlot());
      renderPlots();
      renderPhiBanner();
    };
  }

  function wireDiagnoseFieldPicker() {
    var addBtn = $("diagnoseFieldAddBtn");
    var saveBtn = $("diagnoseFieldQuickSave");
    var quick = $("diagnoseFieldQuickAdd");
    if (addBtn) {
      addBtn.onclick = function () {
        if (!quick) return;
        var open = !quick.classList.contains("hidden");
        if (open) {
          quick.className = "diagnose-field-quick hidden";
          quick.classList.remove("force-open");
        } else {
          quick.className = "diagnose-field-quick force-open";
          var nameEl = $("diagnoseFieldNewName");
          if (nameEl) {
            try { nameEl.focus(); } catch (e) {}
          }
        }
      };
    }
    if (saveBtn) {
      saveBtn.onclick = function () {
        var nameEl = $("diagnoseFieldNewName");
        var cropEl = $("diagnoseFieldNewCrop");
        var name = nameEl ? nameEl.value : "";
        var crop = cropEl ? cropEl.value : "";
        var p = addPlot(name, crop, null, "decimal");
        if (nameEl) nameEl.value = "";
        if (cropEl) cropEl.value = "";
        if (quick) {
          quick.className = "diagnose-field-quick hidden";
          quick.classList.remove("force-open");
        }
        applyPlotLand(p);
        renderPlots();
        renderDiagnoseFieldPicker();
        renderPhiBanner();
      };
    }
  }

  function renderPlots() {
    var listEl = $("fieldPlotList");
    var scanEl = $("fieldScanList");
    var selectEl = $("fieldActiveSelect");
    renderDiagnoseFieldPicker();
    if (!listEl) return;
    var plots = getPlots();
    var activeId = getActivePlotId();
    if (!activeId && plots[0]) {
      activeId = plots[0].id;
      setActivePlotId(activeId);
    }

    if (selectEl) {
      selectEl.innerHTML = plots.length
        ? plots.map(function (p) {
            return "<option value='" + esc(p.id) + "'" +
              (p.id === activeId ? " selected" : "") + ">" +
              esc(p.name) + (p.crop ? (" · " + esc(p.crop)) : "") +
              "</option>";
          }).join("")
        : "<option value=''>" + T("field_no_plots") + "</option>";
      selectEl.onchange = function () {
        setActivePlotId(selectEl.value);
        applyPlotLand(getActivePlot());
        renderPlots();
        renderPhiBanner();
      };
    }

    if (!plots.length) {
      listEl.innerHTML = "<p class='muted'>" + T("field_plots_empty") + "</p>";
    } else {
      listEl.innerHTML = plots.map(function (p) {
        var n = (p.scans && p.scans.length) || 0;
        return "<article class='field-plot-card" + (p.id === activeId ? " is-active" : "") +
          "' data-id='" + esc(p.id) + "'>" +
          "<div><strong>" + esc(p.name) + "</strong>" +
          (p.crop ? "<div class='muted small'>" + esc(p.crop) + "</div>" : "") +
          "<div class='muted small'>" + T("field_scan_count", { n: n }) + "</div></div>" +
          "<div class='field-plot-actions'>" +
          "<button type='button' class='btn btn-secondary btn-sm field-plot-use' data-id='" +
          esc(p.id) + "'>" + T("field_use_plot") + "</button>" +
          "<button type='button' class='btn btn-ghost btn-sm field-plot-del' data-id='" +
          esc(p.id) + "'>" + T("field_delete_plot") + "</button>" +
          "</div></article>";
      }).join("");
      var useBtns = listEl.getElementsByClassName("field-plot-use");
      var delBtns = listEl.getElementsByClassName("field-plot-del");
      var i;
      for (i = 0; i < useBtns.length; i++) {
        useBtns[i].onclick = function () {
          setActivePlotId(this.getAttribute("data-id"));
          applyPlotLand(getActivePlot());
          renderPlots();
          renderPhiBanner();
        };
      }
      for (i = 0; i < delBtns.length; i++) {
        delBtns[i].onclick = function () {
          if (!confirm(T("field_delete_confirm"))) return;
          deletePlot(this.getAttribute("data-id"));
          renderPlots();
        };
      }
    }

    var active = getActivePlot();
    if (!scanEl) return;
    if (!active || !(active.scans && active.scans.length)) {
      scanEl.innerHTML = "<p class='muted'>" + T("field_scans_empty") + "</p>";
      return;
    }
    scanEl.innerHTML = active.scans.slice(0, 20).map(function (s) {
      var conf = s.confidence != null ? (Math.round(Number(s.confidence) * 100) + "%") : "";
      return "<div class='field-scan-item'>" +
        "<div><strong>" + esc(s.title || s.disease) + "</strong>" +
        "<div class='muted small'>" + fmtDate(s.at) +
        (conf ? (" · " + conf) : "") + "</div>" +
        (s.summary ? "<p class='small'>" + esc(String(s.summary).slice(0, 160)) + "</p>" : "") +
        "</div></div>";
    }).join("");
  }

  function renderCalendar() {
    var el = $("fieldCalendarList");
    if (!el) return;
    var list = getSprays();
    if (!list.length) {
      el.innerHTML = "<p class='muted'>" + T("field_calendar_empty") + "</p>";
      return;
    }
    el.innerHTML = list.slice(0, 30).map(function (s) {
      var left = daysLeft(s.harvest_ok_at);
      var status;
      if (s.done) status = T("field_spray_done");
      else if (left > 0) status = T("field_phi_days_left", { days: left });
      else if (left === 0) status = T("field_phi_today");
      else status = T("field_phi_can_harvest");
      return "<article class='field-spray-card" + (s.done ? " is-done" : "") + "'>" +
        "<div><strong>" + esc(s.title || s.disease || T("field_spray")) + "</strong>" +
        (s.plot_name ? "<div class='muted small'>" + esc(s.plot_name) + "</div>" : "") +
        "<div class='muted small'>" + T("field_sprayed_on", { date: fmtDate(s.sprayed_at) }) +
        " · PHI " + (s.phi_days || "?") + " " + T("days") + "</div>" +
        "<div class='field-spray-status'>" + status + "</div>" +
        "<div class='muted small'>" + T("field_harvest_after", { date: fmtDate(s.harvest_ok_at) }) +
        "</div></div>" +
        (!s.done
          ? ("<button type='button' class='btn btn-secondary btn-sm field-spray-done' data-id='" +
            esc(s.id) + "'>" + T("field_mark_done") + "</button>")
          : "") +
        "</article>";
    }).join("");
    var btns = el.getElementsByClassName("field-spray-done");
    var i;
    for (i = 0; i < btns.length; i++) {
      btns[i].onclick = function () {
        markSprayDone(this.getAttribute("data-id"));
        renderCalendar();
        renderPhiBanner();
      };
    }
  }

  function renderOffline() {
    var el = $("fieldOfflineList");
    if (!el) return;
    var pack = getPack();
    if (!pack.length) {
      el.innerHTML = "<p class='muted'>" + T("field_offline_empty") + "</p>";
      return;
    }
    el.innerHTML = pack.map(function (c, idx) {
      return "<article class='field-offline-card' data-idx='" + idx + "'>" +
        "<div><strong>" + esc(c.title || c.disease) + "</strong>" +
        "<div class='muted small'>" + fmtDate(c.saved_at) +
        (c.plot_name ? (" · " + esc(c.plot_name)) : "") + "</div></div>" +
        "<button type='button' class='btn btn-secondary btn-sm field-offline-open' data-idx='" +
        idx + "'>" + T("field_open_card") + "</button></article>";
    }).join("") + "<div id='fieldOfflineDetail' class='field-offline-detail hidden'></div>";

    var btns = el.getElementsByClassName("field-offline-open");
    var i;
    for (i = 0; i < btns.length; i++) {
      btns[i].onclick = function () {
        showOfflineDetail(pack[parseInt(this.getAttribute("data-idx"), 10)]);
      };
    }
  }

  function showOfflineDetail(c) {
    var box = $("fieldOfflineDetail");
    if (!box || !c) return;
    var html = "<h4>" + esc(c.title || c.disease) + "</h4>" +
      "<p>" + esc(c.summary || "") + "</p>";
    if (c.steps && c.steps.length) {
      html += "<ol>";
      var i;
      for (i = 0; i < Math.min(8, c.steps.length); i++) {
        html += "<li>" + esc(c.steps[i]) + "</li>";
      }
      html += "</ol>";
    }
    if (c.treatment && c.treatment.length) {
      html += "<p><strong>" + T("treatment") + ":</strong> " +
        esc(c.treatment.slice(0, 4).join("; ")) + "</p>";
    }
    if (c.prevention && c.prevention.length) {
      html += "<p><strong>" + T("prevention") + ":</strong> " +
        esc(c.prevention.slice(0, 3).join("; ")) + "</p>";
    }
    if (c.phi_days != null) {
      html += "<p class='phi-line'>" + T("phi_offline", { days: c.phi_days }) + "</p>";
    }
    html += "<p><a class='btn btn-primary btn-sm' href='tel:16123'>16123</a> " +
      "<a class='btn btn-secondary btn-sm' href='tel:16358'>16358</a></p>";
    box.innerHTML = html;
    box.className = "field-offline-detail";
  }

  function renderAll() {
    renderPlots();
    renderCalendar();
    renderOffline();
    renderPhiBanner();
  }

  function wireForm() {
    var form = $("fieldPlotForm");
    if (!form) return;
    form.onsubmit = function (e) {
      e.preventDefault();
      var name = ($("fieldPlotName") || {}).value;
      var crop = ($("fieldPlotCrop") || {}).value;
      var sizeEl = $("fieldPlotSize");
      var unitEl = $("fieldPlotUnit");
      var size = sizeEl && sizeEl.value ? parseFloat(sizeEl.value) : null;
      addPlot(name, crop, size, unitEl ? unitEl.value : "decimal");
      if ($("fieldPlotName")) $("fieldPlotName").value = "";
      if ($("fieldPlotCrop")) $("fieldPlotCrop").value = "";
      renderPlots();
      setTab("plots");
    };
  }

  function wireTabs() {
    var tabs = document.querySelectorAll(".field-tab");
    var i;
    for (i = 0; i < tabs.length; i++) {
      tabs[i].onclick = function () {
        setTab(this.getAttribute("data-tab"));
      };
    }
  }

  function init() {
    wireForm();
    wireTabs();
    wireDiagnoseFieldPicker();
    setTab("plots");
    renderAll();
    applyPlotLand(getActivePlot());
    document.addEventListener("langchange", function () {
      renderAll();
      setTab(currentTab);
    });
  }

  window.AgroScanField = {
    init: init,
    onDiagnosis: onDiagnosis,
    renderAll: renderAll,
    getActivePlot: getActivePlot,
    setActivePlotId: setActivePlotId,
    renderDiagnoseFieldPicker: renderDiagnoseFieldPicker,
    getPack: getPack,
    logSpray: logSpray,
    showOfflineDetail: showOfflineDetail
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
