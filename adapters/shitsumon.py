"""衆議院 質問主意書・答弁書アダプタ（第221回国会）."""

import logging
from typing import Any

from bs4 import BeautifulSoup

from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

SHUGIIN_BASE = "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon"

STATUS_NORMALIZED = {
    "答弁受理": "answered",
    "提出": "submitted",
    "審議中": "pending",
}


def _normalize_status(raw: str) -> str:
    for k, v in STATUS_NORMALIZED.items():
        if k in raw:
            return v
    return raw.strip()


class ShitsumonAdapter(BaseAdapter):
    source = "shitsumon"

    def __init__(self, session: int = 221) -> None:
        super().__init__()
        self.session = session

    def fetch(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        try:
            docs.extend(self._fetch_shugiin())
        except Exception as exc:
            logger.warning("[shitsumon] shugiin failed: %s", exc)
        logger.info("[shitsumon] fetched %d items", len(docs))
        return docs

    def _fetch_shugiin(self) -> list[dict[str, Any]]:
        url = f"{SHUGIIN_BASE}/kaiji{self.session}_l.htm"
        resp = self._get(url)
        html = resp.content.decode("cp932", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        docs: list[dict[str, Any]] = []
        table = soup.find("table")
        if not table:
            logger.warning("[shitsumon] no table found at %s", url)
            return docs

        rows = table.find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            try:
                doc = self._parse_row(cells)
                if doc:
                    docs.append(doc)
            except Exception as exc:
                logger.warning("[shitsumon] row parse error: %s", exc)

        return docs

    def _parse_row(self, cells) -> dict[str, Any] | None:
        q_num = cells[0].get_text(strip=True)
        title = cells[1].get_text(strip=True)
        submitter = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        status_raw = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        if not title or not q_num:
            return None

        keika_link = cells[4].find("a") if len(cells) > 4 else None
        keika_href = keika_link.get("href", "") if keika_link else ""
        doc_url = f"{SHUGIIN_BASE}/{keika_href}" if keika_href else ""

        qa_link = cells[5].find("a") if len(cells) > 5 else None
        qa_href = qa_link.get("href", "") if qa_link else ""
        if qa_href:
            doc_url = f"{SHUGIIN_BASE}/{qa_href}"

        return {
            "id": f"shitsumon:shugiin:{self.session}:{q_num}",
            "source": self.source,
            "doc_type": "shitsumon",
            "title": title,
            "body": "",
            "url": doc_url,
            "org": "衆議院",
            "committee": "",
            "speakers": [submitter] if submitter else [],
            "published_at": None,
            "status": _normalize_status(status_raw),
        }
