"""Aperçu MP4 d'un plan de montage, sans After Effects.

Rend le plan image par image avec OpenCV (mêmes courbes d'effets que le script
After Effects, voir `envelope`) puis encode avec ffmpeg en ajoutant la musique.
Pensé pour vérifier un montage en quelques secondes, pas pour la qualité finale :
la qualité finale, c'est After Effects.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .tools import ffmpeg

from .planner import EditPlan

FONT = Path(__file__).parent / "assets" / "Anton-Regular.ttf"


def envelope(x: float, duration: float) -> float:
    """Courbe d'un effet : montée rapide (15 %) puis retombée douce. 0 hors de [0, duration]."""
    if x < 0 or x > duration or duration <= 0:
        return 0.0
    a = 0.15 * duration
    if x < a:
        return x / a
    k = (x - a) / (duration - a)
    return (1 - k) ** 2


class _Source:
    """Lit un clip vers l'avant en évitant de rechercher (seek) à chaque image."""

    def __init__(self, path: str):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.pos = -1
        self.frame = None
        self.still = None
        if self.count <= 1:  # image fixe
            ok, f = self.cap.read()
            self.still = f if ok else None

    def at(self, t: float):
        if self.still is not None:
            return self.still
        idx = max(0, min(int(t * self.fps), max(0, self.count - 1)))
        if idx == self.pos and self.frame is not None:
            return self.frame
        if idx < self.pos or idx > self.pos + 90:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            self.pos = idx - 1
        while self.pos < idx:
            ok = self.cap.grab()
            if not ok:
                break
            self.pos += 1
        ok, f = self.cap.retrieve()
        if ok:
            self.frame = f
        return self.frame


def _cover(frame: np.ndarray, w: int, h: int, zoom: float = 1.0, dx: float = 0.0, dy: float = 0.0) -> np.ndarray:
    fh, fw = frame.shape[:2]
    s = max(w / fw, h / fh) * zoom
    m = np.float32([[s, 0, w / 2 - fw * s / 2 + dx], [0, s, h / 2 - fh * s / 2 + dy]])
    return cv2.warpAffine(frame, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def render_preview(plan: EditPlan, out_path: str | Path, height: int = 540, progress=None) -> Path:
    out_path = Path(out_path)
    scale = height / plan.height
    w = int(round(plan.width * scale / 2) * 2)
    h = int(round(plan.height * scale / 2) * 2)
    fps = plan.fps
    n_frames = int(math.ceil(plan.duration * fps))
    sources = [_Source(p) for p in plan.clips]
    rng = np.random.default_rng(3)
    shake_noise = rng.normal(0, 1, (n_frames + 1, 2))
    title_cache: dict[str, np.ndarray] = {}

    cmd = [ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-"]
    if plan.music:
        cmd += ["-ss", f"{plan.music_start}", "-t", f"{plan.duration}", "-i", plan.music, "-map", "0:v", "-map", "1:a",
                "-af", f"afade=t=in:d={max(plan.fade_in, 0.01)},afade=t=out:st={max(0, plan.duration - plan.fade_out)}:d={max(plan.fade_out, 0.01)}",
                "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-shortest", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    vign = None
    if plan.look.get("vignette", 0) > 0:
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        vign = (1 - plan.look["vignette"] * np.clip(r - 0.5, 0, 1) ** 1.5)[..., None].astype(np.float32)

    seg_i = 0
    try:
        for fi in range(n_frames):
            t = fi / fps
            while seg_i < len(plan.segments) - 1 and t >= plan.segments[seg_i].t_out:
                seg_i += 1
            seg = plan.segments[seg_i]
            src_t = seg.src_in + (t - seg.t_in) * seg.speed
            frame = sources[seg.clip].at(src_t)
            if frame is None:
                frame = np.zeros((h, w, 3), np.uint8)

            # effets de caméra (zoom / shake) avant le recadrage
            zoom, dx, dy = 1.0, 0.0, 0.0
            flash = rgb = blur = glow = 0.0
            for e in plan.effects:
                k = envelope(t - e.t, e.duration)
                if k <= 0:
                    continue
                if e.type == "zoom_punch":
                    zoom += 0.30 * e.strength * k
                elif e.type == "shake":
                    amp = 28 * e.strength * k * scale * 2
                    dx += amp * shake_noise[fi, 0]
                    dy += amp * shake_noise[fi, 1]
                    zoom += 0.05 * k
                elif e.type == "flash":
                    flash = max(flash, e.strength * k)
                elif e.type == "rgb_split":
                    rgb = max(rgb, e.strength * k)
                elif e.type == "blur_whip":
                    blur = max(blur, e.strength * k)
                elif e.type == "glow":
                    glow = max(glow, e.strength * k)
            img = _cover(frame, w, h, zoom, dx, dy)

            if blur > 0.02:
                ks = int(3 + blur * 60 * scale * 2) | 1
                kernel = np.zeros((ks, ks), np.float32)
                kernel[ks // 2, :] = 1.0 / ks
                img = cv2.filter2D(img, -1, kernel)
            if rgb > 0.02:
                sh = int(1 + rgb * 18 * scale * 2)
                b, g, r = cv2.split(img)
                img = cv2.merge([np.roll(b, -sh, axis=1), g, np.roll(r, sh, axis=1)])
            f = img.astype(np.float32)
            if glow > 0.02:
                f = f + 0.6 * glow * cv2.GaussianBlur(f, (0, 0), 12 * scale * 2)
            # look : contraste / saturation / vignette
            c = plan.look.get("contrast", 1.0)
            if abs(c - 1) > 0.01:
                f = (f - 128) * c + 128
            s = plan.look.get("saturation", 1.0)
            if abs(s - 1) > 0.01:
                gray = f.mean(axis=2, keepdims=True)
                f = gray + (f - gray) * s
            if vign is not None:
                f *= vign
            if flash > 0.01:
                f = f * (1 - flash) + 255 * flash
            # fondus d'ouverture / de fermeture
            fade = 1.0
            if plan.fade_in > 0 and t < plan.fade_in:
                fade = t / plan.fade_in
            if plan.fade_out > 0 and t > plan.duration - plan.fade_out:
                fade = min(fade, (plan.duration - t) / plan.fade_out)
            f *= max(0.0, fade)
            img = np.clip(f, 0, 255).astype(np.uint8)

            if plan.look.get("black_bars"):
                bar = int((h - w / 2.39) / 2) if w / h > 1 else int(h * 0.08)
                if bar > 0:
                    img[:bar] = 0
                    img[h - bar:] = 0
            for tx in plan.texts:
                k = t - tx.t
                if 0 <= k <= tx.duration:
                    img = _draw_title(img, tx.text, k, tx.duration, title_cache)

            proc.stdin.write(img.tobytes())
            if progress and fi % 30 == 0:
                progress(fi / n_frames)
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg a échoué pendant l'aperçu")
    return out_path


def _draw_title(img: np.ndarray, text: str, k: float, dur: float, cache: dict) -> np.ndarray:
    """Titre centré avec un « pop » d'entrée et un fondu de sortie."""
    h, w = img.shape[:2]
    key = f"{text}|{w}"
    if key not in cache:
        from PIL import Image, ImageDraw, ImageFont
        size = int(h * 0.16)
        try:
            font = ImageFont.truetype(str(FONT), size)
        except OSError:
            font = ImageFont.load_default()
        box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text.upper(), font=font)
        tw, th = box[2] - box[0] + 20, box[3] - box[1] + 30
        layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((10 - box[0], 10 - box[1]), text.upper(), font=font, fill=(255, 255, 255, 255),
                                   stroke_width=max(2, size // 18), stroke_fill=(20, 8, 32, 255))
        cache[key] = np.array(layer)[..., [2, 1, 0, 3]]  # RGBA → BGRA
    title = cache[key]
    pop = 1.0 + 0.35 * envelope(k, 0.35)
    alpha_mul = min(1.0, k / 0.12, (dur - k) / 0.4) if dur > 0 else 1.0
    th, tw = title.shape[:2]
    s = min(pop, (w * 0.9) / tw * pop)
    t_img = cv2.resize(title, (max(1, int(tw * s)), max(1, int(th * s))), interpolation=cv2.INTER_LINEAR)
    th, tw = t_img.shape[:2]
    x0, y0 = (w - tw) // 2, (h - th) // 2
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(w, x0 + tw), min(h, y0 + th)
    if xb <= xa or yb <= ya:
        return img
    crop = t_img[ya - y0:yb - y0, xa - x0:xb - x0]
    a = (crop[..., 3:4].astype(np.float32) / 255.0) * max(0.0, alpha_mul)
    region = img[ya:yb, xa:xb].astype(np.float32)
    img[ya:yb, xa:xb] = (region * (1 - a) + crop[..., :3].astype(np.float32) * a).astype(np.uint8)
    return img
