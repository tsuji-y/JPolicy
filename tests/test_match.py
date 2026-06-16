"""Tests for core/match.py with mocked LLM calls."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.match import match_l1, match_l2, run_matching


def _doc(**kwargs) -> dict:
    base = {
        "id": "test:1",
        "source": "kokkai",
        "doc_type": "speech",
        "title": "テストタイトル",
        "body": "",
        "url": "",
        "status": "",
    }
    base.update(kwargs)
    return base


class TestL1Match:
    def test_hits_on_keyword_in_title(self):
        doc = _doc(title="低用量ピルの処方について議論")
        hit, kw = match_l1(doc, ["低用量ピル", "月経困難症"])
        assert hit is True
        assert kw == "低用量ピル"

    def test_hits_on_keyword_in_body(self):
        doc = _doc(body="月経困難症の治療費について")
        hit, kw = match_l1(doc, ["月経困難症"])
        assert hit is True

    def test_no_hit(self):
        doc = _doc(title="農業政策について", body="補助金の配分を検討する")
        hit, kw = match_l1(doc, ["月経困難症", "フェムテック"])
        assert hit is False
        assert kw == ""


class TestL2Match:
    def test_hits_on_synonym(self):
        synonyms = {"低用量ピル": ["OC", "LEP", "経口避妊薬"]}
        doc = _doc(title="LEPの保険適用について")
        hit, kw = match_l2(doc, synonyms)
        assert hit is True
        assert "LEP" in kw
        assert "低用量ピル" in kw

    def test_no_hit(self):
        synonyms = {"低用量ピル": ["OC", "LEP"]}
        doc = _doc(title="防衛費の増額について")
        hit, kw = match_l2(doc, synonyms)
        assert hit is False


class TestRunMatching:
    def test_l1_hit_classified_correctly(self):
        docs = [_doc(title="月経困難症の患者への支援")]
        results = run_matching(docs)
        assert len(results) == 1
        doc, layer, kw, summary = results[0]
        assert layer == "L1"
        assert "月経困難症" in kw

    def test_l2_hit_classified_correctly(self):
        docs = [_doc(title="OC処方の保険適用見直し")]
        results = run_matching(docs)
        assert len(results) == 1
        doc, layer, kw, summary = results[0]
        assert layer == "L2"
        assert "低用量ピル" in kw

    def test_l3_called_for_unmatched(self):
        docs = [_doc(title="女性の健康増進と経済的支援")]

        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"score": 0.85, "summary": "女性健康政策に関連"}')]
        mock_client.messages.create.return_value = mock_msg

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic", return_value=mock_client):
                results = run_matching(docs)

        assert len(results) == 1
        doc, layer, score_str, summary = results[0]
        assert layer == "L3"
        assert float(score_str) >= 0.75
        assert summary == "女性健康政策に関連"

    def test_l3_below_threshold_excluded(self):
        docs = [_doc(title="エネルギー政策の見直しについて")]

        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"score": 0.3, "summary": "無関係"}')]
        mock_client.messages.create.return_value = mock_msg

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic", return_value=mock_client):
                results = run_matching(docs)

        assert len(results) == 0

    def test_l3_skipped_without_api_key(self):
        docs = [_doc(title="環境政策について")]
        with patch.dict("os.environ", {}, clear=True):
            results = run_matching(docs)
        assert len(results) == 0

    def test_l3_max_50_enforced(self):
        docs = [_doc(id=f"x:{i}", title=f"関係ない文書{i}") for i in range(60)]
        called_with: list[int] = []

        mock_client = MagicMock()
        def mock_create(**kwargs):
            called_with.append(len(kwargs["messages"]))
            msg = MagicMock()
            msg.content = [MagicMock(text='{"score": 0.2, "summary": "関係なし"}')]
            return msg
        mock_client.messages.create.side_effect = mock_create

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic", return_value=mock_client):
                results = run_matching(docs)

        assert len(called_with) == 50
