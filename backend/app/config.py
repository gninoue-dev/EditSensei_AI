import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration de l'application"""
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    
    # Server
    BACKEND_PORT: int = 8000
    BACKEND_HOST: str = "0.0.0.0"
    FRONTEND_URL: str = "http://localhost:5173"
    
    # WebSocket
    WS_PORT: int = 8001
    WS_HOST: str = "0.0.0.0"
    
    # After Effects
    AE_PORT: int = 14001
    AE_HOST: str = "localhost"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Paths
    UPLOAD_DIR: str = "./uploads"
    PRESET_DIR: str = "./presets"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def upload_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def preset_path(self) -> Path:
        path = Path(self.PRESET_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
