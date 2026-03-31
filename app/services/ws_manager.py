"""WebSocket connection manager for real-time messaging."""

import json
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections per user.

    Single-process in-memory implementation.
    For multi-process scaling, replace with Redis pub/sub.
    """

    def __init__(self) -> None:
        # user_id -> list of active WebSocket connections (supports multiple devices)
        self._connections: dict[UUID, list[WebSocket]] = {}

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = []
        self._connections[user_id].append(websocket)

    def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws is not websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]

    def is_online(self, user_id: UUID) -> bool:
        """Check if a user has any active connections."""
        return user_id in self._connections and len(self._connections[user_id]) > 0

    async def send_to_user(self, user_id: UUID, data: dict) -> None:
        """Send a JSON message to all connections of a user."""
        if user_id not in self._connections:
            return
        message = json.dumps(data, default=str)
        dead_connections = []
        for ws in self._connections[user_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead_connections.append(ws)
        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(user_id, ws)

    async def broadcast_to_users(self, user_ids: list[UUID], data: dict) -> None:
        """Send a JSON message to multiple users."""
        for user_id in user_ids:
            await self.send_to_user(user_id, data)


# Singleton instance
ws_manager = ConnectionManager()
