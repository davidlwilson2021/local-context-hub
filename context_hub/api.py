from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .security import (
    ApiAuthMiddleware,
    auth_template_context,
    may_expose_metadata,
    may_expose_raw_paths,
    require_api_auth,
    token_from_request,
)
from .service import (
    activity_for_project,
    export_project_json,
    export_project_markdown,
    get_project_detail,
    projects_with_last_activity,
    read_transcript,
    recent_activity,
    scan_and_store,
)


app = FastAPI(title="Context Hub")
app.add_middleware(ApiAuthMiddleware)

templates_dir = Path(__file__).parent / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
templates.env.filters["urlencode"] = lambda value: quote(str(value), safe="")


class ScanRequest(BaseModel):
    apps: str = "cursor"


def _include_raw(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_context_hub_token: Optional[str] = Header(default=None, alias="X-Context-Hub-Token"),
) -> bool:
    return may_expose_raw_paths(
        authorization,
        x_context_hub_token,
        query_token=token_from_request(request),
    )


def _include_metadata(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_context_hub_token: Optional[str] = Header(default=None, alias="X-Context-Hub-Token"),
) -> bool:
    return may_expose_metadata(
        authorization,
        x_context_hub_token,
        query_token=token_from_request(request),
    )


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")


def _template(request: Request, name: str, context: dict) -> HTMLResponse:
    return templates.TemplateResponse(
        name,
        {"request": request, **auth_template_context(request), **context},
    )


@app.get("/projects", dependencies=[Depends(require_api_auth)])
def get_projects(
    q: Optional[str] = Query(default=None),
    app_name: Optional[str] = Query(default=None, alias="app"),
):
    return projects_with_last_activity(query=q, app_name=app_name)


@app.get("/activity", dependencies=[Depends(require_api_auth)])
def get_activity(
    request: Request,
    app_name: Optional[str] = Query(default=None, alias="app"),
    limit: int = Query(default=50, ge=1, le=500),
    project_path: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    since: Optional[str] = Query(default=None),
    until: Optional[str] = Query(default=None),
    include_raw: bool = Depends(_include_raw),
    include_metadata: bool = Depends(_include_metadata),
):
    since_dt = _parse_dt(since)
    until_dt = _parse_dt(until)
    if project_path:
        return activity_for_project(
            project_path,
            query=q,
            kind=kind,
            include_raw_path=include_raw,
            include_metadata=include_metadata,
        )
    return recent_activity(
        limit=limit,
        app_name=app_name,
        query=q,
        kind=kind,
        since=since_dt,
        until=until_dt,
        include_raw_path=include_raw,
        include_metadata=include_metadata,
    )


@app.post("/scan", dependencies=[Depends(require_api_auth)])
def post_scan(body: ScanRequest):
    app_list = [a.strip().lower() for a in body.apps.split(",") if a.strip()]
    return scan_and_store(app_list)


@app.get("/export/markdown", dependencies=[Depends(require_api_auth)])
def export_markdown(
    project_path: str = Query(...),
    include_raw: bool = Depends(_include_raw),
    include_metadata: bool = Depends(_include_metadata),
):
    text = export_project_markdown(
        project_path,
        include_raw_path=include_raw,
        include_metadata=include_metadata,
    )
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


@app.get("/export/json", dependencies=[Depends(require_api_auth)])
def export_json(
    project_path: str = Query(...),
    include_raw: bool = Depends(_include_raw),
    include_metadata: bool = Depends(_include_metadata),
):
    return export_project_json(
        project_path,
        include_raw_path=include_raw,
        include_metadata=include_metadata,
    )


@app.get("/transcript", dependencies=[Depends(require_api_auth)])
def get_transcript(
    raw_path: str = Query(...),
):
    data = read_transcript(raw_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Transcript not found or not allowed")
    return data


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    q: Optional[str] = Query(default=None),
    app_name: Optional[str] = Query(default=None, alias="app"),
    kind: Optional[str] = Query(default=None),
):
    projects = projects_with_last_activity(query=q, app_name=app_name)
    recent = recent_activity(limit=50, app_name=app_name, query=q, kind=kind)
    return _template(
        request,
        "index.html",
        {
            "projects": projects,
            "recent": recent,
            "q": q or "",
            "app_name": app_name or "",
            "kind": kind or "",
        },
    )


@app.get("/projects/view", response_class=HTMLResponse)
def project_view(
    request: Request,
    path: str = Query(...),
    q: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    include_raw: bool = Depends(_include_raw),
    include_metadata: bool = Depends(_include_metadata),
):
    project, activities = get_project_detail(
        path,
        query=q,
        kind=kind,
        include_raw_path=include_raw,
        include_metadata=include_metadata,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _template(
        request,
        "project.html",
        {
            "project": project,
            "activities": activities,
            "q": q or "",
            "kind": kind or "",
        },
    )


@app.get("/transcript/view", response_class=HTMLResponse)
def transcript_view(
    request: Request,
    raw_path: str = Query(...),
):
    data = read_transcript(raw_path)
    if data is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return _template(request, "transcript.html", {"transcript": data})


@app.post("/scan/ui")
def scan_ui(request: Request):
    """HTML form-friendly scan trigger."""
    scan_and_store(["cursor", "cowork"])
    token = auth_template_context(request)["auth_token"]
    url = f"/?token={quote(token, safe='')}" if token else "/"
    return RedirectResponse(url=url, status_code=303)
