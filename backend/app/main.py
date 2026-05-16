from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sys

from .config import settings
from .api.routes import router as api_router
from .api.websocket import router as ws_router


# Initialisation FastAPI
app = FastAPI(
    title="ÉDITSENSEI AI",
    description="AI-powered Adobe After Effects editor",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router)
app.include_router(ws_router)


# ====== ROOT ROUTES ======

@app.get("/")
async def root():
    return {
        "name": "ÉDITSENSEI AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "ai_enabled": bool(settings.OPENAI_API_KEY),
        "environment": settings.ENVIRONMENT
    }


# ====== STARTUP/SHUTDOWN ======

@app.on_event("startup")
async def startup_event():
    print("\n" + "="*50)
    print("🚀 ÉDITSENSEI AI Backend")
    print("="*50)
    print(f"📍 Running on {settings.BACKEND_HOST}:{settings.BACKEND_PORT}")
    print(f"🌐 Frontend URL: {settings.FRONTEND_URL}")
    print(f"🎬 After Effects Port: {settings.AE_PORT}")
    print(f"🤖 Model: {settings.OPENAI_MODEL}")
    print(f"🔑 OpenAI Configured: {bool(settings.OPENAI_API_KEY)}")
    print("="*50 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    print("\n🛑 Backend shutdown\n")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG
    )
