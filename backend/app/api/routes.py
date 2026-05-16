from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Optional
import os

from ..models.schemas import CommandRequest, AIResponse, UploadResponse, VideoAnalysis, EditStyle
from ..ai.engine import ai_engine
from ..ae.controller import ae_controller
from ..config import settings
from ..ws_manager import manager


router = APIRouter(prefix="/api", tags=["API"])


# ====== COMMANDES ======

@router.post("/command", response_model=dict)
async def process_command(request: CommandRequest):
    """Traite une commande utilisateur"""
    
    result = await ai_engine.process_user_command(
        user_input=request.text,
        style=request.style,
        layer=request.context.get("layer") if request.context else None
    )
    
    return result


@router.post("/command/quick")
async def quick_command(text: str, style: Optional[EditStyle] = None):
    """Commande rapide (shorthand)"""
    
    result = await ai_engine.process_user_command(text, style)
    return result


# ====== VIDÉO ======

@router.post("/video/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """Upload une vidéo pour analyse"""
    
    if not file.filename.endswith(('.mp4', '.mov', '.avi', '.mkv')):
        raise HTTPException(status_code=400, detail="Format vidéo non supporté")
    
    try:
        # Sauvegarder le fichier
        filepath = settings.upload_path / file.filename
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Analyse simple (à compléter)
        analysis = VideoAnalysis(
            duration=10.0,
            fps=30,
            resolution="1920x1080",
            beats=[],
            transitions=[],
            motion_intensity=0.5,
            dominant_colors=["#FF0000"],
            suggested_style=EditStyle.AGGRESSIVE
        )
        
        await manager.broadcast({
            "type": "video_uploaded",
            "filename": file.filename,
            "filepath": str(filepath)
        })
        
        return UploadResponse(
            filename=file.filename,
            filepath=str(filepath),
            analysis=analysis
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ====== PRESETS ======

@router.get("/presets")
async def list_presets():
    """Liste tous les presets disponibles"""
    
    presets = []
    preset_dir = settings.preset_path
    
    for file in os.listdir(preset_dir):
        if file.endswith('.json'):
            presets.append(file.replace('.json', ''))
    
    return {"presets": presets}


@router.post("/preset/apply")
async def apply_preset(name: str, layer: str):
    """Applique un preset à un calque"""
    
    try:
        preset_file = settings.preset_path / f"{name}.json"
        
        if not preset_file.exists():
            raise HTTPException(status_code=404, detail="Preset non trouvé")
        
        import json
        with open(preset_file, 'r') as f:
            preset_data = json.load(f)
        
        responses = await ae_controller.apply_preset(layer, preset_data)
        
        return {
            "success": all(r.success for r in responses),
            "preset": name,
            "layer": layer,
            "responses": [{"success": r.success, "message": r.message} for r in responses]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ====== STATUS ======

@router.get("/status")
async def get_status():
    """Statut de la connexion"""
    
    return {
        "ae_connected": manager.ae_connection is not None,
        "clients_connected": len(manager.active_connections),
        "auto_execute": ai_engine.auto_execute
    }


@router.post("/settings/auto-execute")
async def set_auto_execute(enabled: bool):
    """Active/désactive l'exécution automatique"""
    
    ai_engine.set_auto_execute(enabled)
    
    return {"auto_execute": enabled}


# ====== DEBUG ======

@router.get("/health")
async def health_check():
    """Health check"""
    
    return {
        "status": "ok",
        "version": "1.0.0",
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "ae_connected": manager.ae_connection is not None
    }


@router.post("/clear-history")
async def clear_conversation_history():
    """Efface l'historique de conversation"""
    
    ai_engine.clear_history()
    
    return {"message": "Historique effacé"}
