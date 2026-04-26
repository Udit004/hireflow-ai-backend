import logging
from typing import Literal, cast
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.generated_test import GeneratedTest
from app.modules.auth.model import User
from app.modules.create_test.schemas import (
    JDTestRequest,
    SaveGeneratedTestRequest,
    SavedTestListItem,
    SavedTestResponse,
    TestQuestion,
    TestResponse,
)
from app.services.orchestrator import TestOrchestrator

logger = logging.getLogger(__name__)
orchestrator = TestOrchestrator()


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
        question_count=test.question_count,
        job_description=test.job_description,
        summary=test.summary,
        total_questions=test.total_questions,
        questions=[TestQuestion(**question) for question in test.questions],
        created_at=test.created_at,
    )


def generate_and_save_test(
    payload: SaveGeneratedTestRequest,
    db: Session,
    requester_uid: str,
) -> SavedTestResponse:
    if payload.created_by_uid != requester_uid:
        raise HTTPException(status_code=403, detail="Not allowed to save tests for another user")

    user = db.get(User, payload.created_by_uid)
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
        created_by_uid=payload.created_by_uid,
        role_title=generated.role_title,
        difficulty=payload.difficulty,
        question_count=payload.question_count,
        job_description=payload.job_description,
        summary=generated.summary,
        total_questions=generated.total_questions,
        questions=question_rows,
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
    saved = db.get(GeneratedTest, test_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Saved test not found")

    if saved.created_by_uid != requester_uid:
        raise HTTPException(status_code=403, detail="Not allowed to access this test")

    return _to_saved_test_response(saved)


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
            total_questions=test.total_questions,
            created_at=test.created_at,
        )
        for test in tests
    ]
