from typing import List, Dict, Any, Optional
from ..models.schemas import AECommand, AEResponse
from ..ws_manager import manager
import json


class AEController:
    """Contrôleur pour communiquer avec After Effects"""
    
    # Mapping des effets supportés
    SUPPORTED_EFFECTS = {
        "glow": {"name": "Glow", "default_intensity": 0.8},
        "blur": {"name": "Gaussian Blur", "default_intensity": 0.5},
        "shake": {"name": "Wiggler", "default_intensity": 0.7},
        "flash": {"name": "Levels", "default_intensity": 1.0},
        "chromatic": {"name": "RGB Displacement", "default_intensity": 0.6},
        "zoom": {"name": "Scale Keyframe", "default_intensity": 0.8},
        "rotation": {"name": "Rotation", "default_intensity": 0.5},
    }
    
    def __init__(self):
        self.is_connected = False
        self.current_layer = None
    
    async def execute_command(self, command: AECommand) -> AEResponse:
        """Exécute une commande After Effects"""
        
        if not manager.ae_connection:
            return AEResponse(
                success=False,
                message="After Effects non connecté"
            )
        
        try:
            # Construire le payload pour AE
            payload = self._build_ae_payload(command)
            
            # Envoyer à AE via WebSocket
            success = await manager.send_to_ae(payload)
            
            if success:
                return AEResponse(
                    success=True,
                    message=f"Commande exécutée: {command.action}",
                    data=payload
                )
            else:
                return AEResponse(
                    success=False,
                    message="Erreur d'envoi à After Effects"
                )
        
        except Exception as e:
            print(f"❌ Erreur AE: {e}")
            return AEResponse(
                success=False,
                message=f"Erreur: {str(e)}"
            )
    
    async def execute_commands(self, commands: List[AECommand]) -> List[AEResponse]:
        """Exécute plusieurs commandes AE"""
        
        results = []
        for command in commands:
            result = await self.execute_command(command)
            results.append(result)
        
        return results
    
    def _build_ae_payload(self, command: AECommand) -> Dict[str, Any]:
        """Construit le payload pour After Effects"""
        
        payload = {
            "type": "ae_command",
            "action": command.action,
            "timestamp": None
        }
        
        if command.action == "add_effect":
            payload.update({
                "effect": command.property or "Glow",
                "layer": command.layer or "null",
                "intensity": command.value.get("intensity", 0.8) if isinstance(command.value, dict) else 0.8
            })
        
        elif command.action == "set_keyframe":
            payload.update({
                "layer": command.layer,
                "property": command.property,
                "value": command.value,
                "time": command.duration or 0
            })
        
        elif command.action == "adjust_property":
            payload.update({
                "layer": command.layer,
                "property": command.property,
                "value": command.value
            })
        
        elif command.action == "add_transition":
            payload.update({
                "transition_type": command.property or "Cross Dissolve",
                "duration": command.duration or 1.0
            })
        
        return payload
    
    async def set_layer(self, layer_name: str) -> bool:
        """Défini le calque courant"""
        self.current_layer = layer_name
        
        command = AECommand(
            action="select_layer",
            layer=layer_name
        )
        
        result = await self.execute_command(command)
        return result.success
    
    async def add_keyframe(self, layer: str, property: str, value: Any, time: float) -> AEResponse:
        """Ajoute une keyframe"""
        
        command = AECommand(
            action="set_keyframe",
            layer=layer,
            property=property,
            value=value,
            duration=time
        )
        
        return await self.execute_command(command)
    
    async def add_effect(self, layer: str, effect: str, intensity: float = 0.8) -> AEResponse:
        """Ajoute un effet"""
        
        command = AECommand(
            action="add_effect",
            layer=layer,
            property=effect,
            value={"intensity": intensity}
        )
        
        return await self.execute_command(command)
    
    async def apply_preset(self, layer: str, preset_data: Dict[str, Any]) -> List[AEResponse]:
        """Applique un preset complet"""
        
        commands = []
        results = []
        
        # Ajouter les effets du preset
        for effect in preset_data.get("effects", []):
            commands.append(AECommand(
                action="add_effect",
                layer=layer,
                property=effect.get("name"),
                value={"intensity": effect.get("intensity", 0.8)},
                duration=effect.get("duration", 1.0)
            ))
        
        # Ajouter les keyframes
        for kf in preset_data.get("keyframes", []):
            commands.append(AECommand(
                action="set_keyframe",
                layer=layer,
                property=kf.get("property"),
                value=kf.get("value"),
                duration=kf.get("time")
            ))
        
        # Exécuter toutes les commandes
        for cmd in commands:
            result = await self.execute_command(cmd)
            results.append(result)
        
        return results


# Instance globale
ae_controller = AEController()
