# 🚀 ÉDITSENSEI AI - Guide d'Installation Complet

## Prérequis Système

### Requis
- **Node.js** 18.0+ ([Télécharger](https://nodejs.org/))
- **Python** 3.9+ ([Télécharger](https://www.python.org/))
- **Git** ([Télécharger](https://git-scm.com/))
- **Adobe After Effects** 2023+ (optionnel, pour le plugin)

### Optionnel
- **VS Code** ou éditeur préféré
- **Postman** (pour tester l'API)

## Installation Complète

### Étape 1: Cloner le Projet

```bash
git clone https://github.com/editsensei/editsensei-ai.git
cd ÉDITSENSEI_AI
```

### Étape 2: Configurer le Backend

#### 2.1 Créer l'environnement Python

```bash
cd backend
python3 -m venv venv

# Activer le venv
# Sur Windows:
venv\Scripts\activate
# Sur macOS/Linux:
source venv/bin/activate
```

#### 2.2 Installer les dépendances

```bash
pip install -r requirements.txt
```

#### 2.3 Configurer OpenAI

```bash
# Copier le fichier .env
cp .env.example .env

# Éditer .env et ajouter votre clé OpenAI
# Obtenir une clé sur: https://platform.openai.com/api-keys
nano .env  # ou éditeur préféré
```

Contenu minimal du `.env`:
```
OPENAI_API_KEY=sk-votre-cle-api-ici
OPENAI_MODEL=gpt-4-turbo-preview
BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0
FRONTEND_URL=http://localhost:5173
```

#### 2.4 Lancer le backend

```bash
python run.py
```

**Résultat attendu:**
```
==================================================
🚀 ÉDITSENSEI AI Backend
==================================================
📍 Running on 0.0.0.0:8000
🌐 Frontend URL: http://localhost:5173
🎬 After Effects Port: 14001
🤖 Model: gpt-4-turbo-preview
🔑 OpenAI Configured: True
==================================================
```

✅ Backend disponible sur: `http://localhost:8000`
📚 API Docs sur: `http://localhost:8000/docs`

### Étape 3: Configurer le Frontend

#### 3.1 Installer les dépendances

```bash
cd frontend
npm install
```

#### 3.2 Configurer l'environnement (optionnel)

```bash
# Créer .env.local si besoin de custom URLs
cat > .env.local << EOF
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/client
EOF
```

#### 3.3 Lancer le frontend

```bash
npm run dev
```

**Résultat attendu:**
```
  VITE v5.0.0  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  press h to show help
```

✅ Frontend disponible sur: `http://localhost:5173`

### Étape 4: Configurer le Plugin After Effects (Optionnel)

#### 4.1 Localiser les dossiers plugins

**Windows:**
```
C:\Program Files\Adobe\Common\Media Cache Files\EXT
```

**macOS:**
```
/Applications/Adobe After Effects 2024/Scripts/ScriptUI Panels/
```

#### 4.2 Installer le plugin

```bash
# Depuis la racine du projet
cp -r ae-plugin ~/path-to-ae-plugins/

# Ou créer un lien symbolique
ln -s $(pwd)/ae-plugin ~/path-to-ae-plugins/editsensei-ai
```

#### 4.3 Redémarrer After Effects

Fermer et rouvrir After Effects.

**Accéder au plugin:**
- **Windows:** Window → Scripts → editsensei-ai
- **macOS:** File → Scripts → Open Script File → `ae-plugin/src/index.html`

## Vérification Installation

### Test Backend API

```bash
curl http://localhost:8000/health
```

**Réponse attendue:**
```json
{
  "status": "ok",
  "ai_enabled": true,
  "environment": "development"
}
```

### Test WebSocket

```bash
# Depuis le répertoire frontend
npm install ws

# Créer test-ws.js
cat > test-ws.js << EOF
const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:8000/ws/client');

ws.on('open', () => {
  console.log('✅ WebSocket connecté');
  ws.send(JSON.stringify({ type: 'ping' }));
});

ws.on('message', (data) => {
  console.log('📨 Message reçu:', data);
  ws.close();
});

ws.on('error', (err) => {
  console.error('❌ Erreur:', err);
});
EOF

node test-ws.js
```

### Test API Command

```bash
curl -X POST http://localhost:8000/api/health \
  -H "Content-Type: application/json"
```

## Architecture Déployée

```
┌─────────────────────────────────────────────────────┐
│                  ÉDITSENSEI AI                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌────────┐│
│  │  Frontend   │◄──►│   Backend    │◄──►│ OpenAI ││
│  │   React     │    │   FastAPI    │    │  API   ││
│  │ :5173       │    │   :8000      │    └────────┘│
│  └─────────────┘    └──────────────┘               │
│        │                    │                      │
│        └────────┬───────────┘                      │
│                 │ WebSocket                        │
│                 ▼                                  │
│          ┌──────────────┐                         │
│          │ After Effects│                         │
│          │   Plugin     │                         │
│          └──────────────┘                         │
│                                                   │
└─────────────────────────────────────────────────────┘
```

## Fichiers Clés

- `backend/app/main.py` - Application FastAPI principale
- `backend/app/ai/engine.py` - Moteur IA orchestration
- `backend/app/ae/controller.py` - Contrôleur After Effects
- `frontend/src/App.tsx` - Application React principale
- `ae-plugin/src/index.html` - Interface du plugin AE
- `ae-plugin/src/aeController.jsx` - Logique du plugin AE

## Commandes Principales

### Backend

```bash
# Démarrer le backend
cd backend
python run.py

# Avec rechargement automatique (debug)
python run.py --reload

# Tests
pytest tests/
```

### Frontend

```bash
# Démarrer en développement
cd frontend
npm run dev

# Build production
npm run build

# Preview du build
npm run preview
```

## Dépannage

### Erreur: "Clé OpenAI non valide"

```bash
# Vérifier la clé
echo $OPENAI_API_KEY

# Réinitialiser dans .env
nano backend/.env
```

### Port déjà utilisé

```bash
# Trouver et tuer le processus
# Sur Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Sur macOS/Linux:
lsof -ti:8000 | xargs kill -9
```

### WebSocket ne se connecte pas

1. Vérifier que le backend tourne
2. Vérifier la URL WebSocket dans le frontend
3. Vérifier les pare-feu/proxy

```bash
# Tester la connexion
telnet localhost 8000
```

### After Effects Plugin ne charge pas

1. Vérifier le chemin d'installation
2. Redémarrer After Effects
3. Vérifier les logs (Window → Developer → Console)

## Variables d'Environnement

### Backend

| Variable | Défaut | Description |
|----------|--------|-------------|
| `OPENAI_API_KEY` | - | Clé API OpenAI (REQUIS) |
| `OPENAI_MODEL` | `gpt-4-turbo-preview` | Modèle OpenAI à utiliser |
| `BACKEND_PORT` | `8000` | Port du serveur backend |
| `BACKEND_HOST` | `0.0.0.0` | Host du serveur backend |
| `FRONTEND_URL` | `http://localhost:5173` | URL du frontend pour CORS |
| `WS_PORT` | `8001` | Port WebSocket (si séparé) |
| `ENVIRONMENT` | `development` | dev ou production |
| `DEBUG` | `True` | Logs debug activés |

### Frontend

| Variable | Défaut | Description |
|----------|--------|-------------|
| `VITE_API_URL` | `http://localhost:8000/api` | URL API backend |
| `VITE_WS_URL` | `ws://localhost:8000/ws/client` | URL WebSocket |

## Prochaines Étapes

1. ✅ Accéder au frontend: http://localhost:5173
2. ✅ Essayer une commande: "Ajoute un glow"
3. ✅ Vérifier les logs backend
4. ✅ Ouvrir After Effects et charger le plugin
5. ✅ Tester une commande avec AE connecté

## Support

Pour les problèmes:
1. Consulter les logs (backend + frontend)
2. Vérifier les configurations
3. Relancer les services
4. Consulter la documentation

---

**Status:** ✅ Installation complète
**Dernière mise à jour:** 2024
