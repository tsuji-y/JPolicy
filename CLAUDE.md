# 政策レーダー（Policy Radar）

日本の公開政策データ（国会会議録・議案・質問主意書・パブコメ・閣議決定）を
定期取得し、キーワード/意味マッチングでSlack通知と静的サイトに出力するパイプライン。

## 技術方針
- Python 3.11+。依存は requests / beautifulsoup4 / feedparser / jinja2 /
  pyyaml / anthropic / pytest のみ。WebフレームワークやORMは使わない
- ストレージは標準ライブラリの sqlite3。DBファイルは data/radar.db として
  リポジトリにコミットして永続化する（プライベートリポジトリ前提）
- すべての関数に型ヒント。パーサは防御的に書き、要素が見つからない場合は
  例外で落とさず警告ログ＋スキップ

## クローリング規律（厳守）
- リクエスト間隔は1秒以上。User-Agent は
  "PolicyRadar/0.1 (academic research; contact: y.tsujimura68@gmail.com)"
- タイムアウト30秒、リトライは指数バックオフで最大3回
- robots.txt を尊重する
- 1ソースの失敗でパイプライン全体を止めない（ログに残して継続）
- 文字コードは決め打ちせず response.apparent_encoding 等で判定

## データ規約
- 共通スキーマ docs テーブル:
  id, source, doc_type, title, body, url, org, committee,
  speakers(JSON), published_at, fetched_at, status, content_hash
- content_hash = sha256(title + body + status)
- 日時はすべてJST（Asia/Tokyo）のISO 8601
- 差分判定: 既存idでhash不一致なら更新。statusのみ変化した議案は
  events テーブルに kind="status_changed" を記録。新規は kind="new"

## ディレクトリ構成
- adapters/   ソース別取得モジュール（kokkai.py, gian.py, shitsumon.py, pubcom.py, kakugi.py）
- core/       db.py, match.py, notify.py
- site/       build.py, templates/
- config/     keywords.yaml, synonyms.yaml
- data/       radar.db
- tests/

## シークレット（環境変数 / GitHub Secrets）
- SLACK_WEBHOOK_URL : 通知先
- ANTHROPIC_API_KEY : L3意味マッチの関連度判定用
