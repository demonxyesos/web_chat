import asyncio
import contextlib

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status

from asyncgram_common.app_factory import add_cors, add_health
from asyncgram_common.config import REDIS_URL
from asyncgram_common.jwt import decode_token_payload
from asyncgram_common.redis_bus import EventBus

from .connections import dispatch_event, manager

app = FastAPI(title="Asyncgram WebSocket Gateway")
add_cors(app)
add_health(app)

event_bus = EventBus(REDIS_URL)
_listener_task: asyncio.Task | None = None


async def _redis_listener() -> None:
    await event_bus.subscribe(dispatch_event)


@app.on_event("startup")
async def startup() -> None:
    global _listener_task
    await event_bus.connect()
    _listener_task = asyncio.create_task(_redis_listener())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _listener_task
    if _listener_task is not None:
        _listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _listener_task
        _listener_task = None
    await event_bus.close()


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token") or ""
    try:
        payload = decode_token_payload(token)
        user_id = int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        try:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except WebSocketDisconnect:
            pass
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id)
