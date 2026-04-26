from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.model import User
from app.modules.auth.firebase_admin_client import verify_id_token
from app.modules.auth.schemas import AuthenticatedUser

bearer_scheme = HTTPBearer(auto_error=True)


def normalize_role(role: str | None) -> str:
    if role in {"recruiter", "candidate"}:
        return role
    return "candidate"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    token = credentials.credentials

    try:
        claims = verify_id_token(token)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token",
        ) from exc

    uid = claims.get("uid")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token missing uid",
        )

    role = normalize_role(claims.get("role"))

    # Prefer DB role when available so role checks work without Firebase custom claims.
    existing_user = db.get(User, uid)
    if existing_user:
        role = normalize_role(existing_user.role)

    return AuthenticatedUser(
        uid=uid,
        email=claims.get("email"),
        role=role,
    )
