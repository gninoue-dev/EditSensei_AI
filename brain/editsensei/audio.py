"""L'oreille d'EditSensei : comprendre la musique pour monter dessus.

Produit une `MusicMap` :
- tempo et position de chaque beat,
- downbeats (1er temps de chaque mesure, 4/4 supposé),
- énergie par beat (0..1) et niveau low / mid / high,
- sections (changements de partie) et drops (montée brutale d'énergie).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .tools import ffmpeg

SR = 22050
HOP = 512


@dataclass
class MusicMap:
    duration: float
    tempo: float
    beats: list[float]
    downbeats: list[float]
    energy: list[float]            # une valeur 0..1 par beat
    levels: list[str]              # "low" | "mid" | "high" par beat
    sections: list[float] = field(default_factory=list)
    drops: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MusicMap":
        return cls(**d)

    # ── aides pour le planificateur ───────────────────────
    def beat_index_at(self, t: float) -> int:
        if not self.beats:
            return 0
        return int(np.clip(np.searchsorted(self.beats, t, side="right") - 1, 0, len(self.beats) - 1))

    def level_at(self, t: float) -> str:
        return self.levels[self.beat_index_at(t)] if self.levels else "mid"

    def energy_at(self, t: float) -> float:
        return self.energy[self.beat_index_at(t)] if self.energy else 0.5

    def moment_of(self, t: float, tol: float = 0.06) -> str:
        """Type d'instant musical le plus fort à l'instant t."""
        if any(abs(t - d) <= tol for d in self.drops):
            return "drop"
        if any(abs(t - s) <= tol for s in self.sections):
            return "section"
        if any(abs(t - d) <= tol for d in self.downbeats):
            return "downbeat"
        return "beat"

    def snap(self, t: float) -> float:
        if not self.beats:
            return t
        i = int(np.argmin(np.abs(np.asarray(self.beats) - t)))
        return self.beats[i]


# ── chargement ────────────────────────────────────────────

def _cache_dir() -> Path:
    d = Path(os.environ.get("EDITSENSEI_HOME", Path.home() / ".editsensei")) / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_key(path: str | Path, salt: str = "") -> str:
    p = Path(path)
    st = p.stat()
    raw = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}|{salt}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def load_audio(path: str | Path, sr: int = SR) -> np.ndarray:
    """Décode n'importe quel fichier (mp3, wav, mp4, mov…) en mono via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav = tmp.name
    try:
        subprocess.run(
            [ffmpeg(), "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "wav", wav],
            check=True,
        )
        import soundfile as sf
        y, _ = sf.read(wav, dtype="float32")
    finally:
        try:
            os.unlink(wav)
        except OSError:
            pass
    return np.asarray(y, dtype=np.float32)


# ── analyse ───────────────────────────────────────────────

def analyze_music(path: str | Path, use_cache: bool = True) -> MusicMap:
    cache = _cache_dir() / f"music-{file_key(path, 'v2')}.json"
    if use_cache and cache.exists():
        return MusicMap.from_dict(json.loads(cache.read_text()))
    mm = analyze_signal(load_audio(path))
    cache.write_text(json.dumps(mm.to_dict()))
    return mm


def analyze_signal(y: np.ndarray, sr: int = SR) -> MusicMap:
    import librosa

    duration = len(y) / sr
    if duration < 1.0 or float(np.max(np.abs(y))) < 1e-4:
        # silence : grille régulière à 120 BPM pour que le montage reste possible
        beats = list(np.arange(0, duration, 0.5))
        return MusicMap(duration, 120.0, beats, beats[::4], [0.5] * len(beats), ["mid"] * len(beats))

    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=HOP, units="frames")
    tempo = float(np.atleast_1d(tempo)[0])
    beat_frames = np.asarray(beat_frames, dtype=int)
    if len(beat_frames) < 4:
        step = 60.0 / max(tempo, 60.0)
        beat_times = np.arange(0, duration, step)
        beat_frames = librosa.time_to_frames(beat_times, sr=sr, hop_length=HOP)
    # ── correction de phase : on veut les temps sur la grosse caisse, pas sur les
    #    charlestons à contretemps (erreur classique des trackers sur l'electro / la phonk)
    low_y = _lowpass(y, sr)
    low_onset = librosa.onset.onset_strength(y=low_y, sr=sr, hop_length=HOP)
    beat_frames = _fix_offbeat(beat_frames, low_onset)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)

    # ── downbeats : la phase (0..3) dont les temps sont les plus forts (grosse caisse)
    low = librosa.feature.rms(y=low_y, hop_length=HOP)[0]
    strength = low[np.clip(beat_frames, 0, len(low) - 1)] + 0.5 * onset[np.clip(beat_frames, 0, len(onset) - 1)] / (onset.max() + 1e-9)
    # les changements de partie (montées, drops) tombent presque toujours sur un 1er temps :
    # on combine l'accent des temps et la force des sauts d'énergie
    rms_all = librosa.feature.rms(y=y, hop_length=HOP)[0]
    beat_rms = rms_all[np.clip(beat_frames, 0, len(rms_all) - 1)]
    jumps = np.zeros(len(beat_rms))
    for i in range(2, len(beat_rms) - 2):
        jumps[i] = max(0.0, beat_rms[i:i + 2].mean() - beat_rms[i - 2:i].mean())
    acc = strength / (strength.max() + 1e-9)
    jmp = jumps / (jumps.max() + 1e-9)

    def phase_score(p: int) -> float:
        a, j = acc[p::4], jmp[p::4]
        return (a.mean() if len(a) else 0) + 2.0 * (np.sort(j)[-3:].sum() if len(j) else 0)

    phase = int(np.argmax([phase_score(p) for p in range(4)]))
    downbeats = beat_times[phase::4]

    # ── énergie par beat (RMS lissé, normalisé 0..1)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    per_beat = []
    edges = list(beat_frames) + [len(rms)]
    for a, b in zip(edges[:-1], edges[1:]):
        seg = rms[a:max(b, a + 1)]
        per_beat.append(float(seg.mean()) if len(seg) else 0.0)
    e = np.asarray(per_beat)
    e = _smooth(e, 3)
    lo, hi = np.percentile(e, 5), np.percentile(e, 95)
    energy = np.clip((e - lo) / (hi - lo + 1e-9), 0, 1)
    q1, q2 = np.percentile(energy, 33), np.percentile(energy, 70)
    levels = ["low" if v < q1 else "high" if v >= q2 else "mid" for v in energy]

    # ── sections : grands changements d'énergie lissée, calés sur les débuts de mesure
    bar_e = _smooth(energy, 8)
    diff = np.abs(np.diff(bar_e, prepend=bar_e[0]))
    sections: list[float] = []
    min_gap = 8 * 60.0 / max(tempo, 1)  # au moins 2 mesures entre deux sections
    for i in np.argsort(diff)[::-1]:
        if diff[i] < 0.08 or len(sections) >= 12:
            break
        t = _nearest(downbeats, beat_times[i]) if len(downbeats) else beat_times[i]
        if all(abs(t - s) > min_gap for s in sections):
            sections.append(float(t))
    sections.sort()

    # ── drops : saut brutal d'énergie (avant faible → après forte)
    drops: list[float] = []
    w = 8
    scores = []
    for i in range(w, len(energy) - 2):
        before = energy[i - w:i].mean()
        after = energy[i:i + w].mean()
        scores.append((after - before, i))
    scores.sort(reverse=True)
    for jump, i in scores:
        if jump < 0.25 or len(drops) >= 3:
            break
        if energy[i:i + w].mean() < 0.6:
            continue
        t = _nearest(downbeats, beat_times[i]) if len(downbeats) else beat_times[i]
        if all(abs(t - d) > 4 * min_gap for d in drops):
            drops.append(float(t))
    drops.sort()

    return MusicMap(
        duration=float(duration),
        tempo=round(tempo, 2),
        beats=[round(float(t), 4) for t in beat_times],
        downbeats=[round(float(t), 4) for t in downbeats],
        energy=[round(float(v), 4) for v in energy],
        levels=levels,
        sections=[round(t, 4) for t in sections],
        drops=[round(t, 4) for t in drops],
    )


def _fix_offbeat(frames: np.ndarray, low_onset: np.ndarray) -> np.ndarray:
    """Si la grosse caisse tombe entre les beats détectés, décale la grille d'un demi-temps."""
    if len(frames) < 4:
        return frames
    n = len(low_onset)

    def score(fr: np.ndarray) -> float:
        # max sur ±2 trames pour tolérer un léger décalage
        idx = np.clip(fr[:, None] + np.arange(-2, 3)[None, :], 0, n - 1)
        return float(low_onset[idx].max(axis=1).mean())

    mids = ((frames[:-1] + frames[1:]) // 2).astype(int)
    if score(mids) > 1.15 * score(frames[:-1]):
        step = int(np.median(np.diff(frames)))
        # on complète le début de la grille (avant le 1er demi-temps) puis on dédoublonne
        prefix = np.arange(mids[0] - step, -1, -step)[::-1]
        return np.unique(np.concatenate([prefix, mids]).astype(int))
    return frames


def _lowpass(y: np.ndarray, sr: int) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    sos = butter(4, 150, btype="low", fs=sr, output="sos")
    return sosfilt(sos, y).astype(np.float32)


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) < 2 or n <= 1:
        return np.asarray(x, dtype=float)
    k = np.ones(n) / n
    pad = np.pad(np.asarray(x, dtype=float), (n // 2, n - 1 - n // 2), mode="edge")
    return np.convolve(pad, k, mode="valid")


def _nearest(arr, t: float) -> float:
    arr = np.asarray(arr)
    return float(arr[int(np.argmin(np.abs(arr - t)))])
