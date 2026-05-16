@echo off
REM ÉDITSENSEI AI - Démarrage sur Windows

echo.
echo ╔════════════════════════════════════════════════════╗
echo ║          ÉDITSENSEI AI - Démarrage Complet         ║
echo ╚════════════════════════════════════════════════════╝
echo.

REM Vérifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python n'est pas installé ou pas dans PATH
    pause
    exit /b 1
)

REM Vérifier Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js n'est pas installé ou pas dans PATH
    pause
    exit /b 1
)

echo ✅ Tous les prérequis sont présents

REM Setup Backend
echo.
echo 📦 Configuration du Backend...
cd backend

if not exist venv (
    echo Création de l'environnement virtuel...
    python -m venv venv
)

call venv\Scripts\activate.bat

if not exist .env (
    echo Création du fichier .env...
    copy .env.example .env
    echo ⚠️  Mettez à jour OPENAI_API_KEY dans backend\.env
)

echo Installation des dépendances Python...
pip install -q -r requirements.txt

echo ✅ Backend configuré
cd ..

REM Setup Frontend
echo.
echo 🎨 Configuration du Frontend...
cd frontend

echo Installation des dépendances Node...
npm install -q

echo ✅ Frontend configuré
cd ..

REM Démarrer les services
echo.
echo 🚀 Démarrage des services...
echo.

REM Backend
echo Démarrage du Backend (port 8000)...
start cmd /k "cd backend && venv\Scripts\activate.bat && python run.py"

REM Attendre un peu
timeout /t 2 /nobreak

REM Frontend
echo Démarrage du Frontend (port 5173)...
start cmd /k "cd frontend && npm run dev"

echo.
echo ╔════════════════════════════════════════════════════╗
echo ║          🎉 ÉDITSENSEI AI est démarré!             ║
echo ╚════════════════════════════════════════════════════╝
echo.
echo 🌐 Frontend:   http://localhost:5173
echo 🔧 Backend:    http://localhost:8000
echo 📚 API Docs:   http://localhost:8000/docs
echo.
echo Appuyez sur Ctrl+C pour arrêter...
echo.

pause
