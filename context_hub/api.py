from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .service import activity_for_project, projects_with_last_activity, recent_activity


app = FastAPI(title="Context Hub")

templates_dir = Path(__file__).parent / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@app.get("/projects")
def get_projects():
    return projects_with_last_activity()


@app.get("/activity")
def get_activity(
    app_name: Optional[str] = Query(default=None, alias="app"),
    limit: int = Query(default=50, ge=1, le=500),
    project_path: Optional[str] = Query(default=None),
):
    if project_path:
        return activity_for_project(project_path)
    return recent_activity(limit=limit, app_name=app_name)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    projects = projects_with_last_activity()
    recent = recent_activity(limit=20)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "projects": projects,
            "recent": recent,
        },
    )

