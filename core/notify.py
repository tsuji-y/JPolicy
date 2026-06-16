"""Slack通知・日次ダイジェスト."""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
JST_OFFSET = "+09:00"


def _days_until(deadline_str: str) -> str | None:
    try:
        deadline = date.fromisoformat(deadline_str)
        delta = (deadline - date.today()).days
        return f"D-{delta}" if delta >= 0 else f"締切超過{abs(delta)}日"
    except (ValueError, TypeError):
        return None


def _send_slack(payload: dict) -> None:
    if not WEBHOOK_URL:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


def notify_event(event: dict) -> None:
    """即時通知: new or status_changed イベント."""
    kind = event.get("kind", "")
    title = event.get("title", "")
    url = event.get("url", "")
    source = event.get("source", "")
    status = event.get("status", "")
    doc_type = event.get("doc_type", "")

    if kind == "new":
        icon = ":new:"
        heading = f"{icon} *新着* [{source}] {doc_type}"
        detail = f"*{title}*"
        if status:
            detail += f"\nステータス: {status}"
    elif kind == "status_changed":
        icon = ":arrows_counterclockwise:"
        detail_data = json.loads(event.get("detail", "{}"))
        heading = f"{icon} *ステータス変化* [{source}] {doc_type}"
        detail = f"*{title}*\n{detail_data.get('old','?')} → {detail_data.get('new','?')}"
    else:
        return

    # パブコメの締切情報
    body = event.get("body", "")
    if source == "pubcom" and "締切" in body:
        import re
        m = re.search(r"締切[：:]?\s*(\d{4}-\d{2}-\d{2})", body)
        if m:
            days_label = _days_until(m.group(1))
            if days_label:
                detail += f"\n締切: {m.group(1)}（{days_label}）"

    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": heading[:150]}},
        {"type": "section", "text": {"type": "mrkdwn", "text": detail[:3000]}},
    ]
    if url:
        blocks.append({
            "type": "actions",
            "elements": [{"type": "button", "text": {"type": "plain_text", "text": "詳細を見る"}, "url": url}],
        })

    _send_slack({"blocks": blocks})


def send_digest(matched_docs: list[tuple[dict, str, str, str | None]]) -> None:
    """日次ダイジェスト: L3ヒットまとめ送信."""
    if not matched_docs:
        logger.info("[notify] no L3 hits for digest")
        return

    lines: list[str] = [f"*本日の政策レーダー L3ダイジェスト* （{date.today().isoformat()}）\n"]
    for doc, layer, keyword, summary in matched_docs:
        title = doc.get("title", "")
        url = doc.get("url", "")
        src = doc.get("source", "")
        line = f"• [{src}] *{title[:60]}*"
        if summary:
            line += f"\n　└ {summary}"
        if url:
            line += f" <{url}|リンク>"
        lines.append(line)

    text = "\n".join(lines)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}},
    ]
    _send_slack({"blocks": blocks})
