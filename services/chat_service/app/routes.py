from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from asyncgram_common.auth_deps import AdminTokenUser, CurrentTokenUser
from asyncgram_common.config import REDIS_URL
from asyncgram_common.redis_bus import EventBus

from . import schemas
from .database import get_db
from .repositories import ChatRepository, MessageRepository, UserRepository
from .services import ChatService, message_to_out

router = APIRouter(tags=["chats"])
event_bus = EventBus(REDIS_URL)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(UserRepository(db), ChatRepository(db), MessageRepository(db), db)


@router.post("/messages", response_model=schemas.MessageOut, status_code=201)
async def create_message(
    msg_in: schemas.MessageCreate,
    current: CurrentTokenUser,
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    msg, chat, author, recipient, reply_to = service.create_message(current.id, msg_in)
    event = service.build_created_event(msg, chat, author, recipient, reply_to)
    await event_bus.publish(event)
    return message_to_out(msg, UserRepository(db))


@router.get("/chats/{username}/messages", response_model=List[schemas.MessageOut])
def list_chat_messages(
    username: str,
    current: CurrentTokenUser,
    limit: int = 50,
    service: ChatService = Depends(get_chat_service),
):
    return service.list_chat_messages(current.id, username, limit)


@router.patch("/messages/{message_id}", response_model=schemas.MessageOut)
async def update_own_message(
    message_id: int,
    body: schemas.MessageUpdate,
    current: CurrentTokenUser,
    service: ChatService = Depends(get_chat_service),
    db: Session = Depends(get_db),
):
    msg, chat, author, recipient = service.update_own_message(current.id, message_id, body.content)
    await event_bus.publish(service.build_edited_event(msg, chat, author, recipient))
    return message_to_out(msg, UserRepository(db))


@router.delete("/messages/{message_id}", status_code=204)
async def delete_own_message(
    message_id: int,
    current: CurrentTokenUser,
    service: ChatService = Depends(get_chat_service),
):
    mid, cid, chat = service.delete_own_message(current.id, message_id)
    await event_bus.publish(service.build_deleted_event(mid, cid, chat))
    return None


@router.get("/chats", response_model=List[schemas.ChatOut])
def list_chats(
    current: CurrentTokenUser,
    service: ChatService = Depends(get_chat_service),
):
    return service.list_chats(current.id)


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(
    chat_id: int,
    current: CurrentTokenUser,
    service: ChatService = Depends(get_chat_service),
):
    service.delete_chat(current.id, chat_id)
    return None


@router.get("/users/search", response_model=List[schemas.UserOut])
def search_users(
    username: str,
    current: CurrentTokenUser,
    service: ChatService = Depends(get_chat_service),
):
    return service.search_users(current.id, username)


@router.get("/internal/messages", response_model=List[schemas.MessageOut])
def internal_list_messages(
    _admin: AdminTokenUser,
    limit: int = 50,
    before_id: int | None = None,
    db: Session = Depends(get_db),
):
    safe = max(1, min(limit, 200))
    users = UserRepository(db)
    rows = MessageRepository(db).list_admin_feed(safe, before_id)
    return [message_to_out(m, users) for m in rows]


@router.delete("/internal/messages/{message_id}", status_code=204)
async def internal_delete_message(
    message_id: int,
    _admin: AdminTokenUser,
    service: ChatService = Depends(get_chat_service),
):
    mid, cid, chat = service.admin_delete_message(message_id)
    if chat:
        await event_bus.publish(service.build_deleted_event(mid, cid, chat))
    return None
