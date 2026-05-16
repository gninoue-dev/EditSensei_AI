#!/usr/bin/env python3
"""
Lanceur du backend ÉDITSENSEI AI
"""

import os
import sys
import subprocess

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(__file__))

# Vérifier la clé OpenAI
from app.config import settings

if not settings.OPENAI_API_KEY:
    print("⚠️  AVERTISSEMENT: OPENAI_API_KEY non configurée!")
    print("Définissez OPENAI_API_KEY dans .env ou en variable d'environnement")
    print("L'application fonctionnera mais sans IA")

# Lancer uvicorn
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
