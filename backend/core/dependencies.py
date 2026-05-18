from fastapi import Depends
from sqlalchemy.orm import Session

from .. import database
from ..repositories.chat_repository import ChatRepository
from ..repositories.message_repository import MessageRepository
from ..repositories.user_repository import UserRepository
from ..services.admin_service import AdminService
from ..services.auth_service import AuthService
from ..services.chat_service import ChatService
from ..services.user_service import UserService
from ..services.ws_chat_service import WsChatService


def get_auth_service(db: Session = Depends(database.get_db)) -> AuthService:
    return AuthService(UserRepository(db), db)


def get_user_service(db: Session = Depends(database.get_db)) -> UserService:
    return UserService(UserRepository(db), db)


def get_chat_service(db: Session = Depends(database.get_db)) -> ChatService:
    return ChatService(UserRepository(db), ChatRepository(db), MessageRepository(db), db)


def get_admin_service(db: Session = Depends(database.get_db)) -> AdminService:
    return AdminService(UserRepository(db), MessageRepository(db), ChatRepository(db), db)


def get_ws_chat_service(db: Session = Depends(database.get_db)) -> WsChatService:
    return WsChatService(UserRepository(db), ChatRepository(db), MessageRepository(db), db)
