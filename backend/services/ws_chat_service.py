from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..core.constants import LOBBY_USERNAME
from ..repositories.chat_repository import ChatRepository
from ..repositories.message_repository import MessageRepository
from ..repositories.user_repository import UserRepository


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


class WsChatService:
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

    async def handle_message(self, user, data: dict) -> None:
        text = (data.get("content") or "").strip()
        to_username = (data.get("to") or "").strip()
        reply_to_id = data.get("reply_to_id")
        file_url = data.get("file_url")
        file_name = data.get("file_name")
        file_type = data.get("file_type")
        file_size = data.get("file_size")
        has_file = bool(file_url)
        if (not text and not has_file) or not to_username:
            return
        if len(text) > 4000:
            text = text[:4000]

        if to_username == LOBBY_USERNAME:
            await self._handle_global_message(
                user, text, reply_to_id, file_url, file_name, file_type, file_size
            )
            return

        recipient = self.users.get_active_by_username(to_username)
        if not recipient:
            return

        chat = self.chats.get_pair_chat(user.id, recipient.id)
        if not chat:
            chat = self.chats.create_pair_chat(user.id, recipient.id)
        elif chat.is_deleted:
            chat.is_deleted = 0
            from .. import models

            self.db.query(models.Message).filter(
                models.Message.chat_id == chat.id, models.Message.is_deleted == 0
            ).update({"is_deleted": 1})
            self.db.commit()

        reply_to = None
        if reply_to_id is not None:
            try:
                rid = int(reply_to_id)
            except (TypeError, ValueError):
                rid = None
            if rid:
                reply_to = self.messages.get_in_chat(rid, chat.id)

        msg = self.messages.create(
            content=text or "",
            chat_id=chat.id,
            author_id=user.id,
            recipient_id=recipient.id,
            reply_to_message_id=reply_to.id if reply_to else None,
            file_url=file_url,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
        )
        chat.updated_at = msg.created_at
        self.db.add(chat)
        self.db.commit()

        reply_payload = self._reply_payload(reply_to)
        payload = self._message_payload(msg, user, recipient, reply_payload)
        await manager.send_to(user.id, payload)
        await manager.send_to(recipient.id, payload)

    async def _handle_global_message(
        self,
        user,
        text: str,
        reply_to_id,
        file_url,
        file_name,
        file_type,
        file_size,
    ) -> None:
        lobby = self.users.get_active_by_username(LOBBY_USERNAME)
        if not lobby:
            return
        chat = self.chats.get_global_chat()
        if not chat:
            return

        reply_to = None
        if reply_to_id is not None:
            try:
                rid = int(reply_to_id)
            except (TypeError, ValueError):
                rid = None
            if rid:
                reply_to = self.messages.get_in_chat(rid, chat.id)

        msg = self.messages.create(
            content=text or "",
            chat_id=chat.id,
            author_id=user.id,
            recipient_id=lobby.id,
            reply_to_message_id=reply_to.id if reply_to else None,
            file_url=file_url,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
        )
        chat.updated_at = msg.created_at
        self.db.add(chat)
        self.db.commit()

        reply_payload = self._reply_payload(reply_to)
        payload = self._message_payload(msg, user, lobby, reply_payload)
        await manager.broadcast_json(payload)

    def _reply_payload(self, reply_to):
        if not reply_to:
            return None
        reply_author = self.users.get_active_by_id(reply_to.author_id)
        return {
            "id": reply_to.id,
            "content": reply_to.content,
            "author": {
                "id": reply_author.id,
                "username": reply_author.username,
                "name": reply_author.name,
            }
            if reply_author
            else None,
        }

    def _message_payload(self, msg, author_user, recipient_user, reply_payload):
        return {
            "id": msg.id,
            "chat_id": msg.chat_id,
            "content": msg.content,
            "created_at": msg.created_at.isoformat(),
            "edited_at": msg.edited_at.isoformat() if msg.edited_at else None,
            "reply_to": reply_payload,
            "author": {"id": author_user.id, "username": author_user.username, "name": author_user.name},
            "recipient": {
                "id": recipient_user.id,
                "username": recipient_user.username,
                "name": recipient_user.name,
            },
            "file_url": msg.file_url,
            "file_name": msg.file_name,
            "file_type": msg.file_type,
            "file_size": msg.file_size,
        }
