from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class JDTestRequest(BaseModel):
    job_description: str = Field(..., min_length=20, description="Raw JD text")
    role_title: str = Field(default="General Role")
    question_count: int = Field(default=10, ge=3, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class TestQuestion(BaseModel):
    question_type: Literal["mcq", "code", "scenario"]
    question: str
    options: list[str] | None = None
    expected_answer: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class TestResponse(BaseModel):
    role_title: str
    summary: str
    total_questions: int
    questions: list[TestQuestion]


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
