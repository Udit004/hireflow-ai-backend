import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base


logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_engine(
    settings.postgres_url,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so SQLAlchemy can discover table metadata.
    from app.models import attempt  # noqa: F401
    from app.models import generated_test  # noqa: F401
    from app.modules.auth import model  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created successfully")
