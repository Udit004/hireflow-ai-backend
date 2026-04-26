import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.attempt import Attempt
from app.models.generated_test import GeneratedTest
from app.modules.auth.model import User
from app.modules.create_test.schemas import (
    CandidateAttemptHistoryItem,
    RecruiterAttemptListItem,
    RecruiterAttemptFeedbackSummary,
    RecruiterAttemptQuestionFeedback,
    JDTestRequest,
    AttemptAnswer,
    PublicTestQuestion,
    PublicTestResponse,
    PublishTestResponse,
    SaveGeneratedTestRequest,
    SavedTestListItem,
    SavedTestResponse,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
    TestQuestion,
    TestResponse,
)
from app.modules.create_test.slug import build_public_test_url, generate_public_slug
from app.modules.create_test.state_machine import DRAFT, PUBLISHED, require_transition
from app.services.orchestrator import TestOrchestrator

logger = logging.getLogger(__name__)
orchestrator = TestOrchestrator()
settings = get_settings()


def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    return {"status": "ok"}


def generate_test(payload: JDTestRequest) -> TestResponse:
    try:
        logger.info(
            "Generate test request received | role_title=%s | question_count=%s | difficulty=%s",
            payload.role_title,
            payload.question_count,
            payload.difficulty,
        )
        response = orchestrator.run(payload)
        logger.info(
            "Generate test request completed | role_title=%s | total_questions=%s",
            response.role_title,
            response.total_questions,
        )
        return response
    except Exception as exc:  # pragma: no cover
        logger.exception(
            "Generate test request failed | role_title=%s | question_count=%s | difficulty=%s",
            payload.role_title,
            payload.question_count,
            payload.difficulty,
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _to_saved_test_response(test: GeneratedTest) -> SavedTestResponse:
    return SavedTestResponse(
        id=test.id,
        created_by_uid=test.created_by_uid,
        role_title=test.role_title,
        difficulty=cast(Literal["easy", "medium", "hard"], test.difficulty),
        status=cast(Literal["draft", "published", "archived"], test.status),
        question_count=test.question_count,
        job_description=test.job_description,
        summary=test.summary,
        total_questions=test.total_questions,
        questions=[TestQuestion(**question) for question in test.questions],
        settings=test.settings,
        public_slug=test.public_slug,
        created_at=test.created_at,
        published_at=test.published_at,
    )


def generate_and_save_test(
    payload: SaveGeneratedTestRequest,
    db: Session,
    requester_uid: str,
) -> SavedTestResponse:
    user = db.get(User, requester_uid)
    if not user:
        raise HTTPException(status_code=404, detail="Creator user not found")

    generation_payload = JDTestRequest(
        job_description=payload.job_description,
        role_title=payload.role_title,
        question_count=payload.question_count,
        difficulty=payload.difficulty,
    )

    generated = orchestrator.run(generation_payload)
    question_rows = jsonable_encoder(generated.questions)

    saved = GeneratedTest(
        created_by_uid=requester_uid,
        role_title=generated.role_title,
        difficulty=payload.difficulty,
        status="draft",
        question_count=payload.question_count,
        job_description=payload.job_description,
        summary=generated.summary,
        total_questions=generated.total_questions,
        questions=question_rows,
        settings=payload.settings,
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return _to_saved_test_response(saved)


def get_saved_test(
    test_id: UUID,
    db: Session,
    requester_uid: str,
) -> SavedTestResponse:
    saved = _get_owned_test(test_id, db, requester_uid)

    return _to_saved_test_response(saved)


def publish_test(
    test_id: UUID,
    db: Session,
    requester_uid: str,
) -> PublishTestResponse:
    saved = _get_owned_test(test_id, db, requester_uid)
    require_transition(saved.status, DRAFT, "publish")

    published_at = datetime.now(timezone.utc)
    max_attempts = 5
    slug: str | None = None

    for _ in range(max_attempts):
        slug = generate_public_slug(8)
        saved.status = PUBLISHED
        saved.public_slug = slug
        saved.published_at = published_at

        try:
            db.commit()
            db.refresh(saved)
            return PublishTestResponse(
                test_id=saved.id,
                status=cast(Literal["draft", "published", "archived"], saved.status),
                public_slug=saved.public_slug or slug,
                published_at=saved.published_at or published_at,
                public_url=build_public_test_url(
                    settings.frontend_public_base_url,
                    saved.public_slug or slug,
                ),
            )
        except IntegrityError:
            db.rollback()

    raise HTTPException(status_code=500, detail="Failed to generate unique public slug")


def get_public_test_by_slug(
    slug: str,
    authenticated_email: str,
    db: Session,
) -> PublicTestResponse:
    saved = db.query(GeneratedTest).filter(GeneratedTest.public_slug == slug).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Public test not found")

    if saved.status != PUBLISHED:
        raise HTTPException(status_code=404, detail="Public test not available")

    normalized_authenticated_email = authenticated_email.strip().lower()
    existing_attempt = (
        db.query(Attempt)
        .filter(
            Attempt.test_id == saved.id,
            Attempt.candidate_email == normalized_authenticated_email,
        )
        .first()
    )
    if existing_attempt:
        raise HTTPException(
            status_code=409,
            detail="This candidate has already attempted this test and cannot open it again.",
        )

    return PublicTestResponse(
        test_id=saved.id,
        role_title=saved.role_title,
        difficulty=cast(Literal["easy", "medium", "hard"], saved.difficulty),
        total_questions=saved.total_questions,
        questions=[_to_public_question(question) for question in saved.questions],
        settings=saved.settings,
    )


def submit_public_attempt(
    slug: str,
    payload: SubmitAttemptRequest,
    authenticated_email: str,
    db: Session,
) -> SubmitAttemptResponse:
    saved = db.query(GeneratedTest).filter(GeneratedTest.public_slug == slug).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Public test not found")

    if saved.status != PUBLISHED:
        raise HTTPException(status_code=409, detail="Attempts are allowed only for published tests")

    normalized_authenticated_email = authenticated_email.strip().lower()
    normalized_payload_email = payload.candidate_email.strip().lower()

    if normalized_payload_email != normalized_authenticated_email:
        raise HTTPException(status_code=403, detail="Candidate email must match logged-in user email")

    existing_attempt = (
        db.query(Attempt)
        .filter(
            Attempt.test_id == saved.id,
            Attempt.candidate_email == normalized_authenticated_email,
        )
        .first()
    )
    if existing_attempt:
        raise HTTPException(
            status_code=409,
            detail="This candidate has already submitted this test and cannot attempt it again.",
        )

    _enforce_duration_limits(saved.settings, payload.started_at)

    score = _calculate_attempt_score(saved.questions, payload.answers)
    submitted_at = datetime.now(timezone.utc)
    answer_rows = jsonable_encoder(payload.answers)

    attempt = Attempt(
        test_id=saved.id,
        candidate_email=normalized_authenticated_email,
        answers=answer_rows,
        score=score,
        started_at=payload.started_at,
        submitted_at=submitted_at,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return SubmitAttemptResponse(
        attempt_id=attempt.id,
        test_id=saved.id,
        score=float(attempt.score),
        submitted_at=attempt.submitted_at,
    )


def _enforce_duration_limits(settings: dict, started_at: datetime | None) -> None:
    duration_minutes = _extract_duration_minutes(settings)
    if duration_minutes is None:
        return

    if started_at is None:
        raise HTTPException(status_code=422, detail="started_at is required when duration is configured")

    now = datetime.now(timezone.utc)
    normalized_start = started_at
    if normalized_start.tzinfo is None:
        normalized_start = normalized_start.replace(tzinfo=timezone.utc)

    if normalized_start > now + timedelta(minutes=1):
        raise HTTPException(status_code=422, detail="started_at cannot be in the future")

    elapsed_seconds = (now - normalized_start).total_seconds()
    allowed_seconds = duration_minutes * 60
    if elapsed_seconds > allowed_seconds:
        raise HTTPException(status_code=409, detail="Test duration exceeded")


def _extract_duration_minutes(settings: dict) -> int | None:
    raw_value = settings.get("duration_minutes", settings.get("duration"))
    if raw_value is None:
        return None

    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return None

    if parsed <= 0:
        return None

    return parsed


def list_test_attempts(
    test_id: UUID,
    db: Session,
    requester_uid: str,
) -> list[RecruiterAttemptListItem]:
    saved = _get_owned_test(test_id, db, requester_uid)

    attempts = (
        db.query(Attempt)
        .filter(Attempt.test_id == saved.id)
        .order_by(Attempt.submitted_at.desc())
        .all()
    )

    attempt_items: list[RecruiterAttemptListItem] = []
    for attempt in attempts:
        question_feedback, feedback_summary = _build_attempt_feedback(saved.questions, attempt.answers)
        attempt_items.append(
            RecruiterAttemptListItem(
                attempt_id=attempt.id,
                test_id=attempt.test_id,
                candidate_email=attempt.candidate_email,
                answers=[AttemptAnswer(**answer) for answer in attempt.answers],
                score=float(attempt.score),
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
                feedback_summary=feedback_summary,
                question_feedback=question_feedback,
            )
        )

    return attempt_items


def _get_owned_test(
    test_id: UUID,
    db: Session,
    requester_uid: str,
) -> GeneratedTest:
    saved = db.get(GeneratedTest, test_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Saved test not found")

    if saved.created_by_uid != requester_uid:
        raise HTTPException(status_code=403, detail="Not allowed to access this test")

    return saved


def _to_public_question(question: dict) -> PublicTestQuestion:
    return PublicTestQuestion(
        question_type=cast(Literal["mcq", "code", "scenario"], question.get("question_type")),
        question=cast(str, question.get("question")),
        options=cast(list[str] | None, question.get("options")),
        difficulty=cast(Literal["easy", "medium", "hard"], question.get("difficulty", "medium")),
    )


def _calculate_attempt_score(
    questions: list[dict],
    answers: list[AttemptAnswer],
) -> Decimal:
    if not questions:
        return Decimal("0.00")

    answers_by_index = {item.question_index: item.answer.strip().lower() for item in answers}
    mcq_total = 0
    mcq_correct = 0

    for index, question in enumerate(questions):
        if question.get("question_type") != "mcq":
            continue

        mcq_total += 1
        expected = str(question.get("expected_answer", "")).strip().lower()
        candidate = answers_by_index.get(index, "")
        if expected and candidate == expected:
            mcq_correct += 1

    if mcq_total == 0:
        return Decimal("0.00")

    percentage = (Decimal(mcq_correct) * Decimal("100")) / Decimal(mcq_total)
    return percentage.quantize(Decimal("0.01"))


def _build_attempt_feedback(
    questions: list[dict],
    attempt_answers: list[dict],
) -> tuple[list[RecruiterAttemptQuestionFeedback], RecruiterAttemptFeedbackSummary]:
    answers_by_index = {
        int(answer.get("question_index", -1)): str(answer.get("answer", "")).strip()
        for answer in attempt_answers
    }
    feedback_items: list[RecruiterAttemptQuestionFeedback] = []
    answered_count = 0
    unanswered_count = 0
    auto_graded_count = 0
    correct_count = 0
    incorrect_count = 0
    manual_review_count = 0

    for index, question in enumerate(questions):
        question_type = cast(Literal["mcq", "code", "scenario"], question.get("question_type"))
        candidate_answer = answers_by_index.get(index)
        expected_answer = str(question.get("expected_answer", "")).strip()
        normalized_candidate = candidate_answer.lower() if candidate_answer else ""
        normalized_expected = expected_answer.lower()

        if candidate_answer:
            answered_count += 1
        else:
            unanswered_count += 1

        if not candidate_answer:
            verdict: Literal["correct", "incorrect", "needs_review", "unanswered"] = "unanswered"
            feedback = "No answer was submitted for this question."
        elif question_type == "mcq":
            auto_graded_count += 1
            if normalized_candidate == normalized_expected and normalized_expected:
                verdict = "correct"
                correct_count += 1
                feedback = "The submitted option matches the expected answer."
            else:
                verdict = "incorrect"
                incorrect_count += 1
                feedback = "The submitted option does not match the expected answer."
        else:
            verdict = "needs_review"
            manual_review_count += 1
            feedback = _build_manual_review_feedback(candidate_answer, expected_answer)

        feedback_items.append(
            RecruiterAttemptQuestionFeedback(
                question_index=index,
                question_type=question_type,
                question=cast(str, question.get("question")),
                options=cast(list[str] | None, question.get("options")),
                expected_answer=expected_answer,
                candidate_answer=candidate_answer or None,
                verdict=verdict,
                feedback=feedback,
            )
        )

    return (
        feedback_items,
        RecruiterAttemptFeedbackSummary(
            answered_count=answered_count,
            unanswered_count=unanswered_count,
            auto_graded_count=auto_graded_count,
            correct_count=correct_count,
            incorrect_count=incorrect_count,
            manual_review_count=manual_review_count,
        ),
    )


def _build_manual_review_feedback(candidate_answer: str, expected_answer: str) -> str:
    expected_keywords = {
        token
        for token in expected_answer.lower().split()
        if len(token) > 3 and token.isascii()
    }
    candidate_terms = {
        token
        for token in candidate_answer.lower().split()
        if len(token) > 3 and token.isascii()
    }

    keyword_matches = len(expected_keywords & candidate_terms)

    if len(candidate_answer) < 25:
        return "Answer submitted, but it is brief. Manual recruiter review is recommended."

    if expected_keywords and keyword_matches >= max(1, len(expected_keywords) // 2):
        return "Answer covers several expected concepts. Manual recruiter review is still recommended."

    if expected_keywords and keyword_matches > 0:
        return "Answer covers some expected concepts. Manual recruiter review is recommended."

    return "Answer does not clearly match the expected concepts. Manual recruiter review is recommended."


def list_user_tests(
    uid: str,
    db: Session,
    requester_uid: str,
) -> list[SavedTestListItem]:
    if uid != requester_uid:
        raise HTTPException(status_code=403, detail="Not allowed to list another user's tests")

    tests = (
        db.query(GeneratedTest)
        .filter(GeneratedTest.created_by_uid == uid)
        .order_by(GeneratedTest.created_at.desc())
        .all()
    )

    return [
        SavedTestListItem(
            id=test.id,
            created_by_uid=test.created_by_uid,
            role_title=test.role_title,
            difficulty=cast(Literal["easy", "medium", "hard"], test.difficulty),
            status=cast(Literal["draft", "published", "archived"], test.status),
            total_questions=test.total_questions,
            created_at=test.created_at,
        )
        for test in tests
    ]


def list_candidate_attempt_history(
    authenticated_email: str,
    db: Session,
) -> list[CandidateAttemptHistoryItem]:
    normalized_email = authenticated_email.strip().lower()

    attempt_rows = (
        db.query(Attempt, GeneratedTest)
        .join(GeneratedTest, Attempt.test_id == GeneratedTest.id)
        .filter(Attempt.candidate_email == normalized_email)
        .order_by(Attempt.submitted_at.desc())
        .all()
    )

    return [
        CandidateAttemptHistoryItem(
            attempt_id=attempt.id,
            test_id=test.id,
            role_title=test.role_title,
            difficulty=cast(Literal["easy", "medium", "hard"], test.difficulty),
            total_questions=test.total_questions,
            score=float(attempt.score),
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
            public_slug=test.public_slug,
        )
        for attempt, test in attempt_rows
    ]
