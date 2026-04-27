from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # SQLite-specific settings:
    # - check_same_thread=False   → allow access from FastAPI + background threads
    # - timeout=30                → wait up to 30s for locks instead of immediately failing
    # - NullPool                  → each session gets its own fresh connection, avoids
    #     "cannot rollback - no transaction is active" when background threads share state
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        settings.database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,           # wait for write locks
        },
        poolclass=NullPool,
    )

    # Enable WAL journal mode for SQLite: allows concurrent reads during writes
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30s wait on locks
        cursor.close()

else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from app.models import project, document, training, extraction  # noqa
    Base.metadata.create_all(bind=engine)
