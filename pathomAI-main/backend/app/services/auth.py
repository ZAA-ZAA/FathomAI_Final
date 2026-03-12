from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import ApiKeyRecord, AuthSession, Tenant, User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthContext:
    access_token: str | None
    user_id: str
    tenant_id: str
    full_name: str
    email: str
    tenant_name: str
    auth_method: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}:{derived_key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split(":", 1)
    except ValueError:
        return False

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        100_000,
    )
    return hmac.compare_digest(derived_key.hex(), digest_hex)


def slugify_workspace_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "workspace"


def generate_unique_workspace_slug(db: Session, name: str) -> str:
    base_slug = slugify_workspace_name(name)
    slug = base_slug
    counter = 1

    while db.scalar(select(Tenant.id).where(Tenant.slug == slug)) is not None:
        counter += 1
        slug = f"{base_slug}-{counter}"

    return slug


def create_auth_session(db: Session, user: User, tenant: Tenant) -> AuthContext:
    access_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(access_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.auth_session_ttl_hours),
    )
    db.add(session)
    db.commit()

    return AuthContext(
        access_token=access_token,
        user_id=user.id,
        tenant_id=tenant.id,
        full_name=user.full_name,
        email=user.email,
        tenant_name=tenant.name,
        auth_method="bearer",
    )


def create_api_key(db: Session, user: User, tenant: Tenant, name: str) -> tuple[str, ApiKeyRecord]:
    raw_key = f"pthm_{secrets.token_urlsafe(32)}"
    record = ApiKeyRecord(
        user_id=user.id,
        tenant_id=tenant.id,
        name=name.strip(),
        key_hash=hash_api_key(raw_key),
        key_preview=f"{raw_key[:8]}...{raw_key[-4:]}",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return raw_key, record


def revoke_api_key(db: Session, api_key_id: str, user_id: str) -> None:
    record = db.scalar(
        select(ApiKeyRecord).where(
            ApiKeyRecord.id == api_key_id,
            ApiKeyRecord.user_id == user_id,
            ApiKeyRecord.revoked_at.is_(None),
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    record.revoked_at = datetime.now(timezone.utc)
    db.commit()


def delete_auth_session(db: Session, access_token: str) -> None:
    token_hash = hash_token(access_token)
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if session is not None:
        db.delete(session)
        db.commit()


def require_auth_context(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthContext:
    if x_api_key:
        return _require_api_key_context(db, x_api_key)
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    token_hash = hash_token(credentials.credentials)
    statement = (
        select(AuthSession, User, Tenant)
        .join(User, AuthSession.user_id == User.id)
        .join(Tenant, User.tenant_id == Tenant.id)
        .where(AuthSession.token_hash == token_hash)
    )
    row = db.execute(statement).first()

    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    session, user, tenant = row
    if session.expires_at <= datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    return AuthContext(
        access_token=credentials.credentials,
        user_id=user.id,
        tenant_id=tenant.id,
        full_name=user.full_name,
        email=user.email,
        tenant_name=tenant.name,
        auth_method="bearer",
    )


def hash_token(access_token: str) -> str:
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _require_api_key_context(db: Session, api_key: str) -> AuthContext:
    statement = (
        select(ApiKeyRecord, User, Tenant)
        .join(User, ApiKeyRecord.user_id == User.id)
        .join(Tenant, ApiKeyRecord.tenant_id == Tenant.id)
        .where(
            ApiKeyRecord.key_hash == hash_api_key(api_key),
            ApiKeyRecord.revoked_at.is_(None),
        )
    )
    row = db.execute(statement).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    record, user, tenant = row
    record.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return AuthContext(
        access_token=None,
        user_id=user.id,
        tenant_id=tenant.id,
        full_name=user.full_name,
        email=user.email,
        tenant_name=tenant.name,
        auth_method="api_key",
    )
