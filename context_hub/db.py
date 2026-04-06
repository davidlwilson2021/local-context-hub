from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, create_engine, select
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


SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, class_=Session)


def init_db(echo: bool = False) -> None:
    """Create all tables if they don't exist."""
    engine = get_engine(echo=echo)
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
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


def insert_activities(session: Session, activities: Iterable[ActivityItem]) -> int:
    """Insert a batch of activities. Returns the number inserted.

    For now this is naive (no deduplication); you can build on metadata later.
    """
    count = 0
    for item in activities:
        app = get_or_create_app(session, name=item.app_name)
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
        count += 1

    return count


def list_recent_activity(session: Session, limit: int = 20, app_name: Optional[str] = None):
    stmt = select(Activity).order_by(Activity.timestamp.desc()).limit(limit)
    if app_name:
        stmt = (
            select(Activity)
            .join(Activity.app)
            .where(App.name == app_name)
            .order_by(Activity.timestamp.desc())
            .limit(limit)
        )
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

def get_activities_for_project(session: Session, project_path: str):
    """Return activities for a given project path ordered by timestamp descending."""
    project = session.scalar(select(Project).where(Project.path == project_path))
    if not project:
        return []
    stmt = (
        select(Activity)
        .where(Activity.project_id == project.id)
        .order_by(Activity.timestamp.desc())
    )
    return session.scalars(stmt).all()

