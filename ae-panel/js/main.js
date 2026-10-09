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
    if (v) { status("busy", "Je réfléchis…"); } else { status("on", "Prêt"); }
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
      status("on", "Prêt" + (h.claude ? " · Claude connecté" : " · mode local"));
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

  // le cerveau lancé par le panneau s'arrête avec lui
  window.addEventListener("unload", function () {
    if (brainProcess) { try { brainProcess.kill(); } catch (e) {} }
  });

  connect(0);
}());
