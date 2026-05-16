#!/bin/bash

# CRÉATION ARCHITECTURE ÉDITSENSEI AI

cd /home/claude

# 1. STRUCTURE DE BASE
mkdir -p ÉDITSENSEI_AI/{backend/{app/{api,ai,ae,video,models},tests},frontend/{src/{components,hooks,services,types},public},ae-plugin/{src/{components,lib},build},ai-engine/models,video-analysis,presets,shared,websocket-server}

cd ÉDITSENSEI_AI

# 2. BACKEND - Python FastAPI
cd backend

# Créer venv et installer dépendances
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# requirements.txt sera créé à l'étape suivante
# pip install -r requirements.txt

cd ..

# 3. FRONTEND - React + TypeScript + Vite
cd frontend

npm create vite@latest . -- --template react-ts

# Ajouter dépendances
npm install
npm install -D tailwindcss postcss autoprefixer
npm install axios

cd ..

# 4. FICHIERS .env
touch backend/.env
touch backend/.env.example

# 5. Git
git init
echo "venv/" > .gitignore
echo "node_modules/" >> .gitignore
echo ".env" >> .gitignore
echo "*.pyc" >> .gitignore
echo "__pycache__" >> .gitignore
echo ".DS_Store" >> .gitignore
echo "dist/" >> .gitignore

echo "✅ Architecture initialisée avec succès!"
