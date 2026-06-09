from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite only
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called once on startup."""
    from models import lead, interaction, escalation, knowledge_base, demo, user  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_light_migrations()


def _run_light_migrations():
    """
    Idempotent column adds for existing SQLite DBs.
    create_all() creates new tables but never ALTERs existing ones, so new
    nullable columns need a tiny migration to land on a DB that predates them.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    try:
        lead_cols = {c["name"] for c in insp.get_columns("leads")}
    except Exception:
        return  # table not present yet (fresh DB already has the column)

    if "meet_link" not in lead_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE leads ADD COLUMN meet_link VARCHAR(300)"))
    if "owner_id" not in lead_cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE leads ADD COLUMN owner_id INTEGER"))
