#!/bin/bash
# Lance le cerveau d'EditSensei à la main (le panneau le démarre normalement tout seul)
cd "$(dirname "$0")/../brain" && exec .venv/bin/python -m editsensei
