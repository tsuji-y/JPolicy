"""Database layer: schema, upsert with diff events, notification helpers."""

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

import pytz

logger = logging.getLogger(__name__)

JST = pytz.timezone("Asia/Tokyo")
DB_PATH = Path(__file__).parent.parent / "data" / "radar.db"

DDL = """
CREATE TABLE IF NOT EXISTS docs (
    id           TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    doc_type     TEXT NOT NULL,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    org          TEXT NOT NULL DEFAULT '',
    committee    TEXT NOT NULL DEFAULT '',
    speakers     TEXT NOT NULL DEFAULT '[]',
    published_at TEXT,
    fetched_at   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    notified   INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (doc_id) REFERENCES docs(id)
);

CREATE INDEX IF NOT EXISTS events_notified ON events(notified);
CREATE INDEX IF NOT EXISTS events_doc_id ON events(doc_id);
"""


def _now_jst() -> str:
    return datetime.now(JST).isoformat()


def content_hash(title: str, body: str, status: str) -> str:
    raw = (title + body + status).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def get_conn(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(DDL)


def upsert_doc(doc: dict[str, Any], db_path: Path = DB_PATH) -> Optional[dict[str, Any]]:
    """Insert or update a document. Returns the generated event dict, or None if unchanged."""
    required = {"id", "source", "doc_type", "title"}
    missing = required - doc.keys()
    if missing:
        raise ValueError(f"doc missing required fields: {missing}")

    doc_id = doc["id"]
    title = doc.get("title", "")
    body = doc.get("body", "")
    status = doc.get("status", "")
    new_hash = content_hash(title, body, status)
    now = _now_jst()

    speakers = doc.get("speakers", [])
    if not isinstance(speakers, str):
        speakers = json.dumps(speakers, ensure_ascii=False)

    with get_conn(db_path) as conn:
        row = conn.execute("SELECT content_hash, status FROM docs WHERE id = ?", (doc_id,)).fetchone()

        if row is None:
            conn.execute(
                """INSERT INTO docs
                   (id, source, doc_type, title, body, url, org, committee,
                    speakers, published_at, fetched_at, status, content_hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    doc_id,
                    doc.get("source", ""),
                    doc.get("doc_type", ""),
                    title,
                    body,
                    doc.get("url", ""),
                    doc.get("org", ""),
                    doc.get("committee", ""),
                    speakers,
                    doc.get("published_at"),
                    now,
                    status,
                    new_hash,
                ),
            )
            event = _insert_event(conn, doc_id, "new", "", now)
            logger.info("new doc: %s", doc_id)
            return event

        if row["content_hash"] == new_hash:
            return None

        old_status = row["status"]
        conn.execute(
            """UPDATE docs SET title=?, body=?, url=?, org=?, committee=?,
               speakers=?, published_at=?, fetched_at=?, status=?, content_hash=?
               WHERE id=?""",
            (
                title,
                body,
                doc.get("url", ""),
                doc.get("org", ""),
                doc.get("committee", ""),
                speakers,
                doc.get("published_at"),
                now,
                status,
                new_hash,
                doc_id,
            ),
        )

        if status != old_status:
            detail = json.dumps({"old": old_status, "new": status}, ensure_ascii=False)
            event = _insert_event(conn, doc_id, "status_changed", detail, now)
            logger.info("status changed: %s %s -> %s", doc_id, old_status, status)
            return event

        logger.debug("content updated (no status change): %s", doc_id)
        return None


def _insert_event(
    conn: sqlite3.Connection, doc_id: str, kind: str, detail: str, now: str
) -> dict[str, Any]:
    cur = conn.execute(
        "INSERT INTO events (doc_id, kind, detail, created_at) VALUES (?,?,?,?)",
        (doc_id, kind, detail, now),
    )
    return {"id": cur.lastrowid, "doc_id": doc_id, "kind": kind, "detail": detail, "created_at": now}


def get_pending_events(db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """Return unnotified events joined with their doc."""
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """SELECT e.id, e.doc_id, e.kind, e.detail, e.created_at,
                      d.title, d.url, d.source, d.doc_type, d.status,
                      d.published_at, d.committee, d.org
               FROM events e
               JOIN docs d ON d.id = e.doc_id
               WHERE e.notified = 0
               ORDER BY e.id""",
        ).fetchall()
        return [dict(r) for r in rows]


def mark_notified(event_ids: list[int], db_path: Path = DB_PATH) -> None:
    if not event_ids:
        return
    with get_conn(db_path) as conn:
        conn.executemany(
            "UPDATE events SET notified = 1 WHERE id = ?",
            [(eid,) for eid in event_ids],
        )
