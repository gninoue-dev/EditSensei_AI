"""Les comptes IA qui pilotent EditSensei : Claude, Gemini, ChatGPT, DeepSeek, Copilot.

Deux façons de brancher une IA :
- **compte** : on passe par l'outil officiel en ligne de commande de l'IA, connecté à TON compte
  (abonnement Claude, compte Google, compte ChatGPT, compte GitHub Copilot). Rien à payer en plus,
  aucune clé à copier : tu te connectes une fois dans le terminal et c'est tout.
- **clé API** : une clé copiée depuis la console du fournisseur (Gemini et GitHub en donnent une gratuite).

Le réglage est enregistré dans ~/.editsensei/accounts.json (lisible par toi seul).
Toutes les IA reçoivent la même consigne et doivent rendre le même JSON : le reste du cerveau
ne sait pas laquelle est branchée.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("editsensei.providers")

TIMEOUT = int(os.environ.get("EDITSENSEI_AI_TIMEOUT", "150"))


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    cli: str | None            # commande de l'outil officiel (mode compte)
    login: list[str] | None    # commande à lancer dans un terminal pour se connecter
    install: str | None        # comment installer l'outil
    key_env: str | None        # variable d'environnement de la clé API
    key_url: str | None        # où obtenir une clé
    model: str                 # modèle par défaut en mode clé
    account_note: str = ""


PROVIDERS: dict[str, Provider] = {p.id: p for p in [
    Provider("claude", "Claude", "claude", ["claude", "/login"], "npm install -g @anthropic-ai/claude-code",
             "ANTHROPIC_API_KEY", "https://console.anthropic.com/settings/keys", "claude-sonnet-5-5",
             "Compte Claude Pro ou Max (Claude Code)"),
    Provider("gemini", "Gemini", "gemini", ["gemini"], "npm install -g @google/gemini-cli",
             "GEMINI_API_KEY", "https://aistudio.google.com/apikey", "gemini-2.5-flash",
             "Compte Google (gratuit)"),
    Provider("chatgpt", "ChatGPT", "codex", ["codex", "login"], "npm install -g @openai/codex",
             "OPENAI_API_KEY", "https://platform.openai.com/api-keys", "gpt-4o-mini",
             "Compte ChatGPT Plus/Pro (Codex)"),
    Provider("deepseek", "DeepSeek", None, None, None,
             "DEEPSEEK_API_KEY", "https://platform.deepseek.com/api_keys", "deepseek-chat",
             "Clé API uniquement"),
    Provider("copilot", "Copilot", "copilot", ["copilot"], "npm install -g @github/copilot",
             "GITHUB_TOKEN", "https://github.com/settings/personal-access-tokens", "openai/gpt-4o-mini",
             "Compte GitHub Copilot (clé : jeton GitHub avec la permission « Models »)"),
]}


class AIError(RuntimeError):
    """Échec d'un appel à l'IA (message lisible par l'utilisateur)."""


# ── réglages ──────────────────────────────────────────────

def _home() -> Path:
    return Path(os.environ.get("EDITSENSEI_HOME", Path.home() / ".editsensei"))


def _config_file() -> Path:
    return _home() / "accounts.json"


def load_config() -> dict:
    try:
        cfg = json.loads(_config_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("active", None)
    cfg.setdefault("accounts", {})
    cfg.setdefault("voice", {"auto_send": True, "language": "fr"})
    return cfg


def save_config(cfg: dict) -> None:
    f = _config_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(f, 0o600)  # contient des clés
    except OSError:
        pass


def account(pid: str, cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    return cfg["accounts"].get(pid, {})


def api_key(pid: str, cfg: dict | None = None) -> str | None:
    p = PROVIDERS[pid]
    return account(pid, cfg).get("key") or (os.environ.get(p.key_env) if p.key_env else None)


def update_account(pid: str, mode: str | None = None, key: str | None = None, model: str | None = None,
                   activate: bool = True) -> dict:
    if pid not in PROVIDERS and pid != "local":
        raise AIError(f"IA inconnue : {pid}")
    cfg = load_config()
    if pid != "local":
        acc = cfg["accounts"].setdefault(pid, {})
        if mode in ("account", "key"):
            acc["mode"] = mode
        if key is not None:
            acc["key"] = key.strip() or None
        if model is not None:
            acc["model"] = model.strip() or None
    if activate:
        cfg["active"] = None if pid == "local" else pid
    save_config(cfg)
    return cfg


def mode_of(pid: str, cfg: dict | None = None) -> str:
    """'account' ou 'key' : choix enregistré, sinon ce qui est disponible."""
    acc = account(pid, cfg)
    if acc.get("mode") in ("account", "key"):
        return acc["mode"]
    if PROVIDERS[pid].cli and find_cli(pid):
        return "account"
    return "key"


def active(cfg: dict | None = None) -> str | None:
    """L'IA branchée, ou None (mode local)."""
    if os.environ.get("EDITSENSEI_NO_LLM"):
        return None
    cfg = cfg or load_config()
    pid = cfg.get("active")
    if pid in PROVIDERS and ready(pid, cfg):
        return pid
    if pid is None and not cfg["accounts"]:
        # rien de réglé : on garde le comportement historique (clé Anthropic dans l'environnement)
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "claude"
    return None


def ready(pid: str, cfg: dict | None = None) -> bool:
    if mode_of(pid, cfg) == "account":
        return find_cli(pid) is not None
    return bool(api_key(pid, cfg))


def describe_active(cfg: dict | None = None) -> str:
    pid = active(cfg)
    if not pid:
        return "mode local"
    return f"{PROVIDERS[pid].label} ({'compte' if mode_of(pid, cfg) == 'account' else 'clé API'})"


# ── outils en ligne de commande (mode compte) ─────────────

def _extra_paths() -> list[str]:
    """Le panneau After Effects lance le cerveau avec un PATH minimal : on cherche aussi aux endroits habituels."""
    h = Path.home()
    paths = [h / ".local/bin", h / ".npm-global/bin", h / ".claude/local", Path("/opt/homebrew/bin"),
             Path("/usr/local/bin"), h / ".bun/bin", h / ".volta/bin"]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths.append(Path(appdata) / "npm")
        paths.append(h / ".local" / "bin")
    nvm = h / ".nvm/versions/node"
    if nvm.is_dir():
        paths += sorted((v / "bin" for v in nvm.iterdir()), reverse=True)
    return [str(p) for p in paths if p.is_dir()]


def find_cli(pid: str) -> str | None:
    p = PROVIDERS[pid]
    if not p.cli:
        return None
    custom = account(pid).get("cli_path")
    if custom and Path(custom).exists():
        return custom
    return shutil.which(p.cli) or shutil.which(p.cli, path=os.pathsep.join(_extra_paths()))


def _cli_env() -> dict:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([env.get("PATH", "")] + _extra_paths())
    env.setdefault("NO_COLOR", "1")
    return env


def _run(cmd: list[str], stdin: str | None = None, cwd: str | None = None) -> str:
    try:
        proc = subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=TIMEOUT, cwd=cwd, env=_cli_env())
    except subprocess.TimeoutExpired:
        raise AIError("L'IA met trop de temps à répondre.") from None
    except OSError as e:
        raise AIError(f"Impossible de lancer {cmd[0]} : {e}") from None
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip().splitlines()
        hint = err[-1] if err else f"code {proc.returncode}"
        if re.search(r"log ?in|auth|unauthori[sz]ed|credential|not logged|sign in|401|403", hint, re.I):
            raise AIError(f"Compte non connecté : clique sur « Se connecter » ({hint})")
        raise AIError(hint[:300])
    return proc.stdout


def _ask_cli(pid: str, prompt: str) -> str:
    exe = find_cli(pid)
    if not exe:
        raise AIError(f"Outil « {PROVIDERS[pid].cli} » introuvable. Installe-le : {PROVIDERS[pid].install}")
    # dossier vide : l'IA n'a accès à aucun de tes fichiers
    with tempfile.TemporaryDirectory(prefix="editsensei-ai-") as tmp:
        if pid == "claude":
            out = _run([exe, "-p", "--output-format", "json", "--max-turns", "1"], stdin=prompt, cwd=tmp)
            try:
                data = json.loads(out)
            except ValueError:
                return out
            if data.get("is_error"):
                raise AIError(str(data.get("result") or "erreur Claude"))
            return str(data.get("result", ""))
        if pid == "gemini":
            return _run([exe, "-p", "Réponds au message ci-dessus."], stdin=prompt, cwd=tmp)
        if pid == "chatgpt":
            last = Path(tmp) / "reponse.txt"
            out = _run([exe, "exec", "--skip-git-repo-check", "--output-last-message", str(last), "-"],
                       stdin=prompt, cwd=tmp)
            return last.read_text(encoding="utf-8") if last.exists() else out
        if pid == "copilot":
            return _run([exe, "-p", prompt], cwd=tmp)
    raise AIError(f"{PROVIDERS[pid].label} n'a pas de mode compte : utilise une clé API.")


# ── clés API (HTTP, sans dépendance) ─────────────────────

def _post(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise AIError(f"Clé refusée ({e.code}). Vérifie-la dans les réglages.") from None
        if e.code == 429:
            raise AIError("Limite de requêtes ou crédit épuisé (429).") from None
        raise AIError(f"Erreur {e.code} : {detail}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise AIError(f"Connexion impossible : {getattr(e, 'reason', e)}") from None


def _openai_like(url: str, key: str, model: str, system: str, messages: list[dict], json_mode: bool) -> str:
    body = {"model": model, "messages": [{"role": "system", "content": system}] + messages, "temperature": 0.4}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = _post(url, body, {"Authorization": f"Bearer {key}"})
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        raise AIError("Réponse inattendue de l'IA.") from None


def _ask_key(pid: str, system: str, messages: list[dict], json_mode: bool) -> str:
    key = api_key(pid)
    if not key:
        raise AIError(f"Aucune clé {PROVIDERS[pid].label}. Ajoute-la dans les réglages ⚙️.")
    model = account(pid).get("model") or PROVIDERS[pid].model
    if pid == "claude":
        data = _post("https://api.anthropic.com/v1/messages",
                     {"model": model, "max_tokens": 2000, "system": system, "messages": messages},
                     {"x-api-key": key, "anthropic-version": "2023-06-01"})
        if data.get("stop_reason") == "refusal":
            raise AIError("Claude a refusé cette demande.")
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if pid == "gemini":
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in messages]
        gen = {"temperature": 0.4}
        if json_mode:
            gen["responseMimeType"] = "application/json"
        data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                     {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": gen},
                     {"x-goog-api-key": key})
        try:
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError):
            raise AIError("Gemini n'a rien répondu (demande bloquée ?).") from None
    url = {"chatgpt": "https://api.openai.com/v1/chat/completions",
           "deepseek": "https://api.deepseek.com/chat/completions",
           "copilot": "https://models.github.ai/inference/chat/completions"}[pid]
    return _openai_like(url, key, model, system, messages, json_mode)


# ── point d'entrée unique ─────────────────────────────────

def _flatten(system: str, messages: list[dict]) -> str:
    """Les outils en ligne de commande prennent un seul texte : consigne + conversation."""
    parts = [system, "", "--- Conversation ---"]
    for m in messages:
        parts.append(("Utilisateur" if m["role"] == "user" else "EditSensei") + " : " + m["content"])
    return "\n".join(parts)


def ask(system: str, messages: list[dict], pid: str | None = None, json_mode: bool = True) -> str:
    """Envoie la conversation à l'IA branchée (ou à `pid`) et renvoie son texte."""
    pid = pid or active()
    if not pid:
        raise AIError("Aucune IA connectée.")
    if mode_of(pid) == "account" and PROVIDERS[pid].cli:
        return _ask_cli(pid, _flatten(system, messages))
    return _ask_key(pid, system, messages, json_mode)


def extract_json(text: str) -> dict:
    """Récupère l'objet JSON d'une réponse, même entouré de texte ou de ```json."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                esc = (c == "\\") and not esc
                if c == '"' and not esc:
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except ValueError:
                        break
        start = text.find("{", start + 1)
    raise AIError("L'IA n'a pas renvoyé de JSON lisible.")


def test(pid: str) -> str:
    """Petit échange pour vérifier la connexion. Renvoie la réponse de l'IA."""
    out = ask('Réponds uniquement avec ce JSON : {"ok": true, "message": "<une phrase courte et enthousiaste en français>"}',
              [{"role": "user", "content": "Test de connexion depuis EditSensei."}], pid=pid)
    try:
        return str(extract_json(out).get("message") or "Connecté ✅")
    except AIError:
        return out.strip()[:200] or "Connecté ✅"


# ── connexion : ouvrir un terminal pour se connecter ─────

def open_login(pid: str) -> str:
    p = PROVIDERS[pid]
    if not p.cli or not p.login:
        raise AIError(f"{p.label} se branche uniquement avec une clé API : {p.key_url}")
    exe = find_cli(pid)
    if not exe:
        raise AIError(f"Installe d'abord l'outil {p.label} : {p.install}  (Node.js requis : https://nodejs.org)")
    args = [exe] + p.login[1:]
    if sys.platform == "win32":
        subprocess.Popen(["cmd", "/c", "start", f"Connexion {p.label}", "cmd", "/k"] + args, env=_cli_env())
    elif sys.platform == "darwin":
        script = " ".join("'" + a.replace("'", "'\\''") + "'" for a in args)
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{script}"',
                          "-e", 'tell application "Terminal" to activate'])
    else:
        for term in (["gnome-terminal", "--"], ["konsole", "-e"], ["xfce4-terminal", "-x"], ["x-terminal-emulator", "-e"]):
            if shutil.which(term[0]):
                subprocess.Popen(term + args, env=_cli_env())
                break
        else:
            raise AIError(f"Ouvre un terminal et lance : {' '.join(args)}")
    steps = {
        "claude": "Dans la fenêtre qui s'ouvre, choisis « Claude account » et valide dans le navigateur.",
        "gemini": "Dans la fenêtre qui s'ouvre, choisis « Login with Google » et valide dans le navigateur.",
        "chatgpt": "Une page de connexion ChatGPT s'ouvre dans le navigateur : connecte-toi.",
        "copilot": "Dans la fenêtre qui s'ouvre, tape /login et suis les étapes GitHub.",
    }
    return steps.get(pid, "Suis les étapes dans la fenêtre qui s'ouvre.") + " Puis reviens ici et clique « Tester »."


def status() -> dict:
    cfg = load_config()
    out = []
    for p in PROVIDERS.values():
        acc = account(p.id, cfg)
        key = api_key(p.id, cfg)
        out.append({
            "id": p.id, "label": p.label, "note": p.account_note,
            "has_cli": bool(p.cli), "cli_found": bool(find_cli(p.id)), "install": p.install,
            "mode": mode_of(p.id, cfg), "key_set": bool(key), "key_hint": (key[:4] + "…" + key[-4:]) if key and len(key) > 12 else ("✓" if key else ""),
            "key_url": p.key_url, "model": acc.get("model") or p.model, "ready": ready(p.id, cfg),
        })
    return {"active": active(cfg), "label": describe_active(cfg), "providers": out, "voice": cfg["voice"]}
