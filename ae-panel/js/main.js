/*
 * EditSensei AI — logique du panneau.
 * Panneau (ce fichier)  ⇄  cerveau Python (http://127.0.0.1:8765)  ⇄  After Effects (jsx/editsensei.jsx)
 */
(function () {
  "use strict";

  var BRAIN = "http://127.0.0.1:8765";
  var cs = new CSInterface();
  var session = null;
  var watching = false;
  var watchTimer = null;
  var busy = false;
  var brainProcess = null;
  var aiLabel = "mode local";
  var needsAI = false;

  var $ = function (id) { return document.getElementById(id); };
  var chat = $("chat"), input = $("input"), chips = $("chips");

  // ── affichage ────────────────────────────────────────────
  function add(kind, text, tag) {
    var el = document.createElement("div");
    el.className = "msg " + kind;
    if (tag) {
      var t = document.createElement("span");
      t.className = "tag";
      t.textContent = tag;
      el.appendChild(t);
    }
    el.appendChild(document.createTextNode(text));
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  function typing() {
    var el = document.createElement("div");
    el.className = "msg ai typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  function setChips(list) {
    chips.innerHTML = "";
    (list || []).forEach(function (label) {
      var b = document.createElement("button");
      b.className = "chip";
      b.type = "button";
      b.textContent = label;
      b.onclick = function () { send(label); };
      chips.appendChild(b);
    });
  }

  function status(state, text) {
    $("dot").className = "dot " + state;
    $("statusText").textContent = text;
  }

  function setBusy(v) {
    busy = v;
    ["btnBuild", "btnLearn", "btnLike", "send"].forEach(function (id) { $(id).disabled = v; });
    if (v) { status("busy", "Je réfléchis…"); } else { status("on", "Prêt · " + aiLabel); }
  }

  // ── After Effects ────────────────────────────────────────
  function ae(script) {
    return new Promise(function (resolve, reject) {
      cs.evalScript(script, function (res) {
        if (res === "EvalScript error.") { return reject(new Error("Erreur ExtendScript")); }
        try {
          var r = JSON.parse(res);
          if (r.ok) { resolve(r.data); } else { reject(new Error(r.error)); }
        } catch (e) {
          reject(new Error("Réponse d'After Effects illisible : " + res));
        }
      });
    });
  }

  // ── cerveau ──────────────────────────────────────────────
  function api(path, body) {
    return fetch(BRAIN + path, body === undefined ? {} : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || j.ok === false) { throw new Error(j.error || ("HTTP " + r.status)); }
        return j;
      });
    });
  }

  function loadConfig() {
    try {
      var fs = require("fs"), path = require("path");
      var file = path.join(cs.getSystemPath(SystemPath.EXTENSION), "config.json");
      return JSON.parse(fs.readFileSync(file, "utf8"));
    } catch (e) { return null; }
  }

  /* Démarre le cerveau automatiquement (Node.js du panneau) s'il ne tourne pas déjà. */
  function startBrain() {
    var cfg = loadConfig();
    if (!cfg || typeof require !== "function") { return false; }
    try {
      var spawn = require("child_process").spawn;
      brainProcess = spawn(cfg.python, ["-m", "editsensei"], {
        cwd: cfg.brainDir, detached: false, windowsHide: true,
        env: Object.assign({}, process.env, { PYTHONIOENCODING: "utf-8" })
      });
      brainProcess.on("error", function () { brainProcess = null; });
      return true;
    } catch (e) { return false; }
  }

  function connect(attempt) {
    attempt = attempt || 0;
    return api("/health").then(function (h) {
      aiLabel = h.ai_label || "mode local";
      status("on", "Prêt · " + aiLabel);
      if (attempt === 0 && !h.ai) { needsAI = true; }
      return api("/styles");
    }).then(function (s) {
      var sel = $("styleSelect");
      sel.innerHTML = "";
      s.styles.forEach(function (st) {
        var o = document.createElement("option");
        o.value = st.name;
        o.textContent = (st.source === "preset" ? "" : "✦ ") + st.name;
        sel.appendChild(o);
      });
      if (attempt >= 0 && !chat.childElementCount) {
        add("ai", "Salut ! Je suis EditSensei 🎬\nImporte tes clips et ta musique, puis dis-moi quel edit tu veux. " +
          "Je coupe sur les beats, je place les impacts sur les drops et je construis la compo pour toi.", "編 EDITSENSEI");
        setChips(["Fais un edit anime de 30 s", "Edit smooth en vertical", "Quels styles tu connais ?"]);
        if (needsAI) {
          add("sys", "💡 Branche ton compte IA (Claude, Gemini, ChatGPT, DeepSeek ou Copilot) avec ⚙️ : c'est lui qui pilotera le montage.");
        }
      }
    }).catch(function () {
      if (attempt === 0 && startBrain()) {
        status("busy", "Démarrage du cerveau…");
      }
      if (attempt < 25) {
        setTimeout(function () { connect(attempt + 1); }, 1200);
      } else {
        status("off", "Cerveau introuvable");
        add("err", "Je n'arrive pas à joindre mon cerveau 😵\nLance « scripts/start_brain » (Windows : start_brain.bat) puis rouvre ce panneau.");
      }
    });
  }

  // ── conversation ─────────────────────────────────────────
  function send(text) {
    text = (text || input.value).trim();
    if (!text || busy) { return; }
    input.value = "";
    add("me", text);
    setChips([]);
    setBusy(true);
    var wait = typing();
    var project;
    ae("es_projectInfo()").then(function (p) {
      project = p;
      return api("/chat", { message: text, session: session, project: p });
    }).then(function (r) {
      session = r.session;
      wait.remove();
      add("ai", r.reply, r.action === "build" ? "🎬 MONTAGE" : (r.action === "learned" ? "📚 APPRIS" : null));
      setChips(r.suggestions);
      if (r.action === "learned") { connect(-1); }
      if (r.action === "build" && r.plan) {
        var building = add("sys", "Construction de la compo dans After Effects…");
        // le plan est passé à ExtendScript comme une chaîne JSON échappée
        return ae("es_buildEdit(" + JSON.stringify(JSON.stringify(r.plan)) + ")").then(function (res) {
          building.textContent = "✅ Compo « " + res.comp + " » créée (" + res.layers + " calques). Ctrl+Z pour tout annuler.";
        });
      }
    }).catch(function (e) {
      wait.remove();
      add("err", "Oups : " + e.message);
    }).then(function () { setBusy(false); });
  }

  $("form").addEventListener("submit", function (e) { e.preventDefault(); send(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });

  $("btnBuild").onclick = function () { send("Monte un edit en style " + $("styleSelect").value); };
  $("btnLike").onclick = function () { send("j'aime"); };
  $("btnLearn").onclick = function () {
    send("Apprends le style de la vidéo sélectionnée");
  };

  // ── mode apprenti : on regarde la compo active toutes les 4 s ──
  $("btnWatch").onclick = function () {
    watching = !watching;
    $("btnWatch").classList.toggle("on", watching);
    if (watching) {
      add("sys", "👀 Mode apprenti activé : monte normalement, j'observe tes coupes et tes effets pour apprendre ton style.");
      watchTimer = setInterval(observe, 4000);
      observe();
    } else {
      clearInterval(watchTimer);
      add("sys", "Mode apprenti désactivé.");
    }
  };

  function observe() {
    ae("es_snapshot()").then(function (snap) {
      if (!snap) { return null; }
      return api("/learn/observe", { snapshot: snap });
    }).then(function (r) {
      if (r && r.learned && r.reply) { add("ai", r.reply, "📚 APPRIS"); }
    }).catch(function () { /* silencieux : on réessaie au prochain tour */ });
  }

  // ── réglages : comptes IA ────────────────────────────────
  var settings = $("settings");
  var voiceCfg = { auto_send: true, language: "fr" };

  $("btnSettings").onclick = function () {
    settings.hidden = !settings.hidden;
    if (!settings.hidden) { loadAccounts(); }
  };
  $("btnCloseSettings").onclick = function () { settings.hidden = true; connect(-1); };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (text !== undefined) { e.textContent = text; }
    return e;
  }

  function openUrl(url) {
    try { cs.openURLInDefaultBrowser(url); } catch (e) { window.open(url); }
  }

  function loadAccounts() {
    return api("/accounts").then(function (st) {
      voiceCfg = st.voice || voiceCfg;
      $("voiceAutoSend").checked = voiceCfg.auto_send !== false;
      var box = $("providers");
      box.innerHTML = "";
      st.providers.forEach(function (p) { box.appendChild(providerCard(p, st.active === p.id)); });
      var local = document.querySelector('input[name=provider][value=local]');
      local.checked = !st.active;
      local.onchange = function () { save({ provider: "local" }); };
      return api("/health");
    }).then(function (h) {
      $("voiceInfo").textContent = h.voice.length
        ? "Transcription : " + h.voice.map(function (v) {
            return { local: "Whisper local (hors ligne)", openai: "OpenAI", gemini: "Gemini" }[v];
          }).join(", ") + "."
        : "Aucun moteur de transcription : relance le script d'installation (voix locale gratuite, hors ligne) ou ajoute une clé ChatGPT/Gemini.";
    }).catch(function (e) { $("providers").textContent = "Erreur : " + e.message; });
  }

  function save(body) {
    return api("/accounts/save", body).then(function (st) {
      aiLabel = st.label;
      status("on", "Prêt · " + aiLabel);
      return loadAccounts();
    });
  }

  function providerCard(p, isActive) {
    var card = el("div", "prov" + (isActive ? " active" : ""));
    var top = el("label", "prov-top");
    var radio = el("input");
    radio.type = "radio"; radio.name = "provider"; radio.value = p.id; radio.checked = isActive;
    top.appendChild(radio);
    top.appendChild(el("span", "name", p.label));
    top.appendChild(el("span", "badge" + (p.ready ? " ok" : ""), p.ready ? "prêt" : "à connecter"));
    card.appendChild(top);

    var body = el("div", "prov-body");
    body.hidden = !isActive;
    var msg = el("div", "prov-msg", p.note);

    var modes = el("div", "modes");
    var mode = p.mode;
    function modeRadio(value, label, disabled) {
      var l = el("label"); var r = el("input");
      r.type = "radio"; r.name = "mode-" + p.id; r.value = value; r.checked = (mode === value); r.disabled = disabled;
      r.onchange = function () { mode = value; refresh(); save({ provider: p.id, mode: value, activate: true }); };
      l.appendChild(r); l.appendChild(document.createTextNode(" " + label));
      return l;
    }
    if (p.has_cli) { modes.appendChild(modeRadio("account", "Mon compte")); }
    modes.appendChild(modeRadio("key", "Clé API"));
    body.appendChild(modes);

    var accountBox = el("div");
    accountBox.appendChild(el("div", "", p.cli_found
      ? "✅ Outil " + p.label + " détecté sur ce PC."
      : "Outil non installé. Installe Node.js puis, dans un terminal : " + p.install));
    var keyBox = el("div");
    var key = el("input"); key.type = "password"; key.placeholder = p.key_set ? "Clé enregistrée " + p.key_hint : "Colle ta clé ici";
    var model = el("input"); model.type = "text"; model.value = p.model; model.title = "Modèle utilisé avec la clé";
    var link = el("a", "", "Obtenir une clé ↗"); link.href = "#";
    link.onclick = function (e) { e.preventDefault(); openUrl(p.key_url); };
    keyBox.appendChild(key); keyBox.appendChild(model); keyBox.appendChild(link);
    body.appendChild(accountBox); body.appendChild(keyBox);

    var btns = el("div", "btns");
    var bLogin = el("button", "", "🔑 Se connecter");
    var bSave = el("button", "", "💾 Enregistrer");
    var bTest = el("button", "", "🧪 Tester");
    [bLogin, bSave, bTest].forEach(function (b) { b.type = "button"; btns.appendChild(b); });
    body.appendChild(btns);
    body.appendChild(msg);
    card.appendChild(body);

    function refresh() {
      accountBox.hidden = mode !== "account";
      keyBox.hidden = mode !== "key";
      bLogin.hidden = mode !== "account" || !p.cli_found;
      bSave.hidden = mode !== "key";
    }
    refresh();

    function say(text, kind) { msg.textContent = text; msg.className = "prov-msg " + (kind || ""); }

    radio.onchange = function () { save({ provider: p.id, mode: mode, activate: true }); };
    bLogin.onclick = function () {
      api("/accounts/login", { provider: p.id }).then(function (r) { say(r.reply); })
        .catch(function (e) { say(e.message, "err"); });
    };
    bSave.onclick = function () {
      save({ provider: p.id, mode: "key", key: key.value || null, model: model.value, activate: true })
        .catch(function (e) { say(e.message, "err"); });
    };
    bTest.onclick = function () {
      say("Test en cours… (jusqu'à 30 s en mode compte)");
      bTest.disabled = true;
      var pending = (mode === "key" && key.value)
        ? api("/accounts/save", { provider: p.id, mode: "key", key: key.value, model: model.value, activate: true })
        : Promise.resolve();
      pending.then(function () { return api("/accounts/test", { provider: p.id }); })
        .then(function (r) { say("✅ " + r.reply, "ok"); })
        .catch(function (e) { say("❌ " + e.message, "err"); })
        .then(function () { bTest.disabled = false; });
    };
    return card;
  }

  $("voiceAutoSend").onchange = function () {
    voiceCfg.auto_send = this.checked;
    api("/voice/settings", { auto_send: this.checked }).catch(function () {});
  };

  // ── 🎤 dictée : enregistrement, arrêt auto sur silence, transcription ──
  var recorder = null, recChunks = [], silenceTimer = null, audioCtx = null;

  function stopRecording() {
    if (recorder && recorder.state !== "inactive") { recorder.stop(); }
  }

  $("mic").onclick = function () {
    if (recorder && recorder.state === "recording") { stopRecording(); return; }
    if (busy) { return; }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      add("err", "Micro indisponible dans ce panneau (After Effects doit avoir l'autorisation d'utiliser le micro).");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      recChunks = [];
      var mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
      recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      recorder.ondataavailable = function (e) { if (e.data.size) { recChunks.push(e.data); } };
      recorder.onstop = function () {
        stream.getTracks().forEach(function (t) { t.stop(); });
        if (audioCtx) { audioCtx.close(); audioCtx = null; }
        clearInterval(silenceTimer);
        $("mic").classList.remove("rec");
        var blob = new Blob(recChunks, { type: recorder.mimeType || "audio/webm" });
        if (blob.size < 2000) { status("on", "Prêt · " + aiLabel); return; }
        transcribeBlob(blob);
      };
      recorder.start(250);
      $("mic").classList.add("rec");
      status("busy", "Je t'écoute… (re-clique 🎤 pour arrêter)");
      watchSilence(stream);
    }).catch(function (e) {
      add("err", "Accès au micro refusé : " + e.message +
        "\nmacOS : Réglages Système › Confidentialité › Micro › coche After Effects.");
    });
  };

  /* Arrêt automatique après 1,6 s de silence (une fois que tu as commencé à parler). */
  function watchSilence(stream) {
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var src = audioCtx.createMediaStreamSource(stream);
      var an = audioCtx.createAnalyser();
      an.fftSize = 1024;
      src.connect(an);
      var buf = new Uint8Array(an.fftSize), spoke = false, quietSince = Date.now(), started = Date.now();
      silenceTimer = setInterval(function () {
        an.getByteTimeDomainData(buf);
        var sum = 0;
        for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; sum += v * v; }
        var rms = Math.sqrt(sum / buf.length);
        if (rms > 0.04) { spoke = true; quietSince = Date.now(); }
        if ((spoke && Date.now() - quietSince > 1600) || Date.now() - started > 60000) { stopRecording(); }
      }, 100);
    } catch (e) { /* sans détection de silence : arrêt manuel */ }
  }

  function transcribeBlob(blob) {
    status("busy", "Transcription…");
    var reader = new FileReader();
    reader.onload = function () {
      var b64 = String(reader.result).split(",")[1];
      api("/transcribe", { audio: b64, mime: blob.type }).then(function (r) {
        status("on", "Prêt · " + aiLabel);
        var text = (r.text || "").trim();
        if (!text) { add("sys", "Je n'ai rien entendu 🤔"); return; }
        if (voiceCfg.auto_send !== false) { send(text); }
        else { input.value = (input.value ? input.value + " " : "") + text; input.focus(); }
      }).catch(function (e) {
        status("on", "Prêt · " + aiLabel);
        add("err", "Transcription impossible : " + e.message);
      });
    };
    reader.readAsDataURL(blob);
  }

  // le cerveau lancé par le panneau s'arrête avec lui
  window.addEventListener("unload", function () {
    if (brainProcess) { try { brainProcess.kill(); } catch (e) {} }
  });

  connect(0);
}());
