"""L'œil d'EditSensei : trouver les meilleurs moments de chaque clip.

Pour chaque clip on mesure, ~6 fois par seconde et en basse résolution :
- le mouvement (différence entre images) → les passages d'action,
- la netteté (variance du laplacien) → éviter les images floues / ratées,
- les coupes internes (changement brutal d'histogramme) → ne pas couper au milieu d'un raccord.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .audio import _cache_dir, file_key
from .tools import probe as _probe

SAMPLE_FPS = 6.0
WIDTH = 160


@dataclass
class ClipInfo:
    path: str
    duration: float
    fps: float
    width: int
    height: int
    has_audio: bool = False
    times: list[float] = field(default_factory=list)      # instants échantillonnés
    motion: list[float] = field(default_factory=list)     # 0..1
    sharpness: list[float] = field(default_factory=list)  # 0..1
    cuts: list[float] = field(default_factory=list)       # coupes internes

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ClipInfo":
        return cls(**d)

    @property
    def name(self) -> str:
        return Path(self.path).name

    def score_window(self, start: float, length: float, want_motion: float) -> float:
        """Note d'un passage [start, start+length] : net, sans coupe interne, mouvement proche du voulu."""
        if not self.times:
            return 0.5
        t = np.asarray(self.times)
        m = (t >= start) & (t <= start + length)
        if not m.any():
            return 0.0
        mot = float(np.mean(np.asarray(self.motion)[m]))
        sharp = float(np.mean(np.asarray(self.sharpness)[m]))
        cut_penalty = 0.6 if any(start + 0.05 < c < start + length - 0.05 for c in self.cuts) else 0.0
        return 0.55 * (1 - abs(mot - want_motion)) + 0.45 * sharp - cut_penalty

    def motion_at(self, t: float) -> float:
        if not self.times:
            return 0.5
        return float(np.interp(t, self.times, self.motion))


def probe(path: str | Path) -> dict:
    meta = _probe(str(path))
    if meta["is_video"] and meta["duration"] <= 0.05:
        meta["duration"] = 3.0  # image fixe : traitée comme un plan de 3 s
    meta["fps"] = meta["fps"] or 30.0
    return meta


def analyze_clip(path: str | Path, use_cache: bool = True) -> ClipInfo:
    cache = _cache_dir() / f"clip-{file_key(path, 'v2')}.json"
    if use_cache and cache.exists():
        return ClipInfo.from_dict(json.loads(cache.read_text()))

    import cv2

    meta = probe(path)
    info = ClipInfo(str(path), meta["duration"], meta["fps"], meta["width"], meta["height"], meta["has_audio"])
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cache.write_text(json.dumps(info.to_dict()))
        return info

    src_fps = cap.get(cv2.CAP_PROP_FPS) or meta["fps"] or 30.0
    step = max(1, int(round(src_fps / SAMPLE_FPS)))
    times, motion, sharp, hists = [], [], [], []
    prev = None
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            h, w = frame.shape[:2]
            small = cv2.resize(frame, (WIDTH, max(1, int(h * WIDTH / max(w, 1)))), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            times.append(idx / src_fps)
            motion.append(float(np.mean(cv2.absdiff(gray, prev))) if prev is not None else 0.0)
            sharp.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
            hists.append(cv2.normalize(hist, hist).flatten())
            prev = gray
        idx += 1
    cap.release()

    if times:
        motion_arr = np.asarray(motion)
        if len(motion_arr) > 1:
            motion_arr[0] = motion_arr[1]
        info.times = [round(t, 3) for t in times]
        info.motion = _norm(motion_arr, robust=True)
        info.sharpness = _norm(np.log1p(np.asarray(sharp)), robust=True)
        for i in range(1, len(hists)):
            d = cv2.compareHist(hists[i - 1].astype("float32"), hists[i].astype("float32"), cv2.HISTCMP_BHATTACHARYYA)
            if d > 0.45:
                info.cuts.append(round(times[i], 3))
    cache.write_text(json.dumps(info.to_dict()))
    return info


def _norm(x: np.ndarray, robust: bool = False) -> list[float]:
    if len(x) == 0:
        return []
    lo, hi = (np.percentile(x, 5), np.percentile(x, 95)) if robust else (x.min(), x.max())
    return [round(float(v), 4) for v in np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)]
