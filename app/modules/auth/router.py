from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    AuthenticatedUser,
    UserResponse,
    UserRoleUpdateRequest,
    UserUpsertRequest,
)
from app.modules.auth.service import get_user, sync_user, update_user_role

router = APIRouter(prefix="/users", tags=["auth"])


@router.post(
    "/sync",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def sync_user_route(
    payload: UserUpsertRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserResponse:
    if current_user.uid != payload.uid:
        raise HTTPException(status_code=403, detail="Not allowed to sync another user")
    return sync_user(payload, db)


@router.get("/{uid}", response_model=UserResponse)
def get_user_route(
    uid: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserResponse:
    if current_user.uid != uid:
        raise HTTPException(status_code=403, detail="Not allowed to view this user")
    return get_user(uid, db)


@router.patch("/{uid}/role", response_model=UserResponse)
def update_user_role_route(
    uid: str,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserResponse:
    if current_user.uid != uid:
        raise HTTPException(status_code=403, detail="Not allowed to update another user's role")
    return update_user_role(uid, payload, db)
