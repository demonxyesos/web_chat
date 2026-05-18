from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from ... import schemas, security
from ...core.dependencies import get_auth_service, get_user_service
from ...services.auth_service import AuthService
from ...services.user_service import UserService

router = APIRouter(tags=["auth"])


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
def read_users_me(current_user: security.CurrentUser):
    return current_user


@router.patch("/users/me", response_model=schemas.UserOut)
def update_users_me(
    body: schemas.UserUpdate,
    current_user: security.CurrentUser,
    service: UserService = Depends(get_user_service),
):
    return service.update_me_name(current_user.id, body.name)


@router.delete("/users/me", status_code=204)
def delete_users_me(
    current_user: security.CurrentUser,
    service: UserService = Depends(get_user_service),
):
    service.delete_me(current_user.id)
    return None
