"""Le monteur : transforme musique + clips + style + consignes en plan de montage.

Le plan (`EditPlan`) est neutre : After Effects le construit couche par couche
(ae-panel/jsx/editsensei.jsx) et l'aperçu Python peut le rendre en MP4 (preview.py).

Principes de montage appliqués :
1. Les coupes tombent sur les beats ; plus la musique est intense, plus on coupe vite.
2. Chaque drop ou changement de partie déclenche un nouveau plan (l'impact tombe sur une image neuve).
3. Les passages calmes reçoivent des plans posés, les passages forts des plans d'action.
4. On évite de réutiliser un passage déjà montré et d'enchaîner deux fois le même clip.
5. Les effets suivent les probabilités du style, avec une densité limitée pour rester lisible.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .audio import MusicMap
from .directives import ASPECTS, Directives, describe
from .footage import ClipInfo
from .style import EFFECTS, StyleModel


@dataclass
class Segment:
    clip: int          # index dans la liste des clips
    src_in: float      # début dans le clip source (s)
    src_out: float     # fin dans le clip source (s)
    t_in: float        # début dans le montage (s)
    t_out: float       # fin dans le montage (s)
    speed: float = 1.0
    level: str = "mid"


@dataclass
class Effect:
    type: str          # zoom_punch | shake | flash | blur_whip | glow | rgb_split
    t: float
    duration: float
    strength: float
    moment: str = "beat"


@dataclass
class TextItem:
    text: str
    t: float
    duration: float
    kind: str = "title"   # title (titre animé au centre) | subtitle (sous-titre en bas)


@dataclass
class EditPlan:
    name: str
    width: int
    height: int
    fps: float
    duration: float
    music: str | None
    music_start: float
    tempo: float
    clips: list[str]
    segments: list[Segment] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)
    look: dict = field(default_factory=dict)
    fade_in: float = 0.0
    fade_out: float = 0.0
    style: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EditPlan":
        d = dict(d)
        d["segments"] = [Segment(**s) for s in d.get("segments", [])]
        d["effects"] = [Effect(**e) for e in d.get("effects", [])]
        d["texts"] = [TextItem(**t) for t in d.get("texts", [])]
        return cls(**d)


# ── outils de grille musicale ─────────────────────────────

def _beat_time(beats: np.ndarray, x: float) -> float:
    """Temps correspondant à l'indice de beat fractionnaire x (interpolation / extrapolation)."""
    if len(beats) == 1:
        return float(beats[0] + x * 0.5)
    i = int(np.floor(x))
    if i < 0:
        return float(beats[0] + x * (beats[1] - beats[0]))
    if i >= len(beats) - 1:
        step = beats[-1] - beats[-2]
        return float(beats[-1] + (x - (len(beats) - 1)) * step)
    return float(beats[i] + (x - i) * (beats[i + 1] - beats[i]))


def _beat_index(beats: np.ndarray, t: float) -> float:
    """Indice de beat fractionnaire correspondant au temps t."""
    if len(beats) < 2:
        return t / 0.5
    if t <= beats[0]:
        return (t - beats[0]) / (beats[1] - beats[0])
    if t >= beats[-1]:
        return len(beats) - 1 + (t - beats[-1]) / (beats[-1] - beats[-2])
    i = int(np.searchsorted(beats, t, side="right") - 1)
    return i + (t - beats[i]) / (beats[i + 1] - beats[i])


# ── planification ─────────────────────────────────────────

def choose_window(music: MusicMap, d: Directives, default_len: float = 30.0) -> tuple[float, float]:
    """Choisit le passage de la musique à monter : on veut une montée puis l'impact du drop."""
    total = music.duration
    want = min(d.duration or min(default_len, total), total)
    if d.music_start is not None and d.music_start >= 0:
        start = min(d.music_start, max(0.0, total - want))
        return start, want
    if want >= total - 0.5:
        return 0.0, total
    target = None
    if music.drops:
        drop = music.drops[0]
        lead = 0.35 * want if d.music_start is None else 2 * 60.0 / max(music.tempo, 1)
        target = drop - lead
    elif music.sections:
        target = music.sections[0] - 0.25 * want
    start = max(0.0, min(target if target is not None else 0.0, total - want))
    # départ sur un début de mesure
    if music.downbeats:
        cands = [db for db in music.downbeats if db <= start + 0.01] or [music.downbeats[0]]
        start = max(0.0, cands[-1])
    return float(start), float(min(want, total - start))


def plan_edit(
    music: MusicMap | None,
    clips: list[ClipInfo],
    style: StyleModel,
    d: Directives,
    music_path: str | None = None,
    name: str = "EditSensei",
) -> EditPlan:
    if not clips:
        raise ValueError("Aucun clip à monter : importe tes vidéos dans le projet.")
    rng = random.Random(d.seed)

    if music is None:  # sans musique : grille régulière à 120 BPM
        length = d.duration or min(30.0, sum(c.duration for c in clips))
        beats = list(np.arange(0, length + 0.01, 0.5))
        music = MusicMap(length, 120.0, beats, beats[::4], [0.5] * len(beats), ["mid"] * len(beats))
    start, length = choose_window(music, d)
    end = start + length

    width, height = ASPECTS.get(d.aspect or "", (0, 0))
    if not width:
        ref = max(clips, key=lambda c: c.width * c.height)
        landscape = ref.width >= ref.height if ref.width and ref.height else True
        width, height = (1920, 1080) if landscape else (1080, 1920)
    fps = d.fps or (30.0 if not clips[0].fps else (60.0 if clips[0].fps > 45 else 30.0))

    beats = np.asarray(music.beats, dtype=float)
    energy_shift = d.energy
    slowmo = style.speed.slowmo_on_drop if d.slowmo_on_drop is None else d.slowmo_on_drop

    # 1. points de coupe ─────────────────────────────────
    forced = sorted({t for t in music.drops + music.sections if start + 0.2 < t < end - 0.2})
    cut_times = [start]
    x = _beat_index(beats, start)
    while True:
        t_now = _beat_time(beats, x)
        level = music.level_at(t_now)
        per = {"low": style.cut.beats_low, "mid": style.cut.beats_mid, "high": style.cut.beats_high}[level]
        per *= (1.0 - 0.45 * energy_shift)
        per = _quantize(per)
        # ralenti : le plan qui démarre sur le drop dure plus longtemps
        if slowmo and any(abs(t_now - dr) < 0.05 for dr in music.drops):
            per = max(per, style.speed.slowmo_beats)
        nxt = x + per
        t_next = _beat_time(beats, nxt)
        # une coupe forcée (drop / section) avant le prochain point ? on coupe dessus
        f = next((ft for ft in forced if cut_times[-1] + 0.15 < ft < t_next - 0.05), None)
        if f is not None:
            t_next = f
            nxt = _beat_index(beats, f)
        if t_next >= end - 0.15:
            break
        cut_times.append(round(t_next, 4))
        x = nxt
    cut_times.append(end)

    # 2. choix des plans ─────────────────────────────────
    used: dict[int, list[tuple[float, float]]] = {}
    segments: list[Segment] = []
    order = [i - 1 for i in d.clip_order if 1 <= i <= len(clips)]
    prev_clip = -1
    for k, (a, b) in enumerate(zip(cut_times[:-1], cut_times[1:])):
        out_len = b - a
        level = music.level_at(a + 0.01)
        is_drop = any(abs(a - dr) < 0.05 for dr in music.drops)
        speed = 1.0
        if is_drop and slowmo:
            speed = style.speed.slowmo_factor
        elif level == "low":
            speed = style.speed.speedup_low_energy
        want_motion = {"low": 0.25, "mid": 0.5, "high": 0.8}[level]
        if is_drop:
            want_motion = 0.95
        src_len = out_len * speed

        best = None
        candidates = [order[0]] if (k == 0 and order) else range(len(clips))
        for ci in candidates:
            c = clips[ci]
            if c.duration <= 0:
                continue
            if c.duration < src_len:  # clip trop court : on le ralentit pour couvrir le plan
                s_len = c.duration
                starts = [0.0]
            else:
                s_len = src_len
                step = max(0.25, (c.duration - s_len) / 40)
                starts = list(np.arange(0.0, c.duration - s_len + 1e-6, step))
            for s0 in starts:
                score = c.score_window(s0, s_len, want_motion)
                overlap = sum(max(0.0, min(s0 + s_len, u1) - max(s0, u0)) for u0, u1 in used.get(ci, []))
                score -= 1.2 * overlap / max(s_len, 1e-6)
                if ci == prev_clip and len(clips) > 1:
                    score -= 0.5
                score += rng.uniform(0, 0.08)  # un peu de variété entre les versions
                if best is None or score > best[0]:
                    best = (score, ci, s0, s_len)
        _, ci, s0, s_len = best
        seg_speed = s_len / out_len if out_len > 0 else 1.0
        segments.append(Segment(ci, round(s0, 4), round(s0 + s_len, 4), round(a - start, 4), round(b - start, 4),
                                round(seg_speed, 4), level))
        used.setdefault(ci, []).append((s0, s0 + s_len))
        prev_clip = ci

    # 3. effets ──────────────────────────────────────────
    effects: list[Effect] = []
    gains = {e: d.effect_gain.get(e, 1.0) for e in EFFECTS}
    moments = [(t, music.moment_of(t)) for t in music.beats if start - 0.01 <= t < end - 0.1]
    cut_set = cut_times[1:-1]
    last_at: dict[str, float] = {}
    # écart minimum entre deux effets identiques, en temps musicaux (lisibilité)
    min_gap_beats = {"flash": 2.0, "zoom_punch": 1.0, "shake": 1.0, "rgb_split": 1.5, "glow": 4.0, "blur_whip": 0.5}
    beat_len = 60.0 / max(music.tempo, 40.0)
    for t, moment in moments:
        lvl_boost = {"low": 0.6, "mid": 1.0, "high": 1.3}[music.level_at(t)]
        for eff in EFFECTS:
            if eff in d.disabled or eff == "blur_whip":
                continue
            rule = style.rule(eff)
            p = rule.rate(moment) * gains[eff] * lvl_boost * (1.0 + 0.6 * energy_shift)
            if moment == "drop":
                p = max(p, rule.drop * gains[eff])  # le drop garde toujours son impact
            if rng.random() < min(p, 1.0) and t - last_at.get(eff, -99) >= min_gap_beats[eff] * beat_len - 0.01:
                strength = min(1.0, rule.strength * (1.25 if moment == "drop" else 1.0) * (1 + 0.3 * energy_shift))
                effects.append(Effect(eff, round(t - start, 4), round(rule.duration, 3), round(strength, 3), moment))
                last_at[eff] = t
    if "blur_whip" not in d.disabled:
        rule = style.rule("blur_whip")
        for t in cut_set:
            moment = music.moment_of(t)
            p = rule.rate(moment) * gains["blur_whip"] * (1.0 + 0.6 * energy_shift)
            if rng.random() < min(p, 1.0):
                effects.append(Effect("blur_whip", round(t - start, 4), round(rule.duration, 3), round(rule.strength, 3), moment))
    effects.sort(key=lambda e: (e.t, e.type))

    # 4. textes ──────────────────────────────────────────
    texts = []
    for tx in d.texts:
        at = tx.get("at", "start")
        if at == "drop":
            t0 = (music.drops[0] - start) if music.drops and start <= music.drops[0] < end else length * 0.35
        elif at == "end":
            t0 = max(0.0, length - 3.0)
        elif isinstance(at, (int, float)):
            t0 = float(at)
        else:
            t0 = 0.3
        texts.append(TextItem(tx["text"], round(min(max(0.0, t0), max(0.0, length - 0.5)), 3), 2.5))

    # 5. look ────────────────────────────────────────────
    look = {
        "contrast": round(style.look.contrast + 0.1 * energy_shift, 3),
        "saturation": 0.0 if d.black_white else round(style.look.saturation, 3),
        "black_bars": style.look.black_bars if d.black_bars is None else d.black_bars,
        "vignette": round(style.look.vignette, 3),
    }

    plan = EditPlan(
        name=name, width=width, height=height, fps=fps, duration=round(length, 4),
        music=music_path, music_start=round(start, 4), tempo=music.tempo,
        clips=[c.path for c in clips], segments=segments, effects=effects, texts=texts, look=look,
        fade_in=style.fade_in, fade_out=style.fade_out, style=style.name,
    )
    plan.summary = summarize(plan, music, d)
    return plan


def _quantize(beats_per_cut: float) -> float:
    """Arrondit à des durées musicales : ½, 1, 2, 4, 8 temps."""
    grid = [0.5, 1, 2, 3, 4, 6, 8, 12, 16]
    return float(min(grid, key=lambda g: abs(np.log2(g) - np.log2(max(beats_per_cut, 0.25)))))


def summarize(plan: EditPlan, music: MusicMap, d: Directives) -> str:
    counts: dict[str, int] = {}
    for e in plan.effects:
        counts[e.type] = counts.get(e.type, 0) + 1
    names = {"zoom_punch": ("zoom", "zooms"), "shake": ("shake", "shakes"), "flash": ("flash", "flashs"),
             "blur_whip": ("transition", "transitions"), "glow": ("glow", "glows"), "rgb_split": ("RGB split", "RGB split")}
    fx = ", ".join(f"{n} {names[k][n > 1]}" for k, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    drops_in = [dr for dr in music.drops if plan.music_start <= dr < plan.music_start + plan.duration]
    slow = sum(1 for s in plan.segments if s.speed < 0.95)
    parts = [
        f"J'ai monté {plan.duration:.0f} s en style « {plan.style} » sur un tempo de {plan.tempo:.0f} BPM",
        f"{len(plan.segments)} plans coupés sur les beats",
    ]
    if drops_in:
        parts.append(f"{len(drops_in)} drop{'s' if len(drops_in) > 1 else ''} avec impact" + (" et ralenti" if slow else ""))
    if fx:
        parts.append(fx)
    understood = describe(d)
    text = " · ".join(parts) + "."
    if understood:
        text += " Consignes appliquées : " + ", ".join(understood) + "."
    return text


def clip_label(path: str) -> str:
    return Path(path).stem
