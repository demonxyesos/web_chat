from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from asyncgram_common.constants import LOBBY_USERNAME
from asyncgram_common.events import ChatEvent

from . import models, schemas
from .repositories import ChatRepository, MessageRepository, UserRepository


def user_out(user) -> schemas.UserOut:
    return schemas.UserOut.model_validate(user)


def message_to_out(msg: models.Message, users: UserRepository) -> schemas.MessageOut:
    author = users.get_active_by_id(msg.author_id)
    recipient = users.get_active_by_id(msg.recipient_id)
    if not author or not recipient:
        raise HTTPException(status_code=500, detail="Message user data missing")
    reply_ref = None
    if msg.reply_to_message_id:
        reply = msg.reply_to
        if reply:
            reply_author = users.get_active_by_id(reply.author_id)
            if reply_author:
                reply_ref = schemas.MessageReplyRef(
                    id=reply.id,
                    content=reply.content,
                    author=user_out(reply_author),
                )
    return schemas.MessageOut(
        id=msg.id,
        content=msg.content,
        created_at=msg.created_at,
        edited_at=msg.edited_at,
        chat_id=msg.chat_id,
        reply_to=reply_ref,
        author=user_out(author),
        recipient=user_out(recipient),
        file_url=msg.file_url,
        file_name=msg.file_name,
        file_type=msg.file_type,
        file_size=msg.file_size,
    )


def ws_payload(msg: models.Message, author, recipient, reply_payload=None) -> dict:
    return {
        "id": msg.id,
        "chat_id": msg.chat_id,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
        "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
        "reply_to": reply_payload,
        "author": {
            "id": author.id,
            "username": author.username,
            "name": author.name,
            "role": author.role,
            "created_at": author.created_at.isoformat(),
        },
        "recipient": {
            "id": recipient.id,
            "username": recipient.username,
            "name": recipient.name,
            "role": recipient.role,
            "created_at": recipient.created_at.isoformat(),
        },
        "file_url": msg.file_url,
        "file_name": msg.file_name,
        "file_type": msg.file_type,
        "file_size": msg.file_size,
    }


def reply_payload(reply_to, users: UserRepository):
    if not reply_to:
        return None
    reply_author = users.get_active_by_id(reply_to.author_id)
    if not reply_author:
        return None
    return {
        "id": reply_to.id,
        "content": reply_to.content,
        "author": {
            "id": reply_author.id,
            "username": reply_author.username,
            "name": reply_author.name,
        },
    }


class ChatService:
    def __init__(
        self,
        users: UserRepository,
        chats: ChatRepository,
        messages: MessageRepository,
        db: Session,
    ) -> None:
        self.users = users
        self.chats = chats
        self.messages = messages
        self.db = db

    def create_message(self, author_id: int, msg_in: schemas.MessageCreate):
        if msg_in.to == LOBBY_USERNAME:
            return self._create_global_message(author_id, msg_in)

        if not (msg_in.content or "").strip() and not msg_in.file_url:
            raise HTTPException(status_code=400, detail="Message must have content or a file")

        recipient = self.users.get_active_by_username(msg_in.to)
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")

        chat = self.chats.get_pair_chat(author_id, recipient.id)
        if not chat:
            chat = self.chats.create_pair_chat(author_id, recipient.id)
        elif chat.is_deleted:
            chat.is_deleted = 0
            self.db.query(models.Message).filter(
                models.Message.chat_id == chat.id, models.Message.is_deleted == 0
            ).update({"is_deleted": 1})
            self.db.commit()

        reply_to = None
        if msg_in.reply_to_id is not None:
            reply_to = self.messages.get_in_chat(msg_in.reply_to_id, chat.id)
            if not reply_to:
                raise HTTPException(status_code=400, detail="Invalid reply_to_id")

        msg = self.messages.create(
            content=msg_in.content,
            chat_id=chat.id,
            author_id=author_id,
            recipient_id=recipient.id,
            reply_to_message_id=reply_to.id if reply_to else None,
            file_url=msg_in.file_url,
            file_name=msg_in.file_name,
            file_type=msg_in.file_type,
            file_size=msg_in.file_size,
        )
        chat.updated_at = msg.created_at
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(msg)
        author = self.users.get_active_by_id(author_id)
        return msg, chat, author, recipient, reply_to

    def _create_global_message(self, author_id: int, msg_in: schemas.MessageCreate):
        if not (msg_in.content or "").strip() and not msg_in.file_url:
            raise HTTPException(status_code=400, detail="Message must have content or a file")
        lobby = self.users.get_active_by_username(LOBBY_USERNAME)
        if not lobby:
            raise HTTPException(status_code=503, detail="Global chat not initialized")
        chat = self.chats.get_global_chat()
        if not chat:
            raise HTTPException(status_code=503, detail="Global chat not initialized")
        reply_to = None
        if msg_in.reply_to_id is not None:
            reply_to = self.messages.get_in_chat(msg_in.reply_to_id, chat.id)
            if not reply_to:
                raise HTTPException(status_code=400, detail="Invalid reply_to_id")
        msg = self.messages.create(
            content=msg_in.content,
            chat_id=chat.id,
            author_id=author_id,
            recipient_id=lobby.id,
            reply_to_message_id=reply_to.id if reply_to else None,
            file_url=msg_in.file_url,
            file_name=msg_in.file_name,
            file_type=msg_in.file_type,
            file_size=msg_in.file_size,
        )
        chat.updated_at = msg.created_at
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(msg)
        author = self.users.get_active_by_id(author_id)
        return msg, chat, author, lobby, reply_to

    def build_created_event(self, msg, chat, author, recipient, reply_to) -> ChatEvent:
        payload = ws_payload(msg, author, recipient, reply_payload(reply_to, self.users))
        is_global = getattr(chat, "is_global", 0) == 1
        if is_global:
            return ChatEvent(type="message.created", broadcast=True, payload=payload)
        return ChatEvent(
            type="message.created",
            broadcast=False,
            target_user_ids=[author.id, recipient.id],
            payload=payload,
        )

    def list_chat_messages(self, current_user_id: int, username: str, limit: int):
        if username == LOBBY_USERNAME:
            chat = self.chats.get_global_chat()
            if not chat or chat.is_deleted:
                return []
            safe_limit = max(1, min(limit, 200))
            rows = self.messages.list_active_in_chat(chat.id, safe_limit)
            return [message_to_out(m, self.users) for m in reversed(rows)]

        other = self.users.get_active_by_username(username)
        if not other:
            raise HTTPException(status_code=404, detail="User not found")
        chat = self.chats.get_pair_chat(current_user_id, other.id)
        if not chat or chat.is_deleted:
            return []
        safe_limit = max(1, min(limit, 200))
        rows = self.messages.list_active_in_chat(chat.id, safe_limit)
        return [message_to_out(m, self.users) for m in reversed(rows)]

    def update_own_message(self, current_user_id: int, message_id: int, content: str):
        msg = self.messages.get_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if msg.author_id != current_user_id:
            raise HTTPException(status_code=403, detail="Only the author can edit")
        chat = self.chats.get_active_by_id(msg.chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if not chat.is_global and chat.user_a_id != current_user_id and chat.user_b_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not a participant")
        text = (content or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Content required")
        if len(text) > 4000:
            text = text[:4000]
        msg.content = text
        msg.edited_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(msg)
        chat.updated_at = msg.edited_at
        self.db.add(chat)
        self.db.commit()
        author = self.users.get_active_by_id(msg.author_id)
        recipient = self.users.get_active_by_id(msg.recipient_id)
        return msg, chat, author, recipient

    def build_edited_event(self, msg, chat, author, recipient) -> ChatEvent:
        payload = {
            "type": "message_edited",
            "id": msg.id,
            "chat_id": msg.chat_id,
            "content": msg.content,
            "edited_at": msg.edited_at.isoformat(),
            "author": {"id": author.id, "username": author.username},
            "recipient": {"id": recipient.id, "username": recipient.username},
        }
        is_global = getattr(chat, "is_global", 0) == 1
        if is_global:
            return ChatEvent(type="message_edited", broadcast=True, payload=payload)
        return ChatEvent(
            type="message_edited",
            broadcast=False,
            target_user_ids=[chat.user_a_id, chat.user_b_id],
            payload=payload,
        )

    def delete_own_message(self, current_user_id: int, message_id: int):
        msg = self.messages.get_active_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        if msg.author_id != current_user_id:
            raise HTTPException(status_code=403, detail="Only the author can delete")
        chat = self.chats.get_active_by_id(msg.chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        msg.is_deleted = 1
        self.db.add(msg)
        self.db.commit()
        return msg.id, msg.chat_id, chat

    def build_deleted_event(self, message_id: int, chat_id: int, chat) -> ChatEvent:
        payload = {"type": "message_deleted", "id": message_id, "chat_id": chat_id}
        is_global = getattr(chat, "is_global", 0) == 1
        if is_global:
            return ChatEvent(type="message_deleted", broadcast=True, payload=payload)
        return ChatEvent(
            type="message_deleted",
            broadcast=False,
            target_user_ids=[chat.user_a_id, chat.user_b_id],
            payload=payload,
        )

    def list_chats(self, current_user_id: int) -> list[schemas.ChatOut]:
        chats = list(self.chats.list_active_for_user(current_user_id))
        gchat = self.chats.get_global_chat()
        if gchat and getattr(gchat, "is_deleted", 0) == 0 and not any(c.id == gchat.id for c in chats):
            chats.insert(0, gchat)

        def _is_global(c) -> bool:
            return int(getattr(c, "is_global", 0) or 0) == 1

        global_rows = [c for c in chats if _is_global(c)]
        direct_rows = [c for c in chats if not _is_global(c)]
        direct_sorted = sorted(direct_rows, key=lambda c: c.updated_at, reverse=True)
        ordered = (global_rows[:1] if global_rows else []) + direct_sorted

        chat_ids = [c.id for c in ordered]
        last_map = self.messages.latest_active_by_chat_ids(chat_ids)
        out: list[schemas.ChatOut] = []
        for c in ordered:
            is_global_row = _is_global(c)
            if is_global_row:
                peer = self.users.get_active_by_username(LOBBY_USERNAME)
            else:
                peer_id = c.user_b_id if c.user_a_id == current_user_id else c.user_a_id
                peer = self.users.get_active_by_id(peer_id)
            if not peer or (not is_global_row and peer.is_deleted):
                continue
            last = last_map.get(c.id)
            last_out = message_to_out(last, self.users) if last else None
            out.append(
                schemas.ChatOut(
                    id=c.id,
                    peer=user_out(peer),
                    updated_at=c.updated_at,
                    last_message=last_out,
                    is_global=is_global_row,
                )
            )
        return out

    def delete_chat(self, current_user_id: int, chat_id: int) -> None:
        chat = self.chats.get_active_by_id(chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if getattr(chat, "is_global", 0) == 1:
            raise HTTPException(status_code=403, detail="Cannot delete global chat")
        if chat.user_a_id != current_user_id and chat.user_b_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not a participant")
        chat.is_deleted = 1
        self.db.add(chat)
        self.db.commit()

    def search_users(self, current_user_id: int, username_query: str):
        q = (username_query or "").strip()
        if not q:
            return []
        return [user_out(u) for u in self.users.search_active(q, current_user_id)]

    def admin_delete_message(self, message_id: int) -> tuple[int, int, models.Chat | None]:
        msg = self.messages.get_active_by_id(message_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        chat = self.chats.get_active_by_id(msg.chat_id)
        mid = msg.id
        cid = msg.chat_id
        msg.is_deleted = 1
        self.db.add(msg)
        self.db.commit()
        return mid, cid, chat
