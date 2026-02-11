"""
WebSocket endpoint for real-time chat - MemAgent

Provides bidirectional communication with progress updates during agent pipeline execution.
"""

from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.monitoring import logger
from app.deps import get_db

router = None  # WebSocket router to be added to main app


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("websocket_connected", session_id=session_id)
    
    def disconnect(self, session_id: str):
        """Remove connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info("websocket_disconnected", session_id=session_id)
    
    async def send_message(self, session_id: str, message: dict):
        """Send message to specific session."""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error("websocket_send_failed", session_id=session_id, error=str(e))
                self.disconnect(session_id)
    
    async def broadcast(self, message: dict):
        """Broadcast to all connections."""
        for session_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error("websocket_broadcast_failed", session_id=session_id, error=str(e))
                self.disconnect(session_id)


manager = ConnectionManager()


async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time chat.
    
    Accepts messages and streams responses from the agent team.
    """
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            message = data.get("message", "")
            
            if not message:
                continue
            
            # Send acknowledgment
            await manager.send_message(session_id, {
                "type": "ack",
                "message": "Message received"
            })
            
            # Process message through agent team
            # TODO: Integrate with MemoryTeam
            # For now, echo back
            await manager.send_message(session_id, {
                "type": "agent_response",
                "message": f"Received: {message}",
                "status": "processing"
            })
            
    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info("client_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("websocket_error", session_id=session_id, error=str(e))
        manager.disconnect(session_id)
