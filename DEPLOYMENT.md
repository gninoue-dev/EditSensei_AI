# 🚀 ÉDITSENSEI AI - Déploiement Production

## Architecture Production

```
┌─────────────────────────────────────────────┐
│         Nginx (Reverse Proxy)               │
│         Port 80/443                         │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
   Backend          Frontend
   (Gunicorn)       (Node/Serve)
   Port 8000        Port 3000
```

## Déploiement avec Docker

### 1. Préparer l'environnement

```bash
# Créer .env.production
cat > .env.production << EOF
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4-turbo-preview
BACKEND_PORT=8000
ENVIRONMENT=production
DEBUG=False
EOF
```

### 2. Build et démarrage

```bash
# Build images
docker-compose build

# Démarrer en production
docker-compose up -d

# Vérifier statut
docker-compose ps

# Voir les logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. Nginx Configuration

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:5173;
}

server {
    listen 80;
    server_name editsensei.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name editsensei.example.com;

    # SSL Certificates
    ssl_certificate /etc/ssl/certs/editsensei.crt;
    ssl_certificate_key /etc/ssl/private/editsensei.key;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

## Déploiement sur Heroku

### 1. Setup Heroku

```bash
# Login
heroku login

# Créer l'app
heroku create editsensei-ai

# Ajouter buildpacks
heroku buildpacks:add heroku/python
heroku buildpacks:add heroku/nodejs
```

### 2. Configuration

```bash
# Ajouter les variables d'environnement
heroku config:set OPENAI_API_KEY=sk-xxx
heroku config:set ENVIRONMENT=production
heroku config:set DEBUG=False
```

### 3. Deploy

```bash
# Push to Heroku
git push heroku main

# Voir les logs
heroku logs -t
```

## Déploiement sur AWS

### Avec Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 editsensei-ai
eb create production

# Deploy
eb deploy

# View logs
eb logs
```

### Avec ECS + Fargate

```bash
# Build et push images
aws ecr create-repository --repository-name editsensei-backend
aws ecr create-repository --repository-name editsensei-frontend

docker tag editsensei-backend:latest \
  123456789.dkr.ecr.us-east-1.amazonaws.com/editsensei-backend:latest

docker push \
  123456789.dkr.ecr.us-east-1.amazonaws.com/editsensei-backend:latest

# Créer ECS cluster et services via AWS Console ou CLI
```

## Monitoring & Logs

### Avec CloudWatch (AWS)

```bash
# Voir les logs
aws logs tail /editsensei/backend --follow
aws logs tail /editsensei/frontend --follow
```

### Avec Datadog

```bash
# Installer agent
DD_AGENT_MAJOR_VERSION=7 DD_API_KEY=xxx bash -c "$(curl -L https://s3.amazonaws.com/dd-agent/scripts/install_agent.sh)"

# Configuration
cat > datadog.yaml << EOF
logs:
  - type: file
    path: /app/logs/*.log
    service: editsensei
    source: python
EOF
```

## Performance & Scaling

### Caching

```python
# Redis pour le cache
from redis import Redis

redis = Redis(host='redis-server', port=6379)

# Cache des réponses IA
@cache.cached(timeout=3600, key_prefix='ai_response_')
def process_command(text):
    ...
```

### Load Balancing

```bash
# Upstart multiple workers
gunicorn -w 4 -b 0.0.0.0:8000 app.main:app
```

### CDN

```bash
# Avec Cloudflare
# - DNS: editsensei.example.com -> Cloudflare
# - Cache static assets
# - DDoS protection
```

## Security Checklist

- [ ] HTTPS activé
- [ ] CORS configuré correctement
- [ ] Rate limiting actif
- [ ] OPENAI_API_KEY ne jamais en clair
- [ ] Base de données sécurisée
- [ ] Logs en place
- [ ] Backup automatiques
- [ ] Monitoring actif
- [ ] WAF activé (CloudFlare/AWS)
- [ ] Secrets en env variables

## Problèmes Courants

### Erreur 502 Bad Gateway

```bash
# Vérifier les services
docker-compose logs backend
docker-compose ps

# Redémarrer
docker-compose down
docker-compose up -d
```

### WebSocket timeout

```bash
# Augmenter les timeouts Nginx
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

### Mémoire insuffisante

```bash
# Limiter les workers
gunicorn -w 2 --max-requests 1000 app.main:app
```

## Rollback

```bash
# Avec Docker
git revert <commit>
docker-compose build
docker-compose up -d

# Avec Heroku
heroku releases
heroku rollback v5
```

---

**Production ready!** 🎬
