"""
Database engine and session factory.
Use get_db() as a FastAPI dependency in route handlers.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import DATABASE_URL

# echo=True logs all SQL in development — very useful for debugging
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,   # Test connections before use (handles DB restarts)
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """All ORM models inherit from this."""
    pass


def get_db():
    """
    FastAPI dependency that yields a database session.
    Automatically closes the session when the request is done.

    Usage in a route:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
