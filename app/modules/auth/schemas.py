from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserUpsertRequest(BaseModel):
    uid: str = Field(..., min_length=1, max_length=128)
    email: str | None = None
    display_name: str | None = None
    role: Literal["admin", "educator", "student"] = "student"


class UserRoleUpdateRequest(BaseModel):
    role: Literal["admin", "educator", "student"]


class UserResponse(BaseModel):
    uid: str
    email: str | None = None
    display_name: str | None = None
    role: Literal["admin", "educator", "student"]
    created_at: datetime
    updated_at: datetime


class AuthenticatedUser(BaseModel):
    uid: str
    email: str | None = None
    role: Literal["admin", "educator", "student"] = "student"
