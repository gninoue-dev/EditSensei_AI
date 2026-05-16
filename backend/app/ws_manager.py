from fastapi import WebSocket
from typing import Set, Dict, List
import json
import asyncio


class ConnectionManager:
    """Gère les connexions WebSocket"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.ae_connection: WebSocket = None
        self.message_queue: List[dict] = []
    
    async def connect(self, websocket: WebSocket):
        """Connexion client"""
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"✅ Client connecté. Total: {len(self.active_connections)}")
    
    async def disconnect(self, websocket: WebSocket):
        """Déconnexion client"""
        self.active_connections.discard(websocket)
        if self.ae_connection == websocket:
            self.ae_connection = None
        print(f"❌ Client déconnecté. Total: {len(self.active_connections)}")
    
    async def register_ae_connection(self, websocket: WebSocket):
        """Enregistre la connexion After Effects"""
        self.ae_connection = websocket
        await self.broadcast({
            "type": "status",
            "message": "After Effects connecté",
            "ae_connected": True
        })
        print("🎬 After Effects enregistré")
    
    async def broadcast(self, data: dict):
        """Envoie un message à tous les clients"""
        message = json.dumps(data)
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Erreur envoi: {e}")
                disconnected.add(connection)
        
        # Nettoyer les connexions mortes
        for conn in disconnected:
            await self.disconnect(conn)
    
    async def send_to_ae(self, data: dict) -> bool:
        """Envoie une commande à After Effects"""
        if not self.ae_connection:
            print("⚠️  After Effects non connecté")
            return False
        
        try:
            await self.ae_connection.send_json(data)
            return True
        except Exception as e:
            print(f"Erreur envoi AE: {e}")
            self.ae_connection = None
            return False
    
    async def receive_from_ae(self, websocket: WebSocket) -> dict:
        """Reçoit une réponse de After Effects"""
        try:
            data = await websocket.receive_json()
            return data
        except Exception as e:
            print(f"Erreur réception AE: {e}")
            return None


manager = ConnectionManager()
