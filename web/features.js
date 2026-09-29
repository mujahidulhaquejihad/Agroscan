// Extra AgroScan features: dark mode, history, weather/spraying, crop calendar,
// daily tip, disease library, text-to-speech, downloadable report.
(function () {
  const T = () => window.AgroScanI18n;
  const $ = (id) => document.getElementById(id);
  const API = (window.AGROSCAN_CONFIG && window.AGROSCAN_CONFIG.API_BASE) || "";

  function bind(id, fn) {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  }

  /* ---------------- Dark mode ---------------- */
  const THEME_KEY = "agroscan_theme";
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    const b = $("darkToggle");
    if (b) b.textContent = theme === "dark" ? "\u2600" : "\u263D";
  }
  function initDark() {
    applyTheme(localStorage.getItem(THEME_KEY) || "light");
    bind("darkToggle", () => {
      const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(THEME_KEY, next);
      applyTheme(next);
    });
  }

  /* ---------------- Diagnosis history (sidebar + Photo page) ---------------- */
  const HKEY = "agroscan_history";
  const HMAX = 15;
  const getHistory = () => {
    try {
      const raw = JSON.parse(localStorage.getItem(HKEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (e) { return []; }
  };
  function persistHistory(list) {
    const clipped = (list || []).slice(0, HMAX);
    try {
      localStorage.setItem(HKEY, JSON.stringify(clipped));
      return true;
    } catch (e) {
      // Quota: drop oldest image data first, then drop entries
      let next = clipped.map((e, i) => {
        if (i > 4 && e && e.image) {
          const copy = Object.assign({}, e);
          copy.image = "";
          copy.thumb = copy.thumb && copy.thumb.length < 80000 ? copy.thumb : "";
          return copy;
        }
        return e;
      });
      try {
        localStorage.setItem(HKEY, JSON.stringify(next));
        return true;
      } catch (e2) {
        next = next.slice(0, 8);
        try {
          localStorage.setItem(HKEY, JSON.stringify(next));
          return true;
        } catch (e3) {
          return false;
        }
      }
    }
  }
  function saveHistory(entry) {
    const h = getHistory().filter((x) => !(entry.id && x.id === entry.id));
    h.unshift(entry);
    persistHistory(h);
    renderHistory();
    renderPhotoHistory();
  }
  function setHistoryViewMode(on) {
    const workspace = $("diagnose");
    const capture = $("diagnoseCapture");
    const detail = $("photoHistoryDetail");
    const results = $("results");
    if (workspace) workspace.classList.toggle("is-viewing-history", !!on);
    document.body.classList.toggle("history-detail-open", !!on);
    if (capture) capture.classList.toggle("hidden", !!on);
    if (on) {
      if (results) results.classList.add("hidden");
    }
    if (!on && detail) {
      detail.className = "photo-history-detail hidden";
      detail.innerHTML = "";
      setActiveHistoryCard(-1);
    }
  }

  function clearHistoryAll() {
    try { localStorage.removeItem(HKEY); } catch (e) {}
    renderHistory();
    renderPhotoHistory();
    setHistoryViewMode(false);
  }
  function fmtHistTime(t) {
    try { return new Date(t).toLocaleString(); } catch (e) { return ""; }
  }
  function escHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function pctHist(x) {
    if (x == null || isNaN(Number(x))) return "";
    return (Number(x) * 100).toFixed(1) + "%";
  }
  function listItems(arr, limit) {
    if (!arr || !arr.length) return "";
    const max = limit || arr.length;
    return "<ul>" + arr.slice(0, max).map((x) => `<li>${escHtml(x)}</li>`).join("") + "</ul>";
  }

  function compressImageSrc(src, done) {
    if (!src) { done(""); return; }
    // Already a small data URL
    if (src.indexOf("data:image") === 0 && src.length < 120000) {
      done(src);
      return;
    }
    const img = new Image();
    img.onload = function () {
      try {
        let w = img.width, h = img.height;
        const maxSide = 720;
        if (w > maxSide || h > maxSide) {
          if (w > h) { h = Math.round(h * maxSide / w); w = maxSide; }
          else { w = Math.round(w * maxSide / h); h = maxSide; }
        }
        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        let quality = 0.72;
        let out = canvas.toDataURL("image/jpeg", quality);
        while (out.length > 220000 && quality > 0.4) {
          quality -= 0.1;
          out = canvas.toDataURL("image/jpeg", quality);
        }
        done(out);
      } catch (e) {
        done(src.indexOf("data:") === 0 ? src : "");
      }
    };
    img.onerror = function () { done(""); };
    try { img.crossOrigin = "anonymous"; } catch (e) {}
    img.src = src;
  }

  function cloneAdvice(a) {
    if (!a || typeof a !== "object") return null;
    try {
      return JSON.parse(JSON.stringify({
        title: a.title,
        description: a.description,
        summary: a.summary,
        next_steps: a.next_steps || [],
        treatment: a.treatment || [],
        prevention: a.prevention || [],
        when_to_call_helpline: a.when_to_call_helpline || "",
        land: a.land || null,
        treatment_plan: a.treatment_plan || null,
        matched_key: a.matched_key,
        class_name: a.class_name,
        severity: a.severity,
        severity_label: a.severity_label,
      }));
    } catch (e) {
      return null;
    }
  }

  function findUserFeedback(disease, time) {
    try {
      const log = JSON.parse(localStorage.getItem("agroscan_feedback_log_v1") || "[]");
      if (!Array.isArray(log) || !disease) return null;
      const windowMs = 2 * 60 * 60 * 1000;
      for (let i = log.length - 1; i >= 0; i--) {
        const f = log[i];
        if (!f) continue;
        if (f.disease === disease && Math.abs((f.at || 0) - time) < windowMs) {
          return f.vote || null;
        }
      }
    } catch (e) {}
    return null;
  }

  function buildHistoryEntry(data, imageDataUrl) {
    const leaf = (data && data.stage1_leaf_gate) || {};
    const crop = (data && data.stage2_leaf_type) || {};
    const d = (data && (data.stage3_disease || data.stage2_disease)) || {};
    const b = d.best_answer || {};
    const advice = cloneAdvice(b.advice);
    const time = Date.now();
    const disease = b.prediction || "";
    let phi = null;
    const tp = advice && advice.treatment_plan;
    if (tp && tp.chemical_treatments) {
      tp.chemical_treatments.forEach((ct) => {
        if (ct && ct.phi_days != null && (phi == null || ct.phi_days > phi)) phi = ct.phi_days;
      });
    }
    const steps = [];
    if (advice && advice.next_steps) {
      advice.next_steps.forEach((s) => {
        s = s || {};
        steps.push({
          title: s.title || "",
          detail: s.detail || "",
        });
      });
    }
    return {
      id: "h" + time.toString(36) + Math.random().toString(36).slice(2, 6),
      time,
      image: imageDataUrl || "",
      thumb: imageDataUrl || "",
      plant: b.plant || "",
      condition: b.condition || "",
      confidence: b.confidence,
      is_healthy: !!b.is_healthy,
      disease,
      method: b.method || "",
      agreement: b.agreement || "",
      uncertain: !!b.uncertain,
      low_confidence: !!b.low_confidence,
      recommendation: b.recommendation || "",
      top3: b.top3 || [],
      leaf: {
        available: leaf.available,
        is_leaf: leaf.is_leaf,
        leaf_probability: leaf.leaf_probability,
        label: leaf.label,
        model: leaf.model,
      },
      crop: {
        available: crop.available,
        crop: crop.crop,
        confidence: crop.confidence,
        top3: crop.top3 || [],
        source: crop.source,
        user_selected: !!crop.user_selected,
        is_other: !!crop.is_other,
      },
      models: (d.models || []).map((m) => ({
        model: m.model,
        prediction: m.prediction,
        plant: m.plant,
        condition: m.condition,
        confidence: m.confidence,
        is_highest: !!m.is_highest,
        top3: m.top3 || [],
      })),
      winning_model: b.winning_model || "",
      advice,
      summary: (advice && (advice.description || advice.summary)) || "",
      steps: steps.map((s) => (s.title || "") + (s.detail ? (": " + s.detail) : "")),
      treatment: (advice && advice.treatment) || [],
      prevention: (advice && advice.prevention) || [],
      phi_days: phi,
      user_feedback: findUserFeedback(disease, time),
    };
  }

  function renderHistory() {
    const box = $("historyList");
    if (!box) return;
    const h = getHistory();
    if (!h.length) { box.innerHTML = `<p class="muted small">${T().t("history_empty")}</p>`; return; }
    box.innerHTML = h.map((e, idx) => `
      <button type="button" class="hist-item hist-item-btn" data-idx="${idx}">
        ${(e.image || e.thumb) ? `<img src="${escHtml(e.image || e.thumb)}" alt="" />` : `<div class="hist-thumb-ph" aria-hidden="true"></div>`}
        <div>
          <div class="hi-title">${escHtml(e.plant || "")} - ${escHtml(e.condition || "")}</div>
          <div class="muted small">${e.confidence != null ? pctHist(e.confidence) : ""} - ${fmtHistTime(e.time)}</div>
        </div>
      </button>`).join("");
    Array.from(box.querySelectorAll(".hist-item-btn")).forEach((btn) => {
      btn.onclick = () => openHistoryEntry(parseInt(btn.getAttribute("data-idx"), 10));
    });
  }
  function renderPhotoHistory() {
    const box = $("photoHistoryList");
    const wrap = $("photoHistory");
    if (!box) return;
    const h = getHistory();
    if (wrap) wrap.classList.toggle("is-empty", !h.length);
    if (!h.length) {
      box.innerHTML = `<p class="muted small">${T().t("history_empty")}</p>`;
      return;
    }
    box.innerHTML = h.map((e, idx) => `
      <button type="button" class="photo-hist-card" data-idx="${idx}">
        ${(e.image || e.thumb)
          ? `<img class="photo-hist-thumb" src="${escHtml(e.image || e.thumb)}" alt="" />`
          : `<div class="photo-hist-thumb photo-hist-thumb-ph" aria-hidden="true"></div>`}
        <div class="photo-hist-body">
          <strong>${escHtml(e.plant || "")} — ${escHtml(e.condition || "")}</strong>
          <span class="muted small">${e.confidence != null ? pctHist(e.confidence) : ""} · ${fmtHistTime(e.time)}</span>
        </div>
      </button>`).join("");
    Array.from(box.querySelectorAll(".photo-hist-card")).forEach((btn) => {
      btn.onclick = () => openHistoryEntry(parseInt(btn.getAttribute("data-idx"), 10));
    });
  }

  function setActiveHistoryCard(idx) {
    const box = $("photoHistoryList");
    if (!box) return;
    Array.from(box.querySelectorAll(".photo-hist-card")).forEach((btn) => {
      btn.classList.toggle("is-active", parseInt(btn.getAttribute("data-idx"), 10) === idx);
    });
  }

  function openHistoryEntry(idx) {
    const h = getHistory();
    const e = h[idx];
    if (!e) return;
    setActiveHistoryCard(idx);
    // Refresh linked user feedback if they voted later
    if (!e.user_feedback) {
      const vote = findUserFeedback(e.disease, e.time);
      if (vote) e.user_feedback = vote;
    }
    const detail = $("photoHistoryDetail");
    if (!detail) return;
    const imgSrc = e.image || e.thumb || "";
    const a = e.advice || {};
    const tp = a.treatment_plan || {};
    let html = "";
    html += `<div class="photo-hist-exit-bar">` +
      `<button type="button" class="btn btn-primary btn-sm photo-hist-exit-btn" id="photoHistExitTop">` +
      `← ${T().t("photo_hist_exit")}</button>` +
      `<span class="muted small">${T().t("photo_hist_exit_hint")}</span>` +
      `</div>`;

    if (imgSrc) {
      html += `<img src="${escHtml(imgSrc)}" alt="" class="photo-hist-full-img" />`;
    }
    html += `<div class="photo-hist-detail-head"><div>` +
      `<h4>${escHtml(e.plant || "")} — ${escHtml(e.condition || "")}</h4>` +
      `<p class="muted small">${fmtHistTime(e.time)}` +
      (e.confidence != null ? ` · ${T().t("confidence")} ${pctHist(e.confidence)}` : "") +
      `</p></div></div>`;

    // Stage 1 leaf
    if (e.leaf && e.leaf.available !== false) {
      html += `<div class="photo-hist-section"><h5>${T().t("leaf_check")}</h5>` +
        `<p>${e.leaf.is_leaf === false ? T().t("not_leaf_simple") : T().t("is_leaf")}` +
        (e.leaf.leaf_probability != null ? ` (${pctHist(e.leaf.leaf_probability)})` : "") +
        `</p></div>`;
    }

    // Stage 2 crop
    if (e.crop && (e.crop.crop || (e.crop.top3 && e.crop.top3.length))) {
      html += `<div class="photo-hist-section"><h5>${T().t("leaf_type")}</h5>` +
        `<p><strong>${T().t("crop_label")}:</strong> ${escHtml(
          String(e.crop.crop || "").toLowerCase() === "other" ? T().t("crop_other") : (e.crop.crop || "")
        )}` +
        (e.crop.confidence != null && String(e.crop.crop || "").toLowerCase() !== "other"
          ? ` (${pctHist(e.crop.confidence)})`
          : "") +
        `</p>`;
      if (e.crop.top3 && e.crop.top3.length) {
        html += "<ul class='photo-hist-top3'>";
        e.crop.top3.forEach((c) => {
          const other = String(c.crop || "").toLowerCase() === "other";
          html += `<li>${escHtml(other ? T().t("crop_other") : (c.crop || ""))}` +
            (other ? "" : ` — ${pctHist(c.confidence)}`) + `</li>`;
        });
        html += "</ul>";
      }
      html += `</div>`;
    }

    if (e.low_confidence && e.recommendation) {
      html += `<div class="photo-hist-alert">${escHtml(e.recommendation)}</div>`;
    }

    if (e.models && e.models.length) {
      html += `<div class="photo-hist-section"><h5>${T().t("per_model")}</h5><ul class="photo-hist-models">`;
      e.models.forEach((m) => {
        const hi = m.is_highest || (e.winning_model && m.model === e.winning_model);
        html += `<li class="${hi ? "is-highest" : ""}"><strong>${escHtml(m.model || "")}</strong>` +
          (hi ? ` <span class="badge ok">${T().t("highest_badge")}</span>` : "") +
          `: ${escHtml((m.plant || "") + " — " + (m.condition || m.prediction || ""))}` +
          (m.confidence != null ? ` (${pctHist(m.confidence)})` : "") + `</li>`;
      });
      html += `</ul></div>`;
    }

    html += `<div class="photo-hist-section"><h5>${T().t("best_answer")}</h5>` +
      `<p><strong>${escHtml(e.plant || "")} — ${escHtml(e.condition || "")}</strong>` +
      (e.confidence != null ? ` (${pctHist(e.confidence)})` : "") + `</p>`;
    if (e.method || e.agreement || e.winning_model) {
      html += `<p class="muted small">${escHtml([e.method || (e.winning_model ? (T().t("highest_from") + " " + e.winning_model) : ""), e.agreement].filter(Boolean).join(" · "))}</p>`;
    }
    html += `</div>`;

    if (e.top3 && e.top3.length) {
      html += `<div class="photo-hist-section"><h5>${T().t("photo_hist_top3")}</h5><ul>`;
      e.top3.slice(0, 3).forEach((t) => {
        html += `<li>${escHtml((t.plant || "") + " — " + (t.condition || t.label || ""))}` +
          (t.confidence != null ? ` (${pctHist(t.confidence)})` : "") + `</li>`;
      });
      html += `</ul></div>`;
    }

    const summary = a.description || a.summary || e.summary || "";
    if (summary) {
      html += `<div class="photo-hist-section"><h5>${T().t("treat_prevent")}</h5>` +
        `<p>${escHtml(summary)}</p></div>`;
    }
    if (a.land && a.land.summary) {
      html += `<p class="land-summary">${escHtml(a.land.summary)}</p>`;
    }

    const steps = a.next_steps && a.next_steps.length
      ? a.next_steps
      : (e.steps || []).map((s) => ({ title: s, detail: "" }));
    if (steps.length) {
      html += `<div class="photo-hist-section"><h5>${T().t("next_steps")}</h5><ol>`;
      steps.forEach((s) => {
        if (typeof s === "string") {
          html += `<li>${escHtml(s)}</li>`;
        } else {
          html += `<li><strong>${escHtml(s.title || "")}</strong>` +
            (s.detail ? `<p>${escHtml(s.detail)}</p>` : "") + `</li>`;
        }
      });
      html += `</ol></div>`;
    }

    const treatment = (a.treatment && a.treatment.length) ? a.treatment : (e.treatment || []);
    const prevention = (a.prevention && a.prevention.length) ? a.prevention : (e.prevention || []);
    if (treatment.length || prevention.length) {
      html += `<div class="photo-hist-grid"><div><h5>${T().t("treatment")}</h5>${listItems(treatment)}</div>` +
        `<div><h5>${T().t("prevention")}</h5>${listItems(prevention)}</div></div>`;
    }

    if (a.when_to_call_helpline) {
      html += `<div class="advice-callout"><strong>${T().t("when_to_call")}</strong> ` +
        `${escHtml(a.when_to_call_helpline)}</div>`;
    }

    if (tp.chemical_treatments && tp.chemical_treatments.length) {
      html += `<div class="photo-hist-section"><h5>${T().t("shop_order_meds")}</h5>`;
      tp.chemical_treatments.forEach((ct) => {
        html += `<div class="photo-hist-chem">` +
          `<strong>${escHtml(ct.name || ct.active_ingredient || "")}</strong>` +
          (ct.dose ? `<div>${escHtml(ct.dose)}</div>` : "") +
          (ct.dose_scaled ? `<div class="dose-scaled">${escHtml(ct.dose_scaled)}</div>` : "") +
          (ct.phi_days != null ? `<div class="muted small">PHI: ${escHtml(ct.phi_days)} ${T().t("days")}</div>` : "") +
          (ct.warning ? `<div class="muted small">${escHtml(ct.warning)}</div>` : "") +
          `</div>`;
      });
      html += `</div>`;
    }
    if (tp.organic_alternatives && tp.organic_alternatives.length) {
      html += `<div class="photo-hist-section"><h5>${T().t("organic_alt")}</h5>${listItems(tp.organic_alternatives)}</div>`;
    }
    if (tp.fertilizer_advice || tp.fertilizer_advice_scaled) {
      html += `<div class="photo-hist-section"><h5>${T().t("fertilizer_advice")}</h5>` +
        (tp.fertilizer_advice ? `<p>${escHtml(tp.fertilizer_advice)}</p>` : "") +
        (tp.fertilizer_advice_scaled ? `<p class="dose-scaled">${escHtml(tp.fertilizer_advice_scaled)}</p>` : "") +
        `</div>`;
    }
    if (e.phi_days != null) {
      html += `<p class="phi-line">${T().t("phi_offline", { days: e.phi_days })}</p>`;
    }
    if (tp.legal_note) {
      html += `<p class="muted small">${escHtml(tp.legal_note)}</p>`;
    }

    if (e.user_feedback) {
      html += `<div class="photo-hist-section"><h5>${T().t("feedback_ask")}</h5>` +
        `<p>${e.user_feedback === "yes" ? T().t("feedback_yes") : T().t("feedback_no")}</p></div>`;
    }

    html += `<div class="photo-hist-detail-actions">` +
      `<button type="button" class="btn btn-primary" id="photoHistClose">← ${T().t("photo_hist_exit")}</button>` +
      `<a class="btn btn-secondary btn-sm" href="tel:16123">16123</a>` +
      (e.disease
        ? `<button type="button" class="btn btn-secondary btn-sm" id="photoHistShop">${T().t("shop_order_meds")}</button>`
        : "") +
      `</div>`;

    detail.innerHTML = html;
    detail.className = "photo-history-detail is-open";
    setHistoryViewMode(true);
    if (e.disease) window.AgroScanLastDisease = e.disease;
    try { detail.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (_) {}

    function exitToMain() {
      setHistoryViewMode(false);
      const capture = $("diagnoseCapture");
      try {
        if (capture) capture.scrollIntoView({ behavior: "smooth", block: "start" });
        else if ($("diagnose")) $("diagnose").scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (_) {}
    }
    const exitTop = $("photoHistExitTop");
    if (exitTop) exitTop.onclick = exitToMain;
    const closeBtn = $("photoHistClose");
    if (closeBtn) closeBtn.onclick = exitToMain;
    const shopBtn = $("photoHistShop");
    if (shopBtn) {
      shopBtn.onclick = () => {
        if (window.AgroScanShop && window.AgroScanShop.recommendForDisease) {
          window.AgroScanShop.recommendForDisease(e.disease || "");
        }
        if (window.agroscanShowPane) window.agroscanShowPane("shop");
      };
    }
    if (window.agroscanShowPane) window.agroscanShowPane("diagnose", { keepScroll: true });
  }

  /* ---------------- Weather + spraying advisory ---------------- */
  const WMAP = { en: {}, bn: {} };
  function sprayAdvice(temp, wind, rainProb, precip) {
    const en = [], bn = [];
    let ok = true;
    if (precip > 0 || rainProb >= 60) { ok = false; en.push("Rain likely - spraying may wash off."); bn.push("\u09AC\u09C3\u09B7\u09CD\u099F\u09BF\u09B0 \u09B8\u09AE\u09CD\u09AD\u09BE\u09AC\u09A8\u09BE - \u09B8\u09CD\u09AA\u09CD\u09B0\u09C7 \u09A7\u09C1\u09AF\u09BC\u09C7 \u09AF\u09C7\u09A4\u09C7 \u09AA\u09BE\u09B0\u09C7\u0964"); }
    if (wind >= 15) { ok = false; en.push("Windy - risk of spray drift."); bn.push("\u09AC\u09BE\u09A4\u09BE\u09B8 \u09AC\u09C7\u09B6\u09BF - \u09B8\u09CD\u09AA\u09CD\u09B0\u09C7 \u09B8\u09B0\u09C7 \u09AF\u09C7\u09A4\u09C7 \u09AA\u09BE\u09B0\u09C7\u0964"); }
    if (temp >= 34) { en.push("Very hot - spray early morning/evening."); bn.push("\u0996\u09C1\u09AC \u0997\u09B0\u09AE - \u09B8\u0995\u09BE\u09B2\u09C7/\u09B8\u09A8\u09CD\u09A7\u09CD\u09AF\u09BE\u09AF\u09BC \u09B8\u09CD\u09AA\u09CD\u09B0\u09C7 \u0995\u09B0\u09C1\u09A8\u0964"); }
    if (ok && !en.length) { en.push("Good conditions for spraying."); bn.push("\u09B8\u09CD\u09AA\u09CD\u09B0\u09C7\u09B0 \u099C\u09A8\u09CD\u09AF \u0989\u09AA\u09AF\u09C1\u0995\u09CD\u09A4 \u0986\u09AC\u09B9\u09BE\u0993\u09AF\u09BC\u09BE\u0964"); }
    return { ok, msg: (T().lang === "bn" ? bn : en).join(" ") };
  }
  function weatherFromCoords(la, lo) {
    const box = $("weatherBody");
    if (!box) return;
    box.innerHTML = `<p class="muted small">${T().t("weather_loading")}</p>`;
    const u = `https://api.open-meteo.com/v1/forecast?latitude=${la}&longitude=${lo}&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m&daily=precipitation_probability_max&timezone=auto`;
    fetch(u).then((r) => r.json()).then((d) => {
      const c = d.current, rp = (d.daily.precipitation_probability_max || [0])[0];
      const adv = sprayAdvice(c.temperature_2m, c.wind_speed_10m, rp, c.precipitation);
      box.innerHTML = `
          <div class="wx-grid">
            <div><b>${c.temperature_2m}\u00B0C</b><span>${T().t("wx_temp")}</span></div>
            <div><b>${c.relative_humidity_2m}%</b><span>${T().t("wx_humidity")}</span></div>
            <div><b>${c.wind_speed_10m}</b><span>${T().t("wx_wind")}</span></div>
            <div><b>${rp}%</b><span>${T().t("wx_rain")}</span></div>
          </div>
          <div class="spray ${adv.ok ? "ok" : "no"}">${adv.ok ? "\u2705" : "\u26A0\uFE0F"} ${adv.msg}</div>`;
    }).catch(() => {
      box.innerHTML = `<p class="muted small">${T().t("weather_unavailable")}</p>`;
    });
  }
  function readCachedGeo() {
    var g = window.AgroScanGeo && window.AgroScanGeo.get && window.AgroScanGeo.get();
    if (g && g.lat != null) return g;
    try { g = JSON.parse(localStorage.getItem("agroscan_geo_v1") || "null"); } catch (e) { g = null; }
    if (g && g.lat != null) return g;
    try { g = JSON.parse(localStorage.getItem("agroscan_place_v1") || "null"); } catch (e) { g = null; }
    if (g && g.lat != null) return g;
    return null;
  }
  function loadWeather() {
    const box = $("weatherBody");
    if (!box) return;
    box.innerHTML = `<p class="muted small">${T().t("weather_loading")}</p>`;
    const g = readCachedGeo();
    if (g && g.lat != null) {
      weatherFromCoords(g.lat, g.lng);
      if (window.AgroScanGeo && window.AgroScanGeo.locate) window.AgroScanGeo.locate(function () {}, function () {});
      return;
    }
    if (window.AgroScanGeo && window.AgroScanGeo.locate) {
      window.AgroScanGeo.locate(function (pos) {
        if (pos && pos.lat != null) weatherFromCoords(pos.lat, pos.lng);
      }, function () {
        box.innerHTML = `<button id="wxEnable" class="btn btn-ghost btn-sm">${T().t("weather_enable")}</button>`;
        const b = box.querySelector("#wxEnable");
        if (b) b.addEventListener("click", loadWeather);
      });
      return;
    }
    if (!navigator.geolocation) { box.innerHTML = `<p class="muted small">${T().t("weather_geo_unsupported")}</p>`; return; }
    navigator.geolocation.getCurrentPosition((pos) => {
      weatherFromCoords(pos.coords.latitude, pos.coords.longitude);
    }, () => {
      box.innerHTML = `<button id="wxEnable" class="btn btn-ghost btn-sm">${T().t("weather_enable")}</button>`;
      box.querySelector("#wxEnable").addEventListener("click", loadWeather);
    });
  }

  /* ---------------- Crop season calendar (Bangladesh) ---------------- */
  const SEASONS = [
    { months: [10, 11, 0, 1], en: "Rabi (winter)", bn: "\u09B0\u09AC\u09BF (\u09B6\u09C0\u09A4)", cropsEn: "Wheat, potato, mustard, lentil, boro paddy", cropsBn: "\u0997\u09AE, \u0986\u09B2\u09C1, \u09B8\u09B0\u09BF\u09B7\u09BE, \u09AE\u09B8\u09C1\u09B0, \u09AC\u09CB\u09B0\u09CB \u09A7\u09BE\u09A8" },
    { months: [2, 3, 4, 5], en: "Kharif-1 (pre-monsoon)", bn: "\u0996\u09B0\u09BF\u09AB-\u09E7 (\u09AA\u09CD\u09B0\u09BE\u0995-\u09AC\u09B0\u09CD\u09B7\u09BE)", cropsEn: "Aus paddy, jute, summer vegetables", cropsBn: "\u0986\u0989\u09B6 \u09A7\u09BE\u09A8, \u09AA\u09BE\u099F, \u0997\u09CD\u09B0\u09C0\u09B7\u09CD\u09AE\u0995\u09BE\u09B2\u09C0\u09A8 \u09B8\u09AC\u099C\u09BF" },
    { months: [6, 7, 8, 9], en: "Kharif-2 (monsoon)", bn: "\u0996\u09B0\u09BF\u09AB-\u09E8 (\u09AC\u09B0\u09CD\u09B7\u09BE)", cropsEn: "Aman paddy, vegetables", cropsBn: "\u0986\u09AE\u09A8 \u09A7\u09BE\u09A8, \u09B8\u09AC\u099C\u09BF" },
  ];
  function renderCalendar() {
    const m = new Date().getMonth();
    const s = SEASONS.find((x) => x.months.includes(m)) || SEASONS[0];
    const bn = T().lang === "bn";
    $("calendarBody").innerHTML = `
      <div class="cal-season">${bn ? s.bn : s.en}</div>
      <div class="muted small">${bn ? s.cropsBn : s.cropsEn}</div>`;
  }

  /* ---------------- Daily tip ---------------- */
  const TIPS = [
    { en: "Rotate crops each season to break disease cycles.", bn: "\u09B0\u09CB\u0997\u09C7\u09B0 \u099A\u0995\u09CD\u09B0 \u09AD\u09BE\u0999\u09A4\u09C7 \u09AA\u09CD\u09B0\u09A4\u09BF \u09AE\u09CC\u09B8\u09C1\u09AE\u09C7 \u09AB\u09B8\u09B2 \u09AC\u09A6\u09B2\u09BE\u09A8\u0964" },
    { en: "Remove and destroy infected leaves to slow spread.", bn: "\u09B0\u09CB\u0997\u09BE\u0995\u09CD\u09B0\u09BE\u09A8\u09CD\u09A4 \u09AA\u09BE\u09A4\u09BE \u09B8\u09B0\u09BF\u09AF\u09BC\u09C7 \u09A7\u09CD\u09AC\u0982\u09B8 \u0995\u09B0\u09C1\u09A8\u0964" },
    { en: "Water at the base, not the leaves, to reduce fungus.", bn: "\u09AB\u09BE\u0982\u0997\u09BE\u09B8 \u0995\u09AE\u09BE\u09A4\u09C7 \u09AA\u09BE\u09A4\u09BE\u09AF\u09BC \u09A8\u09AF\u09BC, \u0997\u09CB\u09A1\u09BC\u09BE\u09AF\u09BC \u09AA\u09BE\u09A8\u09BF \u09A6\u09BF\u09A8\u0964" },
    { en: "Scout your field weekly to catch problems early.", bn: "\u09B8\u09AE\u09B8\u09CD\u09AF\u09BE \u0986\u0997\u09C7 \u09A7\u09B0\u09A4\u09C7 \u09B8\u09BE\u09AA\u09CD\u09A4\u09BE\u09B9\u09BF\u0995 \u09AE\u09BE\u09A0 \u09AA\u09B0\u09BF\u09A6\u09B0\u09CD\u09B6\u09A8 \u0995\u09B0\u09C1\u09A8\u0964" },
    { en: "Use certified disease-free seeds and seedlings.", bn: "\u09B8\u09BE\u09B0\u09CD\u099F\u09BF\u09AB\u09BE\u0987\u09A1 \u09B0\u09CB\u0997\u09AE\u09C1\u0995\u09CD\u09A4 \u09AC\u09C0\u099C \u0993 \u099A\u09BE\u09B0\u09BE \u09AC\u09CD\u09AF\u09AC\u09B9\u09BE\u09B0 \u0995\u09B0\u09C1\u09A8\u0964" },
    { en: "Avoid working in the field when plants are wet.", bn: "\u0997\u09BE\u099B \u09AD\u09C7\u099C\u09BE \u09A5\u09BE\u0995\u09B2\u09C7 \u09AE\u09BE\u09A0\u09C7 \u0995\u09BE\u099C \u098F\u09A1\u09BC\u09BF\u09AF\u09BC\u09C7 \u099A\u09B2\u09C1\u09A8\u0964" },
    { en: "Balanced fertiliser keeps plants strong against disease.", bn: "\u09B8\u09C1\u09B7\u09AE \u09B8\u09BE\u09B0 \u0997\u09BE\u099B\u0995\u09C7 \u09B0\u09CB\u0997 \u09AA\u09CD\u09B0\u09A4\u09BF\u09B0\u09CB\u09A7\u09C0 \u09B0\u09BE\u0996\u09C7\u0964" },
  ];
  function renderTip() {
    const day = Math.floor(Date.now() / 86400000) % TIPS.length;
    const tip = TIPS[day];
    $("tipBody").textContent = T().lang === "bn" ? tip.bn : tip.en;
  }

  /* ---------------- Disease library ---------------- */
  let DISEASES = {};
  async function loadLibrary() {
    const lang = T() ? T().lang : "bn";
    try { DISEASES = (await (await fetch(`${API}/api/diseases?lang=${lang}`)).json()).diseases || {}; }
    catch { DISEASES = {}; }
    renderLibrary($("libSearch") ? $("libSearch").value : "");
  }
  function renderLibrary(q) {
    const box = $("libList");
    if (!box) return;
    q = (q || "").toLowerCase();
    const items = Object.values(DISEASES).filter((d) =>
      d.title.toLowerCase().includes(q) || (d.summary || "").toLowerCase().includes(q) ||
      (d.description || "").toLowerCase().includes(q));
    const countEl = $("libCount");
    if (countEl) countEl.textContent = String(items.length);
    const sev = (d) => d.severity_label || (T().t("sev_" + (d.severity || "none")) !== "sev_" + (d.severity || "none") ? T().t("sev_" + (d.severity || "none")) : d.severity);
    box.innerHTML = items.map((d) => `
      <details class="lib-item">
        <summary><span class="sev ${d.severity || ""}">${sev(d)}</span> ${d.title}</summary>
        <p class="muted small">${d.description || d.summary || ""}</p>
        ${d.next_steps && d.next_steps.length ? `<ol class="next-steps lib-steps">${d.next_steps.map((s) =>
          `<li><strong>${s.title || ""}</strong><p>${s.detail || ""}</p></li>`).join("")}</ol>` : ""}
        <div class="small"><b>${T().t("treatment")}:</b> ${(d.treatment || []).join("; ")}</div>
        ${d.when_to_call_helpline ? `<p class="small"><b>${T().t("when_to_call")}:</b> ${d.when_to_call_helpline}</p>` : ""}
      </details>`).join("") || `<p class="muted small">${T().t("library_empty")}</p>`;
  }

  /* ---------------- Text-to-speech ---------------- */
  let speaking = false;
  function speakAdvice() {
    const r = window.lastResult || window.lastResultData;
    const d0 = r && (r.stage3_disease || r.stage2_disease);
    const b = d0 && d0.best_answer;
    if (!b || !window.speechSynthesis) return;
    if (speaking) { window.speechSynthesis.cancel(); speaking = false; setListenLabel(); return; }
    const a = b.advice || {};
    const tp = a.treatment_plan || {};
    const doseLines = (tp.chemical_treatments || []).slice(0, 2).map((ct) => {
      const name = ct.product || ct.product_en || "";
      const dose = ct.dose_display_scaled || ct.dose_scaled || ct.dose_display || ct.dose || "";
      const phi = ct.phi_days != null ? `PHI ${ct.phi_days}` : "";
      return [name, dose, phi].filter(Boolean).join(". ");
    });
    const text = [
      `${b.plant}, ${b.condition}.`,
      a.land && a.land.summary ? a.land.summary : "",
      a.description || a.summary || "",
      (a.next_steps || []).map((s, i) => `${i + 1}. ${s.title}. ${s.detail || ""}`).join(" "),
      doseLines.length ? `${T().t("treatment")}: ${doseLines.join(". ")}` : `${T().t("treatment")}: ${(a.treatment || []).join(". ")}`,
      a.when_to_call_helpline ? `${T().t("when_to_call")}: ${a.when_to_call_helpline}` : "16123",
    ].filter(Boolean).join(" ");
    const u = new SpeechSynthesisUtterance(text);
    u.lang = T().lang === "bn" ? "bn-BD" : "en-US";
    u.rate = 0.92;
    u.onend = () => { speaking = false; setListenLabel(); };
    speaking = true; setListenLabel();
    window.speechSynthesis.speak(u);
  }
  function setListenLabel() {
    const b = $("listenBtn");
    if (b && T()) b.textContent = (speaking ? "\u23F9 " : "\u{1F50A} ") + T().t(speaking ? "stop" : "listen");
  }

  /* ---------------- Download / share report ---------------- */
  function buildReport() {
    const r = window.lastResult;
    if (!r) return "";
    const g = r.stage1_leaf_gate || {};
    let s = "AgroScan - Diagnosis report\n" + new Date().toLocaleString() + "\n\n";
    s += `Leaf check: ${g.is_leaf ? "Leaf" : "Not a leaf"} (${((g.leaf_probability || 0) * 100).toFixed(1)}%)\n`;
    const crop = r.stage2_leaf_type;
    if (crop && crop.crop) {
      s += `Leaf type: ${crop.crop} (${((crop.confidence || 0) * 100).toFixed(1)}%)\n`;
    }
    s += "\n";
    const d = r.stage3_disease || r.stage2_disease;
    if (d) {
      const b = d.best_answer;
      s += `Best answer: ${b.plant} - ${b.condition} (${(b.confidence * 100).toFixed(1)}%)\n`;
      s += `${b.agreement}\n\n`;
      s += "Per-model:\n" + d.models.map((m) => ` - ${m.model}: ${m.plant} ${m.condition} (${(m.confidence * 100).toFixed(1)}%)`).join("\n") + "\n\n";
      if (b.advice) {
        s += `Treatment: ${(b.advice.treatment || []).join("; ")}\n`;
        s += `Prevention: ${(b.advice.prevention || []).join("; ")}\n`;
      }
    }
    return s;
  }
  function downloadReport() {
    const text = buildReport();
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "agroscan-diagnosis.txt";
    a.click();
  }
  async function shareReport() {
    const text = buildReport();
    if (!text) return;
    if (navigator.share) { try { await navigator.share({ title: T().t("share_title"), text }); } catch {} }
    else { navigator.clipboard.writeText(text); alert(T().t("share_copied")); }
  }

  /* ---------------- Farm planner ---------------- */
  let lastFarmPlan = null;

  function reasonLabel(reason) {
    if (reason === "climate_match") return T().t("farm_reason_climate");
    return T().t("farm_reason_season");
  }

  function renderFarmPlan(plan) {
    const box = $("farmPlanResult");
    const cult = $("farmCultivate");
    if (!box) return;
    if (cult) cult.classList.add("hidden");
    lastFarmPlan = plan;
    const disc = T().lang === "bn" ? plan.disclaimer_bn : plan.disclaimer_en;
    const chips = (plan.recommendations || []).map((r) => {
      const profit = r.profit_typical_per_decimal != null
        ? `<small>${T().t("farm_profit_typical")}: ${r.profit_typical_per_decimal} ৳/${T().t("farm_unit_decimal")}</small>`
        : `<small>${reasonLabel(r.reason)}</small>`;
      const cropName = r.crop || r.crop_en || "";
      return `
      <button type="button" class="farm-chip" data-crop="${cropName}">
        ${cropName}
        ${profit}
      </button>`;
    }).join("");
    const multi = (plan.multicrop_options || []).map((m) => `
      <div class="farm-multi-card">
        <strong>${m.main}</strong> ${T().t("farm_with")} ${(m.with || []).join(", ")}
        <div class="muted small">${m.note || ""}</div>
      </div>`).join("");
    box.classList.remove("hidden");
    box.innerHTML = `
      <p class="farm-meta"><strong>${plan.season_label || ""}</strong>${plan.district ? " · " + plan.district : ""}<br/>${plan.land_note || ""}</p>
      <h4 class="advice-section-title">${T().t("farm_suggested")}</h4>
      <div class="farm-chip-list">${chips || `<p class="muted small">—</p>`}</div>
      ${multi ? `<h4 class="advice-section-title">${T().t("farm_multicrop")}</h4><div class="farm-multi">${multi}</div>` : ""}
      <p class="muted small">${disc || ""}</p>
      <p class="muted small">${T().t("farm_scan_hint")}</p>`;
    box.querySelectorAll(".farm-chip").forEach((btn) => {
      btn.addEventListener("click", () => loadCultivate(btn.getAttribute("data-crop")));
    });
  }

  async function loadCultivate(crop) {
    const cult = $("farmCultivate");
    const box = $("farmPlanResult");
    if (!cult || !crop) return;
    cult.classList.remove("hidden");
    cult.innerHTML = `<p class="muted small">${T().t("farm_loading")}</p>`;
    try {
      const lang = T().lang || "bn";
      const res = await fetch(`${API}/api/farm/cultivate/${encodeURIComponent(crop)}?lang=${lang}`);
      if (!res.ok) throw new Error("fail");
      const data = await res.json();
      if (box) box.classList.add("hidden");
      const shopItems = (data.shop_products_needed || []).map((p) => {
        const label = p.catalogue_name_en || p.name_en || p.name || p.sku || "";
        const sku = p.sku || "";
        return `<div class="shop-product"><strong>${label}</strong>
          <span class="muted small">${p.type || ""} ${p.qty_per_decimal || ""}</span>
          ${sku ? `<button type="button" class="btn btn-secondary btn-sm farm-shop-add" data-sku="${sku}">${T().t("shop_add")}</button>` : ""}
        </div>`;
      }).join("");
      cult.innerHTML = `
        <h4 class="advice-section-title">${T().t("farm_how")}: ${data.crop}</h4>
        <ol>${(data.steps || []).map((s) =>
          `<li><strong>${s.title}</strong><p>${s.detail}</p></li>`).join("")}</ol>
        ${shopItems ? `<h4 class="advice-section-title">${T().t("farm_order_inputs")}</h4>${shopItems}` : ""}
        <p class="muted small">${data.helpline || ""}</p>
        <div class="farm-actions">
          <button type="button" id="farmBackBtn" class="btn btn-ghost btn-sm">${T().t("farm_back")}</button>
          <a class="btn btn-primary btn-sm" href="#shop">${T().t("nav_shop")}</a>
        </div>`;
      cult.querySelectorAll(".farm-shop-add").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (window.AgroScanShop && window.AgroScanShop.addSku) {
            window.AgroScanShop.addSku(btn.getAttribute("data-sku"));
          }
          location.hash = "#shop";
          if (window.agroscanShowPane) window.agroscanShowPane("shop");
        });
      });
      const back = $("farmBackBtn");
      if (back) back.addEventListener("click", () => {
        cult.classList.add("hidden");
        if (lastFarmPlan) renderFarmPlan(lastFarmPlan);
      });
    } catch {
      cult.innerHTML = `<p class="muted small">${T().t("farm_error")}</p>`;
    }
  }

  async function submitFarmPlan(e) {
    if (e) e.preventDefault();
    const box = $("farmPlanResult");
    if (box) {
      box.classList.remove("hidden");
      box.innerHTML = `<p class="muted small">${T().t("farm_loading")}</p>`;
    }
    const body = {
      district: ($("farmDistrict") && $("farmDistrict").value) || "",
      land_size: parseFloat(($("farmLandSize") && $("farmLandSize").value) || "10") || 10,
      land_unit: ($("farmLandUnit") && $("farmLandUnit").value) || "decimal",
      season: ($("farmSeason") && $("farmSeason").value) || null,
      lang: (T() && T().lang) || "bn",
    };
    try {
      const res = await fetch(`${API}/api/farm/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("fail");
      renderFarmPlan(await res.json());
    } catch {
      if (box) box.innerHTML = `<p class="muted small">${T().t("farm_error")}</p>`;
    }
  }

  function initFarmPlanner() {
    const form = $("farmPlanForm");
    if (form) form.addEventListener("submit", submitFarmPlan);
  }

  /* ---------------- Public hook called after a prediction ---------------- */
  function onResult(data, thumb) {
    window.lastResult = data;
    const d = data.stage3_disease || data.stage2_disease;
    if (!(d && d.best_answer)) return;
    if ($("resultActions")) $("resultActions").classList.remove("hidden");
    setListenLabel();

    compressImageSrc(thumb || ($("preview") && $("preview").src) || "", (imageDataUrl) => {
      const entry = buildHistoryEntry(data, imageDataUrl);
      saveHistory(entry);
    });
  }

  /* ---------------- init ---------------- */
  function init() {
    try {
      initDark();
      renderHistory();
      renderPhotoHistory();
      renderCalendar();
      renderTip();
      loadLibrary();
      initFarmPlanner();
      const libSearch = $("libSearch");
      if (libSearch) libSearch.addEventListener("input", (e) => renderLibrary(e.target.value));
      bind("clearHistory", clearHistoryAll);
      bind("photoHistoryClear", clearHistoryAll);
      bind("loadWeather", loadWeather);
      bind("listenBtn", speakAdvice);
      bind("downloadBtn", downloadReport);
      bind("shareBtn", shareReport);
      setListenLabel();
      loadWeather();
      document.addEventListener("agroscan-geo", (ev) => {
        const d = ev.detail || {};
        if (d.lat != null) weatherFromCoords(d.lat, d.lng);
      });
      document.addEventListener("langchange", () => {
        renderHistory(); renderPhotoHistory(); renderCalendar(); renderTip();
        loadLibrary();
        if (lastFarmPlan) renderFarmPlan(lastFarmPlan);
        setListenLabel();
        const wb = $("weatherBody");
        if (wb && wb.querySelector(".wx-grid")) loadWeather();
      });
    } catch (err) {
      console.error("AgroScanFeatures init error:", err);
    }
  }

  window.AgroScanFeatures = {
    onResult,
    init,
    speakAdvice,
    closeHistoryView: function () { setHistoryViewMode(false); },
    attachFeedback: function (disease, vote) {
      const h = getHistory();
      let changed = false;
      for (let i = 0; i < h.length; i++) {
        if (h[i].disease === disease || (!disease && i === 0)) {
          h[i].user_feedback = vote;
          changed = true;
          break;
        }
      }
      if (changed) {
        persistHistory(h);
        renderPhotoHistory();
        renderHistory();
      }
    },
  };
  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
