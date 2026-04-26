from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import AuthenticatedUser
from app.modules.create_test.schemas import (
    CandidateAttemptHistoryItem,
    JDTestRequest,
    PublicTestResponse,
    PublishTestResponse,
    RecruiterAttemptListItem,
    SaveGeneratedTestRequest,
    SavedTestListItem,
    SavedTestResponse,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
    TestResponse,
)
from app.modules.create_test.service import (
    generate_and_save_test,
    generate_test,
    get_public_test_by_slug,
    get_saved_test,
    health_check,
    list_candidate_attempt_history,
    list_test_attempts,
    list_user_tests,
    publish_test,
    submit_public_attempt,
)

router = APIRouter(tags=["test-generation"])


@router.get("/health")
def health_check_route() -> dict[str, str]:
    return health_check()


@router.post("/generate-test", response_model=TestResponse)
def generate_test_route(
    payload: JDTestRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> TestResponse:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can generate tests")
    return generate_test(payload)


@router.post(
    "/tests/generate",
    response_model=SavedTestResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_and_save_test_route(
    payload: SaveGeneratedTestRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SavedTestResponse:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can create tests")

    return generate_and_save_test(payload, db, current_user.uid)


@router.post(
    "/tests/generate-and-save",
    response_model=SavedTestResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def generate_and_save_test_legacy_route(
    payload: SaveGeneratedTestRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SavedTestResponse:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can create tests")

    return generate_and_save_test(payload, db, current_user.uid)


@router.get("/tests/{test_id}", response_model=SavedTestResponse)
def get_saved_test_route(
    test_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SavedTestResponse:
    return get_saved_test(test_id, db, current_user.uid)


@router.get("/tests/{test_id}/attempts", response_model=list[RecruiterAttemptListItem])
def list_test_attempts_route(
    test_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[RecruiterAttemptListItem]:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can view test attempts")

    return list_test_attempts(test_id, db, current_user.uid)


@router.post("/tests/{test_id}/publish", response_model=PublishTestResponse)
def publish_test_route(
    test_id: UUID,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PublishTestResponse:
    if current_user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Only recruiters can publish tests")

    return publish_test(test_id, db, current_user.uid)


@router.get("/users/{uid}/tests", response_model=list[SavedTestListItem])
def list_user_tests_route(
    uid: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[SavedTestListItem]:
    return list_user_tests(uid, db, current_user.uid)


@router.get("/users/{uid}/attempts", response_model=list[CandidateAttemptHistoryItem])
def list_candidate_attempt_history_route(
    uid: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[CandidateAttemptHistoryItem]:
    if current_user.uid != uid:
        raise HTTPException(status_code=403, detail="Not allowed to list another user's attempts")

    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can view candidate attempt history")

    if not current_user.email:
        raise HTTPException(status_code=403, detail="Candidate account must have a verified email")

    return list_candidate_attempt_history(current_user.email, db)


@router.get("/public/tests/{slug}", response_model=PublicTestResponse)
def get_public_test_route(
    slug: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> PublicTestResponse:
    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can access public tests")

    if not current_user.email:
        raise HTTPException(status_code=403, detail="Candidate account must have a verified email")

    return get_public_test_by_slug(slug, current_user.email, db)


@router.post("/public/tests/{slug}/submit", response_model=SubmitAttemptResponse)
def submit_public_test_route(
    slug: str,
    payload: SubmitAttemptRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> SubmitAttemptResponse:
    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can submit tests")

    if not current_user.email:
        raise HTTPException(status_code=403, detail="Candidate account must have a verified email")

    return submit_public_attempt(slug, payload, current_user.email, db)
