from app.graph.workflow import build_workflow
from app.core.config import get_settings
from app.schemas.request import JDTestRequest
from app.schemas.response import TestResponse


class TestOrchestrator:
    def __init__(self) -> None:
        self.graph = build_workflow()
        self.settings = get_settings()

    def _build_trace_config(self, payload: JDTestRequest) -> dict:
        return {
            "run_name": "generate-test-workflow",
            "tags": [
                "jd-agentic",
                "langgraph",
                f"env:{self.settings.app_env}",
                f"difficulty:{payload.difficulty}",
            ],
            "metadata": {
                "app_name": self.settings.app_name,
                "role_title": payload.role_title,
                "question_count": payload.question_count,
                "difficulty": payload.difficulty,
            },
        }

    def run(self, payload: JDTestRequest) -> TestResponse:
        result = self.graph.invoke(
            {"request": payload},
            config=self._build_trace_config(payload),
        )
        final_response = result.get("final_response")
        if not isinstance(final_response, TestResponse):
            raise RuntimeError("Workflow did not produce a valid TestResponse")
        return final_response
