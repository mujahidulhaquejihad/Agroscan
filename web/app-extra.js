/* Optional extras: i18n, resources, drag-drop, chatbot */
(function () {
  var cfg = window.AGROVET_CONFIG || {};
  var API = cfg.API_BASE || "";
  function $(id) { return document.getElementById(id); }

  function init() {
    try {
      if (window.AgrovetI18n) {
        window.AgrovetI18n.applyI18n();
        var langBtn = $("langToggle");
        if (langBtn) langBtn.onclick = function () { window.AgrovetI18n.toggleLang(); };
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

  function i18n() { return window.AgrovetI18n; }

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
      if (e.dataTransfer && e.dataTransfer.files[0] && window.agrovetPickFile) {
        var inp = $("fileInput");
        if (inp) { inp.files = e.dataTransfer.files; window.agrovetPickFile(inp); }
      }
    };
  }

  function setupChat() {
    var toggle = $("chatToggle"), panel = $("chatPanel"), close = $("chatClose"), form = $("chatForm");
    var attachBtn = $("chatAttachBtn"), micBtn = $("chatMicBtn"), imgInput = $("chatImageInput");
    if (toggle) toggle.onclick = function () {
      if (panel) panel.className = panel.className.indexOf("hidden") >= 0 ? "chat-panel" : "chat-panel hidden";
    };
    if (close && panel) close.onclick = function () { panel.className = "chat-panel hidden"; };
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
    if (window.AgrovetI18n && window.AgrovetI18n.t) return window.AgrovetI18n.t(key, vars);
    return key;
  }

  function isBnChat() {
    return i18n() && i18n().lang === "bn";
  }

  var chatPendingFile = null;
  var chatSpeech = null;
  var chatListening = false;

  function pushChatBot(text) {
    var log = $("chatLog");
    if (!log || !text) return;
    var b = document.createElement("div");
    b.className = "msg bot";
    b.textContent = text;
    log.appendChild(b);
    log.scrollTop = log.scrollHeight;
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
        for (i = 0; i < Math.min(3, opts.length); i++) {
          (function (opt) {
            var b = document.createElement("button");
            b.type = "button";
            b.className = "chip chip-choice";
            var label = opt.label || opt.crop || "";
            if (opt.confidence != null) {
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
      if (window.AgrovetShop) {
        try { window.AgrovetShop.recommendForDisease(best.prediction); } catch (e) {}
      }
    } else if (data.class_name) {
      window.AgroScanLastDisease = data.class_name;
    }

    if (data.reply) {
      pushChatBot(data.reply);
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

  function stopVoiceListen() {
    chatListening = false;
    refreshMicTitle();
    if (chatSpeech) {
      try { chatSpeech.onend = null; chatSpeech.stop(); } catch (e) {}
    }
  }

  function toggleVoiceListen() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      pushChatBot(tChat("chat_mic_unsupported"));
      return;
    }
    if (chatListening) {
      stopVoiceListen();
      return;
    }
    if (!chatSpeech) {
      chatSpeech = new SR();
      chatSpeech.continuous = false;
      chatSpeech.interimResults = true;
      chatSpeech.maxAlternatives = 1;
      chatSpeech.onresult = function (ev) {
        var txt = $("chatText");
        if (!txt) return;
        var out = "";
        var i;
        for (i = 0; i < ev.results.length; i++) {
          out += ev.results[i][0].transcript;
        }
        txt.value = out.trim();
      };
      chatSpeech.onerror = function () {
        stopVoiceListen();
      };
      chatSpeech.onend = function () {
        chatListening = false;
        refreshMicTitle();
      };
    }
    chatSpeech.lang = isBnChat() ? "bn-BD" : "en-US";
    try {
      chatSpeech.start();
      chatListening = true;
      refreshMicTitle();
    } catch (e) {
      stopVoiceListen();
      pushChatBot(tChat("chat_mic_error"));
    }
  }

  var chatLoadTimer = null;
  var chatLoadStep = 0;
  var chatLoadReady = false;
  var chatLoadDoneFn = null;

  function chatProgressTexts() {
    var bn = i18n() && i18n().lang === "bn";
    if (bn) {
      return [
        "পাতার ছবি মডেলে যাচাই করছি…",
        "রোগ শনাক্ত করে গাইড মিলিয়ে দেখছি…",
        "সহকারী পরামর্শ লিখছি…",
      ];
    }
    return [
      "Running leaf models on your photo…",
      "Matching the disease guide…",
      "Writing assistant feedback…",
    ];
  }

  function chatAlmostReadyText() {
    return (i18n() && i18n().lang === "bn") ? "প্রায় হয়ে গেছে…" : "Almost ready…";
  }

  function setChatLoadText(text) {
    var el = $("chatLoadingMsg");
    var textEl = el && el.querySelector(".chat-load-text");
    if (textEl) textEl.textContent = text;
  }

  function clearChatLoadTimer() {
    if (chatLoadTimer) {
      clearTimeout(chatLoadTimer);
      chatLoadTimer = null;
    }
  }

  function stopChatLoading() {
    clearChatLoadTimer();
    chatLoadReady = false;
    chatLoadDoneFn = null;
    chatLoadStep = 0;
    var el = $("chatLoadingMsg");
    if (el && el.parentNode) el.parentNode.removeChild(el);
    var panel = $("chatPanel");
    if (panel) panel.classList.remove("chat-busy");
  }

  function advanceChatLoading() {
    clearChatLoadTimer();
    var texts = chatProgressTexts();

    // Answer is in — only now show "Almost ready", then reveal.
    if (chatLoadReady) {
      setChatLoadText(chatAlmostReadyText());
      chatLoadTimer = setTimeout(function () {
        var done = chatLoadDoneFn;
        stopChatLoading();
        if (done) done();
      }, 1100);
      return;
    }

    // Still waiting: move to next progress line once, never loop.
    if (chatLoadStep < texts.length - 1) {
      chatLoadStep += 1;
      setChatLoadText(texts[chatLoadStep]);
      chatLoadTimer = setTimeout(advanceChatLoading, 2200);
      return;
    }

    // Stay on the last progress line until the answer arrives.
    // finishChatLoading() will call advanceChatLoading when ready.
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
    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;

    chatLoadStep = 0;
    chatLoadReady = false;
    setChatLoadText(chatProgressTexts()[0]);
    chatLoadTimer = setTimeout(advanceChatLoading, 2200);
  }

  function finishChatLoading(done) {
    chatLoadDoneFn = done;
    chatLoadReady = true;
    clearChatLoadTimer();
    var texts = chatProgressTexts();
    // Finish remaining progress steps slowly, then "Almost ready".
    function continueSteps() {
      if (!chatLoadReady) return;
      if (chatLoadStep < texts.length - 1) {
        chatLoadStep += 1;
        setChatLoadText(texts[chatLoadStep]);
        chatLoadTimer = setTimeout(continueSteps, 1800);
        return;
      }
      chatLoadTimer = setTimeout(advanceChatLoading, 600);
    }
    chatLoadTimer = setTimeout(continueSteps, 800);
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
    x.onload = function () {
      finishChatLoading(function () {
        try {
          var d = JSON.parse(x.responseText);
          if (log) {
            var b = document.createElement("div");
            b.className = "msg bot";
            b.textContent = d.reply;
            log.appendChild(b);
            log.scrollTop = log.scrollHeight;
          }
          var clarifying = d.source === "clarify" && d.options && d.options.length;
          renderChatChips(d.suggestions, d.options, clarifying);
          if (!clarifying) setChatInputLocked(false);
        } catch (e) {
          setChatInputLocked(false);
          if (log) {
            var err = document.createElement("div");
            err.className = "msg bot";
            err.textContent = (i18n() && i18n().lang === "bn")
              ? "সহকারী সেবায় যোগাযোগ করা যায়নি।"
              : "Sorry, I couldn't reach the assistant.";
            log.appendChild(err);
          }
        }
      });
    };
    x.onerror = function () {
      finishChatLoading(function () {
        setChatInputLocked(false);
        if (log) {
          var err = document.createElement("div");
          err.className = "msg bot";
          err.textContent = (i18n() && i18n().lang === "bn")
            ? "সহকারী সেবায় যোগাযোগ করা যায়নি।"
            : "Sorry, I couldn't reach the assistant.";
          log.appendChild(err);
        }
      });
    };
    var lang = i18n() ? i18n().lang : "en";
    var lastDisease = window.AgroScanLastDisease || null;
    var payload = { message: message || "", context_disease: lastDisease, lang: lang };
    if (confirmClass) payload.confirm_class = confirmClass;
    x.send(JSON.stringify(payload));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
