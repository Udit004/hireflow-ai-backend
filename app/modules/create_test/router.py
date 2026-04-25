from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.create_test.schemas import (
    JDTestRequest,
    SaveGeneratedTestRequest,
    SavedTestListItem,
    SavedTestResponse,
    TestResponse,
)
from app.modules.create_test.service import (
    generate_and_save_test,
    generate_test,
    get_saved_test,
    health_check,
    list_user_tests,
)

router = APIRouter(tags=["test-generation"])


@router.get("/health")
def health_check_route() -> dict[str, str]:
    return health_check()


@router.post("/generate-test", response_model=TestResponse)
def generate_test_route(payload: JDTestRequest) -> TestResponse:
    return generate_test(payload)


@router.post(
    "/tests/generate-and-save",
    response_model=SavedTestResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_and_save_test_route(
    payload: SaveGeneratedTestRequest,
    db: Session = Depends(get_db),
) -> SavedTestResponse:
    return generate_and_save_test(payload, db)


@router.get("/tests/{test_id}", response_model=SavedTestResponse)
def get_saved_test_route(test_id: UUID, db: Session = Depends(get_db)) -> SavedTestResponse:
    return get_saved_test(test_id, db)


@router.get("/users/{uid}/tests", response_model=list[SavedTestListItem])
def list_user_tests_route(uid: str, db: Session = Depends(get_db)) -> list[SavedTestListItem]:
    return list_user_tests(uid, db)
