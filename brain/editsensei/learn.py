"""Comment EditSensei apprend.

Deux sources d'exemples, une seule logique :

1. **Vidéos de référence** (`learn_from_video`) : un edit que tu aimes (AMV, edit TikTok…).
   On détecte coupes, flashs, zooms, secousses, flous et RGB split image par image,
   on analyse sa musique, puis on replace chaque événement sur la grille musicale.

2. **Mode apprenti** (`learn_from_snapshot`) : EditSensei regarde ta composition dans
   After Effects pendant que tu montes (coupes = débuts de calques, zooms = images clés
   d'échelle, flashs = solides blancs, effets ajoutés…).

Dans les deux cas on obtient des statistiques (« à quel rythme coupe-t-il quand la
musique est forte ? quelle proportion de drops reçoit un flash ? ») transformées en
`StyleModel`. Les styles se mélangent ensuite (`StyleModel.absorb`) : plus tu lui
montres d'exemples, plus ton style personnel s'affine.

Ce n'est pas un réseau de neurones géant : c'est un apprentissage statistique,
transparent (tu peux lire le JSON du style), rapide et qui marche dès UN exemple.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .audio import MusicMap, analyze_music, analyze_signal, load_audio
from .style import MOMENTS, EffectRule, Look, SpeedRules, StyleModel, get_style, save_style

MY_STYLE = "Mon style"


# ── des événements au style ───────────────────────────────

def style_from_events(
    name: str,
    music: MusicMap,
    cuts: list[float],
    events: dict[str, list[float]],
    look: Look | None = None,
    source: str = "video",
    span: tuple[float, float] | None = None,
    base: StyleModel | None = None,
) -> StyleModel:
    """Statistiques musicales des coupes et effets → modèle de style."""
    t0, t1 = span or (0.0, music.duration)
    beats = np.asarray([b for b in music.beats if t0 <= b <= t1])
    beat_len = 60.0 / max(music.tempo, 40.0)
    base = (base or get_style("Anime") or StyleModel("base")).copy()

    # rythme des coupes par niveau d'énergie
    cuts = sorted(c for c in cuts if t0 < c < t1)
    by_level: dict[str, list[float]] = {"low": [], "mid": [], "high": []}
    marks = [t0] + cuts + [t1]
    for a, b in zip(marks[:-1], marks[1:]):
        if b - a < 0.05:
            continue
        by_level[music.level_at((a + b) / 2)].append((b - a) / beat_len)
    cut = base.cut
    for lvl, attr in (("low", "beats_low"), ("mid", "beats_mid"), ("high", "beats_high")):
        if by_level[lvl]:
            setattr(cut, attr, float(np.median(by_level[lvl])))
    # si un niveau n'a pas d'exemple on le déduit des autres (calme ≥ moyen ≥ fort)
    if not by_level["mid"] and (by_level["low"] or by_level["high"]):
        cut.beats_mid = float(np.sqrt(max(cut.beats_low, 0.25) * max(cut.beats_high, 0.25)))
    if cuts and len(beats):
        on = sum(1 for c in cuts if np.min(np.abs(beats - c)) <= 0.07)
        cut.on_beat = on / len(cuts)

    # fréquence de chaque effet par type d'instant musical
    moment_times = {m: [] for m in MOMENTS}
    for b in beats:
        moment_times[music.moment_of(float(b))].append(float(b))
    effects: dict[str, EffectRule] = {}
    for eff, times in events.items():
        rule = base.rule(eff)
        times = [t for t in times if t0 <= t <= t1]
        hits = {m: 0 for m in MOMENTS}
        for t in times:
            if not len(beats):
                break
            nb = float(beats[int(np.argmin(np.abs(beats - t)))])
            if abs(nb - t) <= 0.12:
                hits[music.moment_of(nb)] += 1
        new = EffectRule(strength=rule.strength, duration=rule.duration)
        # détecteurs moins fiables (RGB split, flou) : on ne leur fait confiance qu'à moitié
        trust = 0.5 if eff in ("rgb_split", "blur_whip", "glow") else 1.0
        for m in MOMENTS:
            n = len(moment_times[m])
            learned = min(1.0, hits[m] / n) if n else rule.rate(m)
            setattr(new, m, trust * learned + (1 - trust) * rule.rate(m))
        effects[eff] = new
    for eff in base.effects:
        effects.setdefault(eff, base.effects[eff])

    style = StyleModel(
        name=name,
        description=f"Appris ({source}) : {len(cuts)} coupes, " + ", ".join(f"{len(v)} {k}" for k, v in events.items() if v),
        source=source,
        cut=cut,
        effects=effects,
        look=look or base.look,
        speed=SpeedRules(**base.speed.__dict__),
        fade_in=base.fade_in,
        fade_out=base.fade_out,
        examples=1,
        tags=[source, "appris"],
    )
    return style.clamped()


# ── 1. apprendre d'une vidéo ──────────────────────────────

def detect_events(path: str | Path, width: int = 192) -> dict:
    """Analyse image par image d'un edit : coupes, flashs, zooms, secousses, flous, RGB split, look.

    Chaque image est réduite à 192 px de large. Le mouvement de caméra est mesuré en suivant
    des points d'image en image (Lucas-Kanade) puis en estimant une similitude
    (échelle + translation) : un zoom punch = échelle qui grimpe puis redescend,
    une secousse = translation qui change de sens à chaque image.
    """
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    times, luma, sharp, hist_d, rgb_shift, sats, stds, bars_votes, vign = [], [], [], [], [], [], [], [], []
    log_scale, trans = [], []
    prev_gray = prev_hist = None
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (width, max(2, int(h * width / w))), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        g32 = gray.astype(np.float32)
        times.append(idx / fps)
        luma.append(float(g32.mean()))
        sharp.append(float(cv2.Laplacian(g32, cv2.CV_32F).var()))
        hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
        hist = cv2.normalize(hist, hist).flatten()
        hd = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)) if prev_hist is not None else 0.0
        hist_d.append(hd)
        if idx % 3 == 0:  # statistiques de look : pas besoin de chaque image
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            sats.append(float(hsv[..., 1].mean() / 255))
            stds.append(float(g32.std() / 255))
            hh, ww = gray.shape
            band = max(1, hh // 12)
            bars_votes.append(g32[:band].mean() < 12 and g32[-band:].mean() < 12 and g32[hh // 3: 2 * hh // 3].mean() > 25)
            center = g32[hh // 3: 2 * hh // 3, ww // 3: 2 * ww // 3].mean() + 1
            corners = np.mean([g32[: hh // 6, : ww // 6].mean(), g32[-hh // 6:, -ww // 6:].mean(),
                               g32[: hh // 6, -ww // 6:].mean(), g32[-hh // 6:, : ww // 6].mean()]) + 1
            vign.append(max(0.0, 1 - corners / center))
        # décalage rouge / bleu (RGB split)
        b_ch, _, r_ch = cv2.split(small.astype(np.float32))
        (sx, _), resp = cv2.phaseCorrelate(b_ch, r_ch)
        rgb_shift.append(abs(sx) if resp > 0.05 else 0.0)
        # mouvement de caméra entre deux images du même plan
        ls, tx, ty = np.nan, np.nan, np.nan
        if prev_gray is not None and hd < 0.3:
            pts = cv2.goodFeaturesToTrack(prev_gray, 80, 0.01, 6)
            if pts is not None and len(pts) >= 8:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pts, None, winSize=(15, 15), maxLevel=2)
                good = st.reshape(-1) == 1
                if good.sum() >= 8:
                    m, _ = cv2.estimateAffinePartial2D(pts[good], nxt[good], method=cv2.RANSAC, ransacReprojThreshold=2.0)
                    if m is not None:
                        sc = float(np.sqrt(m[0, 0] ** 2 + m[1, 0] ** 2))
                        # translation exprimée autour du centre (indépendante de l'échelle)
                        cx, cy = gray.shape[1] / 2, gray.shape[0] / 2
                        tx = float(m[0, 0] * cx + m[0, 1] * cy + m[0, 2] - cx) / gray.shape[1]
                        ty = float(m[1, 0] * cx + m[1, 1] * cy + m[1, 2] - cy) / gray.shape[1]
                        ls = float(np.log(max(sc, 1e-3)))
        log_scale.append(ls)
        trans.append((tx, ty))
        prev_gray, prev_hist = gray, hist
        idx += 1
    cap.release()

    t = np.asarray(times)
    n = len(t)
    if n < 3:
        return {"duration": float(t[-1]) if n else 0.0, "cuts": [], "events": {k: [] for k in
                ("flash", "zoom_punch", "shake", "blur_whip", "rgb_split")}, "look": Look()}
    luma_a, sharp_a, hd = np.asarray(luma), np.asarray(sharp), np.asarray(hist_d)
    win = max(3, int(fps))

    def local_peaks(sig: np.ndarray, thr: np.ndarray | float, min_gap: float) -> list[int]:
        out: list[int] = []
        thr_a = np.broadcast_to(thr, sig.shape)
        for i in range(1, n - 1):
            if sig[i] >= thr_a[i] and sig[i] >= sig[i - 1] and sig[i] >= sig[i + 1]:
                if not out or t[i] - t[out[-1]] >= min_gap:
                    out.append(i)
        return out

    cut_idx = local_peaks(hd, 0.42, 0.12)
    cuts = [float(t[i]) for i in cut_idx]
    near_cut = np.zeros(n, bool)
    for i in cut_idx:
        near_cut[max(0, i - 1): i + 2] = True

    # flash : pic de luminance qui retombe dans les 0,25 s (pas un simple plan plus clair)
    med = _rolling_median(luma_a, win)
    dev = luma_a - med
    mad = float(np.median(np.abs(dev))) + 1e-6
    back = max(2, int(0.25 * fps))
    flashes = []
    for i in local_peaks(dev, max(18.0, 6 * mad), 0.2):
        after = luma_a[i + 1: i + 1 + back]
        if len(after) and after.min() < luma_a[i] - 0.5 * dev[i]:
            flashes.append(float(t[i]))

    # zoom punch : l'échelle redescend nettement juste après (phase de retour du punch)
    ls = np.nan_to_num(np.asarray(log_scale), nan=0.0)
    k = max(2, int(0.25 * fps))
    fwd = np.asarray([ls[i: i + k].sum() for i in range(n)])          # variation d'échelle sur les 0,25 s suivantes
    zooms = []
    for i in local_peaks(-fwd, 0.08, 0.35):
        zooms.append(float(max(0.0, t[i] - 0.05)))

    # secousse : translation qui change de sens image après image (≠ panoramique régulier)
    tr = np.nan_to_num(np.asarray(trans, dtype=float), nan=0.0)
    jitter = np.linalg.norm(np.diff(tr, axis=0, prepend=tr[:1]), axis=1)
    jitter[near_cut] = 0
    shake_e = _rolling_mean(jitter, max(2, int(0.15 * fps)))
    shakes = [float(t[i]) for i in local_peaks(shake_e, max(0.02, float(np.percentile(shake_e, 75)) * 4), 0.35)]

    # flou de transition : netteté effondrée au raccord, comparée aux deux plans voisins
    blur_times = []
    for i in cut_idx:
        lo, hi = max(0, i - 2), min(n, i + 3)
        before = sharp_a[max(0, i - win): max(1, i - 2)]
        after = sharp_a[min(n - 1, i + 3): min(n, i + win)]
        ref = min(np.median(before) if len(before) else np.inf, np.median(after) if len(after) else np.inf)
        if np.isfinite(ref) and sharp_a[lo:hi].min() < 0.25 * ref:
            blur_times.append(float(t[i]))

    # RGB split : décalage rouge/bleu bref et nettement au-dessus du niveau habituel
    rgb = np.asarray(rgb_shift)
    base = _rolling_median(rgb, win)
    rgbs = [float(t[i]) for i in local_peaks(rgb - base, 2.5, 0.3)]

    sat = float(np.median(sats)) if sats else 0.35
    std = float(np.median(stds)) if stds else 0.2
    look = Look(
        contrast=float(np.clip(std / 0.21, 0.7, 1.5)),
        saturation=float(np.clip(sat / 0.38, 0.0, 1.8)),
        black_bars=bool(np.mean(bars_votes) > 0.6) if bars_votes else False,
        vignette=float(np.clip(np.median(vign) * 1.6, 0, 1)) if vign else 0.0,
    )
    return {
        "duration": float(t[-1]),
        "cuts": cuts,
        "events": {"flash": flashes, "zoom_punch": zooms, "shake": shakes, "blur_whip": blur_times, "rgb_split": rgbs},
        "look": look,
    }


def learn_from_video(path: str | Path, name: str | None = None, into: str | None = None) -> tuple[StyleModel, str]:
    """Apprend le style d'un edit. `into` = nom d'un style existant à enrichir (ex. « Mon style »)."""
    path = Path(path)
    music = analyze_music(path)
    det = detect_events(path)
    learned = style_from_events(name or f"Appris · {path.stem}", music, det["cuts"], det["events"], det["look"], "video",
                                span=(0.0, det["duration"] or music.duration))
    target = learned
    if into:
        existing = get_style(into)
        target = existing.absorb(learned) if existing else learned
        target.name = existing.name if existing else into
    save_style(target)
    ev = det["events"]
    report = (
        f"J'ai étudié « {path.name} » ({music.tempo:.0f} BPM, {len(det['cuts'])} coupes). "
        f"J'y vois {len(ev['flash'])} flashs, {len(ev['zoom_punch'])} zooms, {len(ev['shake'])} secousses, "
        f"{len(ev['blur_whip'])} transitions floues et {len(ev['rgb_split'])} RGB split. "
        f"Rythme : une coupe tous les {learned.cut.beats_high:.1f} temps quand c'est fort, "
        f"{learned.cut.beats_low:.1f} quand c'est calme ; {learned.cut.on_beat * 100:.0f} % des coupes tombent sur le beat. "
        f"Style enregistré : « {target.name} » ({target.examples} exemple{'s' if target.examples > 1 else ''})."
    )
    return target, report


# ── 2. mode apprenti : regarder l'humain monter dans After Effects ──

_seen: dict[str, str] = {}


def events_from_snapshot(snap: dict) -> tuple[list[float], dict[str, list[float]]]:
    """Coupes et effets visibles dans un instantané de composition (es_snapshot)."""
    layers = snap.get("layers", [])
    music_path = (snap.get("music") or {}).get("path")
    video = [l for l in layers if l.get("hasVideo") and l.get("source") and l.get("source") != music_path and not l.get("adjustment")]
    cuts = sorted({round(float(l["inPoint"]), 3) for l in video if float(l["inPoint"]) > 0.05})
    ev: dict[str, list[float]] = {"zoom_punch": [], "shake": [], "flash": [], "blur_whip": [], "glow": [], "rgb_split": []}
    for l in layers:
        keys = l.get("keys", {})
        name = (l.get("name") or "").lower()
        effects = l.get("effects", [])
        # zoom : paires d'images clés d'échelle rapprochées → début de l'impulsion
        ev["zoom_punch"] += _pulse_starts(keys.get("scale", []))
        if keys.get("position_expr"):
            # une expression de wiggle / secousse sur toute la durée du calque
            ev["shake"].append(float(l["inPoint"]))
        ev["shake"] += _pulse_starts(keys.get("position", []), max_len=0.6)
        if not l.get("source") and ("flash" in name or "white" in name or "blanc" in name):
            ev["flash"] += _pulse_starts(keys.get("opacity", []))
        if "ADBE Glo2" in effects:
            ev["glow"] += _pulse_starts(keys.get("opacity", [])) or [float(l["inPoint"])]
        if "ADBE Motion Blur" in effects or "ADBE Gaussian Blur 2" in effects:
            ev["blur_whip"] += [c for c in cuts if float(l["inPoint"]) - 0.05 <= c <= float(l["outPoint"]) + 0.05][:50]
        if "ADBE Shift Channels" in effects or "rgb" in name:
            ev["rgb_split"] += _pulse_starts(keys.get("opacity", [])) or [float(l["inPoint"])]
    return cuts, {k: sorted(set(v)) for k, v in ev.items()}


def learn_from_snapshot(snap: dict, weight: float = 0.3) -> tuple[StyleModel | None, str]:
    """Observe une compo ; si elle a changé de façon significative, enrichit « Mon style »."""
    if not snap or not snap.get("music"):
        return None, "Je regarde… (ajoute une musique dans ta compo pour que je comprenne ton rythme)."
    cuts, events = events_from_snapshot(snap)
    if len(cuts) < 4:
        return None, f"Je regarde… ({len(cuts)} coupe{'s' if len(cuts) > 1 else ''} pour l'instant, j'apprends à partir de 4)."
    fingerprint = hashlib.sha1(json.dumps([cuts, events], sort_keys=True).encode()).hexdigest()
    key = str(snap.get("compId"))
    if _seen.get(key) == fingerprint:
        return None, ""
    _seen[key] = fingerprint

    mpath = snap["music"]["path"]
    music = analyze_music(mpath)
    offset = -float(snap["music"].get("startTime", 0.0))  # temps compo → temps musique
    shifted = lambda xs: [x + offset for x in xs]  # noqa: E731
    observed = style_from_events(MY_STYLE, music, shifted(cuts), {k: shifted(v) for k, v in events.items()},
                                 source="observed", span=(offset, offset + float(snap.get("duration", music.duration))))
    mine = get_style(MY_STYLE)
    updated = mine.absorb(observed, weight) if mine else observed
    updated.name = MY_STYLE
    updated.description = f"Ton style, appris en te regardant monter ({updated.examples} observations)."
    save_style(updated)
    n_fx = sum(len(v) for v in events.values())
    return updated, f"J'ai appris de ta compo « {snap.get('name')} » : {len(cuts)} coupes, {n_fx} effets. « {MY_STYLE} » mis à jour."


def learn_from_feedback(plan_dict: dict, music: MusicMap, liked: bool) -> str:
    """👍 sur un montage d'EditSensei : on le considère comme un bon exemple de ton style."""
    if not liked:
        return "Noté. Dis-moi ce qui ne va pas (« moins de flashs », « plus calme »…) et je corrige."
    start = plan_dict["music_start"]
    cuts = [s["t_in"] + start for s in plan_dict["segments"][1:]]
    events: dict[str, list[float]] = {}
    for e in plan_dict["effects"]:
        events.setdefault(e["type"], []).append(e["t"] + start)
    observed = style_from_events(MY_STYLE, music, cuts, events, source="observed",
                                 span=(start, start + plan_dict["duration"]))
    mine = get_style(MY_STYLE)
    updated = mine.absorb(observed, 0.2) if mine else observed
    updated.name = MY_STYLE
    save_style(updated)
    n = updated.examples
    return f"Merci ! J'ai gardé ce montage comme exemple : « {MY_STYLE} » a maintenant {n} exemple{'s' if n > 1 else ''}."


# ── outils ────────────────────────────────────────────────

def _pulse_starts(times: list[float], max_len: float = 1.2) -> list[float]:
    """Images clés groupées en impulsions (≥2 clés en < max_len s) → instant de début de chaque impulsion."""
    ts = sorted(float(t) for t in times)
    out, i = [], 0
    while i < len(ts) - 1:
        j = i
        while j + 1 < len(ts) and ts[j + 1] - ts[i] <= max_len:
            j += 1
        if j > i:
            out.append(ts[i])
        i = j + 1
    return out


def _rolling_median(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) == 0:
        return x
    n = max(1, n)
    pad = np.pad(x, (n, n), mode="edge")
    return np.asarray([np.median(pad[i:i + 2 * n + 1]) for i in range(len(x))])


def _rolling_mean(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) == 0:
        return x
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


__all__ = ["learn_from_video", "learn_from_snapshot", "learn_from_feedback", "detect_events", "style_from_events",
           "analyze_signal", "load_audio", "MY_STYLE"]
