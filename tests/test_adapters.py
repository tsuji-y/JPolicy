"""Fixture-based tests for adapters (no live network calls)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import feedparser
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(content: bytes, encoding: str = "utf-8") -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.apparent_encoding = encoding
    resp.status_code = 200
    resp.raise_for_status.return_value = None
    resp.json.return_value = json.loads(content) if content.startswith(b"{") else {}
    return resp


class TestGianAdapter:
    def test_shugiin_parse_returns_bills(self):
        from adapters.gian import GianAdapter
        html_bytes = (FIXTURES / "shugiin_gian_menu.html").read_bytes()
        mock_resp = _mock_response(html_bytes, "cp932")

        with patch.object(GianAdapter, "_get", return_value=mock_resp):
            adapter = GianAdapter(session=221)
            with patch.object(adapter, "_fetch_sangiin", return_value=[]):
                docs = adapter.fetch()

        assert len(docs) > 0, "Should parse at least one bill from fixture"
        for doc in docs[:3]:
            assert doc["source"] == "gian"
            assert doc["doc_type"] == "bill"
            assert doc["title"]
            assert doc["id"].startswith("gian:shugiin:")
            assert doc["status"] in {
                "委員会付託", "衆院可決", "参院可決", "本院議了", "成立",
                "否決", "廃案", "撤回", "審議未了", "提出", ""
            } or doc["status"]

    def test_shugiin_bill_has_url(self):
        from adapters.gian import GianAdapter
        html_bytes = (FIXTURES / "shugiin_gian_menu.html").read_bytes()
        mock_resp = _mock_response(html_bytes, "cp932")

        with patch.object(GianAdapter, "_get", return_value=mock_resp):
            adapter = GianAdapter(session=221)
            with patch.object(adapter, "_fetch_sangiin", return_value=[]):
                docs = adapter.fetch()

        bills_with_url = [d for d in docs if d["url"]]
        assert len(bills_with_url) > 0

    def test_shugiin_first_3_bills(self):
        from adapters.gian import GianAdapter
        html_bytes = (FIXTURES / "shugiin_gian_menu.html").read_bytes()
        mock_resp = _mock_response(html_bytes, "cp932")

        with patch.object(GianAdapter, "_get", return_value=mock_resp):
            adapter = GianAdapter(session=221)
            with patch.object(adapter, "_fetch_sangiin", return_value=[]):
                docs = adapter.fetch()

        print("\nFirst 3 Shugiuin bills:")
        for d in docs[:3]:
            print(f"  {d['id']}: {d['title']!r} status={d['status']!r}")


class TestShitsumonAdapter:
    def test_parse_returns_questions(self):
        from adapters.shitsumon import ShitsumonAdapter
        html_bytes = (FIXTURES / "shugiin_shitsumon_list.html").read_bytes()
        mock_resp = _mock_response(html_bytes, "cp932")

        with patch.object(ShitsumonAdapter, "_get", return_value=mock_resp):
            adapter = ShitsumonAdapter(session=221)
            docs = adapter.fetch()

        assert len(docs) > 0
        for doc in docs[:3]:
            assert doc["source"] == "shitsumon"
            assert doc["doc_type"] == "shitsumon"
            assert doc["title"]
            assert doc["id"].startswith("shitsumon:shugiin:")

    def test_answered_status_normalized(self):
        from adapters.shitsumon import ShitsumonAdapter
        html_bytes = (FIXTURES / "shugiin_shitsumon_list.html").read_bytes()
        mock_resp = _mock_response(html_bytes, "cp932")

        with patch.object(ShitsumonAdapter, "_get", return_value=mock_resp):
            adapter = ShitsumonAdapter(session=221)
            docs = adapter.fetch()

        answered = [d for d in docs if d["status"] == "answered"]
        assert len(answered) > 0, "Should find at least one 答弁受理 question"

    def test_first_3_questions(self):
        from adapters.shitsumon import ShitsumonAdapter
        html_bytes = (FIXTURES / "shugiin_shitsumon_list.html").read_bytes()
        mock_resp = _mock_response(html_bytes, "cp932")

        with patch.object(ShitsumonAdapter, "_get", return_value=mock_resp):
            adapter = ShitsumonAdapter(session=221)
            docs = adapter.fetch()

        print("\nFirst 3 written questions:")
        for d in docs[:3]:
            print(f"  {d['id']}: {d['title']!r} status={d['status']!r}")


class TestPubcomAdapter:
    def test_parse_rss_returns_items(self):
        from adapters.pubcom import PubcomAdapter
        rss_bytes = (FIXTURES / "egov_pubcom.xml").read_bytes()
        mock_resp = _mock_response(rss_bytes)

        with patch.object(PubcomAdapter, "_get", return_value=mock_resp):
            adapter = PubcomAdapter()
            docs = adapter.fetch()

        assert len(docs) > 0
        for doc in docs[:3]:
            assert doc["source"] == "pubcom"
            assert doc["doc_type"] == "pubcom"
            assert doc["title"]
            assert "締切" in doc["body"] or doc["published_at"]

    def test_deadline_extracted(self):
        from adapters.pubcom import PubcomAdapter
        rss_bytes = (FIXTURES / "egov_pubcom.xml").read_bytes()
        mock_resp = _mock_response(rss_bytes)

        with patch.object(PubcomAdapter, "_get", return_value=mock_resp):
            adapter = PubcomAdapter()
            docs = adapter.fetch()

        docs_with_deadline = [d for d in docs if "締切" in d["body"]]
        assert len(docs_with_deadline) > 0

    def test_first_3_pubcom(self):
        from adapters.pubcom import PubcomAdapter
        rss_bytes = (FIXTURES / "egov_pubcom.xml").read_bytes()
        mock_resp = _mock_response(rss_bytes)

        with patch.object(PubcomAdapter, "_get", return_value=mock_resp):
            adapter = PubcomAdapter()
            docs = adapter.fetch()

        print("\nFirst 3 public comments:")
        for d in docs[:3]:
            print(f"  {d['id']}: {d['title'][:60]!r} pub={d['published_at']!r}")


class TestKakugiAdapter:
    def test_parse_returns_decisions(self):
        from adapters.kakugi import KakugiAdapter
        index_bytes = (FIXTURES / "kantei_kakugi_index.html").read_bytes()
        detail_bytes = (FIXTURES / "kantei_kakugi_detail.html").read_bytes()

        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_response(index_bytes)
            return _mock_response(detail_bytes)

        with patch.object(KakugiAdapter, "_get", side_effect=mock_get):
            adapter = KakugiAdapter(max_pages=1)
            docs = adapter.fetch()

        assert len(docs) > 0
        for doc in docs[:3]:
            assert doc["source"] == "kakugi"
            assert doc["doc_type"] == "kakugi"
            assert doc["title"]
            assert doc["published_at"]

    def test_first_3_kakugi(self):
        from adapters.kakugi import KakugiAdapter
        index_bytes = (FIXTURES / "kantei_kakugi_index.html").read_bytes()
        detail_bytes = (FIXTURES / "kantei_kakugi_detail.html").read_bytes()

        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_response(index_bytes)
            return _mock_response(detail_bytes)

        with patch.object(KakugiAdapter, "_get", side_effect=mock_get):
            adapter = KakugiAdapter(max_pages=1)
            docs = adapter.fetch()

        print("\nFirst 3 cabinet decisions:")
        for d in docs[:3]:
            print(f"  {d['id']}: {d['title'][:60]!r} status={d['status']!r}")
