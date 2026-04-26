import logging
from datetime import datetime, timezone
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
    RecruiterAttemptListItem,
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
    db: Session,
) -> PublicTestResponse:
    saved = db.query(GeneratedTest).filter(GeneratedTest.public_slug == slug).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Public test not found")

    if saved.status != PUBLISHED:
        raise HTTPException(status_code=404, detail="Public test not available")

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
    db: Session,
) -> SubmitAttemptResponse:
    saved = db.query(GeneratedTest).filter(GeneratedTest.public_slug == slug).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Public test not found")

    if saved.status != PUBLISHED:
        raise HTTPException(status_code=409, detail="Attempts are allowed only for published tests")

    score = _calculate_attempt_score(saved.questions, payload.answers)
    submitted_at = datetime.now(timezone.utc)
    answer_rows = jsonable_encoder(payload.answers)

    attempt = Attempt(
        test_id=saved.id,
        candidate_email=payload.candidate_email,
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

    return [
        RecruiterAttemptListItem(
            attempt_id=attempt.id,
            test_id=attempt.test_id,
            candidate_email=attempt.candidate_email,
            score=float(attempt.score),
            started_at=attempt.started_at,
            submitted_at=attempt.submitted_at,
        )
        for attempt in attempts
    ]


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
