"""3層マッチングエンジン: L1完全一致 / L2同義語 / L3意味スコア."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent / "config"
MAX_L3_PER_RUN = 50
L3_SCORE_THRESHOLD = 0.75

MatchResult = tuple[dict[str, Any], str, str, str | None]


def _load_keywords() -> tuple[list[str], str]:
    cfg = yaml.safe_load((CONFIG_DIR / "keywords.yaml").read_text(encoding="utf-8"))
    keywords: list[str] = []
    theme = ""
    for t in cfg.get("themes", []):
        keywords.extend(t.get("l1_keywords", []))
        if not theme:
            theme = t.get("theme", "")
    return keywords, theme


def _load_synonyms() -> dict[str, list[str]]:
    path = CONFIG_DIR / "synonyms.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("synonyms", {})


def _text(doc: dict) -> str:
    return (doc.get("title", "") + " " + doc.get("body", ""))


def match_l1(doc: dict, keywords: list[str]) -> tuple[bool, str]:
    text = _text(doc)
    for kw in keywords:
        if kw in text:
            return True, kw
    return False, ""


def match_l2(doc: dict, synonyms: dict[str, list[str]]) -> tuple[bool, str]:
    text = _text(doc)
    for canonical, syns in synonyms.items():
        for s in syns:
            if s in text:
                return True, f"{canonical}（{s}）"
    return False, ""


def match_l3(docs: list[dict], theme: str) -> list[tuple[dict, float, str]]:
    """Call Claude to score relevance. Returns (doc, score, summary) tuples above threshold."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("[match] ANTHROPIC_API_KEY not set, skipping L3")
        return []

    if len(docs) > MAX_L3_PER_RUN:
        logger.warning("[match] L3 input %d > max %d, truncating", len(docs), MAX_L3_PER_RUN)
        docs = docs[:MAX_L3_PER_RUN]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("[match] anthropic package not installed, skipping L3")
        return []

    results: list[tuple[dict, float, str]] = []
    for doc in docs:
        try:
            score, summary = _score_doc(client, doc, theme)
            if score >= L3_SCORE_THRESHOLD:
                results.append((doc, score, summary))
        except Exception as exc:
            logger.warning("[match] L3 scoring failed for %s: %s", doc.get("id"), exc)

    return results


def _score_doc(client, doc: dict, theme: str) -> tuple[float, str]:
    body_excerpt = doc.get("body", "")[:500]
    prompt = f"""テーマ: {theme}

文書タイトル: {doc.get('title', '')}
本文冒頭: {body_excerpt}

上記の文書が上記テーマと関連するかどうかを判断してください。
以下のJSON形式で回答してください（コードブロックなし）:
{{"score": 0.0から1.0の関連度, "summary": "一行要約（日本語）"}}"""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    import json as _json
    text = msg.content[0].text.strip()
    data = _json.loads(text)
    return float(data["score"]), data["summary"]


def run_matching(docs: list[dict]) -> list[MatchResult]:
    """Run L1/L2/L3 on a list of docs. Returns matched (doc, layer, keyword, summary) tuples."""
    keywords, theme = _load_keywords()
    synonyms = _load_synonyms()

    l1_hits: list[MatchResult] = []
    l2_hits: list[MatchResult] = []
    l3_candidates: list[dict] = []

    for doc in docs:
        hit, kw = match_l1(doc, keywords)
        if hit:
            l1_hits.append((doc, "L1", kw, None))
            continue
        hit, kw = match_l2(doc, synonyms)
        if hit:
            l2_hits.append((doc, "L2", kw, None))
            continue
        l3_candidates.append(doc)

    l3_hits: list[MatchResult] = []
    if l3_candidates and os.environ.get("ANTHROPIC_API_KEY"):
        scored = match_l3(l3_candidates, theme)
        for doc, score, summary in scored:
            l3_hits.append((doc, "L3", f"{score:.2f}", summary))

    all_hits = l1_hits + l2_hits + l3_hits
    logger.info(
        "[match] L1=%d L2=%d L3=%d total=%d",
        len(l1_hits), len(l2_hits), len(l3_hits), len(all_hits),
    )
    return all_hits
