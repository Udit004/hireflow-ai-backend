import logging

from fastapi import APIRouter, HTTPException

from app.schemas.request import JDTestRequest
from app.schemas.response import TestResponse
from app.services.orchestrator import TestOrchestrator

router = APIRouter(tags=["test-generation"])
orchestrator = TestOrchestrator()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check() -> dict[str, str]:
    logger.info("Health check requested")
    return {"status": "ok"}


@router.post("/generate-test", response_model=TestResponse)
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
