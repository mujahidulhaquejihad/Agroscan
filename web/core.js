/* AgroScan core - ES5-safe (works in older browsers, no fetch/async required) */
(function () {
  var API = "";
  if (window.AGROSCAN_CONFIG && window.AGROSCAN_CONFIG.API_BASE) {
    API = window.AGROSCAN_CONFIG.API_BASE;
  }

  function $(id) { return document.getElementById(id); }

  function T(key, vars) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key, vars) : key;
  }

  var LAND_KEY = "agroscan_land";

  function getLandInputs() {
    var sizeEl = $("adviceLandSize") || $("farmLandSize");
    var unitEl = $("adviceLandUnit") || $("farmLandUnit");
    var size = sizeEl ? parseFloat(sizeEl.value) : NaN;
    var unit = unitEl ? unitEl.value : "decimal";
    if (!(size > 0)) {
      try {
        var saved = JSON.parse(localStorage.getItem(LAND_KEY) || "null");
        if (saved && saved.size > 0) {
          size = saved.size;
          unit = saved.unit || "decimal";
        }
      } catch (e) {}
    }
    if (!(size > 0)) {
      size = 10;
      unit = unit || "decimal";
    }
    return { size: size, unit: unit || "decimal" };
  }

  function saveLandInputs() {
    var land = getLandInputs();
    try {
      localStorage.setItem(LAND_KEY, JSON.stringify(land));
    } catch (e) {}
    var farmSize = $("farmLandSize");
    var farmUnit = $("farmLandUnit");
    if (farmSize && $("adviceLandSize")) farmSize.value = $("adviceLandSize").value;
    if (farmUnit && $("adviceLandUnit")) farmUnit.value = $("adviceLandUnit").value;
    return land;
  }

  function syncLandUiFromStorage() {
    try {
      var saved = JSON.parse(localStorage.getItem(LAND_KEY) || "null");
      if (!saved || !(saved.size > 0)) return;
      if ($("adviceLandSize")) $("adviceLandSize").value = saved.size;
      if ($("adviceLandUnit")) $("adviceLandUnit").value = saved.unit || "decimal";
      if ($("farmLandSize")) $("farmLandSize").value = saved.size;
      if ($("farmLandUnit")) $("farmLandUnit").value = saved.unit || "decimal";
    } catch (e) {}
  }

  function refreshAdviceForLand() {
    var cls = window.AgroScanLastDisease;
    if (!cls) return;
    var land = saveLandInputs();
    var lang = (window.AgroScanI18n && window.AgroScanI18n.lang) || "bn";
    var q = "/api/advice/" + encodeURIComponent(cls) +
      "?lang=" + encodeURIComponent(lang) +
      "&land_size=" + encodeURIComponent(land.size) +
      "&land_unit=" + encodeURIComponent(land.unit);
    xhrGet(API + q, function (advice) {
      if (!lastResultData || !lastResultData.stage3_disease || !lastResultData.stage3_disease.best_answer) {
        return;
      }
      lastResultData.stage3_disease.best_answer.advice = advice;
      renderResult(lastResultData);
    }, function () {});
  }

  function setStatus(text, isBad) {
    var el = $("status");
    if (!el) return;
    el.textContent = text;
    if (isBad) el.className = "status pill bad";
    else el.className = "status pill";
  }

  function xhrGet(url, ok, fail) {
    var x = new XMLHttpRequest();
    x.open("GET", url, true);
    x.timeout = 10000;
    x.onload = function () {
      if (x.status >= 200 && x.status < 300) {
        try { ok(JSON.parse(x.responseText)); }
        catch (e) { fail("bad json"); }
      } else fail("HTTP " + x.status);
    };
    x.onerror = function () { fail("network"); };
    x.ontimeout = function () { fail("timeout"); };
    x.send();
  }

  function formatErr(detail) {
    if (!detail) return T("err_prediction");
    if (typeof detail === "string") return detail;
    if (detail.msg) return detail.msg;
    if (detail.length && detail[0] && detail[0].msg) return detail[0].msg;
    return JSON.stringify(detail);
  }

  function xhrPostFile(url, file, ok, fail, onProgress, extraFields) {
    var fd = new FormData();
    fd.append("file", file, file.name || "leaf.jpg");
    if (extraFields) {
      var k;
      for (k in extraFields) {
        if (extraFields.hasOwnProperty(k) && extraFields[k] != null && extraFields[k] !== "") {
          fd.append(k, extraFields[k]);
        }
      }
    }
    var x = new XMLHttpRequest();
    x.open("POST", url, true);
    x.timeout = 300000;
    if (x.upload && onProgress) {
      x.upload.onprogress = function (ev) {
        if (ev.lengthComputable) {
          onProgress(T("uploading_pct", { pct: Math.round(ev.loaded / ev.total * 100) }));
        }
      };
    }
    x.onload = function () {
      if (!x.responseText) {
        fail("Empty response (HTTP " + x.status + ").");
        return;
      }
      try {
        var data = JSON.parse(x.responseText);
        if (x.status >= 200 && x.status < 300) ok(data);
        else fail(formatErr(data.detail) || ("HTTP " + x.status));
      } catch (e) {
        fail("Server returned invalid JSON (HTTP " + x.status + ")");
      }
    };
    x.onerror = function () { fail("Network error during upload."); };
    x.ontimeout = function () { fail("Timed out after 5 min."); };
    x.send(fd);
  }

  function compressForUpload(file, done) {
    if (!window.FileReader || !document.createElement("canvas").getContext) {
      done(file);
      return;
    }
    var reader = new FileReader();
    reader.onload = function () {
      var img = new Image();
      img.onload = function () {
        var maxSide = 1024;
        var w = img.width, h = img.height;
        if (w > maxSide || h > maxSide) {
          if (w > h) { h = Math.round(h * maxSide / w); w = maxSide; }
          else { w = Math.round(w * maxSide / h); h = maxSide; }
        }
        var canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        if (canvas.toBlob) {
          canvas.toBlob(function (blob) {
            if (!blob) { done(file); return; }
            var out = new File([blob], "leaf.jpg", { type: "image/jpeg" });
            done(out);
          }, "image/jpeg", 0.85);
        } else {
          done(file);
        }
      };
      img.onerror = function () { done(file); };
      img.src = reader.result;
    };
    reader.onerror = function () { done(file); };
    reader.readAsDataURL(file);
  }

  var selectedFile = null;
  var selectedCropOverride = null;
  var pendingPredictData = null;
  var apiOnline = false;
  var statusTry = 0;
  var lastResultData = null;
  var lastStatusKey = "status_checking";
  var lastStatusVars = null;
  var lastStatusBad = false;

  function isImage(file) {
    if (!file) return false;
    if (file.type && file.type.indexOf("image/") === 0) return true;
    return /\.(jpe?g|png|webp|bmp|gif)$/i.test(file.name || "");
  }

  function updateAnalyzeBtn() {
    var btn = $("analyzeBtn");
    if (btn) btn.disabled = !(selectedFile && apiOnline);
  }

  function refreshStatusText() {
    setStatus(T(lastStatusKey, lastStatusVars), lastStatusBad);
  }

  function checkStatus() {
    lastStatusKey = "status_checking";
    lastStatusVars = null;
    lastStatusBad = false;
    refreshStatusText();
    xhrGet(API + "/api/status", function (s) {
      var models = s.disease_models_loaded || [];
      if (models.length) {
        apiOnline = true;
        lastStatusKey = "status_models";
        lastStatusVars = { n: models.length, device: s.device || "cpu" };
        lastStatusBad = false;
        refreshStatusText();
        var banner = $("offlineBanner");
        if (banner) banner.className = "offline-banner hidden";
      } else {
        apiOnline = false;
        lastStatusKey = "status_not_trained";
        lastStatusBad = true;
        refreshStatusText();
      }
      updateAnalyzeBtn();
    }, function () {
      statusTry++;
      if (statusTry < 20) {
        lastStatusKey = statusTry < 3 ? "status_loading" : "status_connecting";
        lastStatusVars = statusTry < 3 ? null : { n: statusTry };
        lastStatusBad = false;
        refreshStatusText();
        setTimeout(checkStatus, 2000);
      } else {
        apiOnline = false;
        lastStatusKey = "status_api_offline";
        lastStatusVars = null;
        lastStatusBad = true;
        refreshStatusText();
        var banner = $("offlineBanner");
        if (banner) {
          banner.className = "offline-banner";
          var urlEl = $("offlineApiUrl");
          if (urlEl) {
            var base = (window.AGROSCAN_CONFIG && (window.AGROSCAN_CONFIG.API_BASE || window.AGROSCAN_CONFIG.PRODUCTION_API)) || "";
            urlEl.textContent = base || (window.location.origin || "");
          }
        }
        updateAnalyzeBtn();
      }
    });
  }

  window.agroscanPickFile = function (input) {
    var file = input.files && input.files[0];
    var err = $("errorBox");
    if (err) err.className = "error hidden";
    if (!file) return;
    if (!isImage(file)) {
      if (err) { err.textContent = T("err_bad_image"); err.className = "error"; }
      return;
    }

    function acceptFile(chosen) {
      selectedFile = chosen || file;
      selectedCropOverride = null;
      var preview = $("preview");
      var placeholder = $("placeholder");
      var fname = $("fileName");
      if (preview) {
        preview.src = URL.createObjectURL(selectedFile);
        preview.style.display = "block";
      }
      if (placeholder) placeholder.style.display = "none";
      if (fname) {
        var kb = Math.round(selectedFile.size / 1024);
        fname.textContent = T("file_ready", { name: selectedFile.name || "leaf.jpg", kb: kb, action: T("file_action") });
        fname.className = "file-name muted small";
      }
      updateAnalyzeBtn();
    }

    // Always offer leaf crop / auto-leaf after camera or gallery pick
    if (window.AgroScanCrop) {
      window.AgroScanCrop.open(file, function (cropped) {
        acceptFile(cropped || file);
        if (document.body.classList.contains("simple-ui") && selectedFile) {
          setTimeout(function () {
            if (selectedFile) runAnalyze();
          }, 200);
        }
      }, { autoLeaf: true });
    } else {
      acceptFile(file);
      if (document.body.classList.contains("simple-ui") && selectedFile) {
        setTimeout(function () {
          if (selectedFile) runAnalyze();
        }, 250);
      }
    }
  };

  function pct(x) { return (x * 100).toFixed(1) + "%"; }

  function renderResult(data) {
    lastResultData = data;
    window.lastResultData = data;
    var results = $("results");
    if (results) results.className = "results";
    document.body.classList.add("has-results");
    document.body.classList.remove("history-detail-open");
    var workspace = $("diagnose");
    if (workspace) workspace.classList.remove("is-viewing-history");
    var capture = $("diagnoseCapture");
    if (capture) capture.classList.remove("hidden");
    var histDetail = $("photoHistoryDetail");
    if (histDetail) {
      histDetail.className = "photo-history-detail hidden";
      histDetail.innerHTML = "";
    }

    var g = data.stage1_leaf_gate || {};
    var s1 = $("stage1Body");
    var s1Card = $("stage1Card");
    var notLeaf = g.available !== false && g.is_leaf === false;
    if (s1Card) {
      if (notLeaf) s1Card.classList.add("force-show");
      else s1Card.classList.remove("force-show");
    }
    if (s1) {
      if (g.available === false) {
        s1.innerHTML = "<p class='muted'>" + (g.note || T("leaf_skipped")) + "</p>";
      } else if (!g.is_leaf) {
        s1.innerHTML = "<p class='simple-alert'>" + T("not_leaf_simple") + "</p>" +
          "<p class='muted'>" + T("photo_tip") + "</p>" +
          (data.message ? "<p class='muted' style='margin-top:10px'>" + data.message + "</p>" : "");
      } else {
        var leafLow = g.leaf_probability < 0.8;
        s1.innerHTML = "<p>" + T("image_is") + " <span class='leaf-yes'>" + T("is_leaf") + "</span></p>" +
          "<div class='conf'>" + T("leaf_prob") + " <strong>" + pct(g.leaf_probability) + "</strong></div>" +
          "<div class='bar'><i style='width:" + (g.leaf_probability * 100) + "%'></i></div>" +
          (leafLow ? "<p class='muted small' style='margin-top:8px'>" + T("photo_tip") + "</p>" : "");
      }
    }

    var crop = data.stage2_leaf_type;
    var cropCard = $("cropCard");
    if (cropCard) {
      if (!g.is_leaf || !crop) {
        cropCard.className = "card stage hidden";
      } else if (crop.available === false) {
        cropCard.className = "card stage";
        if ($("cropBody")) {
          $("cropBody").innerHTML = "<p class='muted'>" + (crop.note || T("leaf_skipped")) + "</p>";
        }
      } else {
        cropCard.className = "card stage";
        if ($("cropBody")) {
          var cropHtml = "<p>" + T("crop_label") + ": <strong>" + (crop.crop || "") + "</strong></p>" +
            "<div class='conf'>" + T("confidence") + " <strong>" + pct(crop.confidence || 0) + "</strong></div>" +
            "<div class='bar'><i style='width:" + ((crop.confidence || 0) * 100) + "%'></i></div>";
          if (crop.needs_user_pick && crop.top3 && crop.top3.length) {
            cropHtml += "<div class='crop-picker'><p class='muted'>" + T("crop_pick_hint") + "</p><div class='crop-pick-btns'>";
            var ci;
            for (ci = 0; ci < Math.min(3, crop.top3.length); ci++) {
              var opt = crop.top3[ci];
              cropHtml += "<button type='button' class='btn btn-secondary btn-sm crop-pick-btn' data-crop='" +
                (opt.crop || "") + "'>" + (opt.crop || "") +
                " (" + pct(opt.confidence || 0) + ")</button>";
            }
            cropHtml += "</div></div>";
          }
          $("cropBody").innerHTML = cropHtml;
          var pickBtns = $("cropBody").getElementsByClassName("crop-pick-btn");
          var pi;
          for (pi = 0; pi < pickBtns.length; pi++) {
            pickBtns[pi].onclick = function () {
              selectedCropOverride = this.getAttribute("data-crop");
              runAnalyze();
            };
          }
        }
      }
    }

    var d = data.stage3_disease || data.stage2_disease;
    var bestCard = $("bestCard"), modelsCard = $("modelsCard"), adviceCard = $("adviceCard");
    if (!d) {
      if (bestCard) bestCard.className = "card stage best hidden";
      if (modelsCard) modelsCard.className = "card stage hidden";
      if (adviceCard) adviceCard.className = "card stage hidden";
      if ($("lowConfAlert")) $("lowConfAlert").className = "low-conf-alert hidden";
      if ($("resultActions")) $("resultActions").className = "result-actions hidden";
      return;
    }

    var b = d.best_answer;
    if (!b) {
      if (bestCard) bestCard.className = "card stage best hidden";
      if (modelsCard) modelsCard.className = "card stage hidden";
      if (adviceCard) adviceCard.className = "card stage hidden";
      return;
    }

    // Always prefer the single model with the highest confidence (never an average).
    var modelList = d.models || [];
    var winner = null;
    var wi;
    for (wi = 0; wi < modelList.length; wi++) {
      var cand = modelList[wi] || {};
      var cConf = Number(cand.confidence);
      if (!isFinite(cConf)) continue;
      if (!winner || cConf > Number(winner.confidence)) winner = cand;
    }
    if (winner) {
      for (wi = 0; wi < modelList.length; wi++) {
        var mm = modelList[wi] || {};
        mm.is_highest = mm === winner || (
          mm.model === winner.model && Number(mm.confidence) === Number(winner.confidence)
        );
      }
      b = {
        prediction: winner.prediction || b.prediction,
        plant: winner.plant || b.plant,
        condition: winner.condition || b.condition,
        is_healthy: !!winner.is_healthy,
        confidence: winner.confidence,
        winning_model: winner.model,
        selection: "highest_confidence",
        method: (T("highest_from") + " " + (winner.model || "")).trim(),
        agreement: b.agreement || "",
        uncertain: Number(winner.confidence) < 0.8,
        low_confidence: Number(winner.confidence) < 0.8,
        recommendation: Number(winner.confidence) < 0.8
          ? (b.recommendation || T("low_conf_msg"))
          : null,
        advice: b.advice,
        top3: winner.top3 || b.top3 || [],
      };
      d.best_answer = b;
      d.selection = "highest_confidence";
    }

    // Expose for chat context (app-extra.js sends context_disease).
    window.AgroScanLastDisease = b.prediction ? b.prediction : null;
    var alertBox = $("lowConfAlert");
    var lowConf = b.low_confidence || b.confidence < 0.8;

    if (alertBox) {
      if (lowConf) {
        var msg = b.recommendation || T("low_conf_msg");
        alertBox.innerHTML = "<strong>\u26A0 " + T("low_conf_title", { pct: pct(b.confidence) }) + "</strong>" +
          msg + "<br><br>" +
          T("call_label") + " " +
          "<a href='tel:16123'>Krishi 16123</a> \u00B7 <a href='tel:16358'>Vet 16358</a>";
        alertBox.className = "low-conf-alert";
      } else {
        alertBox.className = "low-conf-alert hidden";
      }
    }

    // Show all 3 models first, then the highest-confidence result.
    if (modelsCard && modelList.length) {
      modelsCard.className = "card stage";
      var confWord = T("model_conf");
      var highestLabel = T("highest_badge");
      var mi;
      var modelsHtml = "";
      for (mi = 0; mi < modelList.length; mi++) {
        var m = modelList[mi] || {};
        var isHi = !!m.is_highest;
        modelsHtml += "<div class='model-tile" + (isHi ? " is-highest" : "") + "'>" +
          "<h3>" + (m.model || "") +
          (isHi ? " <span class='badge ok'>" + highestLabel + "</span>" : "") +
          "</h3>" +
          "<div class='pred'>" + (m.plant || "") + "</div>" +
          "<div class='sub " + (m.is_healthy ? "leaf-yes" : "") + "'>" + (m.condition || "") + "</div>" +
          "<div class='conf'>" + pct(m.confidence || 0) + " " + confWord + "</div>" +
          "<div class='bar'><i style='width:" + ((m.confidence || 0) * 100) + "%'></i></div>";
        if (m.top3 && m.top3.length) {
          modelsHtml += "<div class='top3'>";
          var ti;
          for (ti = 0; ti < m.top3.length; ti++) {
            var x = m.top3[ti] || {};
            modelsHtml += "<div><span>" + (x.plant || "") + " - " + (x.condition || "") +
              "</span><span>" + pct(x.confidence || 0) + "</span></div>";
          }
          modelsHtml += "</div>";
        }
        modelsHtml += "</div>";
      }
      if ($("modelsBody")) $("modelsBody").innerHTML = modelsHtml;
    } else if (modelsCard) {
      modelsCard.className = "card stage hidden";
    }

    if (bestCard) bestCard.className = "card stage best";
    if ($("bestBody")) {
      $("bestBody").innerHTML = "<div class='verdict'><span class='plant'>" + b.plant +
        "</span><span class='cond " + (b.is_healthy ? "healthy" : "disease") + "'>" + b.condition +
        "</span>" + (lowConf ? "<span class='badge warn'>" + T("badge_low") + "</span>" : "<span class='badge ok'>" + T("badge_ok") + "</span>") +
        "</div><div class='conf'>" + T("confidence") + " <strong>" + pct(b.confidence) + "</strong>" +
        (b.winning_model ? " · <strong>" + b.winning_model + "</strong>" : "") +
        "</div>" +
        "<div class='bar'><i style='width:" + (b.confidence * 100) + "%'></i></div>" +
        "<div class='meta-row'><span>" + (b.method || "") +
        "</span>" + (b.agreement ? "<span>" + b.agreement + "</span>" : "") + "</div>";
    }

    if (b.advice && adviceCard) {
      adviceCard.className = "card stage";
      var a = b.advice;
      var html = "";
      if (a.land && a.land.summary) {
        html += "<p class='land-summary'>" + a.land.summary + "</p>";
      } else if (a.treatment_plan && a.treatment_plan.land && a.treatment_plan.land.summary) {
        html += "<p class='land-summary'>" + a.treatment_plan.land.summary + "</p>";
      }
      if (a.description) html += "<p class='advice-desc'>" + a.description + "</p>";
      else if (a.summary) html += "<p class='muted'>" + a.summary + "</p>";

      if (a.next_steps && a.next_steps.length) {
        html += "<h4 class='advice-section-title'>" + T("next_steps") + "</h4><ol class='next-steps'>";
        var i;
        for (i = 0; i < a.next_steps.length; i++) {
          var step = a.next_steps[i] || {};
          html += "<li><strong>" + (step.title || "") + "</strong>";
          if (step.detail) html += "<p>" + step.detail + "</p>";
          html += "</li>";
        }
        html += "</ol>";
      }

      html += "<div class='advice-grid'>" +
        "<div><h4>" + T("treatment") + "</h4><ul>";
      var j;
      for (j = 0; a.treatment && j < a.treatment.length; j++) html += "<li>" + a.treatment[j] + "</li>";
      html += "</ul></div><div><h4>" + T("prevention") + "</h4><ul>";
      for (j = 0; a.prevention && j < a.prevention.length; j++) html += "<li>" + a.prevention[j] + "</li>";
      html += "</ul></div></div>";

      if (a.when_to_call_helpline) {
        html += "<div class='advice-callout'><strong>" + T("when_to_call") + "</strong> " +
          a.when_to_call_helpline + "</div>";
      }
      if (a.expected_outcome) {
        html += "<p class='muted small'><strong>" + T("expected_outcome") + ":</strong> " +
          a.expected_outcome + "</p>";
      }

      var tp = a.treatment_plan;
      if (tp && tp.warnings && tp.warnings.length) {
        var wi;
        for (wi = 0; wi < tp.warnings.length; wi++) {
          var wr = tp.warnings[wi] || {};
          html += "<div class='advice-warning'><strong>" + (wr.title || "") + "</strong> " +
            (wr.body || "") + "</div>";
        }
      }

      if (a.symptoms && a.symptoms.length) {
        html += "<h4 class='advice-section-title'>" + T("symptoms") + "</h4><ul>";
        for (j = 0; j < a.symptoms.length; j++) html += "<li>" + a.symptoms[j] + "</li>";
        html += "</ul>";
      }

      if (tp) {
        if (tp.safety_warning && !(tp.warnings && tp.warnings.length)) {
          html += "<div class='advice-warning'>" + tp.safety_warning + "</div>";
        }
        if (tp.chemical_treatments && tp.chemical_treatments.length) {
          html += "<h4 class='advice-section-title'>" + T("treatment_detail") + "</h4>";
          html += "<div class='treatment-plans'>";
          var ti;
          for (ti = 0; ti < tp.chemical_treatments.length; ti++) {
            var ct = tp.chemical_treatments[ti] || {};
            html += "<div class='treatment-card'><strong>" + (ct.product || ct.product_en || "") + "</strong>";
            if (ct.cures_disease === false) {
              html += "<p class='muted small'>" + T("spray_not_a_cure") + "</p>";
            }
            html += "<p><em>" + T("dose") + ":</em> " + (ct.dose_display || ct.dose || "") + "</p>";
            if (ct.dose_display_scaled || ct.dose_scaled) {
              html += "<p class='dose-scaled'><em>" + T("dose_for_land") + ":</em> " +
                (ct.dose_display_scaled || ct.dose_scaled) + "</p>";
            }
            if (ct.water_volume_per_decimal) {
              html += "<p class='muted small'><em>" + T("water_per_decimal") + ":</em> " +
                ct.water_volume_per_decimal + "</p>";
            }
            if (ct.timing) html += "<p><em>" + T("when_to_apply") + ":</em> " + ct.timing + "</p>";
            html += "<p>" + (ct.how_to_apply || "") + "</p>";
            html += "<p class='muted small'>" + T("spray_interval") + ": " + (ct.interval_days || "?") +
              " " + T("days") + " · " + T("max_sprays") + ": " + (ct.max_sprays_per_season || "?") +
              " · PHI: " + (ct.phi_days || "?") + " " + T("days") + "</p>";
            if (ct.registration_verified && ct.ap_numbers && ct.ap_numbers.length) {
              html += "<p class='muted small'>AP: " + (Array.isArray(ct.ap_numbers) ? ct.ap_numbers.join(", ") : ct.ap_numbers) + "</p>";
            }
            if (ct.brands_available_bd && ct.brands_available_bd.length) {
              html += "<p class='muted small'>" + T("shop_brands") + ": " + ct.brands_available_bd.join(", ") + "</p>";
            }
            html += "</div>";
          }
          html += "</div>";
        }
        if (tp.organic_alternatives && tp.organic_alternatives.length) {
          html += "<h4 class='advice-section-title'>" + T("organic_alt") + "</h4><ul>";
          for (j = 0; j < tp.organic_alternatives.length; j++) html += "<li>" + tp.organic_alternatives[j] + "</li>";
          html += "</ul>";
        }
        if (tp.fertilizer_advice) {
          html += "<p><strong>" + T("fertilizer_advice") + ":</strong> " + tp.fertilizer_advice + "</p>";
        }
        if (tp.fertilizer_advice_scaled) {
          html += "<p class='dose-scaled'><strong>" + T("fertilizer_for_land") + ":</strong> " +
            tp.fertilizer_advice_scaled + "</p>";
        }
        if (tp.legal_note) {
          html += "<p class='muted small'>" + tp.legal_note + "</p>";
        }
        html += "<p class='muted small'>" + T("price_confirm_note") + "</p>";
        html += "<button type='button' id='orderMedsBtn' class='btn btn-primary btn-sm'>" +
          T("shop_order_meds") + "</button>";
      }

      if ($("adviceBody")) $("adviceBody").innerHTML = html;
      var orderBtn = $("orderMedsBtn");
      if (orderBtn && window.AgroScanShop) {
        orderBtn.onclick = function () {
          window.AgroScanShop.recommendForDisease(window.AgroScanLastDisease || "");
          if (window.agroscanShowPane) window.agroscanShowPane("shop");
          else location.hash = "#shop";
        };
      }
    }

    if (window.AgroScanFeatures && window.AgroScanFeatures.onResult) {
      window.AgroScanFeatures.onResult(data, $("preview") ? $("preview").src : "");
    }
    if (window.AgroScanFarmerUX && window.AgroScanFarmerUX.onDiagnosis) {
      window.AgroScanFarmerUX.onDiagnosis(data);
    }
    if (window.agroscanShowPane) {
      window.agroscanShowPane("diagnose", { focusResults: true });
    } else if (results) {
      results.scrollIntoView({ behavior: "smooth" });
    }
  }

  function setLoaderText(text) {
    var loader = $("loader");
    if (!loader) return;
    var p = loader.getElementsByTagName("p")[0];
    if (p) p.textContent = text;
  }

  function runAnalyze() {
    window.__agroscanAutoSpoke = false;
    if (window.AgroScanFeatures && window.AgroScanFeatures.closeHistoryView) {
      window.AgroScanFeatures.closeHistoryView();
    }
    if (!selectedFile || !apiOnline) {
      var err0 = $("errorBox");
      if (err0) {
        err0.textContent = !apiOnline ? T("err_no_server") : T("err_no_image");
        err0.className = "error";
      }
      return;
    }
    var loader = $("loader"), err = $("errorBox"), results = $("results");
    if (results) results.className = "results hidden";
    document.body.classList.remove("has-results");
    if (err) err.className = "error hidden";
    if (loader) loader.className = "loader";
    setLoaderText(T("compressing"));
    lastStatusKey = "status_analyzing";
    lastStatusBad = false;
    refreshStatusText();
    var btn = $("analyzeBtn");
    if (btn) btn.disabled = true;

    compressForUpload(selectedFile, function (uploadFile) {
      setLoaderText(T("uploading"));
      var land = saveLandInputs();
      var extra = {
        land_size: String(land.size),
        land_unit: land.unit,
        lang: (window.AgroScanI18n && window.AgroScanI18n.lang) || "bn"
      };
      if (selectedCropOverride) extra.crop = selectedCropOverride;
      xhrPostFile(API + "/api/predict", uploadFile, function (data) {
        if (loader) loader.className = "loader hidden";
        renderResult(data);
        if (window.AgroScanShop && data.stage3_disease && data.stage3_disease.best_answer) {
          window.AgroScanShop.recommendForDisease(data.stage3_disease.best_answer.prediction || "");
        }
        checkStatus();
        updateAnalyzeBtn();
      }, function (msg) {
        if (loader) loader.className = "loader hidden";
        checkStatus();
        if (err) {
          err.textContent = typeof msg === "string" ? msg : T("err_prediction");
          err.className = "error";
        }
        updateAnalyzeBtn();
      }, function (progressText) {
        setLoaderText(progressText);
      }, extra);
    });
  }

  function runAnalyzeWithCrop() {
    if (!selectedFile) return;
    if (window.AgroScanCrop) {
      window.AgroScanCrop.open(selectedFile, function (croppedFile) {
        selectedFile = croppedFile;
        var preview = $("preview");
        if (preview) {
          preview.src = URL.createObjectURL(croppedFile);
          preview.style.display = "block";
        }
        runAnalyze();
      });
    } else {
      runAnalyze();
    }
  }

  function init() {
    var year = $("year");
    if (year) year.textContent = new Date().getFullYear();

    var fileInput = $("fileInput");
    if (fileInput) fileInput.onchange = function () { window.agroscanPickFile(fileInput); };

    var analyzeBtn = $("analyzeBtn");
    if (analyzeBtn) analyzeBtn.onclick = function (e) {
      if (e && e.preventDefault) e.preventDefault();
      runAnalyze();
    };

    var cropBtn = $("cropOnlyBtn");
    if (cropBtn) cropBtn.onclick = function () {
      if (!selectedFile) return;
      if (window.AgroScanCrop) {
        window.AgroScanCrop.open(selectedFile, function (f) {
          selectedFile = f;
          var preview = $("preview");
          if (preview) { preview.src = URL.createObjectURL(f); preview.style.display = "block"; }
          updateAnalyzeBtn();
        }, { autoLeaf: true });
      }
    };

    document.addEventListener("langchange", function () {
      refreshStatusText();
      if (selectedFile) {
        var fname = $("fileName");
        if (fname && fname.textContent) {
          var kb = Math.round(selectedFile.size / 1024);
          fname.textContent = T("file_ready", { name: selectedFile.name, kb: kb, action: T("file_action") });
        }
      }
      if (window.AgroScanLastDisease) refreshAdviceForLand();
      else if (lastResultData) renderResult(lastResultData);
    });

    syncLandUiFromStorage();
    var landApply = $("adviceLandApply");
    if (landApply) landApply.onclick = function () { refreshAdviceForLand(); };
    var landSize = $("adviceLandSize");
    var landUnit = $("adviceLandUnit");
    if (landSize) landSize.onchange = saveLandInputs;
    if (landUnit) landUnit.onchange = saveLandInputs;

    checkStatus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
