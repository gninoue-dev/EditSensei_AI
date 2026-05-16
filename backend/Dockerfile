FROM python:3.11-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY app/ ./app/
COPY run.py .

# Créer les dossiers
RUN mkdir -p uploads presets

# Exposer les ports
EXPOSE 8000 8001

# Lancer l'application
CMD ["python", "run.py"]
