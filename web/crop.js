/* Leaf crop editor: 4 corners + auto leaf crop (ES5) */
(function () {
  var API = "";
  if (window.AGROVET_CONFIG && window.AGROVET_CONFIG.API_BASE) {
    API = window.AGROVET_CONFIG.API_BASE;
  }

  var state = {
    open: false,
    file: null,
    originalFile: null,
    img: null,
    points: [],
    dragging: -1,
    onDone: null,
    busy: false
  };

  function $(id) { return document.getElementById(id); }

  function T(key, vars) {
    return window.AgrovetI18n ? window.AgrovetI18n.t(key, vars) : key;
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
      '<div class="crop-head"><h3 id="cropTitle">' + T("crop_title") + '</h3>' +
      '<button type="button" id="cropClose" class="chat-close" aria-label="Close">&times;</button></div>' +
      '<p class="muted small" id="cropHint">' + T("crop_hint") + '</p>' +
      '<p id="cropStatus" class="muted small crop-status hidden"></p>' +
      '<div class="crop-stage"><canvas id="cropCanvas"></canvas></div>' +
      '<div class="crop-actions">' +
      '<button type="button" id="cropAutoBtn" class="btn btn-secondary">' + T("crop_auto") + '</button>' +
      '<button type="button" id="cropResetBtn" class="btn btn-ghost">' + T("crop_reset") + '</button>' +
      '<button type="button" id="cropSkipBtn" class="btn btn-ghost">' + T("crop_skip") + '</button>' +
      '<button type="button" id="cropApplyBtn" class="btn btn-primary">' + T("crop_apply") + '</button>' +
      '</div></div>';
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

  function open(file, done, opts) {
    opts = opts || {};
    ensureModal();
    refreshLabels();
    state.originalFile = file;
    state.file = file;
    state.onDone = done;
    state.open = true;
    var modal = $("cropModal");
    modal.className = "crop-modal";
    loadFileToCanvas(file, opts.autoLeaf !== false);
  }

  function close() {
    state.open = false;
    setBusy(false);
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
    state.file = state.originalFile;
    loadFileToCanvas(state.originalFile, false);
  }

  function blobToFile(blob, name) {
    try {
      return new File([blob], name || "leaf_cropped.jpg", { type: "image/jpeg" });
    } catch (e) {
      return blob;
    }
  }

  function postCrop(url, file, extra, ok, fail) {
    var fd = new FormData();
    fd.append("file", file, file.name || "leaf.jpg");
    if (extra && extra.points) fd.append("points", JSON.stringify(extra.points));
    if (extra && extra.isolate) fd.append("isolate", "true");
    var x = new XMLHttpRequest();
    x.open("POST", url, true);
    x.timeout = 120000;
    x.responseType = "blob";
    x.onload = function () {
      if (x.status >= 200 && x.status < 300) ok(x.response);
      else fail("HTTP " + x.status);
    };
    x.onerror = function () { fail("network"); };
    x.ontimeout = function () { fail("timeout"); };
    x.send(fd);
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
    var src = state.originalFile || state.file;
    if (!src || state.busy) return;
    setBusy(true);
    postCrop(API + "/api/preprocess/auto-crop", src, { isolate: true }, function (blob) {
      var f = blobToFile(blob, "leaf_auto.jpg");
      state.file = f;
      var img = new Image();
      img.onload = function () {
        fitCanvas(img);
        setBusy(false);
      };
      img.onerror = function () { setBusy(false); };
      img.src = URL.createObjectURL(f);
    }, function () {
      setBusy(false);
    });
  }

  function applyCrop() {
    if (!state.file || state.busy) return;
    setBusy(true);
    var pts = scalePointsToImage();
    postCrop(API + "/api/preprocess/perspective-crop", state.file, { points: pts }, function (blob) {
      var f = blobToFile(blob, "leaf_crop.jpg");
      setBusy(false);
      finish(f);
    }, function () {
      setBusy(false);
      finish(state.file);
    });
  }

  document.addEventListener("langchange", function () {
    if (state.open) refreshLabels();
  });

  window.AgrovetCrop = {
    open: open,
    close: close,
    skip: function (file, done) { if (done) done(file); }
  };
})();
