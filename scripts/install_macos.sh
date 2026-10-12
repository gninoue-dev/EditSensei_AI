#!/bin/bash
# EditSensei AI — installation sur macOS (After Effects 2022 ou plus récent)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BRAIN="$ROOT/brain"
DEST="$HOME/Library/Application Support/Adobe/CEP/extensions/com.editsensei.panel"

echo "=== EditSensei AI : installation ==="
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
cd "$BRAIN"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[voix]"

for v in 9 10 11 12; do defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1; done

rm -rf "$DEST"; mkdir -p "$DEST"
cp -R "$ROOT/ae-panel/." "$DEST/"
rm -rf "$DEST/tests"
printf '{"brainDir": "%s", "python": "%s"}\n' "$BRAIN" "$BRAIN/.venv/bin/python" > "$DEST/config.json"
echo "Terminé ! Redémarre After Effects puis : Fenêtre > Extensions > EditSensei AI"
echo "Ensuite, branche ton IA dans le panneau : bouton ⚙️ (Claude, Gemini, ChatGPT, DeepSeek ou Copilot)."
if ! command -v node >/dev/null 2>&1; then
  echo "Pour te connecter avec ton COMPTE (sans clé API), installe Node.js (https://nodejs.org) puis par exemple :"
  echo "  npm install -g @anthropic-ai/claude-code   (ou @google/gemini-cli, @openai/codex, @github/copilot)"
fi
echo "Micro : Réglages Système › Confidentialité et sécurité › Micro › autorise After Effects."
