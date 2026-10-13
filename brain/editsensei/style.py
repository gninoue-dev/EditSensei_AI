"""Le « modèle » de montage : un style chiffré que l'IA applique… et qu'elle apprend.

Un style décrit COMMENT monter, indépendamment des clips et de la musique :
- le rythme des coupes selon l'énergie de la musique,
- la probabilité de chaque effet sur chaque type d'instant musical,
- le « look » global (contraste, saturation, bandes cinéma…).

Les styles fournis (anime, smooth, aggressive, gaming) sont dans /styles.
Les styles appris (vidéos de référence, mode apprenti) sont dans ~/.editsensei/styles.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Instants musicaux sur lesquels un effet peut tomber
MOMENTS = ("beat", "downbeat", "drop", "section")
# Effets que le monteur sait poser (dans After Effects ET dans l'aperçu)
EFFECTS = ("zoom_punch", "shake", "flash", "blur_whip", "glow", "rgb_split")

BUILTIN_DIR = Path(__file__).resolve().parents[2] / "styles"


def user_dir() -> Path:
    d = Path(os.environ.get("EDITSENSEI_HOME", Path.home() / ".editsensei")) / "styles"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class CutRhythm:
    """Nombre de temps (beats) entre deux coupes, selon l'énergie de la musique."""
    beats_low: float = 4.0
    beats_mid: float = 2.0
    beats_high: float = 1.0
    on_beat: float = 0.95  # part des coupes calées pile sur un beat


@dataclass
class EffectRule:
    """Probabilité qu'un effet tombe sur chaque type d'instant + force/durée."""
    beat: float = 0.0
    downbeat: float = 0.0
    drop: float = 0.0
    section: float = 0.0
    strength: float = 0.5   # 0..1
    duration: float = 0.25  # secondes

    def rate(self, moment: str) -> float:
        return float(getattr(self, moment, 0.0))


@dataclass
class Look:
    contrast: float = 1.0      # 1 = neutre
    saturation: float = 1.0
    black_bars: bool = False   # bandes cinéma 2.39:1
    vignette: float = 0.0      # 0..1


@dataclass
class SpeedRules:
    slowmo_on_drop: bool = False
    slowmo_factor: float = 0.5   # 0.5 = deux fois plus lent
    slowmo_beats: float = 2.0
    speedup_low_energy: float = 1.0  # >1 accélère les passages calmes


@dataclass
class StyleModel:
    name: str
    description: str = ""
    source: str = "preset"   # preset | video | observed | mixed
    cut: CutRhythm = field(default_factory=CutRhythm)
    effects: dict[str, EffectRule] = field(default_factory=dict)
    look: Look = field(default_factory=Look)
    speed: SpeedRules = field(default_factory=SpeedRules)
    fade_in: float = 0.3
    fade_out: float = 0.6
    examples: int = 0        # nombre d'exemples appris (poids de la mémoire)
    tags: list[str] = field(default_factory=list)

    # ── accès ─────────────────────────────────────────────
    def rule(self, effect: str) -> EffectRule:
        return self.effects.get(effect) or EffectRule()

    @property
    def slug(self) -> str:
        return slugify(self.name)

    # ── (dé)sérialisation ─────────────────────────────────
    def to_dict(self) -> dict:
        d = asdict(self)
        d["effects"] = {k: asdict(v) for k, v in self.effects.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "StyleModel":
        effects = {k: EffectRule(**v) for k, v in (d.get("effects") or {}).items() if k in EFFECTS}
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            source=d.get("source", "preset"),
            cut=CutRhythm(**(d.get("cut") or {})),
            effects=effects,
            look=Look(**(d.get("look") or {})),
            speed=SpeedRules(**(d.get("speed") or {})),
            fade_in=d.get("fade_in", 0.3),
            fade_out=d.get("fade_out", 0.6),
            examples=d.get("examples", 0),
            tags=list(d.get("tags", [])),
        )

    def copy(self) -> "StyleModel":
        return StyleModel.from_dict(json.loads(json.dumps(self.to_dict())))

    # ── apprentissage ─────────────────────────────────────
    def absorb(self, other: "StyleModel", weight: float | None = None) -> "StyleModel":
        """Mélange `other` dans ce style (moyenne pondérée) : c'est ainsi qu'il apprend.

        Par défaut, le poids d'un nouvel exemple diminue avec l'expérience
        (1/(n+1)) : le style se stabilise au lieu d'être écrasé par la dernière vidéo.
        """
        w = weight if weight is not None else 1.0 / (self.examples + 1)
        w = max(0.0, min(1.0, w))
        out = self.copy()

        def mix(a: float, b: float) -> float:
            return a * (1 - w) + b * w

        for f in ("beats_low", "beats_mid", "beats_high", "on_beat"):
            setattr(out.cut, f, mix(getattr(self.cut, f), getattr(other.cut, f)))
        for eff in EFFECTS:
            a, b = self.rule(eff), other.rule(eff)
            out.effects[eff] = EffectRule(**{k: mix(getattr(a, k), getattr(b, k)) for k in asdict(a)})
        out.look.contrast = mix(self.look.contrast, other.look.contrast)
        out.look.saturation = mix(self.look.saturation, other.look.saturation)
        out.look.vignette = mix(self.look.vignette, other.look.vignette)
        out.look.black_bars = other.look.black_bars if w >= 0.5 else self.look.black_bars
        out.speed.slowmo_factor = mix(self.speed.slowmo_factor, other.speed.slowmo_factor)
        out.speed.slowmo_beats = mix(self.speed.slowmo_beats, other.speed.slowmo_beats)
        out.speed.slowmo_on_drop = other.speed.slowmo_on_drop if w >= 0.5 else self.speed.slowmo_on_drop
        out.fade_in = mix(self.fade_in, other.fade_in)
        out.fade_out = mix(self.fade_out, other.fade_out)
        out.examples = self.examples + max(1, other.examples)
        out.source = "mixed" if self.source != other.source else self.source
        out.tags = sorted(set(self.tags) | set(other.tags))
        return out.clamped()

    def clamped(self) -> "StyleModel":
        c = self.cut
        c.beats_low = clamp(c.beats_low, 0.5, 16)
        c.beats_mid = clamp(c.beats_mid, 0.5, 16)
        c.beats_high = clamp(c.beats_high, 0.25, 16)
        c.on_beat = clamp(c.on_beat, 0, 1)
        for r in self.effects.values():
            for m in MOMENTS:
                setattr(r, m, clamp(getattr(r, m), 0, 1))
            r.strength = clamp(r.strength, 0, 1)
            r.duration = clamp(r.duration, 0.04, 2.0)
        self.look.contrast = clamp(self.look.contrast, 0.6, 1.6)
        self.look.saturation = clamp(self.look.saturation, 0.0, 2.0)
        self.look.vignette = clamp(self.look.vignette, 0, 1)
        self.speed.slowmo_factor = clamp(self.speed.slowmo_factor, 0.2, 1.0)
        self.speed.slowmo_beats = clamp(self.speed.slowmo_beats, 0.5, 8)
        self.speed.speedup_low_energy = clamp(self.speed.speedup_low_energy, 1.0, 3.0)
        self.fade_in = clamp(self.fade_in, 0, 3)
        self.fade_out = clamp(self.fade_out, 0, 3)
        return self


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def slugify(name: str) -> str:
    s = name.lower()
    for a, b in (("éèêë", "e"), ("àâä", "a"), ("îï", "i"), ("ôö", "o"), ("ùûü", "u"), ("ç", "c")):
        for ch in a:
            s = s.replace(ch, b)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "style"


# ── bibliothèque de styles ────────────────────────────────

def list_styles() -> list[StyleModel]:
    styles: dict[str, StyleModel] = {}
    for d in (BUILTIN_DIR, user_dir()):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                s = StyleModel.from_dict(json.loads(p.read_text(encoding="utf-8")))
                styles[s.slug] = s  # un style appris peut remplacer un preset du même nom
            except (KeyError, TypeError, ValueError):
                continue
    return list(styles.values())


def get_style(name: str) -> StyleModel | None:
    wanted = slugify(name)
    for s in list_styles():
        if s.slug == wanted:
            return s
    # recherche souple : « anime » trouve « Anime Impact »
    for s in list_styles():
        if wanted and (wanted in s.slug or s.slug in wanted):
            return s
    return None


def save_style(style: StyleModel) -> Path:
    path = user_dir() / f"{style.slug}.json"
    path.write_text(json.dumps(style.clamped().to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
