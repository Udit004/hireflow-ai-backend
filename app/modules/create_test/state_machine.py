from typing import Final

from fastapi import HTTPException

DRAFT: Final[str] = "draft"
PUBLISHED: Final[str] = "published"
ARCHIVED: Final[str] = "archived"


def require_transition(current_status: str, expected_current: str, action: str) -> None:
    if current_status != expected_current:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot {action} when test status is '{current_status}'",
        )
