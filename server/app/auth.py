from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.db_models import SessionRecord, User, utcnow
from app.schemas import UserOut
from app.security import create_session_token, hash_token


def serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        externalUserId=user.external_user_id,
        email=user.email,
        phone=user.phone,
        nickname=user.nickname,
        avatarUrl=user.avatar_url,
    )


def upsert_user(
    db: Session,
    *,
    external_user_id: str,
    email: str = "",
    phone: str = "",
    nickname: str = "",
    avatar_url: str = "",
) -> User:
    user = db.query(User).filter(User.external_user_id == external_user_id).one_or_none()
    if not user:
        user = User(external_user_id=external_user_id)
        db.add(user)
    user.email = email or user.email
    user.phone = phone or user.phone
    user.nickname = nickname or user.nickname or external_user_id
    user.avatar_url = avatar_url or user.avatar_url
    user.status = "active"
    return user


def create_session(db: Session, response: Response, user: User) -> str:
    settings = get_settings()
    token = create_session_token()
    expires_at = utcnow() + timedelta(days=settings.session_ttl_days)
    db.add(SessionRecord(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
    )
    return token


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "未登录。"})
    session = db.query(SessionRecord).filter(SessionRecord.token_hash == hash_token(token)).one_or_none()
    if not session or session.expires_at <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "登录已过期。"})
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "用户不可用。"})
    session.last_seen_at = utcnow()
    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    session = db.query(SessionRecord).filter(SessionRecord.token_hash == hash_token(token)).one_or_none()
    if not session or session.expires_at <= utcnow():
        return None
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        return None
    session.last_seen_at = utcnow()
    return user


async def exchange_official_code(code: str, settings: Settings) -> dict[str, Any]:
    if code.startswith("dev:") and not settings.official_auth_exchange_url:
        slug = code.removeprefix("dev:").strip() or "user"
        return {
            "external_user_id": f"dev-{slug}",
            "email": f"{slug}@genstudio.local",
            "phone": "",
            "nickname": slug,
            "avatar_url": "",
        }
    if not settings.official_auth_exchange_url:
        raise HTTPException(status_code=503, detail={"message": "官网授权接口未配置。"})
    async with httpx.AsyncClient(timeout=20.0, trust_env=False) as client:
        response = await client.post(
            settings.official_auth_exchange_url,
            json={
                "code": code,
                "clientId": settings.official_auth_client_id,
                "clientSecret": settings.official_auth_client_secret,
            },
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail={"message": "官网授权接口返回格式错误。"}) from exc
    if not response.is_success:
        message = payload.get("message") if isinstance(payload, dict) else ""
        raise HTTPException(status_code=response.status_code, detail={"message": message or "官网授权失败。"})
    data = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail={"message": "官网授权接口未返回用户信息。"})
    external_id = data.get("id") or data.get("userId") or data.get("externalUserId")
    if not external_id:
        raise HTTPException(status_code=502, detail={"message": "官网授权接口缺少用户 ID。"})
    return {
        "external_user_id": str(external_id),
        "email": str(data.get("email") or ""),
        "phone": str(data.get("phone") or ""),
        "nickname": str(data.get("nickname") or data.get("name") or external_id),
        "avatar_url": str(data.get("avatarUrl") or data.get("avatar_url") or ""),
    }
