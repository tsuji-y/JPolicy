"""衆議院・参議院 議案アダプタ（第221回国会）."""

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

SHUGIIN_BASE = "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian"
SANGIIN_BASE = "https://www.sangiin.go.jp/japanese/joho1/kousei/gian"

STATUS_MAP = {
    "衆議院で審議中": "委員会付託",
    "参議院で審議中": "委員会付託",
    "衆議院で可決": "衆院可決",
    "参議院で可決": "参院可決",
    "本院議了": "本院議了",
    "成立": "成立",
    "否決": "否決",
    "廃案": "廃案",
    "撤回": "撤回",
    "審議未了": "審議未了",
}

SUBMITTER_MAP = {
    "05": "衆院提出",
    "06": "参院提出",
    "09": "委員会提出",
}


def _normalize_status(raw: str) -> str:
    for k, v in STATUS_MAP.items():
        if k in raw:
            return v
    if raw.strip():
        logger.warning("[gian] unknown status: %r", raw)
    return raw.strip()


class GianAdapter(BaseAdapter):
    source = "gian"

    def __init__(self, session: int = 221) -> None:
        super().__init__()
        self.session = session

    def fetch(self) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        try:
            docs.extend(self._fetch_shugiin())
        except Exception as exc:
            logger.warning("[gian] shugiin failed: %s", exc)
        try:
            docs.extend(self._fetch_sangiin())
        except Exception as exc:
            logger.warning("[gian] sangiin failed: %s", exc)
        logger.info("[gian] fetched %d bills", len(docs))
        return docs

    def _fetch_shugiin(self) -> list[dict[str, Any]]:
        url = f"{SHUGIIN_BASE}/menu.htm"
        resp = self._get(url)
        html = resp.content.decode("cp932", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        docs: list[dict[str, Any]] = []
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if "議案件名" not in headers and "議案件名" not in str(headers):
                continue
            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                try:
                    doc = self._parse_shugiin_row(cells)
                    if doc:
                        docs.append(doc)
                except Exception as exc:
                    logger.warning("[gian] row parse error: %s", exc)
        return docs

    def _parse_shugiin_row(self, cells) -> dict[str, Any] | None:
        session_num = cells[0].get_text(strip=True)
        bill_num = cells[1].get_text(strip=True)
        title = cells[2].get_text(strip=True)
        status_raw = cells[3].get_text(strip=True)

        if not title:
            return None

        progress_link = cells[4].find("a") if len(cells) > 4 else None
        keika_href = progress_link.get("href", "") if progress_link else ""
        keika_url = f"{SHUGIIN_BASE}/{keika_href.lstrip('./')}" if keika_href else ""

        honbun_link = cells[5].find("a") if len(cells) > 5 else None
        honbun_href = honbun_link.get("href", "") if honbun_link else ""
        doc_url = f"{SHUGIIN_BASE}/{honbun_href.lstrip('./')}" if honbun_href else ""

        submitter_code = re.search(r"g(\d{5})\d{3}", honbun_href)
        submitter = "衆院提出"
        if submitter_code:
            submitter = SUBMITTER_MAP.get(submitter_code.group(1)[3:5], "衆院提出")

        return {
            "id": f"gian:shugiin:{session_num}:{bill_num}",
            "source": self.source,
            "doc_type": "bill",
            "title": title,
            "body": "",
            "url": doc_url,
            "org": "衆議院",
            "committee": "",
            "speakers": [],
            "published_at": None,
            "status": _normalize_status(status_raw),
        }

    def _fetch_sangiin(self) -> list[dict[str, Any]]:
        url = f"{SANGIIN_BASE}/{self.session}/gian.htm"
        resp = self._get(url)
        html = resp.content.decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        docs: list[dict[str, Any]] = []
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header_cells = [td.get_text(strip=True) for td in rows[0].find_all(["th", "td"])]
            if not any("件名" in h or "議案" in h for h in header_cells):
                continue
            for row in rows[1:]:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                try:
                    doc = self._parse_sangiin_row(cells)
                    if doc:
                        docs.append(doc)
                except Exception as exc:
                    logger.warning("[gian] sangiin row error: %s", exc)
        return docs

    def _parse_sangiin_row(self, cells) -> dict[str, Any] | None:
        bill_num = cells[0].get_text(strip=True)
        title = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        status_raw = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        if not title:
            return None

        link = cells[1].find("a") if len(cells) > 1 else None
        href = link.get("href", "") if link else ""
        url = f"{SANGIIN_BASE}/{self.session}/{href}" if href else ""

        return {
            "id": f"gian:sangiin:{self.session}:{bill_num}",
            "source": self.source,
            "doc_type": "bill",
            "title": title,
            "body": "",
            "url": url,
            "org": "参議院",
            "committee": "",
            "speakers": [],
            "published_at": None,
            "status": _normalize_status(status_raw),
        }
