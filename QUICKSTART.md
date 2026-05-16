# 🚀 ÉDITSENSEI AI - Quick Start

## Installation Rapide (5 minutes)

### 1️⃣ Clone & Setup
```bash
git clone https://github.com/editsensei/editsensei-ai.git
cd ÉDITSENSEI_AI

# Backend
cd backend
python3 -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt

# .env - Ajouter votre clé OpenAI
cp .env.example .env
nano .env  # Éditer et ajouter OPENAI_API_KEY
```

### 2️⃣ Frontend
```bash
cd ../frontend
npm install
```

### 3️⃣ Démarrer

#### Option 1: Script automatique (Unix/Mac)
```bash
chmod +x start.sh
./start.sh
```

#### Option 2: Manuel (Windows/Multi-terminal)
```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python run.py

# Terminal 2 - Frontend
cd frontend
npm run dev

# Terminal 3 - Optional: Watch logs
tail -f backend/logs.txt
```

#### Option 3: Docker
```bash
docker-compose up
```

---

## 🎯 Utilisation Immédiate

### Via Interface Web
1. Ouvrir http://localhost:5173
2. Taper une commande: "Ajoute un glow"
3. Voir la réponse IA en bas

### Commandes Exemples
```
"Ajoute un impact anime"
"Rends ce passage plus agressif"  
"Sync avec le beat"
"Plus smooth, s'il te plaît"
"Impact gaming à 2 secondes"
```

### Via cURL (API)
```bash
curl -X POST http://localhost:8000/api/command \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Ajoute un glow",
    "style": "aggressive"
  }'
```

---

## 📌 Structure Clé

```
ÉDITSENSEI_AI/
├── backend/          ← FastAPI + IA (port 8000)
├── frontend/         ← React UI (port 5173)
├── ae-plugin/        ← Plugin After Effects
├── presets/          ← Configurations d'effets
└── README.md         ← Documentation complète
```

---

## ⚡ Vérification Installation

```bash
# Backend health
curl http://localhost:8000/health

# Frontend
curl http://localhost:5173

# WebSocket
npx wscat -c ws://localhost:8000/ws/client
```

---

## 🔧 Troubleshooting Rapide

| Problème | Solution |
|----------|----------|
| Port 8000 occupé | `lsof -ti:8000 \| xargs kill -9` |
| Clé OpenAI manquante | Ajouter OPENAI_API_KEY dans backend/.env |
| Module Python manquant | `pip install -r requirements.txt` |
| npm install échoue | Supprimer node_modules et recommencer |

---

## 📞 Aide

- 📚 Documentation complète: `README.md`
- 🔧 Guide d'installation: `SETUP.md`
- 💬 API Docs: http://localhost:8000/docs
- 🐛 Issues: GitHub Issues

---

**Prêt? 🎬 Commencez par ouvrir http://localhost:5173**
