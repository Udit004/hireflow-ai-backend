import secrets


def generate_public_slug(length: int = 8) -> str:
    # URL-safe and short enough for copy/paste, while keeping collisions unlikely.
    return secrets.token_urlsafe(length)[:length].lower()


def build_public_test_url(frontend_base_url: str, slug: str) -> str:
    normalized_base = frontend_base_url.rstrip("/")
    return f"{normalized_base}/test/{slug}"
