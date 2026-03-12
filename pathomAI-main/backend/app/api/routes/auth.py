from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tenant, User
from app.schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyRead,
    ApiMessage,
    AuthResponse,
    AuthUserRead,
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    SignUpRequest,
)
from app.services.auth import (
    AuthContext,
    create_api_key,
    create_auth_session,
    delete_auth_session,
    generate_unique_workspace_slug,
    hash_password,
    revoke_api_key,
    require_auth_context,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignUpRequest, db: Session = Depends(get_db)) -> AuthResponse:
    normalized_email = request.email.strip().lower()
    existing_user = db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists")

    tenant = Tenant(
        name=request.tenant_name.strip(),
        slug=generate_unique_workspace_slug(db, request.tenant_name),
    )
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        full_name=request.full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(tenant)
    db.refresh(user)

    context = create_auth_session(db, user, tenant)
    return AuthResponse(access_token=context.access_token, user=_build_auth_user(context))


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    normalized_email = request.email.strip().lower()
    statement = (
        select(User, Tenant)
        .join(Tenant, User.tenant_id == Tenant.id)
        .where(User.email == normalized_email)
    )
    row = db.execute(statement).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user, tenant = row
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    context = create_auth_session(db, user, tenant)
    return AuthResponse(access_token=context.access_token, user=_build_auth_user(context))


@router.get("/me", response_model=AuthUserRead)
def get_current_user(context: AuthContext = Depends(require_auth_context)) -> AuthUserRead:
    return _build_auth_user(context)


@router.patch("/me", response_model=AuthUserRead)
def update_profile(
    request: ProfileUpdateRequest,
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> AuthUserRead:
    user = db.get(User, context.user_id)
    tenant = db.get(Tenant, context.tenant_id)
    if user is None or tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    normalized_email = request.email.strip().lower()
    existing_user = db.scalar(select(User).where(User.email == normalized_email, User.id != user.id))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another account already uses that email")

    user.full_name = request.full_name.strip()
    user.email = normalized_email
    tenant.name = request.tenant_name.strip()
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    return AuthUserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
    )


@router.post("/change-password", response_model=ApiMessage)
def change_password(
    request: PasswordChangeRequest,
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> ApiMessage:
    user = db.get(User, context.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if request.current_password == request.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be different")

    user.password_hash = hash_password(request.new_password)
    db.commit()
    return ApiMessage(message="Password updated")


@router.post("/logout", response_model=ApiMessage)
def logout(
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> ApiMessage:
    if context.access_token:
        delete_auth_session(db, context.access_token)
    return ApiMessage(message="Logged out")


@router.get("/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> list:
    from app.models import ApiKeyRecord

    statement = select(ApiKeyRecord).where(
        ApiKeyRecord.user_id == context.user_id,
        ApiKeyRecord.revoked_at.is_(None),
    ).order_by(ApiKeyRecord.created_at.desc())
    return list(db.scalars(statement).all())


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def generate_api_key(
    request: ApiKeyCreateRequest,
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> ApiKeyCreateResponse:
    user = db.get(User, context.user_id)
    tenant = db.get(Tenant, context.tenant_id)
    if user is None or tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    api_key, record = create_api_key(db, user, tenant, request.name)
    return ApiKeyCreateResponse(api_key=api_key, api_key_record=record)


@router.delete("/api-keys/{api_key_id}", response_model=ApiMessage)
def delete_api_key(
    api_key_id: str,
    context: AuthContext = Depends(require_auth_context),
    db: Session = Depends(get_db),
) -> ApiMessage:
    revoke_api_key(db, api_key_id, context.user_id)
    return ApiMessage(message="API key revoked")


def _build_auth_user(context: AuthContext) -> AuthUserRead:
    return AuthUserRead(
        id=context.user_id,
        full_name=context.full_name,
        email=context.email,
        tenant_id=context.tenant_id,
        tenant_name=context.tenant_name,
    )
