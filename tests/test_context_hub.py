from __future__ import annotations

import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from context_hub.db import get_config_path, get_db_path, init_db, insert_activities, load_config, save_config
from context_hub.models import ActivityItem, ActivityKind, Config
from context_hub.paths import default_cursor_paths, path_is_under
from context_hub.redact import redact_path
from context_hub.security import may_expose_metadata, may_expose_raw_paths
from context_hub.service import _metadata_for_response, scan_and_store


@pytest.fixture()
def isolated_env(monkeypatch, tmp_path):
    data_dir = tmp_path / ".context_hub"
    data_dir.mkdir()
    db_path = data_dir / "context.db"
    config_path = data_dir / "config.json"

    monkeypatch.setattr("context_hub.db._get_data_dir", lambda: data_dir)
    monkeypatch.setattr("context_hub.db.get_db_path", lambda: db_path)
    monkeypatch.setattr("context_hub.db.get_config_path", lambda: config_path)
    init_db()
    yield data_dir


def test_dedup_insert(isolated_env):
    from context_hub.db import get_session

    item = ActivityItem(
        app_name="cursor",
        project_path="/tmp/proj",
        timestamp=datetime.now(timezone.utc),
        kind=ActivityKind.CHAT,
        summary="Test",
        raw_path="/tmp/a.jsonl",
    )
    with get_session() as session:
        n1, s1 = insert_activities(session, [item])
        n2, s2 = insert_activities(session, [item])
    assert n1 == 1 and s1 == 0
    assert n2 == 0 and s2 == 1


def test_api_token_required(isolated_env):
    cfg = load_config()
    cfg.api_token = "secret-token"
    save_config(cfg)

    from context_hub.api import app

    client = TestClient(app)
    assert client.get("/projects").status_code == 401
    assert client.get("/projects", headers={"Authorization": "Bearer secret-token"}).status_code == 200


def test_html_routes_require_token(isolated_env):
    cfg = load_config()
    cfg.api_token = "secret-token"
    save_config(cfg)

    from context_hub.api import app

    client = TestClient(app)
    assert client.get("/").status_code == 401
    assert client.get("/?token=secret-token").status_code == 200
    assert client.get("/transcript/view?raw_path=/etc/passwd").status_code == 401


def test_raw_path_gated(isolated_env):
    cfg = load_config()
    cfg.api_token = "t"
    cfg.expose_raw_paths = False
    save_config(cfg)

    assert may_expose_raw_paths(authorization="Bearer t") is True
    assert may_expose_raw_paths() is False


def test_metadata_gated(isolated_env):
    cfg = load_config()
    cfg.api_token = "t"
    cfg.expose_metadata = False
    save_config(cfg)

    full = {"source": "cursor", "file": "/secret/path.jsonl", "full_content": "data"}
    minimal = _metadata_for_response(full, include_full=False)
    assert "file" not in minimal
    assert minimal.get("source") == "cursor"

    assert may_expose_metadata(authorization="Bearer t") is True
    assert may_expose_metadata() is False


def test_api_metadata_omits_file_key(isolated_env):
    from context_hub.db import Activity, get_or_create_app, get_session

    with get_session() as session:
        app_row = get_or_create_app(session, name="cursor")
        session.add(
            Activity(
                app=app_row,
                timestamp=datetime.now(timezone.utc),
                kind="chat",
                summary="s",
                raw_path="/tmp/x.jsonl",
                extra={"source": "cursor", "file": "/tmp/x.jsonl"},
            )
        )

    from context_hub.service import recent_activity

    rows = recent_activity(limit=5, include_metadata=False)
    assert rows
    meta = rows[0].get("metadata") or {}
    assert "file" not in meta
    assert meta.get("source") == "cursor"


def test_redact_path():
    home = str(Path.home())
    assert home not in redact_path(f"{home}/projects/foo")


def test_path_is_under(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    child = root / "agent-transcripts" / "a.jsonl"
    child.parent.mkdir(parents=True)
    child.write_text("{}", encoding="utf-8")
    assert path_is_under(child, root)
    assert not path_is_under(tmp_path / "outside.txt", root)


def test_scan_cursor_jsonl(isolated_env, tmp_path):
    transcripts = tmp_path / "agent-transcripts"
    transcripts.mkdir()
    line = json.dumps({"title": "Fix bug", "workspace_path": "/work/p"})
    (transcripts / "fix_bug.jsonl").write_text(line + "\n", encoding="utf-8")

    cfg = load_config()
    cfg.cursor_path = str(tmp_path)
    save_config(cfg)

    results = scan_and_store(["cursor"])
    assert results["cursor"]["inserted"] == 1
    results2 = scan_and_store(["cursor"])
    assert results2["cursor"]["skipped"] >= 1

    from context_hub.db import get_session
    from context_hub.db import Activity

    with get_session() as session:
        activity = session.scalars(
            __import__("sqlalchemy").select(Activity).where(Activity.summary == "fix bug")
        ).first()
    assert activity is not None


def test_use_transcript_titles(isolated_env, tmp_path):
    transcripts = tmp_path / "agent-transcripts"
    transcripts.mkdir()
    line = json.dumps({"title": "Secret Title", "workspace_path": "/work/p"})
    (transcripts / "chat.jsonl").write_text(line + "\n", encoding="utf-8")

    cfg = load_config()
    cfg.cursor_path = str(tmp_path)
    cfg.use_transcript_titles = True
    save_config(cfg)

    scan_and_store(["cursor"])

    from context_hub.db import get_session
    from context_hub.db import Activity

    with get_session() as session:
        activity = session.scalars(
            __import__("sqlalchemy").select(Activity).where(Activity.summary == "Secret Title")
        ).first()
    assert activity is not None


def test_scan_skips_symlink_outside_root(isolated_env, tmp_path):
    root = tmp_path / "cursor-data"
    transcripts = root / "agent-transcripts"
    transcripts.mkdir(parents=True)
    outside = tmp_path / "outside.jsonl"
    outside.write_text(json.dumps({"title": "Leak"}) + "\n", encoding="utf-8")
    (transcripts / "escape.jsonl").symlink_to(outside)

    cfg = load_config()
    cfg.cursor_path = str(root)
    save_config(cfg)

    results = scan_and_store(["cursor"])
    assert results["cursor"]["inserted"] == 0


def test_data_dir_permissions(isolated_env):
    if sys.platform == "win32":
        pytest.skip("Unix permissions only")
    from context_hub.db import _secure_chmod

    _secure_chmod(isolated_env, 0o700)
    assert stat.S_IMODE(isolated_env.stat().st_mode) == 0o700
    db_path = isolated_env / "context.db"
    if db_path.exists():
        _secure_chmod(db_path, 0o600)
        assert stat.S_IMODE(db_path.stat().st_mode) == 0o600


def test_serve_allow_lan_requires_token(isolated_env, monkeypatch):
    cfg = load_config()
    cfg.api_token = None
    save_config(cfg)

    from context_hub.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--allow-lan"])
    assert result.exit_code == 1
    assert "api_token" in result.stdout


def test_default_cursor_paths():
    paths = default_cursor_paths()
    assert isinstance(paths, list)
