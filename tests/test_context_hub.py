from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from context_hub.db import get_config_path, get_db_path, init_db, insert_activities, load_config, save_config
from context_hub.models import ActivityItem, ActivityKind, Config
from context_hub.paths import default_cursor_paths, path_is_under
from context_hub.redact import redact_path
from context_hub.security import may_expose_raw_paths
from context_hub.service import scan_and_store


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
        timestamp=datetime.utcnow(),
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


def test_raw_path_gated(isolated_env):
    cfg = load_config()
    cfg.api_token = "t"
    cfg.expose_raw_paths = False
    save_config(cfg)

    assert may_expose_raw_paths(authorization="Bearer t") is True
    assert may_expose_raw_paths() is False


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


def test_default_cursor_paths():
    paths = default_cursor_paths()
    assert isinstance(paths, list)
