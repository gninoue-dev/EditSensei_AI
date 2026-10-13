"""Le chef d'orchestre de la conversation.

Reçoit un message + l'état du projet After Effects, décide quoi faire :
- répondre (aide, liste des styles, questions),
- monter / remonter (analyse → plan → le panneau construit la compo),
- apprendre d'une vidéo du projet,
- enregistrer un 👍 / 👎.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .audio import analyze_music
from .directives import Directives, describe, normalize, parse
from .footage import analyze_clip
from .learn import MY_STYLE, learn_from_feedback, learn_from_video
from .planner import EditPlan, plan_edit
from .style import get_style, list_styles

AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mxf", ".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Session:
    id: str
    directives: Directives = field(default_factory=Directives)
    style: str = "Anime"
    plan: EditPlan | None = None
    history: list[dict] = field(default_factory=list)   # pour Claude (optionnel)
    count: int = 0


SESSIONS: dict[str, Session] = {}


def get_session(sid: str | None) -> Session:
    if not sid or sid not in SESSIONS:
        sid = sid or uuid.uuid4().hex[:10]
        SESSIONS[sid] = Session(sid)
        mine = get_style(MY_STYLE)
        if mine and mine.examples >= 3:
            SESSIONS[sid].style = MY_STYLE  # assez d'exemples : on monte avec ton style par défaut
    return SESSIONS[sid]


# ── projet After Effects ──────────────────────────────────

def split_media(items: list[dict]) -> tuple[str | None, list[str]]:
    """Trouve la musique et les clips du projet (les éléments sélectionnés passent en priorité)."""
    usable = [i for i in items if i.get("path") and Path(i["path"]).exists()]
    audio = [i for i in usable if i.get("isAudio") or Path(i["path"]).suffix.lower() in AUDIO_EXT]
    video = [i for i in usable if i not in audio and (i.get("hasVideo", True)) and Path(i["path"]).suffix.lower() in VIDEO_EXT]
    sel_audio = [i for i in audio if i.get("selected")]
    sel_video = [i for i in video if i.get("selected")]
    music = (sel_audio or audio or [None])[0]
    clips = sel_video if len(sel_video) >= 2 else video
    return (music["path"] if music else None), [c["path"] for c in clips]


# ── messages types ────────────────────────────────────────

HELP = (
    "Je suis EditSensei 🎬. Importe tes clips et ta musique dans le projet, puis dis-moi par exemple :\n"
    "• « Fais un edit anime de 30 s en vertical, slow-mo au drop »\n"
    "• « Plus agressif », « moins de flashs », « sans shake », « texte \"ENY\" au drop »\n"
    "• « Une autre version », « style smooth », « bandes noires »\n"
    "• « Apprends le style de ref.mp4 » (une vidéo du projet) ou active le mode apprenti 👀\n"
    "Je coupe sur les beats, place les impacts sur les drops et je construis la compo pour toi."
)


def _is_greeting(t: str) -> bool:
    return bool(re.fullmatch(r"(salut|bonjour|bonsoir|yo|hello|hey|coucou|cc|slt)[ !.,]*(editsensei|sensei)?[ !.]*", t))


def handle(message: str, sid: str | None, project: dict | None) -> dict:
    s = get_session(sid)
    project = project or {}
    items = project.get("items", [])
    t = normalize(message)
    out: dict = {"session": s.id, "action": "none", "reply": "", "plan": None, "suggestions": []}

    # ── aide / salutations / styles
    if _is_greeting(t) or t in ("aide", "help", "?", "comment ca marche", "que sais tu faire"):
        out["reply"] = ("Salut ! 👋 " if _is_greeting(t) else "") + HELP
        out["suggestions"] = ["Fais un edit anime de 30 s", "Liste les styles", "Mode apprenti"]
        return out
    if re.search(r"\b(liste|quels?|montre)\b.*\bstyles?\b", t) or t in ("styles", "les styles"):
        lines = [f"• {st.name} — {st.description}" + (f" ({st.examples} exemples appris)" if st.source != "preset" else "")
                 for st in list_styles()]
        out["reply"] = "Voici les styles que je connais :\n" + "\n".join(lines)
        return out

    # ── apprendre d'une vidéo du projet : « apprends le style de ref.mp4 »
    if re.search(r"\b(apprends?|apprendre|etudie|analyse|copie|imite)\b", t) and re.search(r"\b(style|video|edit|montage|ca|cette)\b", t):
        target = _find_item(message, items)
        if not target:
            out["reply"] = ("Quelle vidéo dois-je étudier ? Importe-la dans le projet et sélectionne-la "
                            "dans le panneau Projet, ou écris son nom (ex. « apprends le style de ref.mp4 »).")
            return out
        into = MY_STYLE if re.search(r"\b(mon style|dans mon style|a mon style)\b", t) else None
        m = re.search(r"(?:appelle|nomme)(?:-le| le)?\s+[\"“«]?([^\"”»]+)", message, re.I)
        style, report = learn_from_video(target, name=(m.group(1).strip() if m else None), into=into)
        out.update(action="learned", reply=report + f"\nDis « monte avec le style {style.name} » pour l'utiliser.",
                   suggestions=[f"Monte avec le style {style.name}", "Liste les styles"])
        return out

    # ── 👍 / 👎
    if t in ("j'aime", "j aime", "parfait", "trop bien", "top", "👍", "c'est parfait", "genial", "nickel", "c'est bon"):
        return _feedback(s, True, out)
    if t in ("j'aime pas", "j aime pas", "nul", "bof", "👎", "c'est nul"):
        return _feedback(s, False, out)

    # ── consignes : Claude si disponible, sinon parseur local
    styles = [st.name for st in list_styles()]
    ai = llm.interpret(message, s.history, styles, _context(items, s)) if llm.available() else None
    if ai:
        ai_reply, d = ai
        local = parse(message)  # le parseur local reste prioritaire sur ce qu'il sait lire (durées, textes…)
        d = d.merged(local) if local.build else d
    else:
        ai_reply, d = "", parse(message)
    if not d.build:
        out["reply"] = ai_reply or ("Je n'ai pas compris ce que je dois changer 🤔 " + HELP.split("\n", 1)[1])
        _remember(s, message, out["reply"])
        return out

    s.directives = s.directives.merged(d)
    if d.style:
        found = get_style(d.style)
        if found:
            s.style = found.name

    music_path, clip_paths = split_media(items)
    if not clip_paths:
        out["reply"] = ("Je ne trouve aucun clip vidéo dans le projet 📂. Importe tes vidéos (Fichier › Importer) "
                        "puis redemande-moi. Astuce : sélectionne-les pour que je n'utilise qu'elles.")
        return out
    style = get_style(s.style) or get_style("Anime")
    music = analyze_music(music_path) if music_path else None
    clips = [analyze_clip(p) for p in clip_paths]
    s.count += 1
    plan = plan_edit(music, clips, style, s.directives, music_path, name=f"EditSensei {s.count:02d}")
    s.plan = plan
    s.directives.build = False
    out.update(action="build", plan=plan.to_dict())
    lead = (ai_reply + "\n") if ai_reply else ""
    if not music_path:
        lead += "⚠️ Pas de musique dans le projet : j'ai monté sur un rythme de 120 BPM. Importe un son pour caler les coupes dessus.\n"
    out["reply"] = lead + plan.summary
    out["suggestions"] = ["Plus agressif", "Une autre version", "Slow-mo au drop", "J'aime 👍"]
    _remember(s, message, out["reply"])
    return out


def _feedback(s: Session, liked: bool, out: dict) -> dict:
    if not s.plan:
        out["reply"] = "Monte d'abord quelque chose avec moi, puis dis-moi si ça te plaît 🙂"
        return out
    music = analyze_music(s.plan.music) if s.plan.music else None
    if music is None:
        out["reply"] = "Merci ! (je n'apprends le rythme que sur des montages avec musique)"
        return out
    out["reply"] = learn_from_feedback(s.plan.to_dict(), music, liked)
    out["action"] = "learned" if liked else "none"
    return out


def _find_item(message: str, items: list[dict]) -> str | None:
    t = normalize(message)
    vids = [i for i in items if i.get("path") and Path(i["path"]).suffix.lower() in VIDEO_EXT and Path(i["path"]).exists()]
    for i in vids:
        stem = normalize(Path(i["path"]).stem)
        if stem and (normalize(i.get("name", "")) in t or stem in t):
            return i["path"]
    sel = [i for i in vids if i.get("selected")]
    if len(sel) == 1:
        return sel[0]["path"]
    # un chemin complet collé dans le message
    m = re.search(r"([A-Za-z]:\\[^\"\n]+\.\w{2,4}|/[^\"\n]+\.\w{2,4})", message)
    if m and Path(m.group(1)).exists():
        return m.group(1)
    return None


def _context(items: list[dict], s: Session) -> str:
    music, clips = split_media(items)
    return (f"{len(clips)} clip(s), musique : {Path(music).name if music else 'aucune'}, style actuel : {s.style}, "
            f"consignes en cours : {', '.join(describe(s.directives)) or 'aucune'}.")


def _remember(s: Session, user: str, reply: str) -> None:
    s.history += [{"role": "user", "content": user}, {"role": "assistant", "content": reply}]
    s.history = s.history[-20:]
