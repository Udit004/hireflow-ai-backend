from typing import Literal

from pydantic import BaseModel, Field


class JDTestRequest(BaseModel):
    job_description: str = Field(..., min_length=20, description="Raw JD text")
    role_title: str = Field(default="General Role")
    question_count: int = Field(default=10, ge=3, le=30)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
