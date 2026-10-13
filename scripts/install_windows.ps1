# EditSensei AI — installation sur Windows (After Effects 2022 ou plus récent)
# Clic droit > « Exécuter avec PowerShell », ou :  powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
$ErrorActionPreference = "Stop"
$Root  = Split-Path -Parent $PSScriptRoot
$Brain = Join-Path $Root "brain"
$Panel = Join-Path $Root "ae-panel"
$Dest  = Join-Path $env:APPDATA "Adobe\CEP\extensions\com.editsensei.panel"

Write-Host "`n=== EditSensei AI : installation ===`n" -ForegroundColor Magenta

# 1. uv (gestionnaire Python ultra-rapide, installe aussi Python si besoin)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installation de uv..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. Le cerveau (Python 3.12 + dépendances, FFmpeg inclus)
Write-Host "Installation du cerveau (peut prendre quelques minutes la première fois)..."
Push-Location $Brain
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[voix]"
Pop-Location
$Python = Join-Path $Brain ".venv\Scripts\python.exe"

# 3. Autoriser les extensions non signées (mode développeur CEP)
foreach ($v in 9..12) {
    $key = "HKCU:\Software\Adobe\CSXS.$v"
    if (-not (Test-Path $key)) { New-Item -Path $key -Force | Out-Null }
    Set-ItemProperty -Path $key -Name "PlayerDebugMode" -Value "1" -Type String
}

# 4. Copier le panneau et lui dire où est le cerveau
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
New-Item -ItemType Directory -Path $Dest -Force | Out-Null
Copy-Item -Path (Join-Path $Panel "*") -Destination $Dest -Recurse -Force
Remove-Item (Join-Path $Dest "tests") -Recurse -Force -ErrorAction SilentlyContinue
@{ brainDir = $Brain; python = $Python } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Dest "config.json")

Write-Host "`nTerminé ! Redémarre After Effects puis : Fenêtre > Extensions > EditSensei AI" -ForegroundColor Green
Write-Host "Ensuite, branche ton IA dans le panneau : bouton ⚙️ (Claude, Gemini, ChatGPT, DeepSeek ou Copilot)."
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Pour te connecter avec ton COMPTE (sans clé API), installe Node.js : https://nodejs.org" -ForegroundColor Yellow
    Write-Host "puis par exemple :  npm install -g @anthropic-ai/claude-code   (ou @google/gemini-cli, @openai/codex, @github/copilot)`n"
}
