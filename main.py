#!/usr/bin/env python3
"""政策レーダー CLI."""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stderr,
)

from core.db import init_db, upsert_doc, get_pending_events, mark_notified
from core.match import run_matching
from core.notify import notify_event, send_digest

ADAPTERS = {
    "kokkai": "adapters.kokkai.KokkaiAdapter",
    "gian": "adapters.gian.GianAdapter",
    "shitsumon": "adapters.shitsumon.ShitsumonAdapter",
    "pubcom": "adapters.pubcom.PubcomAdapter",
    "kakugi": "adapters.kakugi.KakugiAdapter",
}


def _load_adapter(name: str):
    import importlib
    module_path, class_name = ADAPTERS[name].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def cmd_poll(args) -> None:
    init_db()
    sources = list(ADAPTERS.keys()) if args.source == "all" else [args.source]

    all_new_docs: list[dict] = []

    for src in sources:
        try:
            adapter = _load_adapter(src)
            docs = adapter.fetch()
            for doc in docs:
                event = upsert_doc(doc)
                if event and event["kind"] == "new":
                    all_new_docs.append(doc)
        except Exception as exc:
            logging.getLogger(__name__).warning("source %s failed: %s", src, exc)

    pending = get_pending_events()
    notified_ids: list[int] = []

    for ev in pending:
        if ev["kind"] in ("new", "status_changed"):
            try:
                notify_event(ev)
                notified_ids.append(ev["id"])
            except Exception as exc:
                logging.getLogger(__name__).warning("notify failed for event %d: %s", ev["id"], exc)

    mark_notified(notified_ids)
    print(f"poll: {len(pending)} events processed", file=sys.stderr)


def cmd_digest(args) -> None:
    init_db()
    from core.db import get_conn, DB_PATH
    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            """SELECT id, source, doc_type, title, body, url, status
               FROM docs
               WHERE fetched_at >= datetime('now', '-1 day', 'localtime')
               ORDER BY fetched_at DESC
               LIMIT 200"""
        ).fetchall()
    docs = [dict(r) for r in rows]

    matched = run_matching(docs)
    l3_hits = [(d, layer, kw, summ) for d, layer, kw, summ in matched if layer == "L3"]

    send_digest(l3_hits)
    print(f"digest: {len(l3_hits)} L3 hits sent", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="政策レーダー")
    sub = parser.add_subparsers(dest="command")

    poll_p = sub.add_parser("poll", help="データ取得・差分通知")
    poll_p.add_argument(
        "--source",
        default="all",
        choices=["all"] + list(ADAPTERS.keys()),
        help="取得対象ソース",
    )

    sub.add_parser("digest", help="L3 AI判定・日次ダイジェスト送信")

    args = parser.parse_args()

    if args.command == "poll":
        cmd_poll(args)
    elif args.command == "digest":
        cmd_digest(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
