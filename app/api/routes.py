from fastapi import APIRouter, HTTPException

from app.schemas.request import JDTestRequest
from app.schemas.response import TestResponse
from app.services.orchestrator import TestOrchestrator

router = APIRouter(tags=["test-generation"])
orchestrator = TestOrchestrator()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/generate-test", response_model=TestResponse)
def generate_test(payload: JDTestRequest) -> TestResponse:
    try:
        return orchestrator.run(payload)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
