import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["Realtime"])


class DashboardConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        message = json.dumps(data, ensure_ascii=False, default=str)
        for websocket in list(self.active_connections):
            try:
                await websocket.send_text(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


manager = DashboardConnectionManager()


@router.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """Realtime dashboard feed.

    The frontend listens here and refreshes conversations/messages whenever
    a new customer, bot, or agent message is saved.
    """
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "source": "dashboard_ws"})
        while True:
            # Keep the connection open and consume optional client pings.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def broadcast_dashboard_event(event: dict[str, Any]) -> None:
    """Broadcast a dashboard event without failing the request path."""
    try:
        await manager.broadcast(event)
    except Exception:
        # Realtime should never break webhook processing.
        pass
