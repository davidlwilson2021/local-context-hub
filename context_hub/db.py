from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .models import ActivityItem, App as AppModel, Config, Project as ProjectModel


DB_DIR_NAME = ".context_hub"
DB_FILE_NAME = "context.db"
CONFIG_FILE_NAME = "config.json"


class Base(DeclarativeBase):
    pass


class App(Base):
    __tablename__ = "apps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    projects: Mapped[list["Project"]] = relationship(back_populates="app")
    activities: Mapped[list["Activity"]] = relationship(back_populates="app")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    app_id: Mapped[Optional[int]] = mapped_column(ForeignKey("apps.id"), nullable=True)

    app: Mapped[Optional[App]] = relationship(back_populates="projects")
    activities: Mapped[list["Activity"]] = relationship(back_populates="project")


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        Index(
            "uq_activities_app_raw_path",
            "app_id",
            "raw_path",
            unique=True,
            sqlite_where=text("raw_path IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[int] = mapped_column(ForeignKey("apps.id"), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    raw_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    # Use a different attribute name; "metadata" is reserved by SQLAlchemy's Declarative API.
    extra: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    app: Mapped[App] = relationship(back_populates="activities")
    project: Mapped[Optional[Project]] = relationship(back_populates="activities")


class ScanState(Base):
    """Tracks last-seen mtime for incremental provider scans."""

    __tablename__ = "scan_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    mtime: Mapped[float] = mapped_column(Float, nullable=False)
    last_scanned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


def _get_data_dir() -> Path:
    home = Path.home()
    data_dir = home / DB_DIR_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    return _get_data_dir() / DB_FILE_NAME


def get_config_path() -> Path:
    return _get_data_dir() / CONFIG_FILE_NAME


def get_engine(echo: bool = False):
    db_path = get_db_path()
    url = f"sqlite:///{db_path}"
    return create_engine(url, echo=echo, future=True)


def init_db(echo: bool = False) -> None:
    """Create all tables if they don't exist."""
    engine = get_engine(echo=echo)
    Base.metadata.create_all(engine)


def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, class_=Session)


@contextmanager
def get_session() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_config() -> Config:
    path = get_config_path()
    if not path.exists():
        return Config()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Config(**data)


def save_config(config: Config) -> None:
    path = get_config_path()
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def get_or_create_app(session: Session, name: str, display_name: Optional[str] = None) -> App:
    stmt = select(App).where(App.name == name)
    app = session.scalar(stmt)
    if app:
        return app
    app = App(name=name, display_name=display_name or name.title())
    session.add(app)
    session.flush()
    return app


def get_or_create_project(session: Session, path: str, name: Optional[str] = None, app: Optional[App] = None) -> Project:
    stmt = select(Project).where(Project.path == path)
    project = session.scalar(stmt)
    if project:
        return project
    project = Project(path=path, name=name or Path(path).name or path, app=app)
    session.add(project)
    session.flush()
    return project


def activity_exists(session: Session, app_id: int, raw_path: str) -> bool:
    session.flush()
    stmt = select(Activity.id).where(Activity.app_id == app_id, Activity.raw_path == raw_path)
    return session.scalar(stmt) is not None


def get_scan_mtime(session: Session, provider: str, source_path: str) -> Optional[float]:
    stmt = select(ScanState.mtime).where(
        ScanState.provider == provider,
        ScanState.source_path == source_path,
    )
    return session.scalar(stmt)


def upsert_scan_state(session: Session, provider: str, source_path: str, mtime: float) -> None:
    stmt = select(ScanState).where(
        ScanState.provider == provider,
        ScanState.source_path == source_path,
    )
    row = session.scalar(stmt)
    now = datetime.now()
    if row:
        row.mtime = mtime
        row.last_scanned_at = now
    else:
        session.add(
            ScanState(
                provider=provider,
                source_path=source_path,
                mtime=mtime,
                last_scanned_at=now,
            )
        )


def insert_activities(session: Session, activities: Iterable[ActivityItem]) -> tuple[int, int]:
    """Insert activities, skipping duplicates by (app, raw_path). Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0
    for item in activities:
        app = get_or_create_app(session, name=item.app_name)
        if item.raw_path and activity_exists(session, app.id, item.raw_path):
            skipped += 1
            continue

        project: Optional[Project] = None
        project_path = item.project_path or item.metadata.get("project_path")
        if project_path:
            project = get_or_create_project(session, path=project_path, app=app)

        activity = Activity(
            app=app,
            project=project,
            timestamp=item.timestamp,
            kind=item.kind,
            summary=item.summary,
            raw_path=item.raw_path,
            extra=item.metadata,
        )
        session.add(activity)
        session.flush()
        inserted += 1

    return inserted, skipped


def list_recent_activity(
    session: Session,
    limit: int = 20,
    app_name: Optional[str] = None,
    *,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
):
    stmt = select(Activity).join(Activity.app, isouter=True)
    if app_name:
        stmt = stmt.where(App.name == app_name)
    if kind:
        stmt = stmt.where(Activity.kind == kind)
    if since:
        stmt = stmt.where(Activity.timestamp >= since)
    if until:
        stmt = stmt.where(Activity.timestamp <= until)
    if query:
        pattern = f"%{query.lower()}%"
        stmt = stmt.where(
            func.lower(Activity.summary).like(pattern)
            | func.lower(Activity.raw_path).like(pattern)
        )
    stmt = stmt.order_by(Activity.timestamp.desc()).limit(limit)
    return session.scalars(stmt).all()


def list_projects_with_last_activity(session: Session):
    # Simple query: load all projects, then compute last timestamp in Python for clarity.
    projects = session.scalars(select(Project)).all()
    result = []
    for project in projects:
        if project.activities:
            last_ts = max(a.timestamp for a in project.activities)
        else:
            last_ts = None
        result.append((project, last_ts))
    # Sort by last activity (None last)
    result.sort(key=lambda item: (item[1] is None, item[1] or datetime.min), reverse=True)
    return result

def get_activities_for_project(
    session: Session,
    project_path: str,
    *,
    query: Optional[str] = None,
    kind: Optional[str] = None,
    limit: Optional[int] = None,
):
    """Return activities for a given project path ordered by timestamp descending."""
    project = session.scalar(select(Project).where(Project.path == project_path))
    if not project:
        return []
    stmt = select(Activity).where(Activity.project_id == project.id)
    if kind:
        stmt = stmt.where(Activity.kind == kind)
    if query:
        pattern = f"%{query.lower()}%"
        stmt = stmt.where(func.lower(Activity.summary).like(pattern))
    stmt = stmt.order_by(Activity.timestamp.desc())
    if limit:
        stmt = stmt.limit(limit)
    return session.scalars(stmt).all()


def get_activity_by_raw_path(session: Session, raw_path: str) -> Optional[Activity]:
    return session.scalar(select(Activity).where(Activity.raw_path == raw_path))

