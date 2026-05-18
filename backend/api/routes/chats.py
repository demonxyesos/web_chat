from typing import List

from fastapi import APIRouter, Depends

from ... import schemas, security
from ...core.dependencies import get_chat_service
from ...services.chat_service import ChatService
from ...services.ws_chat_service import manager

router = APIRouter(tags=["chats"])


@router.post("/messages", response_model=schemas.MessageOut, status_code=201)
def create_message(
    msg_in: schemas.MessageCreate,
    current_user: security.CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return service.create_message(current_user.id, msg_in)


@router.get("/chats/{username}/messages", response_model=List[schemas.MessageOut])
def list_chat_messages(
    username: str,
    current_user: security.CurrentUser,
    limit: int = 50,
    service: ChatService = Depends(get_chat_service),
):
    return service.list_chat_messages(current_user.id, username, limit)


@router.patch("/messages/{message_id}", response_model=schemas.MessageOut)
async def update_own_message(
    message_id: int,
    body: schemas.MessageUpdate,
    current_user: security.CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    msg, chat = service.update_own_message(current_user.id, message_id, body.content)
    author = msg.author
    recipient = msg.recipient
    ws_payload = {
        "type": "message_edited",
        "id": msg.id,
        "chat_id": msg.chat_id,
        "content": msg.content,
        "edited_at": msg.edited_at.isoformat(),
        "author": {"id": author.id, "username": author.username},
        "recipient": {"id": recipient.id, "username": recipient.username},
    }
    if getattr(chat, "is_global", 0) == 1:
        await manager.broadcast_json(ws_payload)
    else:
        await manager.send_to(chat.user_a_id, ws_payload)
        await manager.send_to(chat.user_b_id, ws_payload)
    return msg


@router.delete("/messages/{message_id}", status_code=204)
async def delete_own_message(
    message_id: int,
    current_user: security.CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    mid, cid, chat = service.delete_own_message(current_user.id, message_id)
    ws_payload = {"type": "message_deleted", "id": mid, "chat_id": cid}
    if getattr(chat, "is_global", 0) == 1:
        await manager.broadcast_json(ws_payload)
    else:
        await manager.send_to(chat.user_a_id, ws_payload)
        await manager.send_to(chat.user_b_id, ws_payload)
    return None


@router.get("/chats", response_model=List[schemas.ChatOut])
def list_chats(
    current_user: security.CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return service.list_chats(current_user.id)


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(
    chat_id: int,
    current_user: security.CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    service.delete_chat(current_user.id, chat_id)
    return None


@router.get("/users/search", response_model=List[schemas.UserOut])
def search_users(
    username: str,
    current_user: security.CurrentUser,
    service: ChatService = Depends(get_chat_service),
):
    return service.search_users(current_user.id, username)
