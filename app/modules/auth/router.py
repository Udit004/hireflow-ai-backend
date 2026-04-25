from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.schemas import UserResponse, UserRoleUpdateRequest, UserUpsertRequest
from app.modules.auth.service import get_user, sync_user, update_user_role

router = APIRouter(prefix="/users", tags=["auth"])


@router.post(
    "/sync",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def sync_user_route(payload: UserUpsertRequest, db: Session = Depends(get_db)) -> UserResponse:
    return sync_user(payload, db)


@router.get("/{uid}", response_model=UserResponse)
def get_user_route(uid: str, db: Session = Depends(get_db)) -> UserResponse:
    return get_user(uid, db)


@router.patch("/{uid}/role", response_model=UserResponse)
def update_user_role_route(
    uid: str,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    return update_user_role(uid, payload, db)
