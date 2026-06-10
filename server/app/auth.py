from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.db_models import SessionCsrfToken, SessionRecord, User, UserCredential, utcnow
from app.admin_permissions import resolve_admin_role
from app.schemas import LoginRequest, ProfileUpdateRequest, RegisterRequest, UserOut
from app.security import create_csrf_token, create_session_token, hash_password, hash_token, verify_password


def is_admin_user(user: User | None, settings: Settings | None = None) -> bool:
    return resolve_admin_role(user, settings) != "none"


def ensure_user_active(user: User) -> User:
    if user.status in {"disabled", "deleted"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "账号已被禁用，请联系管理员。"})
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "用户不可用。"})
    return user


def serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        externalUserId=user.external_user_id,
        email=user.email,
        phone=user.phone,
        nickname=user.nickname,
        avatarUrl=user.avatar_url,
        isAdmin=is_admin_user(user),
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
    clean_external_user_id = (external_user_id or "").strip()
    clean_email = (email or "").strip().lower()
    clean_phone = (phone or "").strip()
    clean_nickname = (nickname or "").strip()
    clean_avatar_url = (avatar_url or "").strip()

    user = db.query(User).filter(User.external_user_id == clean_external_user_id).one_or_none()
    if not user and clean_email:
        user = (
            db.query(User)
            .filter(func.lower(func.trim(User.email)) == clean_email)
            .order_by(User.created_at.asc())
            .first()
        )
    if not user and clean_phone:
        user = (
            db.query(User)
            .filter(func.trim(User.phone) == clean_phone)
            .order_by(User.created_at.asc())
            .first()
        )
    if not user:
        user = User(external_user_id=clean_external_user_id)
        db.add(user)
    elif clean_external_user_id and user.external_user_id != clean_external_user_id:
        owner = db.query(User).filter(User.external_user_id == clean_external_user_id).one_or_none()
        if not owner or owner.id == user.id:
            user.external_user_id = clean_external_user_id
    user.email = clean_email or user.email
    user.phone = clean_phone or user.phone
    user.nickname = clean_nickname or user.nickname or clean_external_user_id
    user.avatar_url = clean_avatar_url or user.avatar_url
    user.status = "active"
    return user


def create_session(db: Session, response: Response, user: User) -> str:
    settings = get_settings()
    token = create_session_token()
    expires_at = utcnow() + timedelta(days=settings.session_ttl_days)
    db.add(SessionRecord(user_id=user.id, token_hash=hash_token(token), expires_at=expires_at))
    cookie_kwargs: dict[str, Any] = {}
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
        **cookie_kwargs,
    )
    return token


def get_session_record(request: Request, db: Session, settings: Settings) -> tuple[str, SessionRecord] | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    session = db.query(SessionRecord).filter(SessionRecord.token_hash == hash_token(token)).one_or_none()
    if not session or session.expires_at <= utcnow():
        return None
    return token, session


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    cookie_kwargs: dict[str, Any] = {}
    if settings.cookie_domain:
        cookie_kwargs["domain"] = settings.cookie_domain
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        **cookie_kwargs,
    )


def clear_session(request: Request, response: Response, db: Session, settings: Settings) -> None:
    session_pair = get_session_record(request, db, settings)
    if session_pair:
        _token, session = session_pair
        db.delete(session)
        db.commit()
    clear_session_cookie(response)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    session_pair = get_session_record(request, db, settings)
    if not session_pair:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "请先登录。"})
    _token, session = session_pair
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "用户不可用。"})
    ensure_user_active(user)
    session.last_seen_at = utcnow()
    return user


def require_admin_user(
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> User:
    ensure_user_active(current_user)
    if not is_admin_user(current_user, settings):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "当前账号没有管理员权限。"})
    return current_user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User | None:
    session_pair = get_session_record(request, db, settings)
    if not session_pair:
        return None
    _token, session = session_pair
    user = db.get(User, session.user_id)
    if not user:
        return None
    ensure_user_active(user)
    session.last_seen_at = utcnow()
    return user


def issue_csrf_token(request: Request, db: Session, settings: Settings) -> str:
    session_pair = get_session_record(request, db, settings)
    if not session_pair:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "请先登录。"})
    _token, session = session_pair
    db.query(SessionCsrfToken).filter(SessionCsrfToken.session_id == session.id).delete()
    token = create_csrf_token()
    expires_at = min(session.expires_at, utcnow() + timedelta(minutes=settings.csrf_ttl_minutes))
    db.add(SessionCsrfToken(session_id=session.id, token_hash=hash_token(token), expires_at=expires_at))
    session.last_seen_at = utcnow()
    db.commit()
    return token


def require_csrf(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    if request.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    session_pair = get_session_record(request, db, settings)
    if not session_pair:
        return
    _token, session = session_pair
    token = request.headers.get("X-CSRF-Token") or request.headers.get("X-XSRF-TOKEN")
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "缺少 CSRF 令牌。"})
    csrf = (
        db.query(SessionCsrfToken)
        .filter(
            SessionCsrfToken.session_id == session.id,
            SessionCsrfToken.token_hash == hash_token(token),
            SessionCsrfToken.expires_at > utcnow(),
        )
        .one_or_none()
    )
    if not csrf:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"message": "CSRF 令牌无效或已过期。"})


def _local_identifier(email: str = "", phone: str = "") -> str:
    return (email or phone).strip().lower()


def register_local_user(db: Session, payload: RegisterRequest) -> User:
    identifier = _local_identifier(payload.email, payload.phone)
    existing = (
        db.query(UserCredential)
        .filter(UserCredential.provider == "local", UserCredential.identifier == identifier)
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": "该账号已经注册。"})
    user = User(
        external_user_id=f"local-{create_session_token()[:24]}",
        email=payload.email,
        phone=payload.phone,
        nickname=payload.nickname or (payload.email.split("@")[0] if payload.email else payload.phone),
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(
        UserCredential(
            user_id=user.id,
            provider="local",
            identifier=identifier,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
        )
    )
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"message": "该账号已经注册。"}) from exc
    return user


def authenticate_local_user(db: Session, payload: LoginRequest, settings: Settings) -> User:
    credential = (
        db.query(UserCredential)
        .filter(UserCredential.provider == "local", UserCredential.identifier == payload.identifier)
        .one_or_none()
    )
    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "账号或密码错误。"})
    if not credential:
        raise generic_error
    if credential.locked_until and credential.locked_until > utcnow():
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={"message": "登录暂时锁定，请稍后再试。"})
    if not verify_password(payload.password, credential.password_hash):
        credential.failed_attempts += 1
        credential.last_failed_at = utcnow()
        if credential.failed_attempts >= settings.login_max_failed_attempts:
            credential.locked_until = utcnow() + timedelta(minutes=settings.login_lock_minutes)
        db.commit()
        if credential.locked_until and credential.locked_until > utcnow():
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail={"message": "登录暂时锁定，请稍后再试。"})
        raise generic_error
    user = db.get(User, credential.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "用户不可用。"})
    ensure_user_active(user)
    credential.failed_attempts = 0
    credential.locked_until = None
    credential.last_failed_at = None
    return user


def update_user_profile(user: User, payload: ProfileUpdateRequest) -> User:
    if payload.nickname is not None and payload.nickname:
        user.nickname = payload.nickname[:128]
    if payload.phone is not None:
        user.phone = payload.phone[:64]
    if payload.avatarUrl is not None:
        user.avatar_url = payload.avatarUrl[:512]
    return user


async def exchange_official_code(code: str, settings: Settings) -> dict[str, Any]:
    if code.startswith("dev:") and not settings.enable_dev_login:
        raise HTTPException(status_code=404, detail={"message": "开发登录未启用。"})
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
