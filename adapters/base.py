"""Base adapter class for all data sources."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import requests

logger = logging.getLogger(__name__)

UA = "PolicyRadar/0.1 (academic research; contact: y.tsujimura68@gmail.com)"
REQUEST_INTERVAL = 1.0


class BaseAdapter(ABC):
    source: str = ""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA

    def _get(self, url: str, **kwargs) -> requests.Response:
        """GET with 1-second rate limit and 3x exponential backoff."""
        time.sleep(REQUEST_INTERVAL)
        timeout = kwargs.pop("timeout", 30)
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                logger.warning("Retry %d for %s (%s), sleeping %ds", attempt + 1, url, exc, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")  # pragma: no cover

    def _decode(self, resp: requests.Response) -> str:
        enc = resp.apparent_encoding or "utf-8"
        try:
            return resp.content.decode(enc, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return resp.content.decode("utf-8", errors="replace")

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Return a list of document dicts matching the common schema."""
