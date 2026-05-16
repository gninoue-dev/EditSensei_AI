#!/bin/bash

# ÉDITSENSEI AI - Script de démarrage complet

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════╗"
echo "║          ÉDITSENSEI AI - Démarrage Complet         ║"
echo "╚════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Vérifier les prérequis
check_requirements() {
    echo -e "${YELLOW}Vérification des prérequis...${NC}"
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 non trouvé${NC}"
        exit 1
    fi
    
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js non trouvé${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Tous les prérequis sont ok${NC}"
}

# Setup Backend
setup_backend() {
    echo -e "\n${BLUE}📦 Configuration du Backend...${NC}"
    
    cd backend
    
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}Création de l'environnement virtuel...${NC}"
        python3 -m venv venv
    fi
    
    echo -e "${YELLOW}Activation du venv...${NC}"
    source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null
    
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}Création du fichier .env...${NC}"
        cp .env.example .env
        echo -e "${RED}⚠️  Mettez à jour OPENAI_API_KEY dans backend/.env${NC}"
    fi
    
    echo -e "${YELLOW}Installation des dépendances Python...${NC}"
    pip install -q -r requirements.txt
    
    echo -e "${GREEN}✅ Backend configuré${NC}"
    
    cd ..
}

# Setup Frontend
setup_frontend() {
    echo -e "\n${BLUE}🎨 Configuration du Frontend...${NC}"
    
    cd frontend
    
    echo -e "${YELLOW}Installation des dépendances Node...${NC}"
    npm install -q
    
    echo -e "${GREEN}✅ Frontend configuré${NC}"
    
    cd ..
}

# Démarrer les services
start_services() {
    echo -e "\n${BLUE}🚀 Démarrage des services...${NC}"
    
    # Backend en arrière-plan
    echo -e "${YELLOW}Démarrage du Backend (port 8000)...${NC}"
    cd backend
    source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null
    python run.py &
    BACKEND_PID=$!
    cd ..
    
    sleep 2
    
    # Frontend en arrière-plan
    echo -e "${YELLOW}Démarrage du Frontend (port 5173)...${NC}"
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    
    sleep 2
    
    # Afficher les URLs
    echo -e "\n${GREEN}╔════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          🎉 ÉDITSENSEI AI est démarré!              ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════╝${NC}"
    echo -e "\n${BLUE}URLs:${NC}"
    echo -e "  🌐 Frontend:   ${GREEN}http://localhost:5173${NC}"
    echo -e "  🔧 Backend:    ${GREEN}http://localhost:8000${NC}"
    echo -e "  📚 API Docs:   ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "\n${YELLOW}Appuyez sur Ctrl+C pour arrêter...${NC}\n"
    
    # Attendre
    wait
}

# Cleanup
cleanup() {
    echo -e "\n${YELLOW}Arrêt des services...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Services arrêtés${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Main
check_requirements
setup_backend
setup_frontend
start_services
