from typing import Optional, List
from ..models.schemas import AIResponse, AECommand, EditStyle, AEResponse
from .openai_handler import openai_handler
from ..ae.controller import ae_controller


class AIEngine:
    """Moteur IA principal - orchestration"""
    
    def __init__(self):
        self.openai = openai_handler
        self.ae = ae_controller
        self.auto_execute = True  # Exécute automatiquement les commandes AE
    
    async def process_user_command(self, user_input: str, style: Optional[EditStyle] = None, layer: Optional[str] = None) -> dict:
        """
        Process une commande utilisateur de bout en bout:
        1. Analyse avec OpenAI
        2. Extrait les commandes AE
        3. Exécute automatiquement si auto_execute=True
        """
        
        # Étape 1: Analyser avec OpenAI
        ai_response = await self.openai.process_command(user_input, style)
        
        if not ai_response.command_understood:
            return {
                "success": False,
                "message": ai_response.interpretation,
                "ae_responses": []
            }
        
        # Étape 2: Extraire et modifier les commandes si couche spécifiée
        ae_commands = ai_response.ae_commands
        
        if layer:
            for cmd in ae_commands:
                if not cmd.layer:
                    cmd.layer = layer
        
        # Étape 3: Exécuter les commandes
        ae_responses = []
        
        if self.auto_execute and ae_commands:
            ae_responses = await ae_controller.execute_commands(ae_commands)
        
        return {
            "success": True,
            "message": ai_response.interpretation,
            "ae_commands": ae_commands,
            "ae_responses": ae_responses,
            "confidence": ai_response.confidence
        }
    
    def set_auto_execute(self, enabled: bool):
        """Active/désactive l'exécution automatique"""
        self.auto_execute = enabled
    
    def clear_history(self):
        """Efface l'historique de conversation"""
        self.openai.clear_history()


# Instance globale
ai_engine = AIEngine()
