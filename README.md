# 楽天トラベル特化ブログ

楽天トラベルAPIを `自宅PC` から叩いてホテル候補を集め、生成済みのHTMLだけを `GitHub Pages` に公開する構成です。

## この構成の狙い

- 月額0円で続けやすい
- 楽天APIはバックエンド方式のまま使える
- 公開サイトは PC がオフでも見られる

`完全無料` と `PCオフでも公開継続` の両立を優先し、`更新処理だけPC`、`公開はGitHub Pages` に分けています。

## 動き方

1. PCで `scripts/update_site.py` を実行
2. 楽天APIから最新候補を取得
3. `dist/` に静的HTMLを書き出し
4. GitHub API経由でリポジトリの `site/` を更新
5. GitHub Actions が `site/` を GitHub Pages にデプロイ

## 必要なもの

- 楽天ウェブサービスの `API/バックエンドサービス` アプリ
- GitHub の `fine-grained personal access token`
- Windows PC

## 設定ファイル

`.env.example` を参考に、ルートに `.env` を作ります。

```env
RAKUTEN_APPLICATION_ID=...
RAKUTEN_ACCESS_KEY=...
RAKUTEN_AFFILIATE_ID=...
GITHUB_TOKEN=...
GITHUB_REPOSITORY=choritomo/rakuten-travel
GITHUB_BRANCH=main
GITHUB_PAGES_DIR=site
SITE_BASE_URL=https://choritomo.github.io/rakuten-travel
```

## よく使うコマンド

サンプルで見た目確認:

```bash
python scripts/generate_site.py --sample-data --output-dir dist
```

楽天APIでローカル生成だけ:

```bash
python scripts/update_site.py --build-only
```

生成してGitHub Pagesまで公開:

```bash
python scripts/update_site.py
```

PowerShell から回すなら:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_update.ps1
```

## 主要ファイル

- `scripts/generate_site.py`: 楽天APIまたはサンプルから静的HTMLを生成
- `scripts/update_site.py`: 生成してGitHubへ公開
- `scripts/run_update.ps1`: タスクスケジューラ向けのPowerShellラッパー
- `src/rakuten_travel_blog/generator.py`: 楽天データから記事候補を作る本体
- `src/rakuten_travel_blog/github_publish.py`: GitHub Contents API で `site/` を更新
- `RUNBOOK_JA.md`: 初回セットアップと運用手順

## iPhone からできること

- Chrome Remote Desktop などで自宅PCを遠隔操作
- GitHub Actions の結果確認
- 必要なときだけ手動再実行

完全無料のままなら、`PCをシャットダウンせずスリープ運用` にして、Windowsタスクスケジューラの `スリープ解除` を使うのが一番現実的です。

## 参考

- [楽天トラベル施設情報API](https://webservice.rakuten.co.jp/documentation/hotel-detail-search)
- [楽天トラベル施設検索API](https://webservice.rakuten.co.jp/documentation/simple-hotel-search)
- [楽天トラベル空室検索API](https://webservice.rakuten.co.jp/documentation/vacant-hotel-search)
- [楽天トラベルランキングAPI](https://webservice.rakuten.co.jp/documentation/hotel-ranking)
- [Rakuten Web Service クレジット表示](https://webservice.rakuten.co.jp/guide/credit)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
