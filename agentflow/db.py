from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from agentflow.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as session:
        yield session

def initialize_database() -> None:
    from agentflow import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
