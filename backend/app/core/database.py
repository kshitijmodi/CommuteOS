from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# pool_pre_ping=True: a real bug found live, 2026-08-10/11 - Neon's
# free-tier Postgres (behind a connection pooler) periodically closes
# idle connections server-side, and SQLAlchemy's default pool doesn't
# know that until it tries to actually use one, surfacing as a genuine
# 500 ("SSL connection has been closed unexpectedly") on the first real
# request after a period of no traffic (this app's own free-tier web
# service also spins down when idle - the two combine to make "the
# first chat message after a while" the exact real trigger). pre_ping
# adds one cheap SELECT 1 before handing out a pooled connection and
# transparently reconnects if it's dead, rather than surfacing the
# error to the caller - the standard, documented fix for this exact
# failure mode.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request, always closed after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
