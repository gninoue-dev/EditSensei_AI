"""Serveur local du cerveau (http://127.0.0.1:8765) appelé par le panneau After Effects.

Lancer :  python -m editsensei.server     (ou scripts/start_brain.*)
"""

from __future__ import annotations

import logging
import os
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import __version__, llm
from .assistant import SESSIONS, handle
from .learn import learn_from_snapshot, learn_from_video
from .planner import EditPlan
from .preview import render_preview
from .style import list_styles

log = logging.getLogger("editsensei")
app = FastAPI(title="EditSensei Brain", version=__version__)
# le panneau CEP est une page locale (origine file:// ou null) : on n'écoute que 127.0.0.1
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatIn(BaseModel):
    message: str
    session: str | None = None
    project: dict | None = None


class LearnVideoIn(BaseModel):
    path: str
    name: str | None = None
    into: str | None = None


class ObserveIn(BaseModel):
    snapshot: dict | None = None


class PreviewIn(BaseModel):
    plan: dict
    height: int = 540


@app.exception_handler(Exception)
async def on_error(_, exc: Exception):
    log.error("Erreur : %s\n%s", exc, traceback.format_exc())
    return JSONResponse(status_code=500, content={"ok": False, "error": f"{type(exc).__name__} : {exc}"})


@app.get("/health")
def health():
    return {"ok": True, "version": __version__, "claude": llm.available(), "sessions": len(SESSIONS)}


@app.get("/styles")
def styles():
    return {"ok": True, "styles": [{"name": s.name, "description": s.description, "source": s.source,
                                    "examples": s.examples} for s in list_styles()]}


@app.post("/chat")
def chat(body: ChatIn):
    return {"ok": True, **handle(body.message, body.session, body.project)}


@app.post("/learn/video")
def learn_video(body: LearnVideoIn):
    style, report = learn_from_video(body.path, body.name, body.into)
    return {"ok": True, "style": style.name, "reply": report}


@app.post("/learn/observe")
def observe(body: ObserveIn):
    style, msg = learn_from_snapshot(body.snapshot or {})
    return {"ok": True, "learned": style is not None, "reply": msg}


@app.post("/preview")
def preview(body: PreviewIn):
    plan = EditPlan.from_dict(body.plan)
    out = Path(tempfile.gettempdir()) / f"editsensei-preview-{abs(hash(plan.name)) % 10_000}.mp4"
    render_preview(plan, out, height=body.height)
    return {"ok": True, "path": str(out)}


def main() -> None:
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    port = int(os.environ.get("EDITSENSEI_PORT", "8765"))
    print(f"🎬 EditSensei — cerveau prêt sur http://127.0.0.1:{port}  (Claude : {'oui' if llm.available() else 'non, mode local'})")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
