from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.logging import configure_logging


configure_logging()

app = FastAPI(
    title="JD Agentic Test System",
    version="0.1.0",
    description="Generate interview tests from a job description using LangGraph agents.",
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "JD Agentic Test System is running"}
