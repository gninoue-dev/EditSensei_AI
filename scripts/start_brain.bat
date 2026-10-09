@echo off
rem Lance le cerveau d'EditSensei à la main (le panneau le démarre normalement tout seul)
cd /d "%~dp0..\brain"
.venv\Scripts\python.exe -m editsensei
pause
