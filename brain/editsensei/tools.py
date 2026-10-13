"""Accès à FFmpeg : celui du système s'il existe, sinon celui fourni par imageio-ffmpeg."""

from __future__ import annotations

import re
import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(path: str) -> dict:
    """Infos d'un média lues dans la sortie de `ffmpeg -i` (pas besoin de ffprobe)."""
    proc = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    err = proc.stderr
    dur = 0.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    video = re.search(r"Stream #.*Video:.*?(\d{2,5})x(\d{2,5})", err)
    fps_m = re.search(r"(\d+(?:\.\d+)?)\s*fps", err) or re.search(r"(\d+(?:\.\d+)?)\s*tbr", err)
    rot = re.search(r"rotate\s*:\s*(-?\d+)|rotation of (-?\d+(?:\.\d+)?) degrees", err)
    w, h = (int(video.group(1)), int(video.group(2))) if video else (0, 0)
    if rot:
        angle = abs(int(float(rot.group(1) or rot.group(2))))
        if angle in (90, 270):
            w, h = h, w
    return {
        "duration": dur,
        "fps": float(fps_m.group(1)) if (video and fps_m) else 0.0,
        "width": w,
        "height": h,
        "has_audio": bool(re.search(r"Stream #.*Audio:", err)),
        "is_video": bool(video),
    }
