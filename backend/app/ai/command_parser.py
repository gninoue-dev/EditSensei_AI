# Command Parser - Analyse les commandes utilisateur
# Peut être amélioré avec NLP avancé

import re
from typing import Dict, List, Tuple
from ..models.schemas import EditStyle


class CommandParser:
    """Parse et interpète les commandes utilisateur"""
    
    STYLE_KEYWORDS = {
        EditStyle.AGGRESSIVE: ["agressif", "violent", "intense", "fort", "puissant", "énergique"],
        EditStyle.SMOOTH: ["smooth", "fluide", "lisse", "doux", "léger", "tranquille"],
        EditStyle.ANIME: ["anime", "manga", "impact", "flash", "rgb", "couleur"],
        EditStyle.GAMING: ["gaming", "gaming", "rapide", "énergique", "dynamique", "fast"],
        EditStyle.CINEMATIC: ["cinéma", "cinématique", "pro", "professionnel", "élégant"],
    }
    
    EFFECT_KEYWORDS = {
        "glow": ["glow", "lueur", "halo", "brillance", "éclat"],
        "blur": ["blur", "flou", "flouter", "doux"],
        "shake": ["shake", "trembler", "vibration", "secousse"],
        "chromatic": ["chromatic", "rgb", "aberration", "couleur", "split"],
        "zoom": ["zoom", "rapprocher", "agrandir", "scale"],
        "flash": ["flash", "éclair", "explosion", "blanc"],
        "rotation": ["rotation", "tourner", "spin", "rotation"],
    }
    
    ACTION_KEYWORDS = {
        "add": ["ajoute", "add", "insère", "applique"],
        "remove": ["enlève", "remove", "supprime", "retire"],
        "adjust": ["ajuste", "modify", "change", "modifie"],
        "sync": ["sync", "synchronise", "beat", "rythme"],
    }
    
    @classmethod
    def extract_style(cls, text: str) -> EditStyle | None:
        """Extrait le style de la commande"""
        text_lower = text.lower()
        
        for style, keywords in cls.STYLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return style
        
        return None
    
    @classmethod
    def extract_effects(cls, text: str) -> List[str]:
        """Extrait les effets mentionnés"""
        text_lower = text.lower()
        found_effects = []
        
        for effect, keywords in cls.EFFECT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower and effect not in found_effects:
                    found_effects.append(effect)
        
        return found_effects
    
    @classmethod
    def extract_layer(cls, text: str) -> str | None:
        """Extrait le nom du calque"""
        # Chercher "layer X", "calque X", ou guillemets
        
        # Pattern: "layer 1", "Layer 1", "calque 1"
        layer_match = re.search(r'(?:layer|calque)\s+(\d+|\w+)', text, re.IGNORECASE)
        if layer_match:
            return f"Layer {layer_match.group(1)}"
        
        # Pattern: entre guillemets
        quote_match = re.search(r'"([^"]+)"', text)
        if quote_match:
            return quote_match.group(1)
        
        return None
    
    @classmethod
    def extract_intensity(cls, text: str) -> float | None:
        """Extrait l'intensité si mentionnée"""
        text_lower = text.lower()
        
        # Chercher "0.8", "80%", etc.
        intensity_match = re.search(r'(\d+(?:\.\d+)?)\s*%?', text_lower)
        if intensity_match:
            value = float(intensity_match.group(1))
            if '%' in text_lower[intensity_match.start():intensity_match.end()+1]:
                value = value / 100
            return min(value, 1.0)
        
        # Chercher des intensités textuelles
        if any(word in text_lower for word in ["fort", "strong", "high"]):
            return 0.8
        if any(word in text_lower for word in ["moyen", "medium"]):
            return 0.5
        if any(word in text_lower for word in ["faible", "light", "léger"]):
            return 0.3
        
        return None
    
    @classmethod
    def parse(cls, text: str) -> Dict:
        """Parse complet d'une commande"""
        
        return {
            "text": text,
            "style": cls.extract_style(text),
            "effects": cls.extract_effects(text),
            "layer": cls.extract_layer(text),
            "intensity": cls.extract_intensity(text),
            "is_valid": len(cls.extract_effects(text)) > 0 or "sync" in text.lower(),
        }


# Instance globale
parser = CommandParser()
