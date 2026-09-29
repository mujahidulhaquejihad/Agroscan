/* Leaf crop editor: local preprocess + 4-corner tweak (ES5) */
(function () {
  var state = {
    open: false,
    file: null,
    originalFile: null,
    img: null,
    points: [],
    dragging: -1,
    onDone: null,
    busy: false,
    moved: false,
    gen: 0
  };
  var checkTimer = null;
  var checkStage = 0;
  var checkSub = 0;

  function checkStageCopy() {
    return [
      { title: "scan_l2_title", subs: ["scan_l2_sub", "scan_l2_sub2"] },
      { title: "scan_l3_title", subs: ["scan_l3_sub", "scan_l3_sub2", "scan_l3_sub3"] }
    ];
  }

  function applyCheckStage(stage, subIdx) {
    var spec = checkStageCopy()[stage] || checkStageCopy()[0];
    var subKey = spec.subs[subIdx % spec.subs.length];
    showScan(T(spec.title), T(subKey), { allowSkip: false, keepTimer: true });
  }

  function $(id) { return document.getElementById(id); }

  function T(key, vars) {
    return window.AgroScanI18n ? window.AgroScanI18n.t(key, vars) : key;
  }

  function ensureOverlay() {
    if ($("scanOverlay")) return;
    var el = document.createElement("div");
    el.id = "scanOverlay";
    el.className = "scan-overlay hidden";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.innerHTML =
      '<div class="scan-overlay-card">' +
      '<div class="spinner" aria-hidden="true"></div>' +
      '<p id="scanOverlayTitle"></p>' +
      '<p id="scanOverlaySub" class="muted small"></p>' +
      '<ol id="scanOverlaySteps" class="scan-overlay-steps" hidden></ol>' +
      '<button type="button" id="scanOverlaySkip" class="btn btn-ghost">' + T("crop_skip") + "</button>" +
      "</div>";
    document.body.appendChild(el);
    $("scanOverlaySkip").onclick = function () {
      var f = state.file || state.originalFile;
      if (state.onDone) finish(f);
      else hideScan();
    };
  }

  function stopCheckStages() {
    if (checkTimer) {
      clearInterval(checkTimer);
      checkTimer = null;
    }
  }

  function showScan(title, sub, opts) {
    opts = opts || {};
    ensureOverlay();
    if (!opts.keepTimer) stopCheckStages();
    var skip = $("scanOverlaySkip");
    var steps = $("scanOverlaySteps");
    $("scanOverlayTitle").textContent = title || "";
    $("scanOverlaySub").textContent = sub || "";
    if (skip) skip.hidden = !opts.allowSkip;
    if (steps) steps.hidden = true;
    $("scanOverlay").className = "scan-overlay";
    $("scanOverlay").setAttribute("aria-busy", "true");
  }

  function hideScan() {
    stopCheckStages();
    var el = $("scanOverlay");
    if (el) {
      el.className = "scan-overlay hidden";
      el.setAttribute("aria-busy", "false");
    }
  }

  function startCheckStages() {
    ensureOverlay();
    checkStage = 0;
    checkSub = 0;
    applyCheckStage(0, 0);
    stopCheckStages();
    checkTimer = setInterval(function () {
      var stages = checkStageCopy();
      if (checkStage < stages.length - 1) {
        checkStage += 1;
        checkSub = 0;
      } else {
        checkSub += 1;
      }
      applyCheckStage(checkStage, checkSub);
    }, 1800);
  }

  function setBusy(on) {
    state.busy = !!on;
    var autoBtn = $("cropAutoBtn");
    var applyBtn = $("cropApplyBtn");
    var skipBtn = $("cropSkipBtn");
    var status = $("cropStatus");
    if (autoBtn) autoBtn.disabled = state.busy;
    if (applyBtn) applyBtn.disabled = state.busy;
    if (skipBtn) skipBtn.disabled = state.busy;
    if (status) {
      status.textContent = state.busy ? T("crop_working") : "";
      status.className = state.busy ? "muted small crop-status" : "muted small crop-status hidden";
    }
  }

  function ensureModal() {
    if ($("cropModal")) return;
    var wrap = document.createElement("div");
    wrap.id = "cropModal";
    wrap.className = "crop-modal hidden";
    wrap.innerHTML =
      '<div class="crop-dialog">' +
      '<div class="crop-head"><h3 id="cropTitle">' + T("crop_title") + "</h3>" +
      '<button type="button" id="cropClose" class="chat-close" aria-label="Close">&times;</button></div>' +
      '<p class="muted small" id="cropHint">' + T("crop_hint") + "</p>" +
      '<p id="cropStatus" class="muted small crop-status hidden"></p>' +
      '<div class="crop-stage"><canvas id="cropCanvas"></canvas></div>' +
      '<div class="crop-actions">' +
      '<button type="button" id="cropAutoBtn" class="btn btn-secondary">' + T("crop_auto") + "</button>" +
      '<button type="button" id="cropResetBtn" class="btn btn-ghost">' + T("crop_reset") + "</button>" +
      '<button type="button" id="cropSkipBtn" class="btn btn-ghost">' + T("crop_skip") + "</button>" +
      '<button type="button" id="cropApplyBtn" class="btn btn-primary">' + T("crop_apply") + "</button>" +
      "</div></div>";
    document.body.appendChild(wrap);
    $("cropClose").onclick = function () { skipOriginal(); };
    $("cropAutoBtn").onclick = runAutoCrop;
    $("cropResetBtn").onclick = resetToOriginal;
    $("cropSkipBtn").onclick = skipOriginal;
    $("cropApplyBtn").onclick = applyCrop;
    var canvas = $("cropCanvas");
    canvas.onmousedown = onDown;
    canvas.onmousemove = onMove;
    canvas.onmouseup = onUp;
    canvas.onmouseleave = onUp;
    canvas.ontouchstart = onTouchStart;
    canvas.ontouchmove = onTouchMove;
    canvas.ontouchend = onUp;
  }

  function refreshLabels() {
    var title = $("cropTitle");
    var hint = $("cropHint");
    if (title) title.textContent = T("crop_title");
    if (hint) hint.textContent = T("crop_hint");
    if ($("cropAutoBtn")) $("cropAutoBtn").textContent = T("crop_auto");
    if ($("cropResetBtn")) $("cropResetBtn").textContent = T("crop_reset");
    if ($("cropSkipBtn")) $("cropSkipBtn").textContent = T("crop_skip");
    if ($("cropApplyBtn")) $("cropApplyBtn").textContent = T("crop_apply");
    if ($("scanOverlaySkip")) $("scanOverlaySkip").textContent = T("crop_skip");
  }

  function defaultPoints(w, h) {
    var m = Math.min(w, h) * 0.08;
    return [
      [m, m],
      [w - m, m],
      [w - m, h - m],
      [m, h - m]
    ];
  }

  function draw() {
    var canvas = $("cropCanvas");
    if (!canvas || !state.img) return;
    var ctx = canvas.getContext("2d");
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(state.img, 0, 0, w, h);
    ctx.strokeStyle = "#00e676";
    ctx.lineWidth = 2;
    ctx.fillStyle = "rgba(0, 230, 118, 0.12)";
    ctx.beginPath();
    ctx.moveTo(state.points[0][0], state.points[0][1]);
    var i;
    for (i = 1; i < 4; i++) ctx.lineTo(state.points[i][0], state.points[i][1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    for (i = 0; i < 4; i++) {
      ctx.beginPath();
      ctx.arc(state.points[i][0], state.points[i][1], 10, 0, Math.PI * 2);
      ctx.fillStyle = i === state.dragging ? "#ffeb3b" : "#067a42";
      ctx.fill();
      ctx.strokeStyle = "#fff";
      ctx.stroke();
    }
  }

  function hitTest(x, y) {
    var i;
    for (i = 0; i < 4; i++) {
      var dx = state.points[i][0] - x;
      var dy = state.points[i][1] - y;
      if (dx * dx + dy * dy < 520) return i;
    }
    return -1;
  }

  function canvasPos(ev) {
    var canvas = $("cropCanvas");
    var rect = canvas.getBoundingClientRect();
    var cx = ev.clientX != null ? ev.clientX : (ev.touches && ev.touches[0] ? ev.touches[0].clientX : 0);
    var cy = ev.clientY != null ? ev.clientY : (ev.touches && ev.touches[0] ? ev.touches[0].clientY : 0);
    return {
      x: (cx - rect.left) * (canvas.width / rect.width),
      y: (cy - rect.top) * (canvas.height / rect.height)
    };
  }

  function onDown(ev) {
    if (state.busy) return;
    ev.preventDefault();
    var p = canvasPos(ev);
    state.dragging = hitTest(p.x, p.y);
  }
  function onMove(ev) {
    if (state.dragging < 0 || state.busy) return;
    ev.preventDefault();
    var p = canvasPos(ev);
    var w = $("cropCanvas").width, h = $("cropCanvas").height;
    state.points[state.dragging] = [
      Math.max(0, Math.min(w, p.x)),
      Math.max(0, Math.min(h, p.y))
    ];
    state.moved = true;
    draw();
  }
  function onUp() { state.dragging = -1; }
  function onTouchStart(ev) { onDown(ev); }
  function onTouchMove(ev) { onMove(ev); }

  function fitCanvas(img) {
    var max = 560;
    var w = img.width, h = img.height;
    if (w > max || h > max) {
      if (w > h) { h = Math.round(h * max / w); w = max; }
      else { w = Math.round(w * max / h); h = max; }
    }
    var canvas = $("cropCanvas");
    canvas.width = w;
    canvas.height = h;
    state.img = img;
    state.points = defaultPoints(w, h);
    state.moved = false;
    draw();
  }

  function loadFileToCanvas(file, thenAuto) {
    var img = new Image();
    img.onload = function () {
      fitCanvas(img);
      if (thenAuto) runAutoCrop();
    };
    img.src = URL.createObjectURL(file);
  }

  function blobToFile(blob, name) {
    try {
      return new File([blob], name || "leaf_cropped.jpg", { type: blob.type || "image/jpeg" });
    } catch (e) {
      return blob;
    }
  }

  function loadImg(file, ok, fail) {
    var img = new Image();
    img.onload = function () { ok(img); };
    img.onerror = function () { if (fail) fail(); };
    img.src = URL.createObjectURL(file);
  }

  function canvasToFile(canvas, name, ok) {
    if (canvas.toBlob) {
      canvas.toBlob(function (blob) {
        ok(blob ? blobToFile(blob, name) : null);
      }, "image/jpeg", 0.85);
      return;
    }
    ok(null);
  }

  function shrinkFile(file, maxSide, ok) {
    loadImg(file, function (img) {
      var w = img.width, h = img.height;
      if (w > maxSide || h > maxSide) {
        if (w > h) { h = Math.round(h * maxSide / w); w = maxSide; }
        else { w = Math.round(w * maxSide / h); h = maxSide; }
      }
      var c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      c.getContext("2d").drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(img.src);
      canvasToFile(c, "leaf.jpg", function (f) { ok(f || file); });
    }, function () { ok(file); });
  }

  function hsv255(r, g, b) {
    var rr = r / 255, gg = g / 255, bb = b / 255;
    var max = Math.max(rr, gg, bb), min = Math.min(rr, gg, bb), d = max - min;
    var h = 0;
    if (d !== 0) {
      if (max === rr) h = ((gg - bb) / d + (gg < bb ? 6 : 0)) * 60;
      else if (max === gg) h = ((bb - rr) / d + 2) * 60;
      else h = ((rr - gg) / d + 4) * 60;
    }
    return { h: h / 2, s: max === 0 ? 0 : (d / max) * 255, v: max * 255 };
  }

  function isLeafPixel(r, g, b) {
    var hsv = hsv255(r, g, b);
    if (hsv.v > 210 && hsv.s < 40) return false;
    if (hsv.h >= 25 && hsv.h <= 95 && hsv.s >= 25 && hsv.v >= 25) return true;
    if (hsv.h >= 15 && hsv.h <= 35 && hsv.s >= 30 && hsv.v >= 40) return true;
    if (hsv.h >= 5 && hsv.h <= 25 && hsv.s >= 20 && hsv.v >= 20 && hsv.v <= 180) return true;
    return (2 * g - r - b) > 18;
  }

  function localAutoCrop(file, ok) {
    loadImg(file, function (img) {
      var max = 480;
      var w = img.width, h = img.height;
      var tw = w, th = h;
      if (w > max || h > max) {
        if (w > h) { th = Math.round(h * max / w); tw = max; }
        else { tw = Math.round(w * max / h); th = max; }
      }
      var c = document.createElement("canvas");
      c.width = tw;
      c.height = th;
      var ctx = c.getContext("2d");
      ctx.drawImage(img, 0, 0, tw, th);
      var pix = ctx.getImageData(0, 0, tw, th).data;
      var minX = tw, minY = th, maxX = 0, maxY = 0, count = 0;
      var i, x, y, r, g, b;
      for (y = 0; y < th; y++) {
        for (x = 0; x < tw; x++) {
          i = (y * tw + x) * 4;
          r = pix[i];
          g = pix[i + 1];
          b = pix[i + 2];
          if (!isLeafPixel(r, g, b)) continue;
          count++;
          if (x < minX) minX = x;
          if (y < minY) minY = y;
          if (x > maxX) maxX = x;
          if (y > maxY) maxY = y;
        }
      }
      if (count < 0.015 * tw * th || maxX <= minX || maxY <= minY) {
        URL.revokeObjectURL(img.src);
        ok(file);
        return;
      }
      var padX = Math.round((maxX - minX) * 0.06);
      var padY = Math.round((maxY - minY) * 0.06);
      var sx = w / tw, sy = h / th;
      var x0 = Math.max(0, Math.round((minX - padX) * sx));
      var y0 = Math.max(0, Math.round((minY - padY) * sy));
      var x1 = Math.min(w, Math.round((maxX + padX) * sx));
      var y1 = Math.min(h, Math.round((maxY + padY) * sy));
      if (x1 - x0 < 16 || y1 - y0 < 16) {
        URL.revokeObjectURL(img.src);
        ok(file);
        return;
      }
      var out = document.createElement("canvas");
      out.width = x1 - x0;
      out.height = y1 - y0;
      out.getContext("2d").drawImage(img, x0, y0, out.width, out.height, 0, 0, out.width, out.height);
      URL.revokeObjectURL(img.src);
      canvasToFile(out, "leaf_auto.jpg", function (f) { ok(f || file); });
    }, function () { ok(file); });
  }

  function revealModal(file) {
    ensureModal();
    refreshLabels();
    state.open = true;
    $("cropModal").className = "crop-modal";
    setBusy(false);
    loadFileToCanvas(file, false);
    hideScan();
  }

  function open(file, done, opts) {
    opts = opts || {};
    ensureModal();
    ensureOverlay();
    refreshLabels();
    state.originalFile = file;
    state.file = file;
    state.onDone = done;
    state.moved = false;
    state.gen += 1;
    var gen = state.gen;
    showScan(T("scan_prep"), T("scan_prep_sub"), { allowSkip: true });
    shrinkFile(file, 1024, function (small) {
      if (gen !== state.gen) return;
      state.file = small;
      if (opts.autoLeaf === false) {
        revealModal(small);
        return;
      }
      showScan(T("crop_working"), T("scan_prep_leaf_sub"), { allowSkip: true });
      localAutoCrop(small, function (cropped) {
        if (gen !== state.gen) return;
        state.file = cropped || small;
        revealModal(state.file);
      });
    });
  }

  function close() {
    state.gen += 1;
    state.open = false;
    setBusy(false);
    hideScan();
    var modal = $("cropModal");
    if (modal) modal.className = "crop-modal hidden";
  }

  function finish(file) {
    var cb = state.onDone;
    close();
    if (cb) cb(file);
  }

  function skipOriginal() {
    finish(state.originalFile || state.file);
  }

  function resetToOriginal() {
    if (!state.originalFile) return;
    showScan(T("scan_prep"), T("scan_prep_sub"), { allowSkip: true });
    shrinkFile(state.originalFile, 1024, function (small) {
      state.file = small;
      revealModal(small);
    });
  }

  function scalePointsToImage() {
    if (!state.img || !$("cropCanvas")) return state.points;
    var canvas = $("cropCanvas");
    var sx = state.img.width / canvas.width;
    var sy = state.img.height / canvas.height;
    var out = [], i;
    for (i = 0; i < 4; i++) {
      out.push([Math.round(state.points[i][0] * sx), Math.round(state.points[i][1] * sy)]);
    }
    return out;
  }

  function runAutoCrop() {
    var src = state.file || state.originalFile;
    if (!src || state.busy) return;
    setBusy(true);
    showScan(T("crop_working"), T("scan_prep_leaf_sub"), { allowSkip: true });
    localAutoCrop(src, function (cropped) {
      var f = cropped || src;
      state.file = f;
      var img = new Image();
      img.onload = function () {
        fitCanvas(img);
        setBusy(false);
        hideScan();
      };
      img.onerror = function () {
        setBusy(false);
        hideScan();
      };
      img.src = URL.createObjectURL(f);
    });
  }

  function applyCrop() {
    if (!state.file || state.busy) return;
    if (!state.moved || !state.img) {
      finish(state.file);
      return;
    }
    var pts = scalePointsToImage();
    var xs = [pts[0][0], pts[1][0], pts[2][0], pts[3][0]];
    var ys = [pts[0][1], pts[1][1], pts[2][1], pts[3][1]];
    var x0 = Math.max(0, Math.min.apply(null, xs));
    var y0 = Math.max(0, Math.min.apply(null, ys));
    var x1 = Math.min(state.img.width, Math.max.apply(null, xs));
    var y1 = Math.min(state.img.height, Math.max.apply(null, ys));
    if (x1 - x0 < 8 || y1 - y0 < 8) {
      finish(state.file);
      return;
    }
    var c = document.createElement("canvas");
    c.width = x1 - x0;
    c.height = y1 - y0;
    c.getContext("2d").drawImage(state.img, x0, y0, c.width, c.height, 0, 0, c.width, c.height);
    canvasToFile(c, "leaf_crop.jpg", function (f) {
      finish(f || state.file);
    });
  }

  document.addEventListener("langchange", function () {
    if (state.open) refreshLabels();
    if ($("scanOverlay") && $("scanOverlay").className.indexOf("hidden") < 0) refreshLabels();
  });

  window.AgroScanBusy = {
    show: showScan,
    hide: hideScan,
    startChecking: startCheckStages
  };

  window.AgroScanCrop = {
    open: open,
    close: close,
    skip: function (file, done) { if (done) done(file); }
  };
})();
