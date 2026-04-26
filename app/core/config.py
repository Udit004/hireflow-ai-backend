from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    app_name: str = os.getenv("APP_NAME", "JD Agentic Test System")
    postgres_url: str = os.getenv("POSTGRES_URL", "sqlite:///./jd_agentic.db")
    firebase_service_account_path: str = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "firebase/serviceAccountKey.json",
    )
    firebase_service_account_json: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    firebase_service_account_b64: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_B64", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    gemini_planner_model: str = os.getenv("GEMINI_PLANNER_MODEL", "gemini-2.5-flash-lite")
    gemini_generation_model: str = os.getenv("GEMINI_GENERATION_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    gemini_critic_model: str = os.getenv("GEMINI_CRITIC_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite"))
    temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.25"))
    gemini_planner_temperature: float = float(os.getenv("GEMINI_PLANNER_TEMPERATURE", "0.2"))
    gemini_generation_temperature: float = float(os.getenv("GEMINI_GENERATION_TEMPERATURE", "0.45"))
    gemini_critic_temperature: float = float(os.getenv("GEMINI_CRITIC_TEMPERATURE", "0.15"))
    frontend_public_base_url: str = os.getenv("FRONTEND_PUBLIC_BASE_URL", "http://localhost:3000")


@lru_cache
def get_settings() -> Settings:
    return Settings()
