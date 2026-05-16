import openai
from typing import List, Optional
from ..models.schemas import ConversationMessage, AIResponse, AECommand, EditStyle
from ..config import settings
import json


class OpenAIHandler:
    """Interface avec l'API OpenAI"""
    
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.conversation_history: List[ConversationMessage] = []
    
    async def process_command(self, user_input: str, style: Optional[EditStyle] = None) -> AIResponse:
        """
        Traite une commande utilisateur via OpenAI
        Retourne une AIResponse avec les commandes AE
        """
        
        # Ajouter le message utilisateur à l'historique
        self.conversation_history.append(
            ConversationMessage(role="user", content=user_input)
        )
        
        # Système prompt
        system_prompt = self._build_system_prompt(style)
        
        # Préparer les messages pour OpenAI
        messages = [
            {"role": "system", "content": system_prompt},
            *[
                {"role": msg.role, "content": msg.content}
                for msg in self.conversation_history
            ]
        ]
        
        try:
            # Appel OpenAI
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            assistant_message = response.choices[0].message.content
            
            # Parser la réponse pour extraire les commandes AE
            ae_commands = self._parse_ae_commands(assistant_message)
            confidence = response.choices[0].finish_reason == "stop" and 0.9 or 0.5
            
            # Ajouter la réponse à l'historique
            msg = ConversationMessage(
                role="assistant",
                content=assistant_message,
                ae_actions=ae_commands
            )
            self.conversation_history.append(msg)
            
            return AIResponse(
                command_understood=True,
                interpretation=assistant_message,
                ae_commands=ae_commands,
                confidence=confidence
            )
        
        except Exception as e:
            print(f"❌ Erreur OpenAI: {e}")
            return AIResponse(
                command_understood=False,
                interpretation=f"Erreur: {str(e)}",
                ae_commands=[],
                confidence=0
            )
    
    def _build_system_prompt(self, style: Optional[EditStyle] = None) -> str:
        """Construit le system prompt pour OpenAI"""
        
        style_info = f"L'utilisateur veut un style '{style.value}'." if style else ""
        
        return f"""Tu es un expert en montage vidéo et animation. Tu maîtrises Adobe After Effects et l'art de l'édition.

Tu dois INTERPRÉTER les commandes de montage données par l'utilisateur et TRADUIRE ces commandes en actions After Effects concrètes.

{style_info}

ÉTAPES:
1. Comprendre ce que veut l'utilisateur (ajouter un effet, synchroniser au beat, etc.)
2. Identifier les actions After Effects nécessaires
3. Répondre avec une explication CLAIRE et CONCISE
4. Inclure en JSON une liste d'actions AE à exécuter

ACTIONS AE SUPPORTÉES:
- add_effect: Ajouter un effet (glow, blur, shake, etc.)
- set_keyframe: Ajouter une keyframe sur une propriété
- adjust_property: Ajuster une propriété (scale, position, opacity, etc.)
- add_transition: Ajouter une transition
- set_timing: Définir le timing/vitesse

FORMAT DE RÉPONSE:
```
Explication claire en français...

ACTIONS_AE:
[
  {{"action": "add_effect", "layer": "Layer 1", "effect": "Glow", "intensity": 0.8}},
  {{"action": "set_keyframe", "layer": "Layer 1", "property": "position", "value": [640, 360], "time": 2.5}}
]
```

EXEMPLES DE COMMANDES:

"Ajoute un impact anime"
→ RGB split + flash blanc + zoom violent + shake

"Rends ce passage plus agressif"
→ Shake fort, zoom rapide, glow, flash, cuts rapides

"Sync avec le beat"
→ Keyframes synchronisées au rythme détecté

"Ajoute une velocity TikTok"
→ Accélération progressive + ease out fort + scale final

Réponds TOUJOURS avec clarté et concision. Inclus TOUJOURS les actions JSON.
"""
    
    def _parse_ae_commands(self, response_text: str) -> List[AECommand]:
        """Extrait les commandes AE de la réponse OpenAI"""
        
        ae_commands = []
        
        # Chercher le bloc JSON ACTIONS_AE
        try:
            if "ACTIONS_AE:" in response_text:
                json_start = response_text.find("[", response_text.find("ACTIONS_AE:"))
                json_end = response_text.rfind("]") + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    actions = json.loads(json_str)
                    
                    for action in actions:
                        ae_commands.append(AECommand(
                            action=action.get("action", ""),
                            layer=action.get("layer"),
                            property=action.get("property"),
                            value=action.get("value"),
                            duration=action.get("duration")
                        ))
        except Exception as e:
            print(f"⚠️  Erreur parsing JSON: {e}")
        
        return ae_commands
    
    def clear_history(self):
        """Efface l'historique de conversation"""
        self.conversation_history = []


# Instance globale
openai_handler = OpenAIHandler()
