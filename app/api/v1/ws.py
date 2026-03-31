"""WebSocket endpoint for real-time messaging."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import verify_token
from app.services.ws_manager import ws_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    """WebSocket connection for real-time message push.

    Connect with: ws://host/api/v1/ws?token=<access_token>

    Server pushes JSON messages like:
    {
        "type": "new_message",
        "data": { ... MessageResponse ... }
    }
    """
    # Authenticate via token query parameter
    user_id = verify_token(token, token_type="access")
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        # Keep connection alive, listen for client pings/messages
        while True:
            # We primarily use WebSocket for server -> client push.
            # Client can send pings or acks here if needed.
            data = await websocket.receive_text()
            # For now, just keep alive. Could handle client acks in the future.
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
