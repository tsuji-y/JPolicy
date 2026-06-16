"""首相官邸 閣議決定アダプタ."""

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

KANTEI_BASE = "https://www.kantei.go.jp"
INDEX_URL = f"{KANTEI_BASE}/jp/kakugi/index.html"

_DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")


def _extract_url_date(url: str) -> str | None:
    m = _DATE_RE.search(url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


class KakugiAdapter(BaseAdapter):
    source = "kakugi"

    def __init__(self, max_pages: int = 10) -> None:
        super().__init__()
        self.max_pages = max_pages

    def fetch(self) -> list[dict[str, Any]]:
        try:
            page_urls = self._get_session_urls()
        except Exception as exc:
            logger.warning("[kakugi] index fetch failed: %s", exc)
            return []

        docs: list[dict[str, Any]] = []
        for url in page_urls[: self.max_pages]:
            try:
                docs.extend(self._fetch_page(url))
            except Exception as exc:
                logger.warning("[kakugi] page %s failed: %s", url, exc)

        logger.info("[kakugi] fetched %d items", len(docs))
        return docs

    def _get_session_urls(self) -> list[str]:
        resp = self._get(INDEX_URL)
        soup = BeautifulSoup(resp.content.decode("utf-8", errors="replace"), "html.parser")
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"/jp/kakugi/\d{4}/kakugi-\d+\.html", href):
                full_url = KANTEI_BASE + href if href.startswith("/") else href
                if full_url not in urls:
                    urls.append(full_url)
        return urls

    def _fetch_page(self, url: str) -> list[dict[str, Any]]:
        resp = self._get(url)
        soup = BeautifulSoup(resp.content.decode("utf-8", errors="replace"), "html.parser")

        h1 = soup.find("h1")
        if not h1:
            return []

        heading_text = h1.get_text(strip=True)
        date_str = _extract_url_date(url)

        kakugi_type = "閣議"
        for kind in ("定例閣議", "臨時閣議", "持ち回り閣議"):
            if kind in heading_text:
                kakugi_type = kind
                break

        docs: list[dict[str, Any]] = []
        current_section = ""

        for el in soup.find_all(["h2", "p"]):
            tag = el.name
            text = el.get_text(strip=True)
            if not text:
                continue

            if tag == "h2":
                current_section = text
                continue

            if "（" not in text and "(" not in text:
                continue
            if "（決定）" not in text and "（了解）" not in text and "（報告）" not in text:
                continue

            ministry_el = el.find_next_sibling("p")
            ministry = ""
            if ministry_el:
                m_text = ministry_el.get_text(strip=True)
                if m_text.startswith("（") or m_text.startswith("("):
                    ministry = m_text.strip("（）()")

            title = re.sub(r"（(決定|了解|報告)）$", "", text).strip()
            decision_type = ""
            m = re.search(r"（(決定|了解|報告)）", text)
            if m:
                decision_type = m.group(1)

            doc_id = f"kakugi:{date_str}:{len(docs)}" if date_str else f"kakugi:{url}:{len(docs)}"

            docs.append(
                {
                    "id": doc_id,
                    "source": self.source,
                    "doc_type": "kakugi",
                    "title": title,
                    "body": f"{heading_text}\n【{current_section}】\n{text}\n担当: {ministry}",
                    "url": url,
                    "org": ministry,
                    "committee": current_section,
                    "speakers": [],
                    "published_at": date_str,
                    "status": decision_type,
                }
            )

        return docs
