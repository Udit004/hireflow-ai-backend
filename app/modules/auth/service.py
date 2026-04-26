from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.model import User
from app.modules.auth.schemas import UserResponse, UserRoleUpdateRequest, UserUpsertRequest


def normalize_role(role: str | None) -> str:
    if role in {"recruiter", "candidate"}:
        return role
    return "candidate"


def to_user_response(user: User) -> UserResponse:
    role = normalize_role(user.role)

    # Self-heal old role values stored in DB as users are read.
    if role != user.role:
        user.role = role

    return UserResponse(
        uid=user.uid,
        email=user.email,
        display_name=user.display_name,
        role=role,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def sync_user(payload: UserUpsertRequest, db: Session) -> UserResponse:
    normalized_role = normalize_role(payload.role)

    existing = db.get(User, payload.uid)
    if existing:
        existing.email = payload.email
        existing.display_name = payload.display_name
        existing.role = normalized_role
        db.commit()
        db.refresh(existing)
        return to_user_response(existing)

    user = User(
        uid=payload.uid,
        email=payload.email,
        display_name=payload.display_name,
        role=normalized_role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return to_user_response(user)


def get_user(uid: str, db: Session) -> UserResponse:
    user = db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return to_user_response(user)


def update_user_role(uid: str, payload: UserRoleUpdateRequest, db: Session) -> UserResponse:
    user = db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = normalize_role(payload.role)
    db.commit()
    db.refresh(user)
    return to_user_response(user)
