const cfg = window.AGROVET_CONFIG || {};
const API = cfg.API_BASE || "";
const $ = (id) => document.getElementById(id);
const t = (k) => (window.AgrovetI18n ? window.AgrovetI18n.t(k) : k);
let selectedFile = null;
let lastDisease = null;
let apiOnline = false;

const IMG_EXT = /\.(jpe?g|png|webp|bmp|gif|heic|heif)$/i;

function isImageFile(file) {
  if (!file) return false;
  if (file.type && file.type.startsWith("image/")) return true;
  return IMG_EXT.test(file.name || "");
}

function apiDetail(data) {
  if (!data || !data.detail) return "Request failed";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  return String(data.detail);
}

function initApp() {
  try {
    const year = $("year");
    if (year) year.textContent = new Date().getFullYear();

    if (window.AgrovetI18n) {
      window.AgrovetI18n.applyI18n();
      const langBtn = $("langToggle");
      if (langBtn) langBtn.addEventListener("click", () => window.AgrovetI18n.toggleLang());
    }

    setStatusText("Checking server...");
    checkStatus();
    loadResources();
    setupUpload();
    setupAnalyze();
    setupChat();
    setupGoogle();
  } catch (err) {
    console.error("AgroVet init error:", err);
    showOffline("Page error - hard refresh (Ctrl+Shift+R)");
  }
}

function setStatusText(text) {
  const el = $("status");
  if (el) el.textContent = text;
}

function showOffline(msg) {
  apiOnline = false;
  const el = $("status");
  if (el) {
    el.textContent = msg || "API offline";
    el.classList.add("bad");
  }
  const banner = $("offlineBanner");
  if (banner) banner.classList.remove("hidden");
  updateAnalyzeButton();
}

function showOnline(s) {
  const models = s.disease_models_loaded || [];
  apiOnline = models.length > 0;
  $("offlineBanner").classList.add("hidden");
  const el = $("status");
  if (apiOnline) {
    el.textContent = `${models.length} models - ${s.device || "cpu"}`;
    el.classList.remove("bad");
  } else {
    el.textContent = s.message || "models not trained";
    el.classList.add("bad");
  }
  updateAnalyzeButton();
}

let statusRetries = 0;

async function checkStatus() {
  const url = `${API}/api/status`;
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    const r = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    showOnline(await r.json());
    statusRetries = 0;
  } catch (err) {
    statusRetries += 1;
    if (statusRetries < 15) {
      setStatusText(statusRetries < 3 ? "Loading models..." : `Connecting... (${statusRetries})`);
      setTimeout(checkStatus, 2000);
    } else {
      showOffline("Cannot reach server on :8000");
    }
  }
}

function loadResources() {
  fetch(`${API}/api/resources`).then((r) => r.json()).then((d) => {
    $("emergencyGrid").innerHTML = (d.emergency_contacts || []).map((c) => `
      <div class="contact-card">
        <div class="cname">${c.name}</div>
        <div class="chours">${c.hours}</div>
        <div class="cnote">${c.note}</div>
        <a class="call-btn" href="tel:${c.phone}">&#128222; Call ${c.phone}</a>
      </div>`).join("");
    $("govGrid").innerHTML = (d.gov_links || []).map((g) => `
      <a class="gov-card" href="${g.url}" target="_blank" rel="noopener">
        <div class="gname">${g.name}</div>
        <div class="gdesc">${g.desc}</div>
        <div class="gurl">${g.url}</div>
      </a>`).join("");
  }).catch(() => {});
}

function updateAnalyzeButton() {
  $("analyzeBtn").disabled = !(selectedFile && apiOnline);
}

function setupUpload() {
  const fileInput = $("fileInput");
  const dropzone = $("dropzone");

  fileInput.addEventListener("change", (e) => {
    handleFile(e.target.files[0]);
    e.target.value = "";
  });

  ["dragover", "dragenter"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
  dropzone.addEventListener("drop", (e) => handleFile(e.dataTransfer.files[0]));
}

function handleFile(file) {
  $("errorBox").classList.add("hidden");
  if (!file) return;
  if (!isImageFile(file)) {
    $("errorBox").textContent = "Please choose an image file (JPG, PNG, WEBP, etc.).";
    $("errorBox").classList.remove("hidden");
    return;
  }
  selectedFile = file;
  const preview = $("preview");
  preview.src = URL.createObjectURL(file);
  preview.style.display = "block";
  $("placeholder").style.display = "none";
  const fn = $("fileName");
  fn.textContent = file.name;
  fn.classList.remove("hidden");
  updateAnalyzeButton();
}

function setupAnalyze() {
  $("analyzeBtn").addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!selectedFile || !apiOnline) return;

    $("results").classList.add("hidden");
    $("errorBox").classList.add("hidden");
    $("loader").classList.remove("hidden");
    $("analyzeBtn").disabled = true;

    const fd = new FormData();
    fd.append("file", selectedFile, selectedFile.name || "leaf.jpg");

    try {
      const r = await fetch(`${API}/api/predict`, { method: "POST", body: fd });
      let data;
      try { data = await r.json(); } catch { data = {}; }
      if (!r.ok) throw new Error(apiDetail(data) || `Prediction failed (${r.status})`);
      render(data);
      if (window.AgrovetFeatures) window.AgrovetFeatures.onResult(data, $("preview").src);
    } catch (err) {
      const msg = String(err.message || err);
      $("errorBox").innerHTML = msg.includes("Failed to fetch") || msg.includes("NetworkError")
        ? `<strong>Cannot connect to the server.</strong><br>Keep the terminal running:<br><code>python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000</code>`
        : msg;
      $("errorBox").classList.remove("hidden");
    } finally {
      $("loader").classList.add("hidden");
      updateAnalyzeButton();
    }
  });
}

const pct = (x) => (x * 100).toFixed(1) + "%";
const isBn = () => window.AgrovetI18n && window.AgrovetI18n.lang === "bn";

function render(data) {
  $("results").classList.remove("hidden");
  const g = data.stage1_leaf_gate || {};
  const s1 = $("stage1Body");
  if (g.available === false) {
    s1.innerHTML = `<p class="muted">${g.note || "Leaf gate skipped."}</p>`;
  } else {
    const ok = g.is_leaf;
    const leafTxt = isBn() ? (ok ? "এটি একটি পাতা" : "এটি পাতা নয়") : (ok ? "a LEAF" : "NOT a leaf");
    const probTxt = isBn() ? "পাতার সম্ভাবনা" : "Leaf probability";
    s1.innerHTML = `
      <p>${isBn() ? "এই ছবিটি" : "This image is"} <span class="${ok ? "leaf-yes" : "leaf-no"}">${leafTxt}</span>
      <span class="muted">(model: ${g.model})</span></p>
      <div class="conf">${probTxt}: <strong>${pct(g.leaf_probability)}</strong></div>
      <div class="bar"><i style="width:${g.leaf_probability * 100}%"></i></div>`;
  }

  const crop = data.stage2_leaf_type;
  const cropCard = $("cropCard");
  if (cropCard) {
    if (!g.is_leaf || !crop) {
      cropCard.classList.add("hidden");
    } else {
      cropCard.classList.remove("hidden");
      const cropBody = $("cropBody");
      if (cropBody) {
        if (crop.available === false) {
          cropBody.innerHTML = `<p class="muted">${crop.note || ""}</p>`;
        } else {
          cropBody.innerHTML = `<p>${isBn() ? "ফসল" : "Crop"}: <strong>${crop.crop || ""}</strong></p>
            <div class="conf">${isBn() ? "আত্মবিশ্বাস" : "Confidence"}: <strong>${pct(crop.confidence || 0)}</strong></div>
            <div class="bar"><i style="width:${(crop.confidence || 0) * 100}%"></i></div>`;
        }
      }
    }
  }

  const disease = data.stage3_disease || data.stage2_disease;
  const bestCard = $("bestCard"), modelsCard = $("modelsCard"), adviceCard = $("adviceCard");
  if (!disease) {
    [bestCard, modelsCard, adviceCard].forEach((c) => c && c.classList.add("hidden"));
    $("resultActions").classList.add("hidden");
    if (data.message) s1.innerHTML += `<p class="muted" style="margin-top:10px">${data.message}</p>`;
    return;
  }

  const b = disease.best_answer;
  lastDisease = b.prediction;
  bestCard.classList.remove("hidden");
  const confLabel = isBn() ? "আত্মবিশ্বাস" : "Confidence";
  const lowConf = isBn() ? "কম আত্মবিশ্বাস" : "low confidence";
  const confident = isBn() ? "নিশ্চিত" : "confident";
  $("bestBody").innerHTML = `
    <div class="verdict">
      <span class="plant">${b.plant}</span>
      <span class="cond ${b.is_healthy ? "healthy" : "disease"}">${b.condition}</span>
      ${b.uncertain ? `<span class="badge warn">${lowConf}</span>` : `<span class="badge ok">${confident}</span>`}
    </div>
    <div class="conf">${confLabel}: <strong>${pct(b.confidence)}</strong></div>
    <div class="bar"><i style="width:${b.confidence * 100}%"></i></div>
    <div class="meta-row"><span>${b.method}</span><span>${b.agreement}</span></div>`;

  if (b.advice) {
    adviceCard.classList.remove("hidden");
    const a = b.advice;
    $("adviceBody").innerHTML = `
      <div class="verdict">
        <span style="font-size:18px;font-weight:700">${a.title}</span>
        <span class="sev ${a.severity}">${a.severity}</span>
      </div>
      <p class="muted">${a.summary}</p>
      <div class="advice-grid">
        <div><h4>&#128269; ${t("symptoms")}</h4><ul>${(a.symptoms||[]).map(x=>`<li>${x}</li>`).join("")}</ul></div>
        <div><h4>&#128138; ${t("treatment")}</h4><ul>${(a.treatment||[]).map(x=>`<li>${x}</li>`).join("")}</ul></div>
        <div><h4>&#128737; ${t("prevention")}</h4><ul>${(a.prevention||[]).map(x=>`<li>${x}</li>`).join("")}</ul></div>
        <div><h4>&#129658; ${t("need_help")}</h4><ul>
          <li>${isBn() ? "নিচের ডানে সহকারীকে জিজ্ঞাসা করুন।" : "Ask the assistant (bottom-right) for more."}</li>
          <li>${isBn() ? "কৃষি হেল্পলাইন:" : "Krishi hotline:"} <a href="tel:16123">16123</a></li>
        </ul></div>
      </div>`;
    pushBot(isBn() ? `${a.title} শনাক্ত হয়েছে।` : `Detected ${a.title}.`);
  } else {
    adviceCard.classList.add("hidden");
  }

  modelsCard.classList.remove("hidden");
  $("resultActions").classList.remove("hidden");
  const confWord = isBn() ? "আত্মবিশ্বাস" : "confidence";
  $("modelsBody").innerHTML = disease.models.map((m) => `
    <div class="model-tile">
      <h3>${m.model}</h3>
      <div class="pred">${m.plant}</div>
      <div class="sub ${m.is_healthy ? "leaf-yes" : ""}">${m.condition}</div>
      <div class="conf">${pct(m.confidence)} ${confWord}</div>
      <div class="bar"><i style="width:${m.confidence * 100}%"></i></div>
      <div class="top3">${m.top3.map((x)=>`<div><span>${x.plant} - ${x.condition}</span><span>${pct(x.confidence)}</span></div>`).join("")}</div>
    </div>`).join("");

  if (window.agroscanShowPane) {
    window.agroscanShowPane("diagnose", { focusResults: true });
  } else {
    $("results").scrollIntoView({ behavior: "smooth" });
  }
}

function setupChat() {
  const chatLog = $("chatLog");
  $("chatToggle").addEventListener("click", () => {
    $("chatPanel").classList.toggle("hidden");
    if (!chatLog.dataset.init) { chatLog.dataset.init = "1"; sendChat(""); }
  });
  $("chatClose").addEventListener("click", () => $("chatPanel").classList.add("hidden"));

  $("chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const txt = $("chatText").value.trim();
    if (!txt) return;
    $("chatText").value = "";
    sendChat(txt);
  });
}

function pushMsg(text, who) {
  const d = document.createElement("div");
  d.className = `msg ${who}`;
  d.textContent = text;
  $("chatLog").appendChild(d);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}
const pushBot = (txt) => pushMsg(txt, "bot");

function renderChips(items) {
  $("chatChips").innerHTML = (items || []).map((s) => `<button type="button" class="chip">${s}</button>`).join("");
  $("chatChips").querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => sendChat(c.textContent)));
}

async function sendChat(message) {
  if (message) pushMsg(message, "user");
  try {
    const r = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context_disease: lastDisease }),
    });
    const d = await r.json();
    pushBot(d.reply);
    renderChips(d.suggestions);
  } catch {
    pushBot(isBn() ? "সহকারী সেবায় যোগাযোগ করা যায়নি।" : "Sorry, I couldn't reach the assistant service.");
  }
}

function setupGoogle() {
  function decodeJwt(token) {
    try { return JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); }
    catch { return {}; }
  }
  function showUser(p) {
    $("googleSignin").classList.add("hidden");
    $("userChip").classList.remove("hidden");
    $("userPic").src = p.picture || "";
    $("userName").textContent = p.name || p.email || "Signed in";
  }
  function onGoogleCredential(resp) {
    showUser(decodeJwt(resp.credential));
    if (cfg.VERIFY_ON_SERVER && cfg.GOOGLE_CLIENT_ID) {
      fetch(`${API}/api/auth/google`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: resp.credential, client_id: cfg.GOOGLE_CLIENT_ID }),
      }).catch(() => {});
    }
  }
  $("signOut").addEventListener("click", () => {
    $("userChip").classList.add("hidden");
    $("googleSignin").classList.remove("hidden");
    if (window.google) google.accounts.id.disableAutoSelect();
  });

  function initGoogle(attempt = 0) {
    if (!cfg.GOOGLE_CLIENT_ID) {
      $("googleSignin").innerHTML = `<button type="button" id="googleFallback">${t("signin_google")}</button>`;
      $("googleFallback").addEventListener("click", () =>
        alert("Add your OAuth Client ID to web/config.js (GOOGLE_CLIENT_ID)."));
      return;
    }
    if (!window.google || !google.accounts) {
      if (attempt < 20) return setTimeout(() => initGoogle(attempt + 1), 250);
      return;
    }
    google.accounts.id.initialize({ client_id: cfg.GOOGLE_CLIENT_ID, callback: onGoogleCredential });
    google.accounts.id.renderButton($("googleSignin"), { theme: "outline", size: "large", text: "signin_with" });
  }
  initGoogle();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}
