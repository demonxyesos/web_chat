from fastapi import WebSocket, WebSocketDisconnect

from asyncgram_common.events import ChatEvent


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int) -> None:
        self.active_connections.pop(user_id, None)

    async def broadcast_json(self, message: dict) -> None:
        disconnected: list[int] = []
        for user_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(user_id)
        for uid in disconnected:
            self.disconnect(uid)

    async def send_to(self, user_id: int, message: dict) -> None:
        ws = self.active_connections.get(user_id)
        if not ws:
            return
        try:
            await ws.send_json(message)
        except WebSocketDisconnect:
            self.disconnect(user_id)


manager = ConnectionManager()


async def dispatch_event(event: ChatEvent) -> None:
    payload = event.payload
    if event.broadcast:
        await manager.broadcast_json(payload)
        return
    for user_id in event.target_user_ids:
        await manager.send_to(user_id, payload)
