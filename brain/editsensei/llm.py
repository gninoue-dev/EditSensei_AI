"""La conversation pilotée par l'IA connectée (Claude, Gemini, ChatGPT, DeepSeek ou Copilot).

L'IA est le moteur de la conversation : elle comprend les demandes libres
(« rends ça plus émouvant vers la fin »), répond aux questions sur le montage
et traduit tout ça en directives JSON que le monteur applique.
Le compte se branche dans les réglages du panneau (voir providers.py).

L'IA ne touche jamais directement à After Effects : elle propose des directives,
le planificateur local décide et construit. Sans IA connectée, ou si l'appel
échoue, EditSensei retombe sur son parseur local (directives.py).
"""

from __future__ import annotations

import json
import logging

from . import providers
from .directives import EFFECTS, Directives

log = logging.getLogger("editsensei.llm")

SYSTEM = """Tu es EditSensei, un assistant de montage vidéo intégré à After Effects, spécialisé dans les edits
rythmés (AMV, edits TikTok, gaming, cinématique). Tu parles français, simplement et avec enthousiasme.

Tu ne montes pas toi-même : tu traduis chaque message de l'utilisateur en DIRECTIVES pour le moteur de montage,
et tu écris une courte réponse (1 à 3 phrases).

Règles des directives :
- "build" = true si l'utilisateur veut créer ou modifier un montage ; false pour une simple question / discussion.
- "style" : un des styles disponibles (liste fournie) ou null pour garder le style actuel.
- "duration" en secondes ou null ; "aspect" parmi "16:9", "9:16", "1:1", "4:5" ou null.
- "energy" entre -1 (beaucoup plus calme) et 1 (beaucoup plus nerveux) ; 0 si non mentionné.
- "more" / "less" / "disable" : listes d'effets parmi zoom_punch, shake, flash, blur_whip, glow, rgb_split.
- "slowmo_on_drop", "black_bars" : true / false / null (null = ne pas changer).
- "texts" : titres à afficher, "at" vaut "start", "drop", "end" ou un nombre de secondes.
- "subtitles" : true pour ajouter les paroles / sous-titres automatiques, false pour les retirer, null sinon.
- Les directives sont CUMULATIVES : n'indique que ce que le DERNIER message change.

Réponds UNIQUEMENT avec un objet JSON valide (aucun texte autour, pas de bloc de code) conforme à ce schéma :
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "build": {"type": "boolean"},
        "style": {"type": ["string", "null"]},
        "duration": {"type": ["number", "null"]},
        "aspect": {"type": ["string", "null"], "enum": ["16:9", "9:16", "1:1", "4:5", None]},
        "energy": {"type": "number"},
        "more": {"type": "array", "items": {"type": "string", "enum": list(EFFECTS)}},
        "less": {"type": "array", "items": {"type": "string", "enum": list(EFFECTS)}},
        "disable": {"type": "array", "items": {"type": "string", "enum": list(EFFECTS)}},
        "slowmo_on_drop": {"type": ["boolean", "null"]},
        "black_bars": {"type": ["boolean", "null"]},
        "subtitles": {"type": ["boolean", "null"]},
        "texts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "at": {"type": "string"}},
                "required": ["text", "at"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reply", "build", "style", "duration", "aspect", "energy", "more", "less", "disable",
                 "slowmo_on_drop", "black_bars", "subtitles", "texts"],
    "additionalProperties": False,
}

PROMPT = SYSTEM + json.dumps(SCHEMA, ensure_ascii=False)


def available() -> bool:
    """Une IA est connectée et prête."""
    return providers.active() is not None


def interpret(message: str, history: list[dict], styles: list[str], context: str) -> tuple[str, Directives] | None:
    """Demande à l'IA de traduire le message en directives. None si indisponible ou en cas d'échec."""
    if not available():
        return None
    messages = list(history[-12:]) + [{
        "role": "user",
        "content": f"Styles disponibles : {', '.join(styles)}.\nContexte du projet : {context}\n\nMessage : {message}",
    }]
    try:
        data = providers.extract_json(providers.ask(PROMPT, messages))
    except providers.AIError as e:
        log.warning("IA indisponible (%s) : retour au mode local.", e)
        return None
    return str(data.get("reply", "")), to_directives(data)


def to_directives(data: dict) -> Directives:
    d = Directives()
    d.build = bool(data.get("build"))
    d.style = data.get("style") or None
    d.duration = data.get("duration") or None
    d.aspect = data.get("aspect") or None
    d.energy = float(max(-1.0, min(1.0, data.get("energy") or 0.0)))
    for eff in data.get("more", []):
        if eff in EFFECTS:
            d.effect_gain[eff] = 1.8
    for eff in data.get("less", []):
        if eff in EFFECTS:
            d.effect_gain[eff] = 0.5
    d.disabled = [e for e in data.get("disable", []) if e in EFFECTS]
    d.slowmo_on_drop = data.get("slowmo_on_drop")
    d.black_bars = data.get("black_bars")
    d.subtitles = data.get("subtitles")
    for t in data.get("texts", []):
        at = t.get("at", "start")
        try:
            at = float(at)
        except (TypeError, ValueError):
            at = at if at in ("start", "drop", "end") else "start"
        d.texts.append({"text": t.get("text", ""), "at": at})
    return d
