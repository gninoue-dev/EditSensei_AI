/*
 * Faux After Effects pour tester editsensei.jsx sans Adobe (Node.js).
 *   node ae-panel/tests/mock_ae.js plan.json clip1.mp4 clip2.mp4 … musique.wav
 * Reproduit le strict nécessaire du modèle objet d'AE (projet, compos, calques,
 * propriétés, images clés, expressions) et signale tout appel inconnu.
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const calls = { keys: 0, expressions: 0, effects: [], layers: 0 };

class Property {
  constructor(name, value) {
    this.name = name; this.matchName = name; this._value = value; this.keys = [];
    this.children = []; this.expression = ""; this.expressionEnabled = false;
  }
  get value() { return this._value; }
  get numKeys() { return this.keys.length; }
  get numProperties() { return this.children.length; }
  setValue(v) { this._value = v; }
  setValueAtTime(t, v) {
    if (typeof t !== "number" || isNaN(t)) throw new Error(`setValueAtTime(${t}) sur ${this.name}`);
    calls.keys++; this.keys.push([t, v]); this.keys.sort((a, b) => a[0] - b[0]);
  }
  keyTime(i) { return this.keys[i - 1][0]; }
  setTemporalEaseAtKey(i, a, b) { if (i < 1 || i > this.keys.length) throw new Error("ease hors limites"); }
  property(k) {
    if (typeof k === "number") {
      while (this.children.length < k) this.children.push(new Property(`${this.name}#${this.children.length + 1}`, 0));
      return this.children[k - 1];
    }
    let c = this.children.find((p) => p.matchName === k);
    if (!c) { c = new Property(k, defaultValue(k)); this.children.push(c); }
    return c;
  }
  addProperty(matchName) {
    if (/Effect Parade/.test(this.name)) calls.effects.push(matchName);
    const p = new Property(matchName, 0); this.children.push(p); return p;
  }
  set expr(v) { this.expression = v; }
}
function defaultValue(k) {
  if (/Scale|Position|Anchor/.test(k)) return [100, 100];
  if (/Text Document/.test(k)) return new TextDocument("");
  return 0;
}
class TextDocument { constructor(t) { this.text = t; } }

class Layer {
  constructor(comp, source, name) {
    calls.layers++;
    this.containingComp = comp; this.source = source; this.name = name || (source ? source.name : "Calque");
    this.inPoint = 0; this.outPoint = comp.duration; this.startTime = 0; this.stretch = 100;
    this.parent = null; this.label = 0; this.adjustmentLayer = false; this.nullLayer = false;
    this.hasVideo = source ? source.hasVideo !== false : true; this.hasAudio = source ? !!source.hasAudio : false;
    this.audioEnabled = this.hasAudio; this.blendingMode = 0; this.root = new Property("root");
  }
  property(k) {
    const p = this.root.property(k);
    if (k === "ADBE Transform Group" && !p._init) {
      p._init = true;
      ["ADBE Anchor Point", "ADBE Position", "ADBE Scale", "ADBE Rotate Z", "ADBE Opacity"].forEach((n) => p.property(n));
    }
    if (k === "ADBE Text Properties") p.property("ADBE Text Document")._value = new TextDocument(this.name);
    return p;
  }
}
class FootageItem {
  constructor(file, opts = {}) {
    this.file = new File(file); this.name = path.basename(file); this.id = Math.floor(Math.random() * 1e6);
    this.duration = opts.duration || 8; this.width = opts.width || 640; this.height = opts.height || 360;
    this.frameRate = 30; this.hasVideo = !/\.(wav|mp3)$/i.test(file); this.hasAudio = !this.hasVideo;
    this.mainSource = { isStill: false }; this.selected = false; this.parentFolder = null;
  }
}
class FolderItem { constructor(n) { this.name = n; } }
class CompItem {
  constructor(name, w, h, par, dur, fps) {
    Object.assign(this, { name, width: w, height: h, pixelAspect: par, duration: dur, frameRate: fps, id: 42, time: 0 });
    this._layers = [];
    const comp = this;
    this.layers = {
      add(item) { const l = new Layer(comp, item); comp._layers.unshift(l); return l; },
      addNull(d) { const l = new Layer(comp, null, "Null"); l.nullLayer = true; l.hasVideo = false; comp._layers.unshift(l); return l; },
      addSolid(c, n, w2, h2, p, d) { const l = new Layer(comp, { name: n, hasVideo: true }, n); comp._layers.unshift(l); return l; },
      addText(t) { const l = new Layer(comp, null, t); comp._layers.unshift(l); return l; },
    };
  }
  get numLayers() { return this._layers.length; }
  layer(i) { return this._layers[i - 1]; }
  openInViewer() {}
}
class File {
  constructor(p) { this.fsName = p; this.name = path.basename(p); }
  get exists() { return fs.existsSync(this.fsName); }
}
class ImportOptions { constructor(f) { this.file = f; } }
class Shape {}
class KeyframeEase { constructor(s, i) { this.speed = s; this.influence = i; } }

function makeProject(files) {
  const items = files.map((f) => new FootageItem(f));
  const project = {
    file: null, activeItem: null,
    get numItems() { return items.length; },
    item(i) { return items[i - 1]; },
    importFile(opts) { const it = new FootageItem(opts.file.fsName); items.push(it); return it; },
    items: {
      addComp(...a) { const c = new CompItem(...a); items.push(c); project.activeItem = c; return c; },
      addFolder(n) { const f = new FolderItem(n); items.push(f); return f; },
    },
  };
  return project;
}

const [, , planPath, ...files] = process.argv;
const ctx = {
  app: { project: makeProject(files), version: "24.0 (mock)", beginUndoGroup() {}, endUndoGroup() {} },
  CompItem, FootageItem, FolderItem, File, ImportOptions, Shape, KeyframeEase,
  BlendingMode: { ADD: 1, SCREEN: 2, NORMAL: 0 },
  ParagraphJustification: { CENTER_JUSTIFY: 1 },
  $: { writeln: () => {} },
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, "../jsx/editsensei.jsx"), "utf8"), ctx, { filename: "editsensei.jsx" });

const info = JSON.parse(ctx.es_projectInfo());
if (!info.ok) throw new Error("projectInfo : " + info.error);
const plan = fs.readFileSync(planPath, "utf8");
const res = JSON.parse(ctx.es_buildEdit(plan));
if (!res.ok) { console.error("ÉCHEC :", res.error); process.exit(1); }
const snap = JSON.parse(ctx.es_snapshot());
if (!snap.ok) throw new Error("snapshot : " + snap.error);
const comp = ctx.app.project.activeItem;
const expr = comp._layers.map((l) => l.property("ADBE Transform Group").property("ADBE Position").expression).filter(Boolean);
console.log(JSON.stringify({
  ok: true, items: info.data.items.length, comp: res.data.comp, layers: res.data.layers,
  keyframes: calls.keys, effects: calls.effects, shakeExpression: expr.length,
  snapshotLayers: snap.data.layers.length,
  firstLayers: comp._layers.slice(0, 6).map((l) => l.name),
  names: comp._layers.map((l) => l.name),
}, null, 1));
