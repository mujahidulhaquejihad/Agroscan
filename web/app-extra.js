/* Optional extras: i18n, resources, drag-drop, chatbot */
(function () {
  var cfg = window.AGROSCAN_CONFIG || {};
  var API = cfg.API_BASE || "";
  function $(id) { return document.getElementById(id); }

  function init() {
    try {
      if (window.AgroScanI18n) {
        window.AgroScanI18n.applyI18n();
        var langBtn = $("langToggle");
        if (langBtn) langBtn.onclick = function () { window.AgroScanI18n.toggleLang(); };
      }
      document.addEventListener("langchange", function () {
        if (govLinks.length) paintGovGrid();
        if (emergencyContacts.length) paintEmergency();
        refreshMicTitle();
        var attachBtn = $("chatAttachBtn");
        if (attachBtn) {
          attachBtn.title = tChat("chat_attach");
          attachBtn.setAttribute("aria-label", tChat("chat_attach"));
        }
      });
      loadResources();
      setupDragDrop();
      setupChat();
    } catch (e) { console.error("app-extra:", e); }
  }

  var govLinks = [];
  var govFilter = "all";
  var govQuery = "";

  function i18n() { return window.AgroScanI18n; }

  function catLabel(cat) {
    var key = "resources_cat_" + (cat || "ministry");
    return i18n() ? i18n().t(key) : cat;
  }

  function visitLabel() {
    return i18n() ? i18n().t("resources_visit") : "Visit portal";
  }

  function esc(s) {
    return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  }

  function renderGovCard(c) {
    var cat = c.category || "ministry";
    var abbr = c.abbr || (c.name || "?").slice(0, 3).toUpperCase();
    var name = i18n() ? i18n().govField(c, "name") : c.name;
    var desc = i18n() ? i18n().govField(c, "desc") : c.desc;
    return "<a class='gov-card' href='" + esc(c.url) + "' target='_blank' rel='noopener' data-cat='" + esc(cat) + "'>" +
      "<div class='gov-card-top'><span class='gov-icon'>" + esc(abbr) + "</span>" +
      "<span class='gov-tag'>" + esc(catLabel(cat)) + "</span></div>" +
      "<h3 class='gov-title'>" + esc(name) + "</h3>" +
      "<p class='gov-desc'>" + esc(desc) + "</p>" +
      "<span class='gov-cta'>" + esc(visitLabel()) + " &#8594;</span></a>";
  }

  var emergencyContacts = [];

  function renderEmergencyCard(c) {
    var phone = c.phone;
    var name = i18n() && i18n().emField(phone, "name") ? i18n().emField(phone, "name") : c.name;
    var hours = i18n() && i18n().emField(phone, "hours") ? i18n().emField(phone, "hours") : c.hours;
    var note = i18n() && i18n().emField(phone, "note") ? i18n().emField(phone, "note") : c.note;
    var callTxt = i18n() ? i18n().t("call_btn", { phone: phone }) : ("Call " + phone);
    return "<div class='contact-card'><div class='cname'>" + esc(name) +
      "</div><div class='chours'>" + esc(hours) + "</div><div class='cnote'>" + esc(note) +
      "</div><a class='call-btn' href='tel:" + phone + "'>" + esc(callTxt) + "</a></div>";
  }

  function paintEmergency() {
    var eg = $("emergencyGrid");
    if (!eg || !emergencyContacts.length) return;
    var html = "", i;
    for (i = 0; i < emergencyContacts.length; i++) html += renderEmergencyCard(emergencyContacts[i]);
    eg.innerHTML = html;
  }

  function filterGovLinks() {
    var q = govQuery.toLowerCase().trim();
    var out = [], i, c, hay;
    for (i = 0; i < govLinks.length; i++) {
      c = govLinks[i];
      if (govFilter !== "all" && c.category !== govFilter) continue;
      hay = (c.name + " " + c.desc + " " + (c.abbr || "") + " " + (c.category || "")).toLowerCase();
      if (q && hay.indexOf(q) < 0) continue;
      out.push(c);
    }
    return out;
  }

  function paintGovGrid() {
    var gg = $("govGrid"), empty = $("govEmpty"), count = $("govCount");
    if (!gg) return;
    var list = filterGovLinks(), html = "", i;
    for (i = 0; i < list.length; i++) html += renderGovCard(list[i]);
    gg.innerHTML = html;
    if (empty) empty.className = list.length ? "gov-empty hidden" : "gov-empty";
    if (count) count.textContent = String(govLinks.length);
  }

  function setupGovHub() {
    var search = $("govSearch"), filters = $("govFilters");
    if (search) {
      search.oninput = function () { govQuery = search.value; paintGovGrid(); };
    }
    if (filters) {
      filters.onclick = function (e) {
        var btn = e.target;
        if (!btn || !btn.getAttribute || btn.getAttribute("data-filter") == null) return;
        govFilter = btn.getAttribute("data-filter");
        var chips = filters.querySelectorAll(".gov-filter"), j;
        for (j = 0; j < chips.length; j++) {
          chips[j].className = chips[j].getAttribute("data-filter") === govFilter
            ? "gov-filter active" : "gov-filter";
        }
        paintGovGrid();
      };
    }
  }

  function loadResources() {
    var x = new XMLHttpRequest();
    x.open("GET", API + "/api/resources", true);
    x.onload = function () {
      if (x.status !== 200) return;
      try {
        var d = JSON.parse(x.responseText);
        var eg = $("emergencyGrid");
        if (d.emergency_contacts) {
          emergencyContacts = d.emergency_contacts;
          paintEmergency();
        }
        if (d.gov_links) {
          govLinks = d.gov_links;
          setupGovHub();
          paintGovGrid();
        }
      } catch (e) {}
    };
    x.send();
  }

  function setupDragDrop() {
    var dropzone = $("dropzone");
    if (!dropzone) return;
    dropzone.ondragover = function (e) { e.preventDefault(); dropzone.className = "uploader dragover"; };
    dropzone.ondragleave = function () { dropzone.className = "uploader"; };
    dropzone.ondrop = function (e) {
      e.preventDefault();
      dropzone.className = "uploader";
      if (e.dataTransfer && e.dataTransfer.files[0] && window.agroscanPickFile) {
        var inp = $("fileInput");
        if (inp) { inp.files = e.dataTransfer.files; window.agroscanPickFile(inp); }
      }
    };
  }

  function setupChat() {
    var toggle = $("chatToggle"), panel = $("chatPanel"), close = $("chatClose"), form = $("chatForm");
    var attachBtn = $("chatAttachBtn"), micBtn = $("chatMicBtn"), imgInput = $("chatImageInput");
    if (toggle) toggle.onclick = function () {
      if (!panel) return;
      var opening = panel.className.indexOf("hidden") >= 0;
      panel.className = opening ? "chat-panel" : "chat-panel hidden";
      document.body.classList.toggle("chat-open", opening);
      if (!opening) stopVoiceListen();
    };
    if (close && panel) close.onclick = function () {
      panel.className = "chat-panel hidden";
      document.body.classList.remove("chat-open");
      stopVoiceListen();
    };
    if (form) form.onsubmit = function (e) {
      e.preventDefault();
      stopVoiceListen();
      var txt = $("chatText");
      if (!txt || !txt.value.trim()) return;
      var msg = txt.value.trim();
      txt.value = "";
      sendChat(msg);
    };
    if (attachBtn && imgInput) {
      attachBtn.onclick = function () {
        if (form && form.classList.contains("chat-input-locked")) return;
        imgInput.value = "";
        imgInput.click();
      };
      imgInput.onchange = function () {
        var f = imgInput.files && imgInput.files[0];
        if (f) chatAnalyzeImage(f, null);
      };
    }
    if (micBtn) {
      micBtn.onclick = function () {
        if (form && form.classList.contains("chat-input-locked")) return;
        toggleVoiceListen();
      };
      refreshMicTitle();
    }
    if (attachBtn) {
      attachBtn.title = tChat("chat_attach");
      attachBtn.setAttribute("aria-label", tChat("chat_attach"));
    }
  }

  function tChat(key, vars) {
    if (window.AgroScanI18n && window.AgroScanI18n.t) return window.AgroScanI18n.t(key, vars);
    return key;
  }

  var chatPendingFile = null;
  var chatSpeech = null;
  var chatListening = false;
  var chatSendOnEnd = false;
  var chatRec = null;
  var chatRecStream = null;
  var chatRecChunks = [];
  var chatRecTimer = null;
  var chatRecMime = "";
  var chatAudioCtx = null;

  function chatSourceLabel(src) {
    if (!src || src === "clarify") return "";
    if (src.indexOf("gemini") >= 0 || src === "llm") return tChat("chat_src_guides");
    if (src === "pack" || src === "context" || src === "vision+pack") return tChat("chat_src_pack");
    if (src === "catalog") return tChat("chat_src_list");
    if (src.indexOf("offline") >= 0) return tChat("chat_src_offline");
    if (src === "kb" || src === "vision") return tChat("chat_src_kb");
    return "";
  }

  function rememberChatDisease(d) {
    if (!d) return;
    if (d.class_name) window.AgroScanLastDisease = d.class_name;
    else if (d.matched_key) window.AgroScanLastDisease = d.matched_key;
  }

  function pushChatBot(text, source) {
    var log = $("chatLog");
    if (!log || !text) return;
    var b = document.createElement("div");
    b.className = "msg bot";
    var body = document.createElement("div");
    body.className = "msg-body";
    body.textContent = text;
    b.appendChild(body);
    var label = chatSourceLabel(source);
    if (label) {
      var src = document.createElement("div");
      src.className = "msg-src";
      src.textContent = label;
      b.appendChild(src);
    }
    log.appendChild(b);
    log.scrollTop = log.scrollHeight;
  }

  function collectChatHistory() {
    var log = $("chatLog");
    if (!log) return [];
    var nodes = log.querySelectorAll(".msg.user, .msg.bot");
    var out = [];
    var i;
    for (i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.id === "chatLoadingMsg" || el.classList.contains("msg-loading")) continue;
      var role = el.classList.contains("user") ? "user" : "assistant";
      var body = el.querySelector(".msg-body") || el.querySelector(".chat-msg-cap");
      var text = ((body ? body.textContent : el.textContent) || "").trim();
      if (!text) continue;
      if (text.length > 1200) text = text.slice(0, 1200);
      out.push({ role: role, content: text });
    }
    if (out.length && out[out.length - 1].role === "user") out.pop();
    return out.slice(-8);
  }

  function pushChatUserImage(file) {
    var log = $("chatLog");
    if (!log || !file) return;
    var wrap = document.createElement("div");
    wrap.className = "msg user msg-with-image";
    var img = document.createElement("img");
    img.className = "chat-msg-img";
    img.alt = "";
    try {
      img.src = URL.createObjectURL(file);
    } catch (e) {
      img.remove();
    }
    if (img.src) wrap.appendChild(img);
    var cap = document.createElement("div");
    cap.className = "chat-msg-cap";
    cap.textContent = tChat("chat_photo_sent");
    wrap.appendChild(cap);
    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;
  }

  function postChatVision(file, crop, ok, fail) {
    var fd = new FormData();
    fd.append("file", file, file.name || "leaf.jpg");
    if (crop) fd.append("crop", crop);
    var lang = i18n() ? i18n().lang : "bn";
    fd.append("lang", lang);
    var land = $("landSize");
    var unit = $("landUnit");
    if (land && land.value) fd.append("land_size", land.value);
    if (unit && unit.value) fd.append("land_unit", unit.value);
    var x = new XMLHttpRequest();
    x.open("POST", API + "/api/chat/vision", true);
    x.timeout = 300000;
    if (x.upload) {
      x.upload.onload = function () {
        if (window.AgroScanBusy && window.AgroScanBusy.startChecking) {
          window.AgroScanBusy.startChecking();
        }
      };
    }
    x.onload = function () {
      try {
        var data = JSON.parse(x.responseText || "{}");
        if (x.status >= 200 && x.status < 300) ok(data);
        else fail((data && data.detail) || ("HTTP " + x.status));
      } catch (e) {
        fail("Bad response");
      }
    };
    x.onerror = function () { fail("Network error"); };
    x.ontimeout = function () { fail("Timeout"); };
    x.send(fd);
  }

  function chatAnalyzeImage(file, cropOverride) {
    if (!file) return;
    chatPendingFile = file;
    if (!cropOverride) pushChatUserImage(file);
    startChatLoading();
    setChatInputLocked(true, "loading");
    if (window.AgroScanBusy && window.AgroScanBusy.show) {
      window.AgroScanBusy.show(tChat("scan_prep"), tChat("scan_prep_sub"), { allowSkip: false });
    }
    var chips = $("chatChips");
    if (chips) {
      chips.innerHTML = "";
      chips.classList.remove("chat-choices");
    }
    postChatVision(file, cropOverride, function (data) {
      finishChatLoading(function () {
        handleChatVisionResult(data);
      });
    }, function () {
      finishChatLoading(function () {
        setChatInputLocked(false);
        pushChatBot(tChat("chat_photo_fail"));
      });
    });
  }

  function handleChatVisionResult(data) {
    data = data || {};
    var status = data.status || "";
    var g = data.stage1_leaf_gate || {};
    var crop = data.stage2_leaf_type || {};
    var d = data.stage3_disease || {};
    var best = (d && d.best_answer) || {};

    if (status === "not_leaf" || (g.available !== false && g.is_leaf === false)) {
      setChatInputLocked(false);
      pushChatBot(data.reply || tChat("chat_photo_not_leaf"));
      return;
    }

    if (status === "unsupported_crop") {
      setChatInputLocked(false);
      pushChatBot(data.reply || tChat("chat_photo_unsupported_crop"));
      return;
    }

    if (status === "need_crop" || (crop.needs_user_pick && chatPendingFile)) {
      setChatInputLocked(false);
      pushChatBot(data.reply || tChat("chat_photo_pick_crop"));
      var chips = $("chatChips");
      if (chips) {
        chips.innerHTML = "";
        chips.classList.add("chat-choices");
        var opts = data.options && data.options.length
          ? data.options
          : (crop.top3 || []).map(function (o) {
              return { crop: o.crop, label: o.crop, confidence: o.confidence };
            });
        var i;
        for (i = 0; i < opts.length; i++) {
          (function (opt) {
            var b = document.createElement("button");
            b.type = "button";
            b.className = "chip chip-choice";
            var cropName = opt.crop || opt.label || "";
            var isOther = String(cropName).toLowerCase() === "other";
            var label = isOther ? tChat("crop_other") : (opt.label || cropName);
            if (!isOther && opt.confidence != null) {
              label += " (" + Math.round(Number(opt.confidence) * 100) + "%)";
            }
            b.textContent = label;
            b.onclick = function () {
              chatAnalyzeImage(chatPendingFile, opt.crop || opt.label);
            };
            chips.appendChild(b);
          })(opts[i]);
        }
      }
      return;
    }

    if (best.prediction) {
      window.AgroScanLastDisease = best.prediction;
      if (window.AgroScanShop) {
        try { window.AgroScanShop.recommendForDisease(best.prediction); } catch (e) {}
      }
    } else if (data.class_name) {
      window.AgroScanLastDisease = data.class_name;
    }

    if (data.reply) {
      pushChatBot(data.reply, data.source);
    } else {
      pushChatBot(tChat("chat_photo_fail"));
    }
    renderChatChips(data.suggestions || [
      tChat("chat_photo_ask_treat"),
      tChat("chat_photo_ask_spray"),
      tChat("chat_photo_ask_prevent")
    ], null, false);
    setChatInputLocked(false);
  }

  function refreshMicTitle() {
    var micBtn = $("chatMicBtn");
    if (!micBtn) return;
    var label = chatListening ? tChat("chat_mic_listening") : tChat("chat_mic");
    micBtn.title = label;
    micBtn.setAttribute("aria-label", label);
    micBtn.classList.toggle("is-listening", !!chatListening);
  }

  function stopRecStream() {
    if (chatRecTimer) {
      clearTimeout(chatRecTimer);
      chatRecTimer = null;
    }
    if (chatRecStream) {
      try {
        var tracks = chatRecStream.getTracks();
        var i;
        for (i = 0; i < tracks.length; i++) tracks[i].stop();
      } catch (e) {}
      chatRecStream = null;
    }
    chatRec = null;
  }

  function stopVoiceListen(keepSend) {
    if (!keepSend) chatSendOnEnd = false;
    chatListening = false;
    refreshMicTitle();
    if (chatSpeech) {
      try { chatSpeech.stop(); } catch (e) {}
    }
    if (chatRec && chatRec.state === "recording") {
      try {
        if (chatRec.requestData) chatRec.requestData();
        chatRec.stop();
      } catch (e) {}
    } else {
      stopRecStream();
    }
  }

  function sendHeardChat() {
    var txt = $("chatText");
    var msg = txt && txt.value.trim();
    if (!msg) return;
    txt.value = "";
    sendChat(msg);
  }

  function recMimeType() {
    var types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
    var i;
    if (!window.MediaRecorder) return "";
    for (i = 0; i < types.length; i++) {
      try {
        if (MediaRecorder.isTypeSupported(types[i])) return types[i];
      } catch (e) {}
    }
    return "";
  }

  function showSttBusy() {
    if (window.AgroScanBusy && window.AgroScanBusy.show) {
      window.AgroScanBusy.show(tChat("chat_mic_transcribing"), tChat("chat_mic_transcribing_sub"), { allowSkip: false });
    }
  }

  function hideSttBusy() {
    if (window.AgroScanBusy && window.AgroScanBusy.hide) window.AgroScanBusy.hide();
  }

  function encodeWavMono16(samples, sampleRate) {
    var n = samples.length;
    var buf = new ArrayBuffer(44 + n * 2);
    var v = new DataView(buf);
    function wstr(o, s) {
      var i;
      for (i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
    }
    wstr(0, "RIFF");
    v.setUint32(4, 36 + n * 2, true);
    wstr(8, "WAVEfmt ");
    v.setUint32(16, 16, true);
    v.setUint16(20, 1, true);
    v.setUint16(22, 1, true);
    v.setUint32(24, sampleRate, true);
    v.setUint32(28, sampleRate * 2, true);
    v.setUint16(32, 2, true);
    v.setUint16(34, 16, true);
    wstr(36, "data");
    v.setUint32(40, n * 2, true);
    var i, s;
    for (i = 0; i < n; i++) {
      s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, s < 0 ? s * 32768 : s * 32767, true);
    }
    return new Blob([buf], { type: "audio/wav" });
  }

  function blobToSpeechWav(blob, done) {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC || !blob) {
      done(blob);
      return;
    }
    if (!chatAudioCtx) {
      try { chatAudioCtx = new AC(); } catch (e) { done(blob); return; }
    }
    var ctx = chatAudioCtx;
    function decode() {
      var reader = new FileReader();
      reader.onload = function () {
        var raw = reader.result;
        try { raw = raw.slice(0); } catch (e2) {}
        ctx.decodeAudioData(raw, function (buf) {
          var left = buf.getChannelData(0);
          var data = new Float32Array(left.length);
          var i;
          data.set(left);
          if (buf.numberOfChannels > 1) {
            var right = buf.getChannelData(1);
            var lim = Math.min(data.length, right.length);
            for (i = 0; i < lim; i++) data[i] = (data[i] + right[i]) * 0.5;
          }
          var fromRate = buf.sampleRate;
          var rate = fromRate >= 24000 ? 24000 : 16000;
          var ratio = fromRate / rate;
          var n = Math.max(1, Math.floor(data.length / ratio));
          var samples = new Float32Array(n);
          var start, end, j, acc, k;
          for (i = 0; i < n; i++) {
            start = Math.floor(i * ratio);
            end = Math.min(data.length, Math.floor((i + 1) * ratio) || start + 1);
            acc = 0;
            k = 0;
            for (j = start; j < end; j++) {
              acc += data[j];
              k += 1;
            }
            samples[i] = k ? acc / k : data[start];
          }
          if (n / rate < 0.25) {
            done(null);
            return;
          }
          done(encodeWavMono16(samples, rate));
        }, function () { done(blob); });
      };
      reader.onerror = function () { done(blob); };
      reader.readAsArrayBuffer(blob);
    }
    if (ctx.state === "suspended" && ctx.resume) ctx.resume().then(decode, decode);
    else decode();
  }

  function uploadStt(blob) {
    showSttBusy();
    blobToSpeechWav(blob, function (wav) {
      if (!wav || wav.size < 200) {
        hideSttBusy();
        pushChatBot(tChat("chat_mic_short"));
        return;
      }
      setChatInputLocked(true, "loading");
      var fd = new FormData();
      var name = (wav.type || "").indexOf("wav") >= 0 ? "speech.wav" : "speech.webm";
      fd.append("file", wav, name);
      fd.append("lang", i18n() ? i18n().lang : "bn");
      var x = new XMLHttpRequest();
      x.open("POST", API + "/api/chat/stt", true);
      x.timeout = 25000;
      x.onload = function () {
        hideSttBusy();
        setChatInputLocked(false);
        refreshMicTitle();
        if (x.status < 200 || x.status >= 300) {
          pushChatBot(tChat("chat_stt_fail"));
          return;
        }
        try {
          var d = JSON.parse(x.responseText || "{}");
          if (d.text) sendChat(String(d.text).trim());
          else pushChatBot(tChat("chat_stt_fail"));
        } catch (e) {
          pushChatBot(tChat("chat_stt_fail"));
        }
      };
      x.onerror = x.ontimeout = function () {
        hideSttBusy();
        setChatInputLocked(false);
        refreshMicTitle();
        pushChatBot(tChat("chat_stt_fail"));
      };
      x.send(fd);
    });
  }

  function beginMediaListen() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      pushChatBot(tChat("chat_mic_unsupported"));
      return;
    }
    navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      }
    }).then(function (stream) {
      if (!chatAudioCtx) {
        try {
          var AC = window.AudioContext || window.webkitAudioContext;
          if (AC) chatAudioCtx = new AC();
        } catch (e0) {}
      }
      if (chatAudioCtx && chatAudioCtx.state === "suspended" && chatAudioCtx.resume) {
        chatAudioCtx.resume();
      }
      chatRecStream = stream;
      chatRecChunks = [];
      chatRecMime = recMimeType();
      chatRec = chatRecMime ? new MediaRecorder(stream, { mimeType: chatRecMime }) : new MediaRecorder(stream);
      chatRec.ondataavailable = function (ev) {
        if (ev.data && ev.data.size) chatRecChunks.push(ev.data);
      };
      chatRec.onerror = function () {
        stopRecStream();
        chatListening = false;
        refreshMicTitle();
        pushChatBot(tChat("chat_mic_error"));
      };
      chatRec.onstop = function () {
        var blob = new Blob(chatRecChunks, { type: (chatRecMime || "audio/webm").split(";")[0] });
        stopRecStream();
        chatListening = false;
        refreshMicTitle();
        if (chatSendOnEnd) {
          chatSendOnEnd = false;
          if (!blob.size) {
            pushChatBot(tChat("chat_mic_short"));
            return;
          }
          uploadStt(blob);
        }
      };
      try {
        chatSendOnEnd = true;
        chatRec.start(250);
        chatListening = true;
        refreshMicTitle();
        chatRecTimer = setTimeout(function () {
          if (chatRec && chatRec.state === "recording") {
            try { chatRec.stop(); } catch (e2) {}
          }
        }, 20000);
      } catch (e) {
        chatSendOnEnd = false;
        stopRecStream();
        chatListening = false;
        refreshMicTitle();
        pushChatBot(tChat("chat_mic_error"));
      }
    }).catch(function () {
      pushChatBot(tChat("chat_mic_error"));
    });
  }

  function beginVoiceListen() {
    beginMediaListen();
  }

  function toggleVoiceListen() {
    if (chatListening) {
      if (chatRec && chatRec.state === "recording") {
        stopVoiceListen(true);
        return;
      }
      var txt = $("chatText");
      var msg = txt && txt.value.trim();
      stopVoiceListen();
      if (msg) {
        txt.value = "";
        sendChat(msg);
      }
      return;
    }
    beginVoiceListen();
  }

  function stopChatLoading() {
    var el = $("chatLoadingMsg");
    if (el && el.parentNode) el.parentNode.removeChild(el);
    var panel = $("chatPanel");
    if (panel) panel.classList.remove("chat-busy");
  }

  function startChatLoading() {
    stopChatLoading();
    var log = $("chatLog");
    if (!log) return;
    var panel = $("chatPanel");
    if (panel) panel.classList.add("chat-busy");

    var wrap = document.createElement("div");
    wrap.id = "chatLoadingMsg";
    wrap.className = "msg bot msg-loading";
    wrap.innerHTML =
      '<span class="chat-load-spin" aria-hidden="true"></span>' +
      '<span class="chat-load-text"></span>' +
      '<span class="chat-load-dots" aria-hidden="true"><i></i><i></i><i></i></span>';
    var textEl = wrap.querySelector(".chat-load-text");
    if (textEl) textEl.textContent = (i18n() && i18n().lang === "bn") ? "উত্তর লিখছি…" : "Writing a reply…";
    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;
  }

  function finishChatLoading(done) {
    if (window.AgroScanBusy && window.AgroScanBusy.hide) window.AgroScanBusy.hide();
    stopChatLoading();
    if (done) done();
  }

  function setChatInputLocked(locked, reason) {
    var txt = $("chatText");
    var form = $("chatForm");
    var btn = $("chatSend") || (form ? form.querySelector("button[type=submit]") : null);
    var attachBtn = $("chatAttachBtn");
    var micBtn = $("chatMicBtn");
    var bn = i18n() && i18n().lang === "bn";
    if (txt) {
      txt.disabled = !!locked;
      if (!locked) {
        txt.placeholder = tChat("chat_ph");
      } else if (reason === "loading") {
        txt.placeholder = bn ? "উত্তর আসছে…" : "Answer loading…";
      } else {
        txt.placeholder = bn ? "নিচ থেকে বেছে নিন" : "Choose an option below";
      }
    }
    if (btn) btn.disabled = !!locked;
    if (attachBtn) attachBtn.disabled = !!locked;
    if (micBtn) micBtn.disabled = !!locked;
    if (form) form.classList.toggle("chat-input-locked", !!locked);
    if (locked) stopVoiceListen();
  }

  function renderChatChips(suggestions, options, clarifying) {
    var chips = $("chatChips");
    if (!chips) return;
    chips.innerHTML = "";
    chips.classList.toggle("chat-choices", !!clarifying);
    var items = [];
    if (options && options.length) {
      for (var i = 0; i < options.length; i++) {
        items.push({
          label: options[i].label || options[i].class_name,
          confirmClass: options[i].class_name || null,
          choice: true,
        });
      }
    } else if (!clarifying) {
      for (var j = 0; j < (suggestions || []).length; j++) {
        items.push({ label: suggestions[j], confirmClass: null, choice: false });
      }
    }
    items.forEach(function (item) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = item.choice ? "chip chip-choice" : "chip";
      b.textContent = item.label;
      if (item.confirmClass) b.setAttribute("data-confirm-class", item.confirmClass);
      b.onclick = function () {
        setChatInputLocked(false);
        sendChat(item.label, item.confirmClass);
      };
      chips.appendChild(b);
    });
    setChatInputLocked(!!clarifying && items.length > 0, clarifying ? "clarify" : null);
  }

  function sendChat(message, confirmClass) {
    var log = $("chatLog");
    if (message && log) {
      var u = document.createElement("div");
      u.className = "msg user";
      u.textContent = message;
      log.appendChild(u);
    }
    startChatLoading();
    setChatInputLocked(true, "loading");
    var chips = $("chatChips");
    if (chips) {
      chips.innerHTML = "";
      chips.classList.remove("chat-choices");
    }

    var x = new XMLHttpRequest();
    x.open("POST", API + "/api/chat", true);
    x.setRequestHeader("Content-Type", "application/json");
    x.timeout = 90000;
    x.onload = function () {
      if (x.status < 200 || x.status >= 300) {
        if (typeof x.onerror === "function") x.onerror();
        return;
      }
      finishChatLoading(function () {
        try {
          var d = JSON.parse(x.responseText);
          rememberChatDisease(d);
          pushChatBot(d.reply, d.source);
          var clarifying = d.source === "clarify" && d.options && d.options.length;
          renderChatChips(d.suggestions, d.options, clarifying);
          if (!clarifying) setChatInputLocked(false);
        } catch (e) {
          setChatInputLocked(false);
          pushChatBot(tChat("chat_unreachable"));
        }
      });
    };
    x.onerror = x.ontimeout = function () {
      if (window.AgroScanOffline && window.AgroScanOffline.chat) {
        window.AgroScanOffline.chat(message, lang, lastDisease).then(function (d) {
          finishChatLoading(function () {
            rememberChatDisease(d);
            pushChatBot(d.reply, d.source);
            renderChatChips(d.suggestions, d.options, false);
            setChatInputLocked(false);
          });
        });
        return;
      }
      finishChatLoading(function () {
        setChatInputLocked(false);
        pushChatBot(tChat("chat_unreachable"));
      });
    };
    var lang = i18n() ? i18n().lang : "en";
    var lastDisease = window.AgroScanLastDisease || null;
    var payload = { message: message || "", context_disease: lastDisease, lang: lang };
    var history = collectChatHistory();
    if (history.length) payload.history = history;
    if (confirmClass) payload.confirm_class = confirmClass;
    var place = window.AgroScanShop && window.AgroScanShop.getPlace && window.AgroScanShop.getPlace();
    var geo = window.AgroScanGeo && window.AgroScanGeo.get && window.AgroScanGeo.get();
    if (place && place.district) payload.district = place.district;
    if (place && place.upazila) payload.upazila = place.upazila;
    if (geo && geo.lat != null) payload.lat = geo.lat;
    if (geo && geo.lng != null) payload.lng = geo.lng;
    x.send(JSON.stringify(payload));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
