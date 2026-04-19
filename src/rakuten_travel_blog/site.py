from __future__ import annotations

import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .models import Article, TopicConfig

RAKUTEN_CREDIT_HTML = (
    '<a href="https://webservice.rakuten.co.jp/" target="_blank">'
    '<img src="https://webservice.rakuten.co.jp/img/credit/200709/credit_22121.gif" '
    'border="0" alt="Rakuten Web Service Center" title="Rakuten Web Service Center" '
    'width="221" height="21"/></a>'
)


def build_site(
    root: Path,
    output_dir: Path,
    site_config: dict[str, object],
    topics: list[TopicConfig],
    demo_articles: list[Article],
    runtime_config: dict[str, object],
    generated_at: datetime,
) -> None:
    root_resolved = root.resolve()
    output_resolved = output_dir.resolve()
    if root_resolved not in output_resolved.parents and output_resolved != root_resolved / "dist":
        raise ValueError("Output directory must stay inside the repository.")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "static" / "site.css", assets_dir / "site.css")
    shutil.copyfile(root / "static" / "app.js", assets_dir / "app.js")

    write_site_data(output_dir, site_config, topics, demo_articles, runtime_config, generated_at)
    write_index_page(output_dir, site_config, topics, runtime_config, generated_at)
    for topic in topics:
        demo_article = next((article for article in demo_articles if article.slug == topic.slug), None)
        write_article_page(output_dir, site_config, topic, demo_article, runtime_config)

    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "build.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "topic_count": len(topics),
                "runtime_configured": bool(runtime_config.get("is_configured")),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_sitemap(output_dir, site_config, topics)
    write_robots(output_dir, site_config)


def write_site_data(
    output_dir: Path,
    site_config: dict[str, object],
    topics: list[TopicConfig],
    demo_articles: list[Article],
    runtime_config: dict[str, object],
    generated_at: datetime,
) -> None:
    payload = {
        "siteConfig": site_config,
        "topics": [topic.__dict__ for topic in topics],
        "demoArticles": [article.to_dict() for article in demo_articles],
        "runtimeConfig": runtime_config,
        "generatedAt": generated_at.isoformat(),
    }
    script = "window.__TRAVEL_RADAR__ = " + safe_json(payload) + ";\n"
    (output_dir / "assets" / "site-data.js").write_text(script, encoding="utf-8")


def write_index_page(
    output_dir: Path,
    site_config: dict[str, object],
    topics: list[TopicConfig],
    runtime_config: dict[str, object],
    generated_at: datetime,
) -> None:
    cards = "\n".join(render_topic_card(topic) for topic in topics)
    runtime_notice = (
        "本番キー設定済み。各詳細ページで閲覧時に最新の空室候補を読み込みます。"
        if runtime_config.get("is_configured")
        else "まだ楽天のWebアプリ設定が入っていないため、詳細ページはデモ表示になります。"
    )
    body = f"""
<main class=\"shell\">
  <section class=\"hero\">
    <p class=\"eyebrow\">{escape(str(site_config["hero_badge"]))}</p>
    <h1>{escape(str(site_config["site_name"]))}</h1>
    <p class=\"hero-copy\">{escape(str(site_config["site_subtitle"]))}</p>
    <div class=\"hero-meta\">
      <span>完全無料寄り</span>
      <span>GitHub Pages</span>
      <span>ブラウザでライブ更新</span>
    </div>
  </section>
  <section class=\"info-grid\">
    <article class=\"panel\">
      <h2>無料で回す設計</h2>
      <p>{escape(str(site_config["site_description"]))}</p>
      <p>サーバ側で毎日記事を量産するのではなく、ページの箱だけを無料で公開し、訪問時に楽天トラベルAPIから最新の空室候補を取り込みます。</p>
    </article>
    <article class=\"panel\">
      <h2>今の状態</h2>
      <p>{escape(runtime_notice)}</p>
      <p>ビルド日時: {escape(format_jp_datetime(generated_at))}</p>
    </article>
  </section>
  <section class=\"panel\">
    <h2>この方式の向き不向き</h2>
    <p>向いている: 初期費用ゼロ、PCオフでも公開継続、直前空室のような鮮度勝負。</p>
    <p>弱い: サーバ生成に比べるとSEOはやや不利です。収益が出たら後でサーバ側生成へ移す前提が現実的です。</p>
  </section>
  <section class=\"section-head\">
    <div>
      <p class=\"eyebrow\">Topics</p>
      <h2>公開ページ</h2>
    </div>
  </section>
  <section class=\"card-grid\">
    {cards}
  </section>
</main>
"""
    html = render_page(
        title=str(site_config["site_name"]),
        description=str(site_config["site_description"]),
        body=body,
        site_config=site_config,
        css_href="assets/site.css",
        home_href="./",
        script_prefix="",
        canonical_url=str(site_config["base_url"]).rstrip("/") + "/",
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def write_article_page(
    output_dir: Path,
    site_config: dict[str, object],
    topic: TopicConfig,
    demo_article: Article | None,
    runtime_config: dict[str, object],
) -> None:
    article_dir = output_dir / "posts" / topic.slug
    article_dir.mkdir(parents=True, exist_ok=True)
    fallback_message = (
        "ページを開くと最新の空室候補を読み込みます。"
        if runtime_config.get("is_configured")
        else "まだ楽天のWebアプリ設定が入っていないため、デモデータを表示します。"
    )
    demo_hint = ""
    if demo_article:
        demo_hint = f'<p class="muted-note">デモ例: {escape(demo_article.title)}</p>'
    body = f"""
<main class=\"shell article-shell\" data-topic-slug=\"{escape(topic.slug)}\">
  <section class=\"hero compact\">
    <p class=\"eyebrow\">Live Travel Finder</p>
    <h1 data-article-title>{escape(topic.headline)}</h1>
    <p class=\"hero-copy\" data-article-description>{escape(topic.description)}</p>
    <div class=\"hero-meta\" data-article-conditions>
      <span>読み込み待機中</span>
    </div>
  </section>
  <section class=\"info-grid\">
    <article class=\"panel\">
      <h2>選定ロジック</h2>
      <p>{escape(topic.description)}</p>
      <p>{escape(topic.focus_label)}、総合評価、口コミ件数、料金感をまとめて比較します。</p>
      {demo_hint}
    </article>
    <article class=\"panel\">
      <h2>読み込み状態</h2>
      <div class=\"status-stack\">
        <p data-status-message>{escape(fallback_message)}</p>
        <p class=\"muted-note\" data-status-sub>ブラウザから楽天トラベルAPIへアクセスするため、表示に数秒かかることがあります。</p>
      </div>
    </article>
  </section>
  <section class=\"section-head\">
    <div>
      <p class=\"eyebrow\">Hotels</p>
      <h2>候補ホテル</h2>
    </div>
  </section>
  <section class=\"hotel-list\" data-results>
    <article class=\"panel loading-card\">
      <h3>読み込み準備中</h3>
      <p>JavaScriptが有効なら、この場所に最新の候補が表示されます。</p>
    </article>
  </section>
  <section class=\"panel\">
    <h2>注意事項</h2>
    <ul class=\"notes\" data-notes>
      <li>本ページはアフィリエイト広告を利用しています。</li>
      <li>空室・料金・評価は変動します。予約前に楽天トラベル側の最新情報をご確認ください。</li>
      <li>JavaScriptを無効にしている場合はライブ更新されません。</li>
    </ul>
  </section>
</main>
"""
    html = render_page(
        title=topic.headline,
        description=topic.description,
        body=body,
        site_config=site_config,
        css_href="../../assets/site.css",
        home_href="../../",
        script_prefix="../../",
        canonical_url=str(site_config["base_url"]).rstrip("/") + f"/posts/{topic.slug}/",
    )
    (article_dir / "index.html").write_text(html, encoding="utf-8")


def render_page(
    title: str,
    description: str,
    body: str,
    site_config: dict[str, object],
    css_href: str,
    home_href: str,
    script_prefix: str,
    canonical_url: str,
) -> str:
    disclosure = escape(str(site_config["affiliate_disclosure"]))
    return f"""<!DOCTYPE html>
<html lang=\"ja\">
<head>
  <meta charset=\"utf-8\"/>
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>
  <title>{escape(title)}</title>
  <meta name=\"description\" content=\"{escape(description)}\"/>
  <link rel=\"canonical\" href=\"{escape(canonical_url)}\"/>
  <link rel=\"stylesheet\" href=\"{escape(css_href)}\"/>
</head>
<body>
  <header class=\"topbar\">
    <a class=\"home-link\" href=\"{escape(home_href)}\">{escape(str(site_config["site_name"]))}</a>
    <p>{disclosure}</p>
  </header>
  {body}
  <footer class=\"footer\">
    <p>{escape(str(site_config["footer_note"]))}</p>
    <div class=\"credit\">{RAKUTEN_CREDIT_HTML}</div>
  </footer>
  <script src=\"{escape(script_prefix)}assets/site-data.js\"></script>
  <script src=\"{escape(script_prefix)}assets/app.js\"></script>
</body>
</html>
"""


def render_topic_card(topic: TopicConfig) -> str:
    topic_labels = [
        topic.focus_label,
        "週末直前",
        "ライブ取得",
    ]
    badges = "".join(f"<span>{escape(label)}</span>" for label in topic_labels)
    return f"""
<article class=\"article-card\">
  <p class=\"eyebrow\">Live Page</p>
  <h3><a href=\"posts/{escape(topic.slug)}/\">{escape(topic.headline)}</a></h3>
  <p>{escape(topic.description)}</p>
  <div class=\"topic-pills\">
    {badges}
  </div>
  <a class=\"ghost-link\" href=\"posts/{escape(topic.slug)}/\">詳細を見る</a>
</article>
"""


def write_sitemap(output_dir: Path, site_config: dict[str, object], topics: list[TopicConfig]) -> None:
    base_url = str(site_config["base_url"]).rstrip("/")
    urls = [f"{base_url}/"]
    urls.extend(f"{base_url}/posts/{topic.slug}/" for topic in topics)
    body = "\n".join(
        f"  <url><loc>{xml_escape(url)}</loc></url>"
        for url in urls
    )
    sitemap = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
{body}
</urlset>
"""
    (output_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")


def write_robots(output_dir: Path, site_config: dict[str, object]) -> None:
    base_url = str(site_config["base_url"]).rstrip("/")
    robots = f"""User-agent: *
Allow: /

Sitemap: {base_url}/sitemap.xml
"""
    (output_dir / "robots.txt").write_text(robots, encoding="utf-8")


def format_jp_datetime(value: datetime) -> str:
    return f"{value.year}年{value.month}月{value.day}日 {value.hour:02d}:{value.minute:02d}"


def safe_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
