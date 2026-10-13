/*
 * EditSensei AI — côté After Effects (ExtendScript, ES3).
 *
 * Fonctions appelées par le panneau (js/main.js) via CSInterface.evalScript :
 *   es_projectInfo()            → JSON : compo active, éléments de métrage (chemins, durées, audio)
 *   es_buildEdit(planJson)      → construit une NOUVELLE composition à partir du plan du cerveau
 *   es_snapshot()               → JSON : état de la compo active (pour le mode apprenti)
 *
 * Tout passe par des matchNames (indépendants de la langue d'After Effects : FR, EN…).
 * Chaque construction est un seul bloc d'annulation : Ctrl+Z défait tout le montage.
 */

// ── JSON minimal (ExtendScript n'a pas JSON natif partout) ─────────────────
if (typeof JSON !== "object") { JSON = {}; }
(function () {
    function q(s) {
        return '"' + String(s).replace(/[\\"\u0000-\u001f]/g, function (c) {
            var m = { '"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t" };
            return m[c] || "\\u" + ("0000" + c.charCodeAt(0).toString(16)).slice(-4);
        }) + '"';
    }
    if (typeof JSON.stringify !== "function") {
        JSON.stringify = function enc(v) {
            if (v === null || v === undefined) { return "null"; }
            var t = typeof v;
            if (t === "number") { return isFinite(v) ? String(v) : "null"; }
            if (t === "boolean") { return String(v); }
            if (t === "string") { return q(v); }
            if (v instanceof Array) {
                var a = [];
                for (var i = 0; i < v.length; i++) { a.push(enc(v[i])); }
                return "[" + a.join(",") + "]";
            }
            var o = [];
            for (var k in v) { if (v.hasOwnProperty(k)) { o.push(q(k) + ":" + enc(v[k])); } }
            return "{" + o.join(",") + "}";
        };
    }
    if (typeof JSON.parse !== "function") {
        JSON.parse = function (s) { return eval("(" + s + ")"); };
    }
}());

var ES_AUDIO_EXT = /\.(mp3|wav|aif|aiff|m4a|aac|flac|ogg)$/i;
var ES_LABEL = 9; // couleur d'étiquette des calques créés (vert)

function es_ok(data) { return JSON.stringify({ ok: true, data: data }); }
function es_err(msg) { return JSON.stringify({ ok: false, error: String(msg) }); }

// ── Lecture du projet ─────────────────────────────────────────────────────

function es_projectInfo() {
    try {
        if (!app.project) { return es_err("Aucun projet ouvert."); }
        var items = [];
        for (var i = 1; i <= app.project.numItems; i++) {
            var it = app.project.item(i);
            if (!(it instanceof FootageItem) || !it.file) { continue; }
            var path = it.file.fsName;
            var isAudio = ES_AUDIO_EXT.test(path) || (it.hasAudio && !it.hasVideo);
            items.push({
                id: it.id, name: it.name, path: path,
                duration: it.duration, width: it.width, height: it.height,
                fps: it.frameRate, hasVideo: it.hasVideo, hasAudio: it.hasAudio,
                isAudio: isAudio, isStill: it.mainSource && it.mainSource.isStill,
                selected: it.selected
            });
        }
        var comp = app.project.activeItem;
        var active = null;
        if (comp && comp instanceof CompItem) {
            active = { id: comp.id, name: comp.name, width: comp.width, height: comp.height,
                       fps: comp.frameRate, duration: comp.duration, layers: comp.numLayers };
        }
        return es_ok({ items: items, activeComp: active, version: app.version, projectName: app.project.file ? app.project.file.name : "Sans titre" });
    } catch (e) {
        return es_err(e.toString());
    }
}

// ── Construction du montage ───────────────────────────────────────────────

function es_findItemByPath(path) {
    var norm = String(path).replace(/\\/g, "/").toLowerCase();
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FootageItem && it.file && it.file.fsName.replace(/\\/g, "/").toLowerCase() === norm) {
            return it;
        }
    }
    var f = new File(path);
    if (f.exists) {
        return app.project.importFile(new ImportOptions(f));
    }
    return null;
}

function es_folder(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FolderItem && it.name === name) { return it; }
    }
    return app.project.items.addFolder(name);
}

/* Enveloppe d'un effet : 0 → 1 en 15 % de la durée → 0 (même courbe que l'aperçu Python). */
function es_pulse(prop, t, dur, base, peak) {
    var a = t + dur * 0.15;
    var times = [Math.max(0, t - 0.001), a, t + dur];
    var vals = [base, peak, base];
    for (var i = 0; i < times.length; i++) {
        prop.setValueAtTime(times[i], vals[i]);
    }
}

function es_addEffect(layer, matchName) {
    try {
        return layer.property("ADBE Effect Parade").addProperty(matchName);
    } catch (e) {
        return null; // effet indisponible dans cette version : on continue sans
    }
}

function es_adjustment(comp, name, duration) {
    var l = comp.layers.addSolid([1, 1, 1], name, comp.width, comp.height, 1, duration);
    l.adjustmentLayer = true;
    l.label = ES_LABEL;
    return l;
}

function es_buildEdit(planJson) {
    var plan;
    try { plan = JSON.parse(planJson); } catch (e0) { return es_err("Plan illisible : " + e0); }

    app.beginUndoGroup("EditSensei : " + plan.name);
    try {
        var folder = es_folder("EditSensei");
        var compName = plan.name + " · " + plan.style;
        var comp = app.project.items.addComp(compName, plan.width, plan.height, 1, plan.duration, plan.fps);
        comp.parentFolder = folder;
        comp.bgColor = [0, 0, 0];

        // 1. Musique
        if (plan.music) {
            var mItem = es_findItemByPath(plan.music);
            if (mItem) {
                var ml = comp.layers.add(mItem);
                ml.startTime = -plan.music_start;
                ml.inPoint = 0;
                ml.outPoint = plan.duration;
                ml.name = "🎵 Musique";
                var lv = ml.property("ADBE Audio Group").property("ADBE Audio Levels");
                if (plan.fade_in > 0) { lv.setValueAtTime(0, [-48, -48]); lv.setValueAtTime(plan.fade_in, [0, 0]); }
                if (plan.fade_out > 0) { lv.setValueAtTime(plan.duration - plan.fade_out, [0, 0]); lv.setValueAtTime(plan.duration, [-48, -48]); }
            }
        }

        // 2. Plans (du dernier au premier pour que l'ordre des calques suive le temps)
        var items = [];
        for (var c = 0; c < plan.clips.length; c++) { items.push(es_findItemByPath(plan.clips[c])); }
        for (var s = plan.segments.length - 1; s >= 0; s--) {
            var seg = plan.segments[s];
            var src = items[seg.clip];
            if (!src) { continue; }
            var layer = comp.layers.add(src);
            layer.label = ES_LABEL;
            layer.name = (s + 1) + " · " + src.name;
            var still = src.mainSource && src.mainSource.isStill;
            if (!still && Math.abs(seg.speed - 1) > 0.01) {
                layer.stretch = 100 / seg.speed;          // 0.5 → 200 % (ralenti)
            }
            var k = (still ? 1 : layer.stretch / 100);
            layer.startTime = seg.t_in - (still ? 0 : seg.src_in * k);
            layer.inPoint = seg.t_in;
            layer.outPoint = seg.t_out;
            // remplir le cadre (recadrage centré)
            var sc = Math.max(plan.width / src.width, plan.height / src.height) * 100;
            layer.property("ADBE Transform Group").property("ADBE Scale").setValue([sc, sc]);
            if (src.hasAudio) {
                try { layer.audioEnabled = false; } catch (eA) {}
            }
        }

        // 3. Effets de caméra : un calque nul « Caméra » parent de tous les plans
        var cam = comp.layers.addNull(plan.duration);
        cam.name = "🎥 Caméra EditSensei";
        cam.label = ES_LABEL;
        cam.property("ADBE Transform Group").property("ADBE Anchor Point").setValue([50, 50]);
        cam.property("ADBE Transform Group").property("ADBE Position").setValue([plan.width / 2, plan.height / 2]);
        for (var li = 1; li <= comp.numLayers; li++) {
            var L = comp.layer(li);
            if (L !== cam && L.hasVideo && !L.nullLayer) { L.parent = cam; }
        }
        var camScale = cam.property("ADBE Transform Group").property("ADBE Scale");
        var camPos = cam.property("ADBE Transform Group").property("ADBE Position");
        var shakes = [];
        var zooms = [];
        for (var e = 0; e < plan.effects.length; e++) {
            var fx = plan.effects[e];
            if (fx.type === "zoom_punch") { zooms.push(fx); }
            if (fx.type === "shake") { shakes.push(fx); }
        }
        // zooms : images clés (100 → 100+30·force → 100)
        if (zooms.length) {
            camScale.setValueAtTime(0, [100, 100]);
            for (var z = 0; z < zooms.length; z++) {
                var p = 100 + 30 * zooms[z].strength;
                es_pulse(camScale, zooms[z].t, zooms[z].duration, [100, 100], [p, p]);
            }
            es_ease(camScale);
        }
        // shakes : expression bruitée active seulement pendant chaque secousse
        if (shakes.length) {
            var arr = [];
            for (var sh = 0; sh < shakes.length; sh++) {
                arr.push("[" + shakes[sh].t + "," + shakes[sh].duration + "," + shakes[sh].strength + "]");
            }
            camPos.expression =
                "// EditSensei : secousses calées sur la musique\n" +
                "var S=[" + arr.join(",") + "];var a=0;var amp=0;\n" +
                "for(var i=0;i<S.length;i++){var k=time-S[i][0];if(k>=0&&k<=S[i][1]){var d=S[i][1];var e=k<d*0.15?k/(d*0.15):Math.pow(1-(k-d*0.15)/(d*0.85),2);if(e*S[i][2]>a){a=e*S[i][2];}}}\n" +
                "amp=a*" + Math.round(Math.min(plan.width, plan.height) * 0.035) + ";\n" +
                // addition composante par composante : marche avec le moteur JavaScript ET l'ancien moteur
                "[value[0]+noise(time*38)*amp,value[1]+noise(time*38+71)*amp];";
        }

        // 4. Calques de réglage : flash, flou de transition, RGB split, glow, look
        var flashes = [], whips = [], rgbs = [], glows = [];
        for (var e2 = 0; e2 < plan.effects.length; e2++) {
            var f2 = plan.effects[e2];
            if (f2.type === "flash") { flashes.push(f2); }
            if (f2.type === "blur_whip") { whips.push(f2); }
            if (f2.type === "rgb_split") { rgbs.push(f2); }
            if (f2.type === "glow") { glows.push(f2); }
        }
        if (whips.length) {
            var wl = es_adjustment(comp, "💨 Transitions floues", plan.duration);
            var db = es_addEffect(wl, "ADBE Motion Blur"); // Flou directionnel
            if (db) {
                db.property(1).setValue(90); // direction horizontale
                var len = db.property(2);
                len.setValueAtTime(0, 0);
                for (var w = 0; w < whips.length; w++) { es_pulse(len, whips[w].t - whips[w].duration / 2, whips[w].duration, 0, 120 * whips[w].strength); }
            }
        }
        if (rgbs.length) {
            var rl = es_adjustment(comp, "🌈 RGB split", plan.duration);
            var sc2 = es_addEffect(rl, "ADBE Shift Channels");
            var tr = es_addEffect(rl, "ADBE Geometry2"); // Transformer : léger décalage horizontal
            if (tr) {
                var posT = tr.property(2);
                var cx = plan.width / 2, cy = plan.height / 2;
                posT.setValueAtTime(0, [cx, cy]);
                for (var r = 0; r < rgbs.length; r++) {
                    es_pulse(posT, rgbs[r].t, rgbs[r].duration, [cx, cy], [cx + 14 * rgbs[r].strength, cy]);
                }
                rl.blendingMode = BlendingMode.SCREEN;
                var op = rl.property("ADBE Transform Group").property("ADBE Opacity");
                op.setValueAtTime(0, 0);
                for (var r2 = 0; r2 < rgbs.length; r2++) { es_pulse(op, rgbs[r2].t, rgbs[r2].duration, 0, 70 * rgbs[r2].strength); }
            }
            // Décalage de couches : vert et bleu « désactivés » (option 10) → il ne reste que le rouge,
            // décalé par Transformer puis superposé en Écran = frange rouge façon RGB split
            if (sc2) { sc2.property(3).setValue(10); sc2.property(4).setValue(10); }
        }
        if (glows.length) {
            var gl = es_adjustment(comp, "✨ Glow", plan.duration);
            var g = es_addEffect(gl, "ADBE Glo2");
            if (g) {
                var gi = g.property(4); // intensité
                gi.setValueAtTime(0, 0);
                for (var gg = 0; gg < glows.length; gg++) { es_pulse(gi, glows[gg].t, glows[gg].duration, 0, 1.5 * glows[gg].strength); }
            }
        }
        if (flashes.length) {
            var fl = comp.layers.addSolid([1, 1, 1], "⚡ Flash", plan.width, plan.height, 1, plan.duration);
            fl.label = ES_LABEL;
            fl.blendingMode = BlendingMode.ADD;
            var fop = fl.property("ADBE Transform Group").property("ADBE Opacity");
            fop.setValueAtTime(0, 0);
            for (var ff = 0; ff < flashes.length; ff++) { es_pulse(fop, flashes[ff].t, flashes[ff].duration, 0, 100 * flashes[ff].strength); }
        }

        // 5. Look global : contraste / saturation / vignette / bandes cinéma
        var look = plan.look || {};
        var lk = es_adjustment(comp, "🎨 Look " + plan.style, plan.duration);
        var bc = es_addEffect(lk, "ADBE Brightness & Contrast 2");
        if (bc) { bc.property(2).setValue(Math.round(((look.contrast || 1) - 1) * 100)); }
        var hs = es_addEffect(lk, "ADBE HUE SATURATION");
        if (hs && look.saturation !== undefined) {
            try { hs.property(4).setValue(Math.round(((look.saturation) - 1) * 100)); } catch (eS) {}
        }
        if (look.vignette && look.vignette > 0) {
            var vg = comp.layers.addSolid([0, 0, 0], "🌑 Vignette", plan.width, plan.height, 1, plan.duration);
            vg.label = ES_LABEL;
            var mask = vg.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
            var shp = new Shape();
            var mw = plan.width, mh = plan.height;
            shp.vertices = [[mw * 0.5, -mh * 0.05], [mw * 1.05, mh * 0.5], [mw * 0.5, mh * 1.05], [-mw * 0.05, mh * 0.5]];
            shp.inTangents = [[-mw * 0.3, 0], [0, -mh * 0.3], [mw * 0.3, 0], [0, mh * 0.3]];
            shp.outTangents = [[mw * 0.3, 0], [0, mh * 0.3], [-mw * 0.3, 0], [0, -mh * 0.3]];
            shp.closed = true;
            mask.property("ADBE Mask Shape").setValue(shp);
            mask.inverted = true;
            mask.property("ADBE Mask Feather").setValue([mw * 0.25, mw * 0.25]);
            vg.property("ADBE Transform Group").property("ADBE Opacity").setValue(Math.round(look.vignette * 100));
        }
        if (look.black_bars) {
            var barH = plan.width > plan.height ? Math.round((plan.height - plan.width / 2.39) / 2) : Math.round(plan.height * 0.08);
            if (barH > 0) {
                var top = comp.layers.addSolid([0, 0, 0], "▬ Bande haut", plan.width, barH, 1, plan.duration);
                top.property("ADBE Transform Group").property("ADBE Position").setValue([plan.width / 2, barH / 2]);
                var bot = comp.layers.addSolid([0, 0, 0], "▬ Bande bas", plan.width, barH, 1, plan.duration);
                bot.property("ADBE Transform Group").property("ADBE Position").setValue([plan.width / 2, plan.height - barH / 2]);
            }
        }

        // 6. Textes
        for (var ti = 0; ti < (plan.texts || []).length; ti++) {
            var tx = plan.texts[ti];
            if (tx.kind === "subtitle") { es_subtitle(comp, plan, tx); continue; }
            var tl = comp.layers.addText(tx.text.toUpperCase());
            tl.name = "🔤 " + tx.text;
            tl.label = ES_LABEL;
            var td = tl.property("ADBE Text Properties").property("ADBE Text Document");
            var doc = td.value;
            doc.fontSize = Math.round(Math.min(plan.width, plan.height) * 0.14);
            doc.fillColor = [1, 1, 1];
            doc.applyStroke = true;
            doc.strokeColor = [0.08, 0.03, 0.12];
            doc.strokeWidth = Math.max(2, Math.round(doc.fontSize / 18));
            doc.justification = ParagraphJustification.CENTER_JUSTIFY;
            try { doc.font = "Anton-Regular"; } catch (eF) {}
            td.setValue(doc);
            tl.inPoint = tx.t;
            tl.outPoint = Math.min(plan.duration, tx.t + tx.duration);
            var tpos = tl.property("ADBE Transform Group").property("ADBE Position");
            tpos.setValue([plan.width / 2, plan.height / 2 + doc.fontSize / 3]);
            var ts = tl.property("ADBE Transform Group").property("ADBE Scale");
            es_pulse(ts, tx.t, 0.35, [100, 100], [135, 135]);
            var top2 = tl.property("ADBE Transform Group").property("ADBE Opacity");
            top2.setValueAtTime(tx.t, 0);
            top2.setValueAtTime(tx.t + 0.12, 100);
            top2.setValueAtTime(tx.t + tx.duration - 0.4, 100);
            top2.setValueAtTime(tx.t + tx.duration, 0);
        }

        // 7. Fondus d'ouverture et de fermeture (solide noir)
        if (plan.fade_in > 0 || plan.fade_out > 0) {
            var fd = comp.layers.addSolid([0, 0, 0], "🌘 Fondus", plan.width, plan.height, 1, plan.duration);
            var fo = fd.property("ADBE Transform Group").property("ADBE Opacity");
            fo.setValue(0);
            if (plan.fade_in > 0) { fo.setValueAtTime(0, 100); fo.setValueAtTime(plan.fade_in, 0); }
            if (plan.fade_out > 0) { fo.setValueAtTime(plan.duration - plan.fade_out, 0); fo.setValueAtTime(plan.duration, 100); }
        }

        comp.openInViewer();
        app.endUndoGroup();
        return es_ok({ comp: comp.name, compId: comp.id, layers: comp.numLayers });
    } catch (err) {
        app.endUndoGroup();
        return es_err("Construction interrompue : " + err.toString() + (err.line ? " (ligne " + err.line + ")" : ""));
    }
}

/* Adoucit toutes les images clés d'une propriété (easy ease). */
/* Sous-titre : texte blanc contouré en bas du cadre, apparition/disparition rapides. */
function es_subtitle(comp, plan, tx) {
    var tl = comp.layers.addText(tx.text);
    tl.name = "💬 " + tx.text;
    tl.label = ES_LABEL;
    var td = tl.property("ADBE Text Properties").property("ADBE Text Document");
    var doc = td.value;
    doc.fontSize = Math.round(Math.min(plan.width, plan.height) * 0.055);
    doc.fillColor = [1, 1, 1];
    doc.applyStroke = true;
    doc.strokeColor = [0, 0, 0];
    doc.strokeWidth = Math.max(2, Math.round(doc.fontSize / 10));
    doc.justification = ParagraphJustification.CENTER_JUSTIFY;
    try { doc.font = "Montserrat-Bold"; } catch (eF) {}
    td.setValue(doc);
    var tEnd = Math.min(plan.duration, tx.t + tx.duration);
    tl.inPoint = tx.t;
    tl.outPoint = tEnd;
    tl.property("ADBE Transform Group").property("ADBE Position")
        .setValue([plan.width / 2, plan.height * (plan.height > plan.width ? 0.72 : 0.86)]);
    var op = tl.property("ADBE Transform Group").property("ADBE Opacity");
    var f = Math.min(0.08, (tEnd - tx.t) / 4);
    op.setValueAtTime(tx.t, 0);
    op.setValueAtTime(tx.t + f, 100);
    op.setValueAtTime(tEnd - f, 100);
    op.setValueAtTime(tEnd, 0);
    return tl;
}

function es_ease(prop) {
    try {
        var dims = prop.value instanceof Array ? prop.value.length : 1;
        var ease = [];
        for (var d = 0; d < dims; d++) { ease.push(new KeyframeEase(0, 66)); }
        for (var k = 1; k <= prop.numKeys; k++) {
            prop.setTemporalEaseAtKey(k, ease, ease);
        }
    } catch (e) {}
}

// ── Mode apprenti : instantané de la compo active ─────────────────────────

function es_snapshot() {
    try {
        var comp = app.project.activeItem;
        if (!comp || !(comp instanceof CompItem)) { return es_ok(null); }
        var layers = [];
        var music = null;
        for (var i = 1; i <= comp.numLayers; i++) {
            var L = comp.layer(i);
            var info = { index: i, name: L.name, inPoint: L.inPoint, outPoint: L.outPoint, startTime: L.startTime,
                         stretch: L.stretch, hasVideo: L.hasVideo, hasAudio: L.hasAudio, adjustment: L.adjustmentLayer,
                         effects: [], keys: {}, source: null };
            try {
                if (L.source && L.source.file) {
                    info.source = L.source.file.fsName;
                    if (!music && L.hasAudio && !L.hasVideo) { music = { path: info.source, startTime: L.startTime }; }
                }
            } catch (eS) {}
            var fxp = L.property("ADBE Effect Parade");
            if (fxp) {
                for (var e = 1; e <= fxp.numProperties; e++) { info.effects.push(fxp.property(e).matchName); }
            }
            var tg = L.property("ADBE Transform Group");
            var names = { "ADBE Scale": "scale", "ADBE Position": "position", "ADBE Rotate Z": "rotation", "ADBE Opacity": "opacity" };
            for (var mn in names) {
                if (!names.hasOwnProperty(mn)) { continue; }
                var p = tg.property(mn);
                if (p && p.numKeys > 0) {
                    var ts = [];
                    for (var k = 1; k <= p.numKeys; k++) { ts.push(Math.round(p.keyTime(k) * 1000) / 1000); }
                    info.keys[names[mn]] = ts;
                }
                if (p && p.expressionEnabled && p.expression) { info.keys[names[mn] + "_expr"] = 1; }
            }
            layers.push(info);
        }
        return es_ok({ compId: comp.id, name: comp.name, duration: comp.duration, fps: comp.frameRate,
                       width: comp.width, height: comp.height, music: music, layers: layers,
                       time: comp.time });
    } catch (err) {
        return es_err(err.toString());
    }
}
