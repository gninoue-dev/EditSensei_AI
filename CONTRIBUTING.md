# 🤝 ÉDITSENSEI AI - Guide de Contribution

Merci de vouloir contribuer à ÉDITSENSEI AI!

## Comment Contribuer?

### 1. Fork & Clone

```bash
git clone https://github.com/votre-username/editsensei-ai.git
cd ÉDITSENSEI_AI
git checkout -b feature/ma-feature
```

### 2. Setup Local

Suivre le guide `SETUP.md` pour installer l'environnement.

### 3. Faire ses changements

- Créer une branche feature
- Commiter régulièrement
- Push sur votre fork

### 4. Pull Request

1. Pousser votre branche
2. Créer une PR vers `main`
3. Description claire du changement
4. Tests passent?
5. Attendre review

## Structure du Code

### Backend (`backend/app/`)

```
app/
├── api/           # Routes FastAPI
├── ai/            # Moteur IA
├── ae/            # Contrôle After Effects
├── video/         # Analyse vidéo
├── models/        # Schémas Pydantic
└── main.py        # App principale
```

### Frontend (`frontend/src/`)

```
src/
├── components/    # Composants React
├── hooks/         # Hooks personnalisés
├── services/      # Services API/WS
├── types/         # Types TypeScript
└── App.tsx        # App principale
```

### Plugin AE (`ae-plugin/src/`)

```
src/
├── index.html     # Interface
├── aeController.jsx   # Logique
└── manifest.xml   # Config plugin
```

## Standards de Code

### Python

```python
# Type hints obligatoires
def process_command(text: str, style: Optional[EditStyle] = None) -> AIResponse:
    """Docstring en français avec description."""
    pass

# Format: Black
# Linting: Pylint
# PEP8 strict
```

### TypeScript/React

```typescript
// Types explicites toujours
interface Props {
  onCommand?: (cmd: string) => void;
  loading?: boolean;
}

// Hooks avec dépendances
useEffect(() => {
  // ...
}, [dependency]);

// Composants fonctionnels + hooks
export function MyComponent() {
  // ...
}
```

### CSS/TailwindCSS

```css
/* Utiliser TailwindCSS utilities */
/* Organiser par composant */
/* Mobile-first responsive */
```

## Conventions Git

### Commits

```bash
# Format: type(scope): description
git commit -m "feat(ai): add new command parser"
git commit -m "fix(api): handle WebSocket errors"
git commit -m "docs(setup): update installation guide"
```

Types:
- `feat`: Nouvelle fonctionnalité
- `fix`: Correction bug
- `docs`: Documentation
- `style`: Format/lint
- `refactor`: Refactorisation
- `perf`: Performance
- `test`: Tests

### Branches

```bash
# Format: type/description
git checkout -b feat/command-parser
git checkout -b fix/websocket-timeout
git checkout -b docs/api-guide
```

## Tests

### Backend

```bash
cd backend
source venv/bin/activate
pytest tests/

# Avec coverage
pytest --cov=app tests/
```

### Frontend

```bash
cd frontend
npm test
npm run test:coverage
```

### Plugin AE

Tests manuels dans After Effects.

## Documentation

### Code Comments

```python
# Français obligatoire
def analyze_video(filepath: str) -> VideoAnalysis:
    """
    Analyse une vidéo et retourne les infos.
    
    Args:
        filepath: Chemin vers le fichier vidéo
        
    Returns:
        VideoAnalysis avec durée, fps, beats, etc.
        
    Raises:
        FileNotFoundError: Si le fichier n'existe pas
    """
```

### Documentation Files

- `README.md` - Overview
- `SETUP.md` - Installation
- `QUICKSTART.md` - Démarrage rapide
- `DEPLOYMENT.md` - Production
- Code comments - Explication technique

## Processus Review

1. ✅ Tests passent
2. ✅ Code review par 1 maintainer
3. ✅ Documentation à jour
4. ✅ Pas de warnings/errors
5. ✅ Commit history propre

## Problèmes Connus

- WebSocket timeout sur connexions lentes
- Rate limiting pas encore implémenté
- Tests unitaires incomplets

Voir `ISSUES.md` pour la liste complète.

## Idées de Contributions

### Easy (👶 Débutants)
- [ ] Ajouter nouveaux presets
- [ ] Améliorer le CSS
- [ ] Écrire de la documentation
- [ ] Corriger les typos

### Medium (👨‍💻 Intermédiaire)
- [ ] Ajouter tests
- [ ] Refactorer le code
- [ ] Améliorer le parser IA
- [ ] Nouvelles commandes

### Hard (🧠 Avancé)
- [ ] Implémenter la détection d'objets
- [ ] Fine-tune OpenAI
- [ ] Optimization WebSocket
- [ ] Implémenter collaborative editing

## Licence

Tous les contributions sont sous MIT License.

## Code of Conduct

- Soyez respectueux
- Pas de spam
- Pas de harcèlement
- Soyez constructif

## Questions?

- 💬 GitHub Discussions
- 🐛 Issues
- 📧 Email: team@editsensei.ai

---

**Merci pour votre contribution!** 🙏
