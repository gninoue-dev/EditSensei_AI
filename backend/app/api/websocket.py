from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..ws_manager import manager
from ..ai.engine import ai_engine
from ..models.schemas import EditStyle
import json

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/ws/client")
async def websocket_client_endpoint(websocket: WebSocket):
    """WebSocket pour clients Frontend"""
    
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Dispatcher les messages
            msg_type = message.get("type")
            
            if msg_type == "command":
                # Commande texte
                result = await ai_engine.process_user_command(
                    user_input=message.get("text"),
                    style=EditStyle(message.get("style")) if message.get("style") else None,
                    layer=message.get("layer")
                )
                
                await websocket.send_json({
                    "type": "command_result",
                    "data": result
                })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif msg_type == "ae_status_request":
                await websocket.send_json({
                    "type": "ae_status",
                    "connected": manager.ae_connection is not None
                })
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    
    except Exception as e:
        print(f"❌ Erreur WS Client: {e}")
        await manager.disconnect(websocket)


@router.websocket("/ws/ae")
async def websocket_ae_endpoint(websocket: WebSocket):
    """WebSocket pour After Effects Plugin"""
    
    await manager.connect(websocket)
    await manager.register_ae_connection(websocket)
    
    try:
        while True:
            # Recevoir les données d'AE
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ready":
                print("🎬 After Effects plugin prêt")
                await manager.broadcast({
                    "type": "ae_status",
                    "message": "After Effects prêt",
                    "ae_connected": True
                })
            
            elif msg_type == "command_executed":
                # Réponse d'exécution d'une commande
                print(f"✅ Commande exécutée: {data.get('command')}")
                await manager.broadcast({
                    "type": "ae_command_executed",
                    "command": data.get("command"),
                    "success": data.get("success")
                })
            
            elif msg_type == "error":
                print(f"❌ Erreur AE: {data.get('message')}")
                await manager.broadcast({
                    "type": "ae_error",
                    "message": data.get("message")
                })
            
            elif msg_type == "status":
                # Mise à jour de statut
                await manager.broadcast({
                    "type": "ae_status_update",
                    "data": data.get("data")
                })
    
    except WebSocketDisconnect:
        print("❌ After Effects déconnecté")
        await manager.disconnect(websocket)
        await manager.broadcast({
            "type": "ae_status",
            "message": "After Effects déconnecté",
            "ae_connected": False
        })
    
    except Exception as e:
        print(f"❌ Erreur WS AE: {e}")
        await manager.disconnect(websocket)
