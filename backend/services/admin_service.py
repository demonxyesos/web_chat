from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..core.constants import LOBBY_USERNAME
from ..repositories.chat_repository import ChatRepository
from ..repositories.message_repository import MessageRepository
from ..repositories.user_repository import UserRepository


class AdminService:
    def __init__(
        self,
        users: UserRepository,
        messages: MessageRepository,
        chats: ChatRepository,
        db: Session,
    ) -> None:
        self.users = users
        self.messages = messages
        self.chats = chats
        self.db = db

    @staticmethod
    def _require_admin(role: str) -> None:
        if role != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")

    def list_users(self, current_role: str):
        self._require_admin(current_role)
        return self.users.list_active()

    def list_messages(self, current_role: str, limit: int, before_id: int | None):
        self._require_admin(current_role)
        return self.messages.list_admin_feed(limit, before_id)

    def delete_user(self, current_role: str, actor_user_id: int, user_id: int) -> None:
        self._require_admin(current_role)
        if user_id == actor_user_id:
            raise HTTPException(status_code=403, detail="Cannot delete yourself")
        user = self.users.get_active_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.username == LOBBY_USERNAME:
            raise HTTPException(status_code=403, detail="Cannot delete system user")
        user.is_deleted = 1
        self.db.add(user)
        self.db.commit()

    def delete_message(self, current_role: str, message_id: int) -> tuple[int, int, models.Chat | None]:
        self._require_admin(current_role)
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
