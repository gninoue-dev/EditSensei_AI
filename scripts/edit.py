"""Monter sans After Effects, en ligne de commande (aperçu MP4).

  brain/.venv/bin/python scripts/edit.py musique.mp3 clip1.mp4 clip2.mp4 … -m "edit anime 30s slow-mo au drop" -o edit.mp4
  brain/.venv/bin/python scripts/edit.py --learn reference.mp4 --name "Mon AMV"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "brain"))

from editsensei.audio import analyze_music  # noqa: E402
from editsensei.directives import parse  # noqa: E402
from editsensei.footage import analyze_clip  # noqa: E402
from editsensei.learn import learn_from_video  # noqa: E402
from editsensei.planner import plan_edit  # noqa: E402
from editsensei.preview import render_preview  # noqa: E402
from editsensei.style import get_style  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="EditSensei en ligne de commande")
    ap.add_argument("music", nargs="?", help="fichier audio")
    ap.add_argument("clips", nargs="*", help="clips vidéo")
    ap.add_argument("-m", "--message", default="fais un edit", help="consigne en français")
    ap.add_argument("-s", "--style", default=None)
    ap.add_argument("-o", "--out", default="editsensei.mp4")
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--learn", help="vidéo de référence dont apprendre le style")
    ap.add_argument("--name", help="nom du style appris")
    a = ap.parse_args()

    if a.learn:
        _, report = learn_from_video(a.learn, a.name)
        print(report)
        return
    if not a.music or not a.clips:
        ap.error("donne une musique et au moins un clip")
    d = parse(a.message)
    style = get_style(a.style or d.style or "Anime")
    plan = plan_edit(analyze_music(a.music), [analyze_clip(c) for c in a.clips], style, d, a.music)
    print(plan.summary)
    render_preview(plan, a.out, height=a.height, progress=lambda p: print(f"\r  rendu {p * 100:3.0f} %", end=""))
    print(f"\n✅ {a.out}")


if __name__ == "__main__":
    main()
