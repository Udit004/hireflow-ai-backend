from pathlib import Path
import base64
import json
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import get_settings


def initialize_firebase_admin() -> None:
    """Initialize Firebase Admin app once using service account credentials."""
    if firebase_admin._apps:
        return

    settings = get_settings()

    if settings.firebase_service_account_json:
        service_account_info = json.loads(settings.firebase_service_account_json)
        private_key = service_account_info.get("private_key")
        if isinstance(private_key, str):
            service_account_info["private_key"] = private_key.replace("\\n", "\n")
        cred = credentials.Certificate(service_account_info)
    elif settings.firebase_service_account_b64:
        decoded = base64.b64decode(settings.firebase_service_account_b64).decode("utf-8")
        service_account_info = json.loads(decoded)
        private_key = service_account_info.get("private_key")
        if isinstance(private_key, str):
            service_account_info["private_key"] = private_key.replace("\\n", "\n")
        cred = credentials.Certificate(service_account_info)
    else:
        cert_path = Path(settings.firebase_service_account_path)

        if not cert_path.exists():
            raise RuntimeError(
                "Firebase service account credentials are missing. "
                "Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_B64 for Render, "
                "or set FIREBASE_SERVICE_ACCOUNT_PATH to a local JSON file path."
            )

        cred = credentials.Certificate(str(cert_path))

    firebase_admin.initialize_app(cred)


def verify_id_token(id_token: str) -> dict[str, Any]:
    initialize_firebase_admin()
    return auth.verify_id_token(id_token)
