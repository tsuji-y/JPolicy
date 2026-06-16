# 政策レーダー（Policy Radar）

日本の公開政策データ（国会会議録・議案・質問主意書・パブコメ・閣議決定）を定期取得し、
キーワード/意味マッチングで Slack 通知と GitHub Pages ダッシュボードに出力するパイプライン。

## アーキテクチャ

```
データソース              取得・正規化            3層マッチング         出力
─────────────────        ──────────────          ──────────────       ──────────────
国会会議録 API  ──→      kokkai.py               L1: 完全一致         Slack 即時通知
衆参議案ページ  ──→      gian.py          ──→    L2: 同義語      →    GitHub Pages
質問主意書ページ ──→     shitsumon.py             L3: Claude haiku    日次ダイジェスト
e-Gov パブコメ  ──→     pubcom.py                   関連度スコア
首相官邸閣議決定 ──→    kakugi.py
                                ↓
                          sqlite3 (data/radar.db)
```

## セットアップ

### 1. リポジトリの準備

```bash
git clone https://github.com/<your-org>/jp-lobbying.git
cd jp-lobbying
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. GitHub Secrets の登録

リポジトリ Settings → Secrets and variables → Actions に以下を登録:

| Secret 名              | 説明                              |
|-----------------------|-----------------------------------|
| `SLACK_WEBHOOK_URL`   | Slack Incoming Webhook URL        |
| `ANTHROPIC_API_KEY`   | Claude API キー（L3判定用）        |

### 3. GitHub Pages の有効化

リポジトリ Settings → Pages → Source で **GitHub Actions** を選択。
リポジトリはプライベートのままでも Pages は公開できます（Organization の設定に依存）。

### 4. ローカル実行

```bash
# パブコメを取得して通知（SLACK_WEBHOOK_URL 未設定時は標準出力）
python main.py poll --source pubcom

# 全ソース一括取得
python main.py poll --source all

# L3 AI 判定 + 日次ダイジェスト
python main.py digest

# 静的サイト生成
python site/build.py
# → public/index.html を生成

# デモ用ダミーデータ投入
python scripts/seed_demo.py
```

### 5. 監視テーマの変更

[config/keywords.yaml](config/keywords.yaml) を編集:

```yaml
themes:
  - name: women_health
    theme: >
      日本の女性の健康政策（月経関連疾患の治療アクセス、フェムテック、
      プレコンセプションケア、オンライン診療を含む）
    l1_keywords:
      - 月経困難症
      - 低用量ピル
      # 追加キーワードをここに
```

同義語は [config/synonyms.yaml](config/synonyms.yaml) で管理。

## データスキーマ

`data/radar.db` の主要テーブル:

- **docs**: 取得した全文書（共通スキーマ）
- **events**: 新規追加・ステータス変化イベント（通知管理）

## ワークフロー

| ファイル | トリガー | 内容 |
|---------|---------|------|
| `.github/workflows/poll.yml` | 平日 JST 8-20 時毎時 | 全ソース取得・差分通知・DB コミット |
| `.github/workflows/digest.yml` | 毎日 JST 7:00 | L3 判定・ダイジェスト送信・Pages デプロイ |

## 注意事項

- クローリング間隔は 1 秒以上を保証しています
- User-Agent に連絡先メールを含めています
- 取得失敗時はログを残してパイプラインを継続します
