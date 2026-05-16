from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class CommandType(str, Enum):
    """Types de commandes supportées"""
    TEXT_COMMAND = "text_command"
    VIDEO_UPLOAD = "video_upload"
    PRESET_LOAD = "preset_load"
    STYLE_COPY = "style_copy"
    SYNC_BEAT = "sync_beat"


class EditStyle(str, Enum):
    """Styles d'édition disponibles"""
    AGGRESSIVE = "aggressive"
    SMOOTH = "smooth"
    ANIME = "anime"
    GAMING = "gaming"
    CINEMATIC = "cinematic"


# ====== COMMANDES ======

class CommandRequest(BaseModel):
    """Requête de commande texte"""
    text: str
    context: Optional[Dict[str, Any]] = None
    style: Optional[EditStyle] = None


class AECommand(BaseModel):
    """Commande After Effects"""
    action: str  # "add_effect", "set_keyframe", "adjust_property"
    layer: Optional[str] = None
    property: Optional[str] = None
    value: Optional[Any] = None
    duration: Optional[float] = None  # en secondes


class AEResponse(BaseModel):
    """Réponse d'After Effects"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# ====== VIDÉO ======

class VideoAnalysis(BaseModel):
    """Analyse vidéo"""
    duration: float
    fps: float
    resolution: str
    beats: List[float]  # temps des beats
    transitions: List[Dict[str, Any]]
    motion_intensity: float  # 0-1
    dominant_colors: List[str]
    suggested_style: EditStyle


class UploadResponse(BaseModel):
    """Réponse upload vidéo"""
    filename: str
    filepath: str
    analysis: Optional[VideoAnalysis] = None


# ====== PRESETS ======

class KeyframeConfig(BaseModel):
    """Configuration d'une keyframe"""
    time: float  # temps en secondes
    property: str  # "position", "scale", "rotation", etc.
    value: Any


class EffectConfig(BaseModel):
    """Configuration d'un effet"""
    name: str
    intensity: float  # 0-1
    duration: float
    params: Dict[str, Any] = {}


class Preset(BaseModel):
    """Preset d'édition"""
    name: str
    style: EditStyle
    description: str
    keyframes: List[KeyframeConfig] = []
    effects: List[EffectConfig] = []
    transitions: List[str] = []
    metadata: Dict[str, Any] = {}


# ====== IA ======

class AIResponse(BaseModel):
    """Réponse du moteur IA"""
    command_understood: bool
    interpretation: str
    ae_commands: List[AECommand]
    confidence: float  # 0-1


class ConversationMessage(BaseModel):
    """Message dans la conversation"""
    role: str  # "user" ou "assistant"
    content: str
    timestamp: Optional[float] = None
    ae_actions: Optional[List[AECommand]] = None


# ====== WEBSOCKET ======

class WSMessage(BaseModel):
    """Message WebSocket générique"""
    type: str
    data: Dict[str, Any]
    timestamp: Optional[float] = None


class StatusUpdate(BaseModel):
    """Mise à jour de statut"""
    type: str = "status"
    ae_connected: bool
    frontend_connected: bool
    current_command: Optional[str] = None
    last_error: Optional[str] = None
