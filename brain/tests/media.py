"""Médias de test synthétiques (musique avec un drop, clips vidéo animés)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

SR = 22050


def make_track(path: Path, bpm: float = 128.0, bars_intro: int = 8, bars_drop: int = 8) -> dict:
    """Intro calme (kick doux + hi-hat) puis DROP (kick fort + basse) au début de la mesure bars_intro."""
    beat = 60.0 / bpm
    total_beats = 4 * (bars_intro + bars_drop)
    n = int(SR * beat * total_beats) + SR
    y = np.zeros(n, dtype=np.float32)
    t = np.arange(int(SR * 0.25)) / SR
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 18)
    hat = np.random.default_rng(1).normal(0, 1, int(SR * 0.04)) * np.exp(-np.arange(int(SR * 0.04)) / SR * 120)
    for b in range(total_beats):
        i = int(b * beat * SR)
        drop = b >= 4 * bars_intro
        amp = 0.9 if drop else 0.25
        y[i:i + len(kick)] += amp * kick[: n - i]
        j = int((b + 0.5) * beat * SR)
        y[j:j + len(hat)] += (0.25 if drop else 0.08) * hat[: max(0, n - j)]
        if drop:  # basse continue
            seg = np.arange(int(beat * SR)) / SR
            y[i:i + len(seg)] += 0.35 * np.sin(2 * np.pi * 55 * seg)[: n - i]
    y /= np.max(np.abs(y)) + 1e-9
    import soundfile as sf
    sf.write(str(path), y * 0.9, SR)
    return {"bpm": bpm, "drop": 4 * bars_intro * beat, "beat": beat, "duration": len(y) / SR}


def make_clip(path: Path, kind: str = "testsrc2", seconds: float = 8, size: str = "640x360") -> Path:
    src = {
        "testsrc2": f"testsrc2=size={size}:rate=30",
        "mandel": f"mandelbrot=size={size}:rate=30",
        "life": f"life=size={size}:rate=30:mold=10:ratio=0.1:death_color=#C83232:life_color=#00ff00",
        "cells": f"cellauto=size={size}:rate=30:rule=110",
        "gradients": f"gradients=size={size}:rate=30:speed=0.05",
    }[kind]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-t", str(seconds),
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(path)], check=True)
    return path
