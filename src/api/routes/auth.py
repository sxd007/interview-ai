from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import authenticate_user, create_access_token, get_current_user
from src.core import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    if not authenticate_user(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        request.username, timedelta(minutes=settings.jwt_expire_minutes)
    )
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(username: str = Depends(get_current_user)):
    return UserInfo(username=username)
