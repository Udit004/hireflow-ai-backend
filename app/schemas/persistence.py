from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion


class SaveGeneratedTestRequest(JDTestRequest):
    created_by_uid: str = Field(..., min_length=1, max_length=128)


class SavedTestResponse(BaseModel):
    id: UUID
    created_by_uid: str
    role_title: str
    difficulty: Literal["easy", "medium", "hard"]
    question_count: int
    job_description: str
    summary: str
    total_questions: int
    questions: list[TestQuestion]
    created_at: datetime


class SavedTestListItem(BaseModel):
    id: UUID
    created_by_uid: str
    role_title: str
    difficulty: Literal["easy", "medium", "hard"]
    total_questions: int
    created_at: datetime
