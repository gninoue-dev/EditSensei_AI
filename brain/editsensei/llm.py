"""Conversation enrichie par Claude — OPTIONNELLE.

Sans clé, EditSensei comprend déjà tes consignes en local (directives.py).
Avec une clé Anthropic (variable ANTHROPIC_API_KEY, ou `ant auth login`), Claude :
- comprend les demandes plus libres (« rends ça plus émouvant vers la fin »),
- répond naturellement aux questions sur le montage,
- et traduit tout ça en directives JSON que le monteur applique.

Claude ne touche jamais directement à After Effects : il propose des directives,
le planificateur local décide et construit. Si l'appel échoue, on retombe
silencieusement sur le parseur local.
"""

from __future__ import annotations

import json
import logging
import os

from .directives import EFFECTS, Directives

log = logging.getLogger("editsensei.llm")

MODEL = os.environ.get("EDITSENSEI_CLAUDE_MODEL", "claude-opus-5-5")

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
- Les directives sont CUMULATIVES : n'indique que ce que le DERNIER message change.
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
                 "slowmo_on_drop", "black_bars", "texts"],
    "additionalProperties": False,
}

_client = None


def available() -> bool:
    """Claude est utilisable si le SDK est installé et qu'une clé est configurée."""
    if os.environ.get("EDITSENSEI_NO_LLM"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("ANTHROPIC_PROFILE") or os.path.isdir(os.path.expanduser("~/.config/anthropic")))


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def interpret(message: str, history: list[dict], styles: list[str], context: str) -> tuple[str, Directives] | None:
    """Demande à Claude de traduire le message en directives. None si indisponible ou en cas d'échec."""
    if not available():
        return None
    import anthropic

    messages = list(history[-12:]) + [{
        "role": "user",
        "content": f"Styles disponibles : {', '.join(styles)}.\nContexte du projet : {context}\n\nMessage : {message}",
    }]
    try:
        response = _get_client().beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM,
            messages=messages,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            # si un filtre de sécurité refuse la demande, l'API bascule seule sur un autre modèle
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        log.warning("Clé Anthropic invalide : retour au mode local.")
        return None
    except anthropic.RateLimitError:
        log.warning("Limite de requêtes Claude atteinte : retour au mode local.")
        return None
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        log.warning("Claude indisponible (%s) : retour au mode local.", e)
        return None

    if response.stop_reason == "refusal":
        return None
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data.get("reply", ""), to_directives(data)


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
    for t in data.get("texts", []):
        at = t.get("at", "start")
        try:
            at = float(at)
        except (TypeError, ValueError):
            at = at if at in ("start", "drop", "end") else "start"
        d.texts.append({"text": t.get("text", ""), "at": at})
    return d
