# 楽天トラベル特化の無料Webアプリ

楽天トラベルAPIを使って、`直前空室 × 条件特化` のページを GitHub Pages で無料公開するためのリポジトリです。

## いまの方針

`PCが起動していなくても動く` と `完全無料` を両立するため、サーバ側の定期実行ではなく次の方式に切り替えています。

- GitHub Pages で静的ページを公開
- 記事の箱だけをビルドして配置
- 宿データはページ閲覧時にブラウザから楽天トラベルAPIへアクセスして取得

これにより、常時起動サーバーなしで運用できます。

## この方式のメリット

- 月額0円で公開しやすい
- 自分のPCがオフでもページは見られる
- 直前空室のような鮮度が必要なテーマと相性がよい

## この方式の弱み

- サーバ生成の静的記事よりSEOは弱い
- 楽天の `Webアプリケーション` として公開キーをブラウザで使う前提になる
- アクセスが大きく伸びるとAPI呼び出し回数の管理が必要

収益が出たら、後でサーバ側生成へ移すのが現実的です。

## 必要な楽天アプリ

無料構成では、`API/バックエンドサービス` ではなく `Webアプリケーション` として楽天アプリを用意する必要があります。

設定の目安:

- アプリケーション名: `週末旅レーダー`
- アプリケーションURL: `https://choritomo.github.io/rakuten-travel/`
- アプリケーションタイプ: `Webアプリケーション`
- 許可されたWebサイト: `choritomo.github.io`

`API/バックエンドサービス` は許可IP前提なので、完全無料の常時運用とは相性がよくありません。

## GitHub Secrets

GitHub の `Settings > Secrets and variables > Actions` に次を登録します。

- `RAKUTEN_APPLICATION_ID`
- `RAKUTEN_ACCESS_KEY`
- `RAKUTEN_AFFILIATE_ID`

注意:

- この方式では最終的にブラウザ側で楽天APIを呼ぶため、これらの値はビルド後の公開ページ内で参照可能になります
- これは `Webアプリケーション` 方式では想定内の挙動です

## ファイル

- `scripts/generate_site.py`: GitHub Pages 用の静的ページを生成
- `static/app.js`: ブラウザ側で楽天APIを叩いて表示する本体
- `static/site.css`: 見た目
- `config/site.json`: サイト名とベースURL
- `config/topics.json`: 生成するテーマ
- `sample_data/demo_articles.json`: デモ表示用データ
- `.github/workflows/generate-site.yml`: GitHub Pages へのデプロイ
- `RUNBOOK_JA.md`: セットアップ手順

## ローカル確認

```bash
python scripts/generate_site.py --output-dir dist
```

その後、必要なら簡易サーバで確認できます。

```bash
python -m http.server 8000 --directory dist
```

## 初期テーマ

- `last-minute-onsen`: 今週末に空室がある温泉宿
- `family-breakfast`: 朝食評価が高いファミリー向けホテル
- `premium-getaway`: 高評価のご褒美ホテル

## 次にやること

1. 楽天側で `Webアプリケーション` を新規作成する
2. GitHub Secrets に3つの値を登録する
3. GitHub Pages を有効化する
4. リポジトリを push して公開する

## 参考

- [楽天トラベル施設情報API](https://webservice.rakuten.co.jp/documentation/hotel-detail-search)
- [楽天トラベル施設検索API](https://webservice.rakuten.co.jp/documentation/simple-hotel-search)
- [楽天トラベル空室検索API](https://webservice.rakuten.co.jp/documentation/vacant-hotel-search)
- [楽天トラベルランキングAPI](https://webservice.rakuten.co.jp/documentation/hotel-ranking)
- [Rakuten Web Service クレジット表示](https://webservice.rakuten.co.jp/guide/credit)
- [GitHub-hosted runners の IP に関する説明](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
