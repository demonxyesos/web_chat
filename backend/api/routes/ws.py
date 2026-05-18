from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from ... import database, security
from ...core.dependencies import get_ws_chat_service
from ...services.ws_chat_service import manager, WsChatService

router = APIRouter(tags=["ws"])


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token") or ""
    db_iter = database.get_db()
    db: Session = next(db_iter)
    service = get_ws_chat_service(db)
    try:
        user = security.get_user_from_token(token, db)
    except HTTPException:
        try:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except WebSocketDisconnect:
            pass
        return

    await manager.connect(user.id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await service.handle_message(user, data)
    except WebSocketDisconnect:
        manager.disconnect(user.id)
    finally:
        try:
            next(db_iter)
        except StopIteration:
            pass
