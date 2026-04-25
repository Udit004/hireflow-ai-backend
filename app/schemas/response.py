from typing import Literal

from pydantic import BaseModel


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
