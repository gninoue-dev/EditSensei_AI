"""Transcription automatique de la voix en texte.

Sert à deux choses :
- 🎤 la dictée dans le panneau : tu parles, ton message s'écrit (et part tout seul) ;
- 💬 les sous-titres automatiques : les paroles de la musique ou des clips deviennent des titres dans la compo.

Moteurs, dans l'ordre :
1. **Whisper local** (faster-whisper) : gratuit, hors ligne, rien ne quitte ton PC.
   Installé avec `pip install -e ".[voix]"`. Modèle réglable : EDITSENSEI_WHISPER_MODEL (small par défaut).
2. **OpenAI** (clé ChatGPT des réglages) : Whisper en ligne, avec les horodatages.
3. **Gemini** (clé Gemini des réglages) : texte seul, sans horodatage (dictée uniquement).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from . import providers
from .tools import ffmpeg

log = logging.getLogger("editsensei.voice")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    engine: str
    segments: list[Segment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class VoiceError(RuntimeError):
    pass


# ── préparation audio ─────────────────────────────────────

def to_wav(src: str | Path, dst: str | Path, start: float = 0.0, duration: float | None = None) -> Path:
    """N'importe quel média (webm du micro, mp3, vidéo…) → WAV mono 16 kHz, le format attendu par Whisper."""
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if duration:
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0 or not Path(dst).exists():
        raise VoiceError("Audio illisible : " + (proc.stderr.strip().splitlines() or ["ffmpeg"])[-1])
    return Path(dst)


# ── moteurs ───────────────────────────────────────────────

def local_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _whisper():
    from faster_whisper import WhisperModel
    name = os.environ.get("EDITSENSEI_WHISPER_MODEL", "small")
    log.info("Chargement du modèle Whisper « %s » (le premier lancement le télécharge)…", name)
    return WhisperModel(name, device="cpu", compute_type="int8")


def _local(wav: Path, language: str) -> Transcript:
    import numpy as np
    import soundfile as sf
    # on donne directement les échantillons (déjà en 16 kHz mono) : pas besoin du décodeur PyAV de faster-whisper
    samples, _ = sf.read(str(wav), dtype="float32")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    segs, _ = _whisper().transcribe(np.ascontiguousarray(samples), language=language or None, vad_filter=True,
                                    beam_size=5)
    out = [Segment(round(s.start, 3), round(s.end, 3), s.text.strip()) for s in segs if s.text.strip()]
    return Transcript(" ".join(s.text for s in out).strip(), "Whisper local", out)


def _multipart(fields: dict, file_field: str, path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{path.name}"\r\n'
             f"Content-Type: audio/wav\r\n\r\n").encode() + path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def _openai(wav: Path, language: str, key: str) -> Transcript:
    body, ctype = _multipart({"model": "whisper-1", "response_format": "verbose_json", "language": language or "fr"},
                             "file", wav)
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise VoiceError(f"OpenAI a refusé la transcription ({e.code}).") from None
    except urllib.error.URLError as e:
        raise VoiceError(f"Connexion impossible : {e.reason}") from None
    segs = [Segment(round(s["start"], 3), round(s["end"], 3), s["text"].strip())
            for s in data.get("segments", []) if s.get("text", "").strip()]
    return Transcript(data.get("text", "").strip(), "Whisper OpenAI", segs)


def _gemini(wav: Path, language: str, key: str) -> Transcript:
    import base64
    model = providers.account("gemini").get("model") or providers.PROVIDERS["gemini"].model
    body = {"contents": [{"parts": [
        {"text": f"Transcris mot pour mot cet audio (langue : {language or 'fr'}). Réponds uniquement avec le texte."},
        {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(wav.read_bytes()).decode()}},
    ]}]}
    try:
        data = providers._post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                               body, {"x-goog-api-key": key})
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    except (providers.AIError, KeyError, IndexError) as e:
        raise VoiceError(f"Gemini n'a pas pu transcrire : {e}") from None
    return Transcript(text, "Gemini", [])


def engines() -> list[str]:
    out = []
    if local_available():
        out.append("local")
    if providers.api_key("chatgpt"):
        out.append("openai")
    if providers.api_key("gemini"):
        out.append("gemini")
    return out


def transcribe(src: str | Path, language: str = "fr", need_timing: bool = False,
               start: float = 0.0, duration: float | None = None) -> Transcript:
    """Transcrit un fichier audio/vidéo. `need_timing` exclut les moteurs sans horodatage."""
    available = [e for e in engines() if not (need_timing and e == "gemini")]
    if not available:
        raise VoiceError(
            "Aucun moteur de transcription. Installe la voix locale gratuite et hors ligne "
            "en relançant le script d'installation (scripts/install_windows.ps1 ou install_macos.sh) "
            "ou ajoute une clé ChatGPT" + ("" if need_timing else " ou Gemini") + " dans ⚙️.")
    with tempfile.TemporaryDirectory(prefix="editsensei-voix-") as tmp:
        wav = to_wav(src, Path(tmp) / "voix.wav", start, duration)
        last: Exception | None = None
        for eng in available:
            try:
                if eng == "local":
                    return _local(wav, language)
                if eng == "openai":
                    return _openai(wav, language, providers.api_key("chatgpt"))
                return _gemini(wav, language, providers.api_key("gemini"))
            except Exception as e:  # on essaie le moteur suivant
                log.warning("Transcription %s impossible : %s", eng, e)
                last = e
        raise VoiceError(str(last))


# ── sous-titres ───────────────────────────────────────────

_CACHE: dict[tuple, Transcript] = {}


def captions(src: str, start: float, length: float, language: str = "fr", max_chars: int = 32) -> list[dict]:
    """Paroles de `src` entre start et start+length, découpées en courtes lignes (temps relatifs au montage)."""
    key = (src, round(start, 2), round(length, 2), language, os.path.getmtime(src))
    if key not in _CACHE:
        _CACHE[key] = transcribe(src, language, need_timing=True, start=start, duration=length)
    out = []
    for s in _CACHE[key].segments:
        words = s.text.split()
        if not words:
            continue
        lines, cur = [], ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > max_chars:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        # le temps du segment est partagé entre ses lignes au prorata du nombre de lettres
        total = sum(len(x) for x in lines) or 1
        t = s.start
        for line in lines:
            d = (s.end - s.start) * len(line) / total
            if t < length:
                out.append({"text": line, "t": round(t, 3), "duration": round(max(0.4, min(d, length - t)), 3)})
            t += d
    return out
