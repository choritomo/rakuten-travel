# 楽天トラベル PC実行型 運用手順

## 1. この構成でできること

この構成は、`楽天APIの取得はPC`、`公開はGitHub Pages` に分ける方式です。

- 無料で公開を続けやすい
- 楽天の `API/バックエンドサービス` を使える
- 公開ページは PC がオフでも見られる

更新だけはPCが必要ですが、サイト自体は GitHub Pages に残るので止まりません。

## 2. 先に理解しておくこと

- 完全無料のまま `PCの電源オフでも更新実行` は基本的に難しいです
- ただし `PCをスリープ` にしておけば、Windowsタスクスケジューラで自動更新しやすいです
- iPhoneからは `遠隔操作` と `結果確認` はできます

現実的な運用は次の形です。

- 自宅PCは夜だけスリープ
- 深夜にタスクスケジューラで自動更新
- 公開先はGitHub Pages
- トラブル時だけiPhoneから遠隔操作

## 3. 楽天側でやること

楽天ウェブサービスで `API/バックエンドサービス` のアプリを使います。

### 入力の目安

- アプリケーション名: `旅レーダー`
- アプリケーションURL: `https://github.com/choritomo/rakuten-travel`
- アプリケーションタイプ: `API/バックエンドサービス`
- 許可されたIPアドレス: このPCのグローバルIP

### 注意

- 自宅回線のグローバルIPが変わったら、楽天側の許可IPも更新が必要です
- GitHub Actions から楽天APIは叩きません

## 4. GitHub 側でやること

### 4-1. GitHub Pages

1. リポジトリを `public` にする
2. `Settings > Pages`
3. `Build and deployment` の Source を `GitHub Actions` にする

このリポジトリでは、`site/` が更新されると Actions が Pages へデプロイします。

### 4-2. GitHub Token

`Settings > Developer settings > Personal access tokens > Fine-grained tokens` で token を作ります。

最低限ほしい権限:

- Repository access: `choritomo/rakuten-travel`
- Repository permissions: `Contents` を `Read and write`

作った token は `.env` の `GITHUB_TOKEN` に入れます。

## 5. .env を作る

ルートに `.env` を作ります。`.env.example` をそのまま真似して大丈夫です。

```env
RAKUTEN_APPLICATION_ID=ここに楽天のApplication ID
RAKUTEN_ACCESS_KEY=ここに楽天のAccess Key
RAKUTEN_AFFILIATE_ID=ここに楽天アフィリエイトID
GITHUB_TOKEN=ここにGitHub token
GITHUB_REPOSITORY=choritomo/rakuten-travel
GITHUB_BRANCH=main
GITHUB_PAGES_DIR=site
SITE_BASE_URL=https://choritomo.github.io/rakuten-travel
```

## 6. 初回確認

### 見た目だけ確認

```bash
python scripts/generate_site.py --sample-data --output-dir dist
```

### 楽天APIでローカル生成

```bash
python scripts/update_site.py --build-only
```

### 公開まで一気に反映

```bash
python scripts/update_site.py
```

成功すると次の流れになります。

1. `dist/` が更新される
2. GitHub リポジトリの `site/` が更新される
3. GitHub Actions が走る
4. [https://choritomo.github.io/rakuten-travel/](https://choritomo.github.io/rakuten-travel/) が更新される

## 7. タスクスケジューラ設定

Windows の `タスク スケジューラ` で新しいタスクを作ります。

### おすすめ設定

- 名前: `Rakuten Travel Update`
- 実行タイミング: 毎日 5:30
- `最上位の特権で実行する`
- `スケジュールされた時刻に実行できなかった場合はできるだけ早く実行する`
- `タスクを実行するためにスリープを解除する`

### プログラム

- プログラム: `powershell.exe`
- 引数:

```text
-ExecutionPolicy Bypass -File "C:\Users\tomoc\Desktop\codex\楽天トラベル\scripts\run_update.ps1"
```

- 開始:

```text
C:\Users\tomoc\Desktop\codex\楽天トラベル
```

## 8. iPhone からの操作

### できること

- Chrome Remote Desktop で自宅PCに入る
- GitHub の Actions 成功/失敗を見る
- 必要なら `scripts\run_update.ps1` を手動実行する

### 無料でおすすめ

- `Chrome Remote Desktop`
- `Tailscale + Windows標準RDP` もありですが、最初は少し難しめです

### できないことに近いもの

- PCが完全に電源オフの状態から、必ずiPhoneだけで起動する

これは `Wake-on-LAN` と BIOS/ルーター設定が必要で、回線によってはうまくいきません。最初は `スリープ運用` が安全です。

## 9. 困ったとき

### 楽天APIで失敗する

確認ポイント:

- 楽天アプリが `API/バックエンドサービス` になっているか
- 許可IPが今の回線のグローバルIPと合っているか
- `.env` の楽天キーに打ち間違いがないか

### GitHub には公開されない

確認ポイント:

- `.env` の `GITHUB_TOKEN` が入っているか
- token に `Contents: Read and write` があるか
- `GITHUB_REPOSITORY=choritomo/rakuten-travel` になっているか
- GitHub Actions の `Deploy published site` が失敗していないか

### サイトは見えるが内容が古い

確認ポイント:

- タスクスケジューラの最終実行結果
- PCがスリープ解除できているか
- GitHub Actions の実行時刻

## 10. 収益を伸ばす順番

最初はテーマを増やしすぎず、次の順で試すのがおすすめです。

1. `今週末の空室あり温泉`
2. `子連れで朝食評価が高いホテル`
3. `連休直前の高評価宿`
4. `レンタカー` や `観光体験` の横展開

## 参考

- [楽天トラベル施設情報API](https://webservice.rakuten.co.jp/documentation/hotel-detail-search)
- [楽天トラベル施設検索API](https://webservice.rakuten.co.jp/documentation/simple-hotel-search)
- [楽天トラベル空室検索API](https://webservice.rakuten.co.jp/documentation/vacant-hotel-search)
- [楽天トラベルランキングAPI](https://webservice.rakuten.co.jp/documentation/hotel-ranking)
- [Rakuten Web Service クレジット表示](https://webservice.rakuten.co.jp/guide/credit)
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
