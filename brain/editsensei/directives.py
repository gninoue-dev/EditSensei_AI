"""Comprendre les consignes de montage en français, sans aucune API.

« fais-moi un edit anime de 30s en vertical, slow-mo au drop, sans flash,
  plus de shake, texte "ENY" au début » → `Directives`.

Le parseur est volontairement tolérant (fautes, abréviations, anglais courant
dans le milieu de l'edit : « shake », « drop », « smooth »…).
Les directives se CUMULENT au fil de la conversation : « plus agressif » deux
fois de suite rend le montage encore plus nerveux.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from .style import EFFECTS, get_style, list_styles

ASPECTS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}


@dataclass
class Directives:
    style: str | None = None
    duration: float | None = None          # secondes voulues
    music_start: float | None = None       # départ dans la musique (s)
    aspect: str | None = None              # 16:9 | 9:16 | 1:1 | 4:5
    fps: float | None = None
    energy: float = 0.0                    # -1 (calme) … +1 (nerveux)
    effect_gain: dict[str, float] = field(default_factory=dict)  # effet → multiplicateur
    disabled: list[str] = field(default_factory=list)
    slowmo_on_drop: bool | None = None
    black_bars: bool | None = None
    black_white: bool = False
    texts: list[dict] = field(default_factory=list)  # {"text", "at": "start"|"drop"|"end"|secondes}
    clip_order: list[int] = field(default_factory=list)  # clips à mettre en premier (index 1..n)
    seed: int = 7
    build: bool = False   # l'utilisateur demande de (re)monter

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "Directives":
        if not d:
            return cls()
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def merged(self, other: "Directives") -> "Directives":
        """Applique une nouvelle consigne par-dessus les précédentes."""
        out = Directives.from_dict(self.to_dict())
        for k in ("style", "duration", "music_start", "aspect", "fps", "slowmo_on_drop", "black_bars"):
            v = getattr(other, k)
            if v is not None:
                setattr(out, k, v)
        out.energy = max(-1.0, min(1.0, self.energy + other.energy))
        for eff, g in other.effect_gain.items():
            out.effect_gain[eff] = max(0.0, min(4.0, out.effect_gain.get(eff, 1.0) * g))
            if eff in out.disabled and g > 0:
                out.disabled.remove(eff)
        for eff in other.disabled:
            if eff not in out.disabled:
                out.disabled.append(eff)
        out.black_white = other.black_white or self.black_white
        if other.texts:
            out.texts = self.texts + other.texts
        if other.clip_order:
            out.clip_order = other.clip_order
        if other.seed != 7:
            out.seed = other.seed
        out.build = other.build
        return out


# ── vocabulaire ───────────────────────────────────────────

EFFECT_WORDS = {
    "zoom_punch": ["zoom", "zooms", "punch", "impact", "impacts"],
    "shake": ["shake", "shakes", "tremblement", "tremblements", "secousse", "secousses", "camera shake", "vibration"],
    "flash": ["flash", "flashs", "flashes", "flash blanc", "eclair", "eclairs"],
    "blur_whip": ["blur", "flou", "flous", "whip", "transition", "transitions", "swipe"],
    "glow": ["glow", "lueur", "lumineux", "brillance", "bloom"],
    "rgb_split": ["rgb", "rgb split", "chromatique", "aberration", "glitch", "decalage couleur"],
}

MORE = ["plus de", "encore plus de", "beaucoup de", "rajoute", "ajoute", "ajoutes", "mets", "met", "mettre", "add", "more", "davantage de", "un max de"]
LESS = ["moins de", "un peu moins de", "reduis", "diminue", "less"]
NONE = ["sans", "pas de", "aucun", "aucune", "enleve", "enlever", "retire", "supprime", "vire", "no"]

BUILD_WORDS = ["monte", "monter", "fais", "fait", "faire", "cree", "creer", "genere", "edit", "montage",
               "refais", "recommence", "relance", "go", "vas-y", "vas y", "lance", "applique", "make", "build"]

MORE_ENERGY = ["plus agressif", "plus nerveux", "plus energique", "plus dynamique", "plus rapide", "plus hype",
               "plus intense", "plus violent", "plus fort", "plus de peps", "faster", "plus d'energie", "plus dur"]
LESS_ENERGY = ["plus doux", "plus calme", "plus lent", "plus smooth", "plus pose", "moins agressif",
               "moins nerveux", "plus tranquille", "plus soft", "slower", "plus leger", "moins rapide"]


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'")
    return re.sub(r"\s+", " ", t).strip()


def parse(message: str) -> Directives:
    raw = message
    t = normalize(message)
    d = Directives()

    # textes entre guillemets : « texte "ENY" au début »
    for m in re.finditer(r"[\"“«]\s*([^\"”»]{1,40}?)\s*[\"”»]", raw):
        txt = m.group(1).strip()
        after = normalize(raw[m.end():m.end() + 30])
        before = normalize(raw[max(0, m.start() - 30):m.start()])
        ctx = before + " " + after
        at: str | float = "start"
        if "drop" in ctx:
            at = "drop"
        elif "fin" in ctx or "end" in ctx:
            at = "end"
        else:
            sec = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:s|sec|secondes?)\b", after)
            if sec:
                at = float(sec.group(1).replace(",", "."))
        d.texts.append({"text": txt, "at": at})
    t_wo_quotes = re.sub(r"[\"“«][^\"”»]*[\"”»]", " ", t)

    # style demandé : nom d'un style connu (presets + styles appris)
    for s in sorted(list_styles(), key=lambda s: -len(s.slug)):
        words = {normalize(s.name), s.slug.replace("-", " ")} | {normalize(tag) for tag in s.tags}
        if any(re.search(rf"\b{re.escape(w)}\b", t_wo_quotes) for w in words if len(w) >= 3):
            d.style = s.name
            break
    if d.style is None and re.search(r"\b(mon style|mon propre style|comme moi|a ma facon|mes habitudes)\b", t_wo_quotes):
        mine = get_style("Mon style")
        d.style = mine.name if mine else None

    # durée : « 30s », « 30 secondes », « 1 min », « 1:15 »
    m = re.search(r"\b(\d+)\s*(?:min|minutes?)\s*(\d+)?\s*(?:s|sec)?\b", t_wo_quotes)
    if m and not re.search(r"\b(?:a|à|depuis|commence|partir)\s+(?:de\s+)?" + m.group(0), t_wo_quotes):
        d.duration = int(m.group(1)) * 60 + int(m.group(2) or 0)
    else:
        m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:s|sec|secs|secondes?)\b", t_wo_quotes)
        if m and not re.search(r"(?:a|depuis|partir de|commence a)\s+" + re.escape(m.group(0)), t_wo_quotes):
            d.duration = float(m.group(1).replace(",", "."))

    # départ dans la musique : « à partir de 0:45 », « commence à 45s »
    m = re.search(r"(?:a partir de|depuis|commence a|commencer a|debut a|start at)\s+(\d+):(\d{2})", t_wo_quotes)
    if m:
        d.music_start = int(m.group(1)) * 60 + int(m.group(2))
    else:
        m = re.search(r"(?:a partir de|depuis|commence a|commencer a|debut a|start at)\s+(\d+(?:[.,]\d+)?)\s*(?:s|sec|secondes?)", t_wo_quotes)
        if m:
            d.music_start = float(m.group(1).replace(",", "."))
    if re.search(r"\b(au|sur le|a partir du)\s+drop\b", t_wo_quotes) and re.search(r"\b(commence|demarre|start)", t_wo_quotes):
        d.music_start = -1.0  # convention : commencer juste avant le drop

    # format
    if re.search(r"\b(vertical|tiktok|reel|reels|short|shorts|9[:/x ]16|story|portrait)\b", t_wo_quotes):
        d.aspect = "9:16"
    elif re.search(r"\b(carre|square|1[:/x ]1)\b", t_wo_quotes):
        d.aspect = "1:1"
    elif re.search(r"\b(4[:/x ]5|feed instagram)\b", t_wo_quotes):
        d.aspect = "4:5"
    elif re.search(r"\b(horizontal|paysage|youtube|16[:/x ]9|landscape)\b", t_wo_quotes):
        d.aspect = "16:9"
    m = re.search(r"\b(24|25|30|50|60)\s*(?:fps|ips|images par seconde)\b", t_wo_quotes)
    if m:
        d.fps = float(m.group(1))

    # énergie globale
    if any(p in t_wo_quotes for p in MORE_ENERGY):
        d.energy += 0.35
    if any(p in t_wo_quotes for p in LESS_ENERGY):
        d.energy -= 0.35

    # effets : plus / moins / sans
    for eff, words in EFFECT_WORDS.items():
        for w in words:
            for m in re.finditer(rf"\b{re.escape(w)}\b", t_wo_quotes):
                before = t_wo_quotes[max(0, m.start() - 22):m.start()]
                if any(re.search(rf"\b{re.escape(n)}\s*(?:de |d')?(?:\w+ )?$", before) for n in NONE):
                    if eff not in d.disabled:
                        d.disabled.append(eff)
                elif any(l in before for l in LESS):
                    d.effect_gain[eff] = 0.5
                elif any(mo in before for mo in MORE) or "plus" in before.split()[-3:]:
                    d.effect_gain[eff] = 1.8

    # ralenti
    if re.search(r"\b(slow[ -]?mo|slow[ -]?motion|ralenti|ralentis|ralentir)\b", t_wo_quotes):
        d.slowmo_on_drop = not re.search(r"\b(sans|pas de|enleve|retire)\s+(?:de\s+|le\s+|les\s+)?(slow|ralenti)", t_wo_quotes)

    # look
    if re.search(r"\b(bandes? noires?|cinema|cinematique|letterbox|scope)\b", t_wo_quotes):
        d.black_bars = not re.search(r"\b(sans|pas de|enleve|retire)\s+(?:les\s+)?bandes?", t_wo_quotes)
    if re.search(r"\b(noir et blanc|black and white|n&b|monochrome)\b", t_wo_quotes):
        d.black_white = True

    # ordre des clips : « commence par le clip 3 »
    m = re.search(r"(?:commence|ouvre|demarre)\s+(?:par|avec)\s+(?:le\s+)?clip\s*(\d+)", t_wo_quotes)
    if m:
        d.clip_order = [int(m.group(1))]

    # variation : « une autre version », « refais différemment »
    if re.search(r"\b(autre version|differemment|different|une autre|varie|variante|nouvelle version|remix)\b", t_wo_quotes):
        d.seed = abs(hash(t_wo_quotes)) % 10_000 + 8

    d.build = bool(
        d.style or d.duration or d.aspect or d.texts or d.energy or d.effect_gain or d.disabled
        or d.slowmo_on_drop is not None or d.black_bars is not None or d.black_white or d.seed != 7
        or any(re.search(rf"\b{re.escape(w)}\b", t_wo_quotes) for w in BUILD_WORDS)
    )
    return d


def describe(d: Directives) -> list[str]:
    """Résumé lisible de ce qui a été compris (pour la réponse dans le chat)."""
    out = []
    if d.style:
        out.append(f"style « {d.style} »")
    if d.duration:
        out.append(f"{d.duration:g} s")
    if d.aspect:
        out.append({"9:16": "format vertical 9:16", "1:1": "format carré", "4:5": "format 4:5", "16:9": "format 16:9"}[d.aspect])
    if d.energy > 0.05:
        out.append("plus nerveux")
    elif d.energy < -0.05:
        out.append("plus calme")
    names = {"zoom_punch": "zooms", "shake": "shakes", "flash": "flashs", "blur_whip": "transitions floues",
             "glow": "glow", "rgb_split": "RGB split"}
    for eff, g in d.effect_gain.items():
        if eff in d.disabled:
            continue
        out.append(("plus de " if g > 1 else "moins de ") + names.get(eff, eff))
    for eff in d.disabled:
        out.append("sans " + names.get(eff, eff))
    if d.slowmo_on_drop is True:
        out.append("ralenti au drop")
    elif d.slowmo_on_drop is False:
        out.append("sans ralenti")
    if d.black_bars is True:
        out.append("bandes cinéma")
    elif d.black_bars is False:
        out.append("sans bandes cinéma")
    if d.black_white:
        out.append("noir et blanc")
    for tx in d.texts:
        out.append(f"texte « {tx['text']} »")
    return out


__all__ = ["Directives", "parse", "describe", "ASPECTS", "EFFECTS"]
