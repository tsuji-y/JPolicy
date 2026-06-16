"""e-Govパブリック・コメント アダプタ（RSS フィード）."""

import logging
import re
from typing import Any

import feedparser

from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

RSS_URL = "https://public-comment.e-gov.go.jp/rss/pcm_list.xml"

_DATE_RE = re.compile(r"案の公示日[：:][\s]*(\d{4}/\d{1,2}/\d{1,2})")
_DEADLINE_RE = re.compile(r"受付締切日時[：:][\s]*(\d{4}/\d{1,2}/\d{1,2})")


def _extract_dates(summary: str) -> tuple[str | None, str | None]:
    start_match = _DATE_RE.search(summary)
    end_match = _DEADLINE_RE.search(summary)
    start = start_match.group(1).replace("/", "-") if start_match else None
    end = end_match.group(1).replace("/", "-") if end_match else None
    return start, end


class PubcomAdapter(BaseAdapter):
    source = "pubcom"

    def fetch(self) -> list[dict[str, Any]]:
        try:
            resp = self._get(RSS_URL)
            feed = feedparser.parse(resp.content)
        except Exception as exc:
            logger.warning("[pubcom] RSS fetch failed: %s", exc)
            return []

        docs: list[dict[str, Any]] = []
        for entry in feed.entries:
            try:
                doc = self._to_doc(entry)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                logger.warning("[pubcom] entry parse error: %s", exc)

        logger.info("[pubcom] fetched %d items", len(docs))
        return docs

    def _to_doc(self, entry) -> dict[str, Any] | None:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "")

        if not title or not link:
            return None

        pub_start, deadline = _extract_dates(summary)

        body = summary
        if deadline:
            body = f"{summary}\n締切: {deadline}"

        case_id = ""
        id_match = re.search(r"id=(\d+)", link)
        if id_match:
            case_id = id_match.group(1)

        return {
            "id": f"pubcom:{case_id or title[:40]}",
            "source": self.source,
            "doc_type": "pubcom",
            "title": title,
            "body": body,
            "url": link,
            "org": "",
            "committee": "",
            "speakers": [],
            "published_at": pub_start,
            "status": "open",
        }
