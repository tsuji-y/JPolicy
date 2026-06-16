"""国会会議録検索システム API アダプタ（発言検索）."""

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)

API_URL = "https://kokkai.ndl.go.jp/api/speech"
CONFIG_PATH = Path(__file__).parent.parent / "config" / "keywords.yaml"


class KokkaiAdapter(BaseAdapter):
    source = "kokkai"

    def __init__(self, days: int = 7) -> None:
        super().__init__()
        self.days = days
        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        self.keywords: list[str] = []
        for theme in cfg.get("themes", []):
            self.keywords.extend(theme.get("l1_keywords", []))

    def fetch(self) -> list[dict[str, Any]]:
        until = date.today()
        from_date = until - timedelta(days=self.days)
        docs: list[dict[str, Any]] = []
        seen: set[str] = set()

        for keyword in self.keywords:
            try:
                docs.extend(self._fetch_keyword(keyword, from_date, until, seen))
            except Exception as exc:
                logger.warning("[kokkai] keyword=%r failed: %s", keyword, exc)

        logger.info("[kokkai] fetched %d speeches", len(docs))
        return docs

    def _fetch_keyword(
        self, keyword: str, from_date: date, until: date, seen: set[str]
    ) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        start = 1

        while True:
            params = {
                "any": keyword,
                "recordPacking": "json",
                "maximumRecords": 100,
                "startRecord": start,
                "from": from_date.isoformat(),
                "until": until.isoformat(),
            }
            resp = self._get(API_URL, params=params)
            data = resp.json()

            for rec in data.get("speechRecord", []):
                doc_id = rec.get("speechID", "")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                docs.append(self._to_doc(rec))

            next_pos = data.get("nextRecordPosition")
            if not next_pos:
                break
            start = next_pos

        return docs

    def _to_doc(self, rec: dict) -> dict[str, Any]:
        speakers = [rec.get("speaker", "")] if rec.get("speaker") else []
        return {
            "id": f"kokkai:{rec.get('speechID', '')}",
            "source": self.source,
            "doc_type": "speech",
            "title": f"[{rec.get('nameOfMeeting', '')}] {rec.get('speaker', '')}（{rec.get('date', '')}）",
            "body": rec.get("speech", ""),
            "url": rec.get("speechURL", ""),
            "org": "国会",
            "committee": rec.get("nameOfMeeting", ""),
            "speakers": speakers,
            "published_at": rec.get("date", ""),
            "status": "",
        }
