from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TestStatus = Literal["draft", "published", "archived"]


class JDTestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_description: str = Field(..., alias="jd_text", min_length=20, description="Raw JD text")
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
    settings: dict = Field(default_factory=dict)


class SavedTestResponse(BaseModel):
    id: UUID
    created_by_uid: str
    role_title: str
    difficulty: Literal["easy", "medium", "hard"]
    status: TestStatus
    question_count: int
    job_description: str
    summary: str
    total_questions: int
    questions: list[TestQuestion]
    settings: dict
    public_slug: str | None
    created_at: datetime
    published_at: datetime | None


class SavedTestListItem(BaseModel):
    id: UUID
    created_by_uid: str
    role_title: str
    difficulty: Literal["easy", "medium", "hard"]
    status: TestStatus
    total_questions: int
    attempt_count: int
    public_slug: str | None
    created_at: datetime


class PublishTestResponse(BaseModel):
    test_id: UUID
    status: TestStatus
    public_slug: str
    published_at: datetime
    public_url: str


class PublicTestQuestion(BaseModel):
    question_type: Literal["mcq", "code", "scenario"]
    question: str
    options: list[str] | None = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class PublicTestResponse(BaseModel):
    test_id: UUID
    role_title: str
    difficulty: Literal["easy", "medium", "hard"]
    total_questions: int
    questions: list[PublicTestQuestion]
    settings: dict


class AttemptAnswer(BaseModel):
    question_index: int = Field(..., ge=0)
    answer: str = Field(..., min_length=1)


class SubmitAttemptRequest(BaseModel):
    candidate_email: str = Field(..., min_length=5)
    answers: list[AttemptAnswer] = Field(default_factory=list)
    started_at: datetime | None = None


class SubmitAttemptResponse(BaseModel):
    attempt_id: UUID
    test_id: UUID
    score: float
    submitted_at: datetime


class RecruiterAttemptFeedbackSummary(BaseModel):
    answered_count: int
    unanswered_count: int
    auto_graded_count: int
    correct_count: int
    incorrect_count: int
    manual_review_count: int


class RecruiterAttemptQuestionFeedback(BaseModel):
    question_index: int = Field(..., ge=0)
    question_type: Literal["mcq", "code", "scenario"]
    question: str
    options: list[str] | None = None
    expected_answer: str
    candidate_answer: str | None = None
    verdict: Literal["correct", "incorrect", "needs_review", "unanswered"]
    feedback: str


class RecruiterAttemptListItem(BaseModel):
    attempt_id: UUID
    test_id: UUID
    candidate_email: str
    answers: list[AttemptAnswer]
    score: float
    started_at: datetime | None
    submitted_at: datetime
    feedback_summary: RecruiterAttemptFeedbackSummary
    question_feedback: list[RecruiterAttemptQuestionFeedback]


class CandidateAttemptHistoryItem(BaseModel):
    attempt_id: UUID
    test_id: UUID
    role_title: str
    difficulty: Literal["easy", "medium", "hard"]
    total_questions: int
    score: float
    started_at: datetime | None
    submitted_at: datetime
    public_slug: str | None
