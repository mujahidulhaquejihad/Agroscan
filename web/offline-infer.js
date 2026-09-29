/* On-device L1/L2/L3 (ONNX Runtime Web). Chat still uses the hosted API. */
(function () {
  var PACK_URL = "./offline-pack.json";
  var MODEL_DIR = "./models/";
  var pack = null;
  var sessions = {};
  var loadPromise = null;
  var ready = false;

  function isNative() {
    try {
      return !!(window.Capacitor && typeof window.Capacitor.isNativePlatform === "function"
        && window.Capacitor.isNativePlatform());
    } catch (e) {
      return false;
    }
  }

  function softmax(logits) {
    var m = -Infinity;
    var i;
    for (i = 0; i < logits.length; i++) if (logits[i] > m) m = logits[i];
    var ex = [];
    var s = 0;
    for (i = 0; i < logits.length; i++) {
      var v = Math.exp(logits[i] - m);
      ex.push(v);
      s += v;
    }
    for (i = 0; i < ex.length; i++) ex[i] /= s || 1;
    return ex;
  }

  function argmax(arr) {
    var i;
    var bi = 0;
    for (i = 1; i < arr.length; i++) if (arr[i] > arr[bi]) bi = i;
    return bi;
  }

  function topk(probs, names, k) {
    var idx = [];
    var i;
    for (i = 0; i < probs.length; i++) idx.push(i);
    idx.sort(function (a, b) { return probs[b] - probs[a]; });
    var out = [];
    for (i = 0; i < Math.min(k, idx.length); i++) {
      out.push({ i: idx[i], name: names[idx[i]], confidence: round4(probs[idx[i]]) });
    }
    return out;
  }

  function round4(x) { return Math.round(Number(x) * 10000) / 10000; }

  function isOtherCrop(crop) {
    var s = String(crop || "").trim().toLowerCase();
    return s === "other" || s === "unknown" || s === "none" || s === "n/a";
  }

  function cropFromClass(name) {
    var crop = String(name || "").split("___")[0];
    crop = crop.replace("_(maize)", "").replace("(maize)", "");
    crop = crop.replace("_(including_sour)", "").replace(",_bell", "");
    var low = crop.toLowerCase().replace(/_/g, " ").trim();
    if (low.indexOf("corn") === 0) return "Corn";
    if (low.indexOf("pepper") === 0) return "Pepper";
    if (low.indexOf("cherry") === 0) return "Cherry";
    if (low.indexOf("amaranth") !== -1) return "Red Amaranth";
    return crop.replace(/_/g, " ").trim() || name;
  }

  function pretty(className) {
    var plant;
    var cond;
    if (className.indexOf("___") >= 0) {
      var parts = className.split("___");
      plant = parts[0];
      cond = parts.slice(1).join("___");
    } else if (className.indexOf("_") >= 0) {
      plant = className.split("_")[0];
      cond = className.slice(plant.length + 1);
    } else {
      plant = className;
      cond = "";
    }
    plant = plant.replace(/_/g, " ").trim();
    var condClean = cond.replace(/_/g, " ").trim();
    if (condClean.toLowerCase().indexOf("variety ") === 0) {
      return { plant: plant, condition: condClean, is_healthy: false };
    }
    var healthy = condClean.toLowerCase() === "healthy" || condClean.toLowerCase() === "normal";
    return {
      plant: plant,
      condition: healthy ? "Healthy" : condClean,
      is_healthy: healthy,
    };
  }

  function ensureOther(top3, otherLabel) {
    var out = (top3 || []).map(function (x) { return { crop: x.crop, confidence: x.confidence }; });
    var i;
    for (i = 0; i < out.length; i++) if (isOtherCrop(out[i].crop)) return out;
    out.push({ crop: otherLabel || "Other", confidence: 0 });
    return out;
  }

  function decorateCrop(stage, packCfg) {
    stage = stage || {};
    var top3 = stage.top3 || [];
    if (!top3.length && stage.crop) {
      top3 = [{ crop: stage.crop, confidence: stage.confidence || 0 }];
    }
    stage.top3 = ensureOther(top3, packCfg.other_label);
    var conf = Number(stage.confidence) || 0;
    if (stage.available && !isOtherCrop(stage.crop) && conf < packCfg.crop_other) {
      stage.guess = stage.crop;
      stage.crop = packCfg.other_label;
      stage.is_other = true;
    } else {
      stage.is_other = isOtherCrop(stage.crop);
    }
    return stage;
  }

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = function () {
        URL.revokeObjectURL(url);
        reject(new Error("image"));
      };
      img.src = url;
    });
  }

  function preprocess(img, inputSize, mean, std) {
    var resize = Math.round(inputSize * 1.15);
    var w = img.naturalWidth || img.width;
    var h = img.naturalHeight || img.height;
    var nw;
    var nh;
    if (w < h) {
      nw = resize;
      nh = Math.round(h * resize / w);
    } else {
      nh = resize;
      nw = Math.round(w * resize / h);
    }
    var tmp = document.createElement("canvas");
    tmp.width = nw;
    tmp.height = nh;
    tmp.getContext("2d").drawImage(img, 0, 0, nw, nh);
    var sx = Math.max(0, Math.floor((nw - inputSize) / 2));
    var sy = Math.max(0, Math.floor((nh - inputSize) / 2));
    var crop = document.createElement("canvas");
    crop.width = inputSize;
    crop.height = inputSize;
    crop.getContext("2d").drawImage(tmp, sx, sy, inputSize, inputSize, 0, 0, inputSize, inputSize);
    var pix = crop.getContext("2d").getImageData(0, 0, inputSize, inputSize).data;
    var plane = inputSize * inputSize;
    var arr = new Float32Array(3 * plane);
    var i;
    for (i = 0; i < plane; i++) {
      arr[i] = (pix[i * 4] / 255 - mean[0]) / std[0];
      arr[plane + i] = (pix[i * 4 + 1] / 255 - mean[1]) / std[1];
      arr[2 * plane + i] = (pix[i * 4 + 2] / 255 - mean[2]) / std[2];
    }
    return arr;
  }

  function tensor(float32, size) {
    return new ort.Tensor("float32", float32, [1, 3, size, size]);
  }

  async function runModel(key, img) {
    var spec = pack.models[key];
    var sess = sessions[key];
    var t = tensor(preprocess(img, spec.size, pack.mean, pack.std), spec.size);
    var out = await sess.run({ input: t });
    var name = sess.outputNames[0];
    return softmax(Array.from(out[name].data));
  }

  async function ensureLoaded() {
    if (ready) return pack;
    if (loadPromise) return loadPromise;
    loadPromise = (async function () {
      var res = await fetch(PACK_URL);
      if (!res.ok) throw new Error("offline-pack.json missing");
      pack = await res.json();
      if (typeof ort === "undefined") throw new Error("onnxruntime missing");
      if (ort.env && ort.env.wasm) {
        ort.env.wasm.wasmPaths = "./ort/";
        ort.env.wasm.numThreads = 1;
      }
      var keys = ["leaf_gate", "leaf_type", "disease"];
      var i;
      for (i = 0; i < keys.length; i++) {
        var spec = pack.models[keys[i]];
        sessions[keys[i]] = await ort.InferenceSession.create(MODEL_DIR + spec.file, {
          executionProviders: ["wasm"],
        });
      }
      ready = true;
      return pack;
    })();
    try {
      return await loadPromise;
    } catch (e) {
      loadPromise = null;
      throw e;
    }
  }

  function adviceFor(className, lang) {
    var row = (pack.advice || {})[className];
    if (!row) return null;
    var useBn = String(lang || "bn").indexOf("bn") === 0;
    return (useBn ? row.bn : row.en) || row.en || row.bn || null;
  }

  function otherMessage(lang) {
    if (String(lang || "").indexOf("en") === 0) {
      return "This plant is not in AgroScan's trained crops, so disease diagnosis was skipped. Pick a listed crop if this is a known plant, or use Other if it is not.";
    }
    return "এই গাছ AgroScan-এর প্রশিক্ষিত ফসলের তালিকায় নেই, তাই রোগ বিশ্লেষণ করা হয়নি। তালিকার কোনো ফসল হলে সেটি বেছে নিন, না হলে অন্যান্য চাপুন।";
  }

  async function predict(file, opts) {
    opts = opts || {};
    var lang = opts.lang || "bn";
    var cropOverride = opts.crop || null;
    await ensureLoaded();
    var img = await loadImage(file);
    var leafNames = pack.models.leaf_gate.classes;
    var leafP = await runModel("leaf_gate", img);
    var namesLow = leafNames.map(function (n) { return String(n).trim().toLowerCase(); });
    var leafIdx = namesLow.indexOf("leaf");
    if (leafIdx < 0) leafIdx = argmax(leafP);
    var leafProb = leafP[leafIdx];
    var isLeaf = leafProb >= pack.leaf_accept;
    var result = {
      source: "on_device",
      stage1_leaf_gate: {
        available: true,
        model: "MobileNetV3",
        is_leaf: isLeaf,
        leaf_probability: round4(leafProb),
        label: isLeaf ? "leaf" : "non_leaf",
      },
      stage2_leaf_type: null,
      stage3_disease: null,
      stage2_disease: null,
    };
    if (!isLeaf) {
      result.message = lang.indexOf("en") === 0
        ? "This photo does not look like a leaf, so disease analysis was skipped."
        : "এই ছবিটি পাতা বলে মনে হয় না, তাই রোগ বিশ্লেষণ করা হয়নি।";
      return result;
    }

    var cropNames = pack.models.leaf_type.classes;
    var cropP = await runModel("leaf_type", img);
    var cropTop = topk(cropP, cropNames, 3);
    var crop = decorateCrop({
      available: true,
      source: "leaf_type",
      model: "EfficientNet-B3",
      crop: cropNames[argmax(cropP)],
      confidence: round4(Math.max.apply(null, cropP)),
      top3: cropTop.map(function (t) { return { crop: t.name, confidence: t.confidence }; }),
    }, pack);

    if (cropOverride) {
      crop.crop = cropOverride;
      crop.is_other = isOtherCrop(cropOverride);
      crop.user_selected = true;
      crop.needs_user_pick = false;
      crop.top3 = ensureOther(crop.top3, pack.other_label);
    } else if (crop.available && (crop.confidence < pack.crop_confirm || crop.is_other)) {
      crop.needs_user_pick = true;
    } else {
      crop.needs_user_pick = false;
    }
    result.stage2_leaf_type = crop;

    if (crop.needs_user_pick && !cropOverride) {
      result.message = lang.indexOf("en") === 0
        ? "Crop confidence is below 90%. Pick the correct crop below, or Other if this plant is not in the list."
        : "ফসল চেনার আত্মবিশ্বাস ৯০% এর নিচে। নিচ থেকে সঠিক ফসল বেছে নিন, অথবা তালিকায় না থাকলে অন্যান্য চাপুন।";
      return result;
    }
    var chosen = cropOverride || crop.crop;
    if (isOtherCrop(chosen)) {
      result.message = otherMessage(lang);
      return result;
    }

    var disNames = pack.models.disease.classes;
    var disP = await runModel("disease", img);
    var masked = new Array(disP.length);
    var i;
    var hits = [];
    for (i = 0; i < disNames.length; i++) {
      if (cropFromClass(disNames[i]).toLowerCase() === String(chosen).toLowerCase()) hits.push(i);
    }
    if (!hits.length) {
      for (i = 0; i < disP.length; i++) masked[i] = disP[i];
    } else {
      var sum = 0;
      for (i = 0; i < hits.length; i++) sum += disP[hits[i]];
      for (i = 0; i < disP.length; i++) masked[i] = 0;
      for (i = 0; i < hits.length; i++) masked[hits[i]] = disP[hits[i]] / (sum || 1);
    }
    var bestI = argmax(masked);
    var info = pretty(disNames[bestI]);
    var conf = masked[bestI];
    var top = topk(masked, disNames, 3).filter(function (t) { return t.confidence > 0; });
    if (!top.length) top = [{ name: disNames[bestI], confidence: round4(conf) }];
    var top3 = top.map(function (t) {
      var p = pretty(t.name);
      return { label: t.name, plant: p.plant, condition: p.condition, is_healthy: p.is_healthy, confidence: t.confidence };
    });
    var modelRow = {
      model: "EfficientNet-B3",
      prediction: disNames[bestI],
      plant: info.plant,
      condition: info.condition,
      is_healthy: info.is_healthy,
      confidence: round4(conf),
      is_highest: true,
      top3: top3,
    };
    var best = {
      prediction: disNames[bestI],
      plant: info.plant,
      condition: info.condition,
      is_healthy: info.is_healthy,
      confidence: round4(conf),
      winning_model: "EfficientNet-B3",
      selection: "highest_confidence",
      method: lang.indexOf("en") === 0
        ? ("On-device — EfficientNet-B3 (" + (Math.round(conf * 1000) / 10) + "%)")
        : ("অফলাইন — EfficientNet-B3 (" + (Math.round(conf * 1000) / 10) + "%)"),
      agreement: "",
      uncertain: conf < pack.uncertain,
      low_confidence: conf < pack.low_confidence,
      recommendation: conf < pack.low_confidence
        ? (lang.indexOf("en") === 0
          ? "Confidence is below 80%. Take a clearer close-up of one leaf, or call Krishi 16123."
          : "আত্মবিশ্বাস ৮০% এর নিচে। পরিষ্কার, কাছ থেকে একটি পাতার ছবি তুলুন, অথবা কৃষি ১৬১২৩-এ কল করুন।")
        : null,
      advice: adviceFor(disNames[bestI], lang),
      top3: top3,
    };
    result.stage3_disease = { models: [modelRow], best_answer: best, selection: "highest_confidence" };
    result.stage2_disease = result.stage3_disease;
    return result;
  }

  function chatOffline(message, lang, contextDisease) {
    var useBn = String(lang || "bn").indexOf("bn") === 0;
    var msg = String(message || "").trim();
    var cls = contextDisease || null;
    if (!cls && pack && pack.advice && msg) {
      var low = msg.toLowerCase();
      var bestName = null;
      var bestScore = 0;
      Object.keys(pack.advice).forEach(function (name) {
        var bits = name.toLowerCase().replace(/_/g, " ").split("___");
        var score = 0;
        bits.forEach(function (b) {
          if (b && low.indexOf(b) >= 0) score += b.length;
        });
        if (score > bestScore) {
          bestScore = score;
          bestName = name;
        }
      });
      if (bestScore >= 5) cls = bestName;
    }
    if (cls && pack && pack.advice[cls]) {
      var a = adviceFor(cls, lang) || {};
      var lines = [];
      if (a.title) lines.push(a.title);
      if (a.description) lines.push(a.description);
      if (a.treatment && a.treatment.length) lines.push((useBn ? "চিকিৎসা: " : "Treatment: ") + a.treatment.slice(0, 3).join("; "));
      var reply = lines.join("\n") || cls;
      if (useBn) reply += "\n\nGemini চ্যাটের জন্য ইন্টারনেট লাগবে।";
      else reply += "\n\nTurn on internet for Gemini chat.";
      return { reply: reply, source: "offline-pack", suggestions: [] };
    }
    return {
      reply: useBn
        ? "চ্যাটের জন্য ইন্টারনেট লাগবে (Gemini)। পাতার ছবি স্ক্যান অফলাইনেও চলে।"
        : "Chat needs internet (Gemini). Leaf scan still works offline on this phone.",
      source: "offline",
      suggestions: [],
    };
  }

  window.AgroScanOffline = {
    isNative: isNative,
    available: function () { return ready; },
    init: function () {
      return ensureLoaded().then(function () { return true; }).catch(function () { return false; });
    },
    predict: predict,
    chat: function (message, lang, contextDisease) {
      return ensureLoaded().then(function () {
        return chatOffline(message, lang, contextDisease);
      }).catch(function () {
        return chatOffline(message, lang, contextDisease);
      });
    },
    adviceFor: function (cls, lang) {
      return pack ? adviceFor(cls, lang) : null;
    },
  };
})();
