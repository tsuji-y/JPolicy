#!/usr/bin/env python3
"""デモ用ダミーデータを data/radar.db に投入するスクリプト."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db import init_db, upsert_doc

DEMO_DOCS = [
    # kokkai
    {
        "id": "kokkai:demo-001",
        "source": "kokkai",
        "doc_type": "speech",
        "title": "[内閣委員会] 田中花子（令和8年6月10日）",
        "body": "月経困難症の治療においてオンライン診療を活用するための制度整備について政府の方針を伺いたい。現行の保険適用外とされているフェムテックサービスの扱いについても質問する。",
        "url": "https://kokkai.ndl.go.jp/api/speech?speechID=demo-001",
        "org": "国会",
        "committee": "内閣委員会",
        "speakers": ["田中花子"],
        "published_at": "2026-06-10",
        "status": "",
    },
    {
        "id": "kokkai:demo-002",
        "source": "kokkai",
        "doc_type": "speech",
        "title": "[厚生労働委員会] 鈴木一郎（令和8年6月12日）",
        "body": "低用量ピル（OC）のオンライン処方解禁について、プレコンセプションケアの観点から積極的に推進すべきと考えるが大臣の見解は。",
        "url": "https://kokkai.ndl.go.jp/api/speech?speechID=demo-002",
        "org": "国会",
        "committee": "厚生労働委員会",
        "speakers": ["鈴木一郎"],
        "published_at": "2026-06-12",
        "status": "",
    },
    # gian（追跡中議案）
    {
        "id": "gian:shugiin:221:demo-01",
        "source": "gian",
        "doc_type": "bill",
        "title": "女性の健康の包括的な支援に関する法律案",
        "body": "月経困難症及びフェムテックサービスへのアクセス向上を図る",
        "url": "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/honbun/g221demo01.htm",
        "org": "衆議院",
        "committee": "厚生労働委員会",
        "speakers": [],
        "published_at": "2026-03-10",
        "status": "委員会付託",
    },
    {
        "id": "gian:sangiin:221:demo-02",
        "source": "gian",
        "doc_type": "bill",
        "title": "月経困難症治療の保険適用拡充に関する法律案",
        "body": "低用量ピルの保険給付対象の拡大",
        "url": "https://www.sangiin.go.jp/japanese/joho1/kousei/gian/221/meisai/demo02.htm",
        "org": "参議院",
        "committee": "厚生労働委員会",
        "speakers": [],
        "published_at": "2026-04-01",
        "status": "成立",
    },
    # shitsumon
    {
        "id": "shitsumon:shugiin:221:demo-01",
        "source": "shitsumon",
        "doc_type": "shitsumon",
        "title": "フェムテック推進策及びオンライン診療の普及に関する質問主意書",
        "body": "政府はフェムテックの普及とオンライン診療の拡充について具体的施策を講じる予定があるか。",
        "url": "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/ademo01.htm",
        "org": "衆議院",
        "committee": "",
        "speakers": ["山田太郎君"],
        "published_at": "2026-05-20",
        "status": "answered",
    },
    # pubcom
    {
        "id": "pubcom:demo-00001",
        "source": "pubcom",
        "doc_type": "pubcom",
        "title": "女性の健康に関するオンライン診療ガイドライン（案）に対する意見募集",
        "body": "案の公示日：2026/06/01\n受付締切日時：2026/06/30 23:59\nカテゴリー：医療\n締切: 2026-06-30",
        "url": "https://public-comment.e-gov.go.jp/servlet/Public?CLASSNAME=PCMMSTDETAIL&id=demo00001&Mode=0",
        "org": "厚生労働省",
        "committee": "",
        "speakers": [],
        "published_at": "2026-06-01",
        "status": "open",
    },
    # kakugi
    {
        "id": "kakugi:2026-06-10:0",
        "source": "kakugi",
        "doc_type": "kakugi",
        "title": "女性の健康の包括的な支援に関する基本計画について",
        "body": "令和8年6月10日（火）定例閣議案件\n【一般案件】\n女性の健康の包括的な支援に関する基本計画について（決定）\n担当: 内閣府本府",
        "url": "https://www.kantei.go.jp/jp/kakugi/2026/kakugi-2026061001.html",
        "org": "内閣府本府",
        "committee": "一般案件",
        "speakers": [],
        "published_at": "2026-06-10",
        "status": "決定",
    },
]


def seed() -> None:
    init_db()
    print("Seeding demo data into data/radar.db ...")
    for doc in DEMO_DOCS:
        event = upsert_doc(doc)
        status = "new" if event else "unchanged"
        print(f"  [{status}] {doc['id']}: {doc['title'][:60]}")

    # status変化をデモ
    updated_bill = DEMO_DOCS[2].copy()
    updated_bill["status"] = "委員会可決"
    event = upsert_doc(updated_bill)
    if event:
        print(f"  [status_changed] {updated_bill['id']}: 委員会付託 → 委員会可決")

    print("Done.")


if __name__ == "__main__":
    seed()
