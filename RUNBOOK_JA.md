# 楽天トラベル無料Webアプリ 運用手順

## 1. この構成でできること

この構成は、GitHub Pages に静的サイトを置き、ページを開いたタイミングでブラウザから楽天トラベルAPIへアクセスして最新候補を表示する方式です。

目的:

- 完全無料で始める
- 自分のPCがオフでも公開を止めない
- 楽天トラベルの直前空室を狙う

## 2. 先に理解しておく注意点

- `API/バックエンドサービス` ではなく `Webアプリケーション` を使う
- 楽天APIキーはブラウザ側で利用するため公開ページから見える
- その代わり、許可IPの問題を避けられる

これは `完全無料` と `PCオフでも動く` を優先したための割り切りです。

## 3. 楽天側でやること

### 新しいアプリを作る

既に `API/バックエンドサービス` を作っていても、無料運用用には `Webアプリケーション` を作り直すのがおすすめです。

入力例:

- アプリケーション名: `週末旅レーダー`
- アプリケーションURL: `https://choritomo.github.io/rakuten-travel/`
- アプリケーションタイプ: `Webアプリケーション`
- 許可されたWebサイト: `choritomo.github.io`
- アプリケーションの説明:

```text
楽天トラベルAPIを利用して、空室のあるホテル情報を取得し、
条件別の比較ページをGitHub Pages上で表示するためのWebアプリです。
```

## 4. GitHub Secrets の設定

GitHub リポジトリの `Settings > Secrets and variables > Actions` に次を登録します。

- `RAKUTEN_APPLICATION_ID`
- `RAKUTEN_ACCESS_KEY`
- `RAKUTEN_AFFILIATE_ID`

## 5. GitHub Pages の設定

無料で GitHub Pages を使うなら、先にリポジトリを `public` にします。

1. `Settings > Pages` を開く
2. `Build and deployment` の Source を `GitHub Actions` にする
3. まだ `private` なら `Settings > General > Danger Zone > Change repository visibility` から `public` に変える
4. `Actions > Generate travel site > Run workflow` を押す
5. `Deploy to GitHub Pages` が通るのを待つ

## 6. ローカルでの確認

### サイト生成

```bash
python scripts/generate_site.py --output-dir dist
```

### 表示確認

```bash
python -m http.server 8000 --directory dist
```

ブラウザで `http://localhost:8000` を開きます。

## 7. どこがライブ更新されるか

- トップページ: 固定の案内とテーマ一覧
- 各記事ページ: 閲覧時に楽天APIから最新候補を取得

つまり、定期実行しなくてもデータは最新寄りになります。

## 8. テーマの増やし方

`config/topics.json` を編集します。

おすすめ:

- `空室あり温泉`
- `朝食高評価`
- `子連れ`
- `カップル`
- `高評価ご褒美ホテル`

最初はテーマを増やしすぎず、3〜5本に絞る方が安定します。

## 9. 完全無料構成の勝ち方

この構成は SEO だけで勝つより、`直前需要` を狙う方が向いています。

おすすめ順:

1. 週末直前
2. 連休直前
3. 夏休み直前
4. 子連れ条件
5. 温泉条件

## 10. 困ったとき

### 楽天APIが表示されない

よくある原因:

- リポジトリが `private` のまま
- Webアプリではなくバックエンドアプリのキーを使っている
- 許可されたWebサイトが違う
- GitHub Pages のURLと楽天の設定がずれている
- `900001` や `900003` のような番号のホテルに飛ぶなら、ライブ取得ではなくデモ表示になっている

### GitHub Pages は見えるのに候補が出ない

確認ポイント:

- ブラウザのコンソールにエラーが出ていないか
- `choritomo.github.io` が許可サイトに入っているか
- `RAKUTEN_APPLICATION_ID` と `RAKUTEN_ACCESS_KEY` が入っているか

## 11. 収益が出たら次にやること

完全無料の次の段階では、次を順番に足すと強いです。

1. サーバ側の事前生成
2. Search Console 連携
3. クリック率の高いテーマに絞る
4. レンタカーや観光体験も足す

最初は無料で回し、数字が出たら強化するのが安全です。
