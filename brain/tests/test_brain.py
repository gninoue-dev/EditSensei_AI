"""Tests du cerveau d'EditSensei sur des médias synthétiques (aucun fichier à fournir).

Lancer :  cd brain && .venv/bin/python -m pytest -q
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from media import make_clip, make_track

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    import os
    os.environ["EDITSENSEI_HOME"] = str(d / "home")
    os.environ["EDITSENSEI_NO_LLM"] = "1"
    info = make_track(d / "track.wav", bpm=128, bars_intro=8, bars_drop=8)
    clips = [make_clip(d / f"c{i}.mp4", k, s) for i, (k, s) in
             enumerate([("testsrc2", 8), ("mandel", 10), ("life", 6), ("cells", 7)])]
    return {"dir": d, "track": d / "track.wav", "info": info, "clips": clips}


# ── musique ───────────────────────────────────────────────

def test_music_tempo_beats_and_drop(media):
    from editsensei.audio import analyze_music
    mm = analyze_music(media["track"], use_cache=False)
    assert abs(mm.tempo - 128) < 4
    assert len(mm.beats) > 50
    assert mm.drops, "le drop doit être détecté"
    assert abs(mm.drops[0] - media["info"]["drop"]) < 0.15
    # l'énergie après le drop est plus forte qu'avant
    i = mm.beat_index_at(media["info"]["drop"])
    assert np.mean(mm.energy[i:i + 8]) > np.mean(mm.energy[max(0, i - 8):i]) + 0.3


# ── consignes ─────────────────────────────────────────────

@pytest.mark.parametrize("msg,check", [
    ('Fais un edit anime de 30s en vertical, slow-mo au drop, texte "ENY" au drop',
     lambda d: d.style == "Anime" and d.duration == 30 and d.aspect == "9:16" and d.slowmo_on_drop
     and d.texts == [{"text": "ENY", "at": "drop"}]),
    ("plus agressif", lambda d: d.energy > 0 and d.build),
    ("sans flash et moins de zooms", lambda d: "flash" in d.disabled and d.effect_gain.get("zoom_punch") == 0.5),
    ("commence à partir de 0:45, 1 min", lambda d: d.music_start == 45 and d.duration == 60),
    ("enlève les bandes noires", lambda d: d.black_bars is False),
    ("salut ça va ?", lambda d: not d.build),
])
def test_directives(msg, check):
    from editsensei.directives import parse
    assert check(parse(msg))


def test_directives_accumulate():
    from editsensei.directives import Directives, parse
    d = Directives().merged(parse("plus de shake")).merged(parse("encore plus de shake"))
    assert d.effect_gain["shake"] > 2


# ── monteur ───────────────────────────────────────────────

def _plan(media, message="edit anime 20s slow-mo au drop", style="Anime"):
    from editsensei.audio import analyze_music
    from editsensei.directives import parse
    from editsensei.footage import analyze_clip
    from editsensei.planner import plan_edit
    from editsensei.style import get_style
    mm = analyze_music(media["track"])
    clips = [analyze_clip(p) for p in media["clips"]]
    return mm, clips, plan_edit(mm, clips, get_style(style), parse(message), str(media["track"]))


def test_plan_is_continuous_and_valid(media):
    mm, clips, plan = _plan(media)
    assert plan.duration == pytest.approx(20, abs=0.01)
    assert plan.segments[0].t_in == 0
    assert plan.segments[-1].t_out == pytest.approx(plan.duration, abs=1e-3)
    for a, b in zip(plan.segments, plan.segments[1:]):
        assert a.t_out == pytest.approx(b.t_in, abs=1e-6), "pas de trou entre les plans"
    for s in plan.segments:
        assert 0 <= s.src_in < s.src_out <= clips[s.clip].duration + 1e-3
        assert s.t_out > s.t_in


def test_cuts_land_on_beats_and_drop_gets_impact(media):
    mm, _, plan = _plan(media)
    beats = np.asarray(mm.beats)
    half = np.concatenate([beats, (beats[:-1] + beats[1:]) / 2])
    for s in plan.segments[1:]:
        t = s.t_in + plan.music_start
        assert np.min(np.abs(half - t)) < 0.03, f"coupe hors temps à {t:.2f}"
    drop = mm.drops[0] - plan.music_start
    assert any(abs(s.t_in - drop) < 0.05 for s in plan.segments), "un plan démarre sur le drop"
    assert any(s.speed < 1 for s in plan.segments if abs(s.t_in - drop) < 0.05), "ralenti au drop"
    types_at_drop = {e.type for e in plan.effects if abs(e.t - drop) < 0.05}
    assert {"zoom_punch", "flash"} & types_at_drop


def test_disabled_effects_are_absent(media):
    _, _, plan = _plan(media, "edit 20s sans flash sans shake")
    assert not [e for e in plan.effects if e.type in ("flash", "shake")]


def test_energy_changes_cut_rhythm(media):
    _, _, calm = _plan(media, "edit 20s plus calme", style="Smooth")
    _, _, hype = _plan(media, "edit 20s plus agressif", style="Smooth")
    assert len(hype.segments) > len(calm.segments)


# ── aperçu + apprentissage en boucle fermée ───────────────

def test_preview_and_learn_back(media):
    from editsensei.learn import detect_events, learn_from_video
    from editsensei.preview import render_preview
    _, _, plan = _plan(media, "edit 20s", style="Gaming")
    out = render_preview(plan, media["dir"] / "ref.mp4", height=360)
    assert out.exists() and out.stat().st_size > 50_000
    det = detect_events(out)
    true_cuts = [s.t_in for s in plan.segments[1:]]
    found = sum(1 for c in true_cuts if any(abs(c - x) < 0.1 for x in det["cuts"]))
    assert found / len(true_cuts) > 0.9, "presque toutes les coupes sont retrouvées"
    style, report = learn_from_video(out, name="Test")
    assert "coupes" in report
    assert 0.5 <= style.cut.beats_high <= 2.0


def test_observe_mode_learns_from_snapshot(media):
    from editsensei.learn import MY_STYLE, learn_from_snapshot
    from editsensei.style import get_style
    mm, _, _ = _plan(media)
    beats = mm.beats
    layers = [{"name": f"clip{i}", "inPoint": beats[i * 2], "outPoint": beats[i * 2 + 2], "startTime": 0,
               "hasVideo": True, "source": str(media["clips"][i % 4]), "effects": [],
               "keys": {"scale": [beats[i * 2], beats[i * 2] + 0.1, beats[i * 2] + 0.3]} if i % 2 else {}}
              for i in range(12)]
    snap = {"compId": 7, "name": "Mon edit", "duration": beats[24], "music": {"path": str(media["track"]), "startTime": 0},
            "layers": layers}
    style, msg = learn_from_snapshot(snap)
    assert style is not None and "Mon style" in msg
    assert get_style(MY_STYLE) is not None
    assert learn_from_snapshot(snap)[0] is None, "la même compo n'est pas réapprise deux fois"


# ── conversation (API) ────────────────────────────────────

def test_chat_flow(media):
    from fastapi.testclient import TestClient
    from editsensei.server import app
    c = TestClient(app)
    items = [{"name": p.name, "path": str(p), "hasVideo": True} for p in media["clips"]]
    items.append({"name": "track.wav", "path": str(media["track"]), "isAudio": True, "hasVideo": False})
    r = c.post("/chat", json={"message": "Fais un edit anime de 15s en vertical", "project": {"items": items}}).json()
    assert r["ok"] and r["action"] == "build"
    assert r["plan"]["width"] == 1080 and r["plan"]["height"] == 1920
    r2 = c.post("/chat", json={"message": "sans flash", "session": r["session"], "project": {"items": items}}).json()
    assert r2["action"] == "build"
    assert not [e for e in r2["plan"]["effects"] if e["type"] == "flash"]
    assert r2["plan"]["height"] == 1920, "les consignes précédentes restent actives"
    r3 = c.post("/chat", json={"message": "fais un edit", "project": {"items": []}}).json()
    assert r3["action"] == "none" and "clip" in r3["reply"]


# ── After Effects (simulé) ────────────────────────────────

@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js requis pour simuler After Effects")
def test_jsx_builds_comp_in_mock_after_effects(media):
    _, _, plan = _plan(media, 'edit 20s texte "ENY" au drop bandes noires')
    plan_file = media["dir"] / "plan.json"
    plan_file.write_text(json.dumps(plan.to_dict()))
    out = subprocess.run(["node", str(ROOT / "ae-panel/tests/mock_ae.js"), str(plan_file),
                          *[str(p) for p in media["clips"]], str(media["track"])],
                         capture_output=True, text=True, check=True).stdout
    res = json.loads(out)
    assert res["ok"] and res["layers"] > len(plan.segments)
    assert res["keyframes"] > 10
