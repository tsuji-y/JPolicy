"""Tests for core/db.py: new doc, body update, status change, no change."""

import json
import tempfile
from pathlib import Path

import pytest

from core.db import init_db, upsert_doc, get_pending_events, mark_notified


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


def _base_doc(**kwargs) -> dict:
    base = {
        "id": "test-001",
        "source": "test",
        "doc_type": "speech",
        "title": "テスト文書タイトル",
        "body": "テスト本文",
        "url": "https://example.com/1",
        "status": "",
    }
    base.update(kwargs)
    return base


class TestNewDoc:
    def test_event_kind_is_new(self, db: Path):
        doc = _base_doc()
        event = upsert_doc(doc, db_path=db)
        assert event is not None
        assert event["kind"] == "new"
        assert event["doc_id"] == "test-001"

    def test_pending_event_appears(self, db: Path):
        upsert_doc(_base_doc(), db_path=db)
        events = get_pending_events(db_path=db)
        assert len(events) == 1
        assert events[0]["kind"] == "new"


class TestBodyUpdate:
    def test_content_change_no_event(self, db: Path):
        upsert_doc(_base_doc(), db_path=db)
        mark_notified([get_pending_events(db_path=db)[0]["id"]], db_path=db)

        updated = _base_doc(body="本文が変わりました")
        event = upsert_doc(updated, db_path=db)
        # body-only update does not produce a new event (no status change)
        assert event is None

    def test_no_duplicate_event(self, db: Path):
        upsert_doc(_base_doc(), db_path=db)
        mark_notified([get_pending_events(db_path=db)[0]["id"]], db_path=db)
        upsert_doc(_base_doc(body="updated"), db_path=db)
        assert len(get_pending_events(db_path=db)) == 0


class TestStatusChange:
    def test_status_changed_event_generated(self, db: Path):
        upsert_doc(_base_doc(doc_type="bill", status="提出"), db_path=db)
        mark_notified([get_pending_events(db_path=db)[0]["id"]], db_path=db)

        event = upsert_doc(_base_doc(doc_type="bill", status="委員会付託"), db_path=db)
        assert event is not None
        assert event["kind"] == "status_changed"
        detail = json.loads(event["detail"])
        assert detail["old"] == "提出"
        assert detail["new"] == "委員会付託"

    def test_status_change_event_is_pending(self, db: Path):
        upsert_doc(_base_doc(doc_type="bill", status="提出"), db_path=db)
        mark_notified([get_pending_events(db_path=db)[0]["id"]], db_path=db)
        upsert_doc(_base_doc(doc_type="bill", status="成立"), db_path=db)
        pending = get_pending_events(db_path=db)
        assert len(pending) == 1
        assert pending[0]["kind"] == "status_changed"


class TestNoChange:
    def test_no_event_when_unchanged(self, db: Path):
        doc = _base_doc()
        upsert_doc(doc, db_path=db)
        mark_notified([get_pending_events(db_path=db)[0]["id"]], db_path=db)

        event = upsert_doc(doc, db_path=db)
        assert event is None
        assert len(get_pending_events(db_path=db)) == 0


class TestMarkNotified:
    def test_mark_clears_pending(self, db: Path):
        upsert_doc(_base_doc(), db_path=db)
        events = get_pending_events(db_path=db)
        assert len(events) == 1
        mark_notified([events[0]["id"]], db_path=db)
        assert len(get_pending_events(db_path=db)) == 0
