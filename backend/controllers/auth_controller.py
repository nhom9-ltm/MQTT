"""Controller HTTP đăng nhập, cùng các dependency kiểm tra phiên và vai trò dùng cho API cần bảo vệ."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str = ""
    password: str = ""


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    user = auth_service.user_from_token(credentials.credentials) if credentials else None
    if not user:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới được truy cập")
    return user


@router.post("/login")
def login(body: LoginRequest, request: Request):
    try:
        return auth_service.login(body.email, body.password, request.client.host if request.client else None)
    except auth_service.InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if credentials:
        auth_service.logout(credentials.credentials)
