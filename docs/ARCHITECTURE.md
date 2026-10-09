# Architecture d'EditSensei AI v2

```
EditSensei_AI/
├── ae-panel/                 Extension CEP pour After Effects (2022+)
│   ├── CSXS/manifest.xml     déclaration du panneau (Node.js activé pour lancer le cerveau)
│   ├── index.html, css/      interface de chat (thème « Sakura Night »)
│   ├── js/main.js            logique : AE ⇄ cerveau, mode apprenti
│   ├── js/CSInterface.js     bibliothèque officielle Adobe
│   ├── jsx/editsensei.jsx    ExtendScript : lire le projet, CONSTRUIRE la compo, instantanés
│   └── tests/mock_ae.js      faux After Effects (Node) pour tester le JSX sans Adobe
├── brain/                    Le cerveau (Python, serveur local 127.0.0.1:8765)
│   └── editsensei/
│       ├── audio.py          tempo, beats, downbeats, énergie, sections, drops (librosa)
│       ├── footage.py        mouvement / netteté / coupes internes des clips (OpenCV)
│       ├── directives.py     consignes FR → Directives (100 % local)
│       ├── llm.py            Claude optionnel → mêmes Directives (sortie JSON structurée)
│       ├── style.py          le modèle de style (rythme, probabilités d'effets, look) + mélange
│       ├── planner.py        musique + clips + style + consignes → EditPlan
│       ├── preview.py        rendu MP4 d'un plan sans After Effects (OpenCV + FFmpeg)
│       ├── learn.py          apprentissage : vidéos de référence, mode apprenti, 👍
│       ├── assistant.py      orchestration de la conversation (sessions)
│       ├── server.py         API FastAPI pour le panneau
│       └── tools.py          FFmpeg du système ou embarqué (imageio-ffmpeg)
├── styles/                   styles fournis (JSON)
└── scripts/                  installation Windows/macOS, lancement, ligne de commande
```

## Le plan de montage (`EditPlan`)
Format neutre partagé par After Effects et l'aperçu :

| champ | rôle |
|---|---|
| `width`, `height`, `fps`, `duration` | la composition |
| `music`, `music_start` | fichier audio et point de départ dans la musique |
| `segments[]` | `clip`, `src_in`/`src_out` (dans la source), `t_in`/`t_out` (dans le montage), `speed` |
| `effects[]` | `type` (zoom_punch, shake, flash, blur_whip, glow, rgb_split), `t`, `duration`, `strength`, `moment` |
| `texts[]` | titres animés |
| `look` | contraste, saturation, vignette, bandes cinéma |
| `fade_in`, `fade_out` | fondus |

Tous les effets suivent la **même courbe** (montée en 15 % de la durée, retombée quadratique) côté aperçu (`preview.envelope`) et côté After Effects (`es_pulse` + expression de secousse) : ce qu'on voit dans l'aperçu correspond à ce qui est construit.

## Ce que construit After Effects
- **🎵 Musique** décalée de `music_start`, avec fondus audio.
- **Un calque par plan**, dans l'ordre du temps, avec :
  - recadrage pour remplir le cadre ;
  - `stretch` pour les ralentis ;
  - audio des clips coupé.
- **🎥 Caméra EditSensei**, un calque nul parent de tous les plans :
  - zooms en images clés adoucies ;
  - secousses par expression (compatible avec le moteur JavaScript ET l'ancien moteur ExtendScript).
- **Calques de réglage** : 💨 flou directionnel aux raccords, 🌈 RGB split (Décalage de couches + Transformer en mode Écran), ✨ Glow et 🎨 Look (Luminosité/Contraste + Teinte/Saturation).
- **⚡ Flash** : solide blanc en mode Addition, 🌑 vignette (masque inversé adouci), ▬ bandes cinéma, 🔤 titres (pop d'entrée + fondu) et 🌘 fondus noirs.
- Tout passe par des **matchNames** (indépendants de la langue d'After Effects).
- Toute la construction tient dans un seul bloc d'annulation.

## L'apprentissage
`style_from_events(musique, coupes, événements)` est le cœur commun :
1. **Rythme** : durée médiane d'un plan, en temps musicaux, selon l'énergie (calme / moyen / fort) et part des coupes sur le beat.
2. **Effets** : pour chaque type d'instant (beat, premier temps, drop, changement de partie), proportion de ces instants qui reçoivent l'effet.
3. **Look** : contraste, saturation, bandes noires, vignette (vidéos seulement).

Sources d'événements :
- **Vidéo** (`detect_events`), sur chaque image réduite à 192 px :
  - **coupes** : saut d'histogramme ;
  - **flashs** : pic de luminance qui retombe ;
  - **zoom punch** : suivi Lucas-Kanade + similitude estimée par RANSAC, puis échelle qui redescend ;
  - **secousses** : translation qui change de sens à chaque image ;
  - **flous de transition** : netteté effondrée au raccord ;
  - **RGB split** : décalage rouge/bleu par corrélation de phase.
- **Mode apprenti** (`events_from_snapshot`) : débuts de calques, images clés d'échelle et de position, solides « flash », effets ajoutés.
- **👍** : le plan validé lui-même.

Les styles se mélangent avec `StyleModel.absorb` : le poids d'un nouvel exemple est 1/(n+1), donc le style se stabilise. Les détecteurs les moins fiables (RGB split, flou, glow) ne comptent qu'à moitié.

**Validation** : `test_preview_and_learn_back` monte une vidéo avec un style connu, la rend, puis la réanalyse. Plus de 90 % des coupes sont retrouvées.

## Pistes d'évolution
- Un modèle neuronal (par ex. un petit transformeur sur les séquences de beats → effets), entraîné sur la bibliothèque de styles appris quand elle sera assez grande.
- Analyse du contenu (visages, sujet) pour recadrer intelligemment le vertical.
