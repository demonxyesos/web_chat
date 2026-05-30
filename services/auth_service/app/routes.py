from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from asyncgram_common.auth_deps import AdminTokenUser, CurrentTokenUser

from . import schemas
from .database import get_db
from .repositories import UserRepository
from .services import AuthService, UserService

router = APIRouter(tags=["auth"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db), db)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db), db)


@router.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(user_in: schemas.UserCreate, service: AuthService = Depends(get_auth_service)):
    return service.register(user_in)


@router.post("/auth/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: AuthService = Depends(get_auth_service),
):
    return service.issue_token(form_data.username, form_data.password)


@router.get("/users/me", response_model=schemas.UserOut)
def read_users_me(
    current: CurrentTokenUser,
    db: Session = Depends(get_db),
):
    user = UserRepository(db).get_active_by_id(current.id)
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/me", response_model=schemas.UserOut)
def update_users_me(
    body: schemas.UserUpdate,
    current: CurrentTokenUser,
    service: UserService = Depends(get_user_service),
):
    return service.update_me_name(current.id, body.name)


@router.delete("/users/me", status_code=204)
def delete_users_me(
    current: CurrentTokenUser,
    service: UserService = Depends(get_user_service),
):
    service.delete_me(current.id)
    return None


@router.get("/internal/users", response_model=list[schemas.UserOut])
def internal_list_users(
    _admin: AdminTokenUser,
    db: Session = Depends(get_db),
):
    return UserRepository(db).list_active()


@router.delete("/internal/users/{user_id}", status_code=204)
def internal_delete_user(
    user_id: int,
    admin: AdminTokenUser,
    service: UserService = Depends(get_user_service),
):
    service.admin_delete_user(admin.id, user_id)
    return None
