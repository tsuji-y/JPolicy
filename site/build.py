#!/usr/bin/env python3
"""静的サイト生成: data/radar.db → public/index.html."""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz
import yaml
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "radar.db"
TEMPLATE_DIR = PROJECT_ROOT / "site" / "templates"
OUTPUT_DIR = PROJECT_ROOT / "public"
CONFIG_DIR = PROJECT_ROOT / "config"

JST = pytz.timezone("Asia/Tokyo")
PIPELINE_ORDER = ["提出", "委員会付託", "委員会可決", "衆院可決", "本院議了", "成立"]
SOURCE_NAMES = {
    "kokkai": "国会会議録",
    "gian": "議案",
    "shitsumon": "質問主意書",
    "pubcom": "パブコメ",
    "kakugi": "閣議決定",
}


def _now_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _load_keywords() -> list[str]:
    cfg = yaml.safe_load((CONFIG_DIR / "keywords.yaml").read_text(encoding="utf-8"))
    kws: list[str] = []
    for t in cfg.get("themes", []):
        kws.extend(t.get("l1_keywords", []))
    return kws


def _load_synonyms() -> dict[str, list[str]]:
    path = CONFIG_DIR / "synonyms.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("synonyms", {})


def _get_alerts(conn: sqlite3.Connection) -> list[dict]:
    cutoff = (datetime.now(JST) - timedelta(hours=24)).isoformat()
    rows = conn.execute(
        """SELECT e.id, e.kind, e.detail, e.created_at,
                  d.title, d.url, d.source, d.doc_type, d.status
           FROM events e
           JOIN docs d ON d.id = e.doc_id
           WHERE e.created_at >= ?
           ORDER BY e.created_at DESC
           LIMIT 30""",
        (cutoff,),
    ).fetchall()

    alerts = []
    for r in rows:
        ev = dict(r)
        if ev["kind"] == "status_changed":
            try:
                detail = json.loads(ev["detail"])
                ev["old_status"] = detail.get("old", "")
                ev["new_status"] = detail.get("new", "")
            except Exception:
                ev["old_status"] = ev["new_status"] = ""
        alerts.append(ev)
    return alerts


def _get_bills(conn: sqlite3.Connection, keywords: list[str]) -> list[dict]:
    rows = conn.execute(
        """SELECT id, title, url, org, status FROM docs
           WHERE doc_type = 'bill'
           ORDER BY fetched_at DESC
           LIMIT 100"""
    ).fetchall()

    matched: list[dict] = []
    for r in rows:
        d = dict(r)
        text = d.get("title", "")
        if any(kw in text for kw in keywords):
            matched.append(d)

    return matched[:20]


def _get_digest_items(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT e.id, e.detail, e.created_at,
                  d.id as doc_id, d.title, d.url, d.source, d.published_at
           FROM events e
           JOIN docs d ON d.id = e.doc_id
           WHERE e.kind = 'new'
           ORDER BY e.created_at DESC
           LIMIT 20"""
    ).fetchall()

    items: list[dict] = []
    for r in rows:
        item = dict(r)
        try:
            detail = json.loads(item.get("detail", "{}"))
        except Exception:
            detail = {}
        item["layer"] = detail.get("layer", "")
        item["summary"] = detail.get("summary", "")
        items.append(item)
    return items


def _get_source_status(conn: sqlite3.Connection) -> list[dict]:
    statuses: list[dict] = []
    for src, name in SOURCE_NAMES.items():
        row = conn.execute(
            "SELECT MAX(fetched_at) as last FROM docs WHERE source = ?", (src,)
        ).fetchone()
        last = row["last"][:16] if row and row["last"] else "未取得"
        statuses.append({"name": name, "last_fetch": last, "ok": bool(row and row["last"])})
    return statuses


def build() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not DB_PATH.exists():
        logger.info("DB not found at %s, creating empty", DB_PATH)
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        from core.db import DDL
        conn.executescript(DDL)
        conn.commit()
        conn.close()

    conn = _db_conn()
    keywords = _load_keywords()
    synonyms = _load_synonyms()

    ctx = {
        "updated_at": _now_jst(),
        "alerts": _get_alerts(conn),
        "bills": _get_bills(conn, keywords),
        "digest_items": _get_digest_items(conn),
        "l1_keywords": keywords,
        "synonyms": synonyms,
        "source_status": _get_source_status(conn),
    }
    conn.close()

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    tmpl = env.get_template("index.html.j2")
    html = tmpl.render(**ctx)

    output = OUTPUT_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    logger.info("Built %s (%d bytes)", output, len(html))
    print(f"Built: {output}", file=sys.stderr)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    build()
