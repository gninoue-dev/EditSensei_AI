# ÉDITSENSEI AI - Adobe After Effects IA Editor

Assistant IA intelligent pour Adobe After Effects permettant de piloter le montage vidéo via commandes texte naturelles.

## 🎯 Features

- ✅ Chat IA avec OpenAI
- ✅ Commandes texte → Actions After Effects
- ✅ Presets d'effets pré-configurés
- ✅ Communication WebSocket bi-directionnelle
- ✅ Support multi-styles (Aggressive, Smooth, Anime, Gaming)
- ✅ Interface React moderne
- ✅ Plugin After Effects natif

## 🏗️ Architecture

```
ÉDITSENSEI_AI/
├── backend/          # FastAPI + Python
├── frontend/         # React + TypeScript
├── ae-plugin/        # Adobe After Effects Plugin
├── presets/          # Configurations d'effets
└── shared/           # Code partagé
```

### Backend (Python)
- **FastAPI** pour l'API REST
- **WebSocket** pour la communication temps réel
- **OpenAI API** pour la compréhension IA
- **Pydantic** pour la validation

### Frontend (React)
- **TypeScript** pour la sécurité des types
- **TailwindCSS** pour le styling
- **WebSocket Client** pour la communication
- **Axios** pour les appels API

### After Effects Plugin
- **ExtendScript** pour contrôler AE
- **CEP/HTML** pour l'interface utilisateur
- **WebSocket** pour communiquer avec le backend

## 📋 Installation

### 1. Prérequis
- Node.js 18+
- Python 3.9+
- Adobe After Effects 2023+ (optionnel pour tester)

### 2. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
```

Créer un fichier `.env`:
```
OPENAI_API_KEY=sk-votre-cle-api
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:5173
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Plugin After Effects

Copier le dossier `ae-plugin/` dans:
- **Windows**: `C:\Program Files\Adobe\Common\Media Cache Files\EXT`
- **Mac**: `/Applications/Adobe After Effects 2024/Scripts/ScriptUI Panels/`

Ou compiler le plugin avec Adobe UXP:
```bash
cd ae-plugin
npm install
npm run build
```

## 🚀 Démarrage

### 1. Lancer le Backend

```bash
cd backend
python run.py
```

Backend disponible sur: `http://localhost:8000`
API Docs sur: `http://localhost:8000/docs`

### 2. Lancer le Frontend

```bash
cd frontend
npm run dev
```

Frontend disponible sur: `http://localhost:5173`

### 3. Ouvrir le Plugin After Effects

Depuis After Effects:
- **Windows**: Window → Scripts → Run Script File → `ae-plugin/src/index.html`
- **Mac**: File → Scripts → Open Script File → `ae-plugin/src/index.html`

## 💬 Utilisation

### Commandes Texte Simples

```
"Ajoute un glow à ce calque"
"Rends ce passage plus agressif"
"Sync avec le beat"
"Ajoute une transition fluide"
"Impact anime à 2 secondes"
```

### Commandes avec Styles

Sélectionner un style avant d'envoyer la commande:
- **Aggressive**: Shake, glow, zoom rapide
- **Smooth**: Transitions fluides, blur doux
- **Anime**: RGB split, flash, zoom violent
- **Gaming**: Shakes énergiques, mouvements rapides

### Via API REST

```bash
curl -X POST http://localhost:8000/api/command \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Ajoute un glow",
    "style": "aggressive",
    "context": {"layer": "Layer 1"}
  }'
```

### Via WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/client');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'command',
    data: {
      text: 'Ajoute un glow',
      style: 'aggressive',
      layer: 'Layer 1'
    }
  }));
};

ws.onmessage = (event) => {
  const response = JSON.parse(event.data);
  console.log('Réponse:', response);
};
```

## 📊 API Endpoints

### POST `/api/command`
Traite une commande utilisateur

```json
{
  "text": "Ajoute un glow",
  "style": "aggressive",
  "context": {"layer": "Layer 1"}
}
```

### POST `/api/video/upload`
Upload une vidéo pour analyse

### GET `/api/presets`
Liste les presets disponibles

### POST `/api/preset/apply`
Applique un preset à un calque

### GET `/api/status`
Statut de la connexion

### WebSocket `/ws/client`
Connexion client bidirectionnelle

### WebSocket `/ws/ae`
Connexion After Effects bidirectionnelle

## 🔧 Configuration

### Backend (`backend/.env`)
```
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview
BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0
FRONTEND_URL=http://localhost:5173
WS_PORT=8001
WS_HOST=0.0.0.0
AE_PORT=14001
ENVIRONMENT=development
DEBUG=True
```

### Frontend (`.env.local`)
```
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws/client
```

## 🎨 Presets Disponibles

### aggressive.json
- Shake fort
- Glow intense
- Zoom violent
- Chromatic shift

### smooth.json
- Blur léger
- Glow doux
- Opacity fade
- Position slide

### anime.json
- RGB split
- Flash blanc
- Zoom violent
- Rotation shake

### gaming.json
- Shake énergique
- Glow moyen
- Chromatic shift
- Zoom rapide

## 📈 Développement

### Ajouter un nouveau preset

1. Créer `presets/my-preset.json`
2. Définir effects et keyframes
3. Utiliser via API: `/api/preset/apply?name=my-preset&layer=Layer%201`

### Ajouter un nouvel effet

1. Modifier `backend/app/ae/controller.py`
2. Ajouter la logique dans `addEffect()`
3. Inclure dans un preset

### Améliorer le moteur IA

1. Modifier `backend/app/ai/engine.py`
2. Ajuster les prompts dans `openai_handler.py`
3. Tester avec de nouvelles commandes

## 🐛 Troubleshooting

### After Effects ne se connecte pas
- Vérifier que le WebSocket backend écoute sur 8001
- Vérifier les pare-feu
- Consulter les logs dans la console AE

### Erreur OpenAI API
- Vérifier la clé API dans `.env`
- Vérifier le quota OpenAI
- Consulter les logs du backend

### Frontend ne se connecte pas au backend
- Vérifier que le backend tourne sur 8000
- Vérifier la CORS dans `backend/app/main.py`
- Vérifier l'URL dans `frontend/.env.local`

## 📝 Logs

### Backend
```
python run.py
```

### Frontend
```
npm run dev
```

### After Effects
Ouvrir Window → Developer → ExtendScript Debugger

## 📚 Ressources

- [OpenAI API Docs](https://platform.openai.com/docs)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [React Docs](https://react.dev)
- [Adobe After Effects Scripting](https://github.com/Adobe-CEP/CEP-Resources)

## 📄 License

MIT

## 👥 Auteur

ÉDITSENSEI Team

---

**Version:** 1.0.0  
**Dernière mise à jour:** 2024
