from __future__ import annotations

import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .models import Article, HotelRecord, TopicConfig

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
    articles: list[Article],
    topic_errors: dict[str, str],
    build_mode: str,
    build_notice: str | None,
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

    article_map = {article.slug: article for article in articles}
    write_index_page(
        output_dir=output_dir,
        site_config=site_config,
        topics=topics,
        article_map=article_map,
        topic_errors=topic_errors,
        build_mode=build_mode,
        build_notice=build_notice,
        generated_at=generated_at,
    )
    for topic in topics:
        write_article_page(
            output_dir=output_dir,
            site_config=site_config,
            topic=topic,
            article=article_map.get(topic.slug),
            topic_error=topic_errors.get(topic.slug),
            build_mode=build_mode,
            generated_at=generated_at,
        )

    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "build.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "build_mode": build_mode,
                "topic_count": len(topics),
                "article_count": len(articles),
                "topic_errors": topic_errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    write_sitemap(output_dir, site_config, topics)
    write_robots(output_dir, site_config)


def write_index_page(
    output_dir: Path,
    site_config: dict[str, object],
    topics: list[TopicConfig],
    article_map: dict[str, Article],
    topic_errors: dict[str, str],
    build_mode: str,
    build_notice: str | None,
    generated_at: datetime,
) -> None:
    cards = "\n".join(
        render_topic_card(topic, article_map.get(topic.slug), topic_errors.get(topic.slug), build_mode)
        for topic in topics
    )
    mode_label = "楽天APIの実データ" if build_mode == "live" else "サンプルデータ"
    hero_meta = """
      <span>完全無料寄り</span>
      <span>PCで自動取得</span>
      <span>GitHub Pages公開</span>
    """
    build_banner = ""
    if build_notice:
        build_banner = f'<div class="top-banner{" warning" if build_mode == "sample" else ""}">{escape(build_notice)}</div>'

    body = f"""
<main class="shell">
  {build_banner}
  <section class="hero">
    <p class="eyebrow">{escape(str(site_config["hero_badge"]))}</p>
    <h1>{escape(str(site_config["site_name"]))}</h1>
    <p class="hero-copy">{escape(str(site_config["site_subtitle"]))}</p>
    <div class="hero-meta">
      {hero_meta}
    </div>
  </section>
  <section class="info-grid">
    <article class="panel">
      <h2>無料で回す設計</h2>
      <p>{escape(str(site_config["site_description"]))}</p>
      <p>楽天APIは自宅PCから取得し、生成済みのHTMLだけをGitHub Pagesへ公開します。公開先ではAPIを叩かないので、PCがオフでもページ自体は見られます。</p>
    </article>
    <article class="panel">
      <h2>今回の更新</h2>
      <p>取得元: {escape(mode_label)}</p>
      <p>生成日時: {escape(format_jp_datetime(generated_at))}</p>
      <p>更新できたテーマ: {len(article_map)} / {len(topics)}</p>
    </article>
  </section>
  <section class="panel">
    <h2>運用のコツ</h2>
    <p>無料のまま続けるなら、PCはシャットダウンではなくスリープ運用にして、タスクスケジューラで夜間に起こして更新するのが現実的です。</p>
    <p>iPhoneからは遠隔操作アプリで状態確認や再実行ができます。</p>
  </section>
  <section class="section-head">
    <div>
      <p class="eyebrow">Topics</p>
      <h2>公開ページ</h2>
    </div>
  </section>
  <section class="card-grid">
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
        canonical_url=str(site_config["base_url"]).rstrip("/") + "/",
    )
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def write_article_page(
    output_dir: Path,
    site_config: dict[str, object],
    topic: TopicConfig,
    article: Article | None,
    topic_error: str | None,
    build_mode: str,
    generated_at: datetime,
) -> None:
    article_dir = output_dir / "posts" / topic.slug
    article_dir.mkdir(parents=True, exist_ok=True)

    if article:
        body = render_article_body(article, topic, build_mode, generated_at)
        page_title = article.title
        description = article.description
    else:
        body = render_unavailable_body(topic, topic_error, build_mode, generated_at)
        page_title = topic.headline
        description = topic.description

    html = render_page(
        title=page_title,
        description=description,
        body=body,
        site_config=site_config,
        css_href="../../assets/site.css",
        home_href="../../",
        canonical_url=str(site_config["base_url"]).rstrip("/") + f"/posts/{topic.slug}/",
    )
    (article_dir / "index.html").write_text(html, encoding="utf-8")


def render_article_body(
    article: Article,
    topic: TopicConfig,
    build_mode: str,
    generated_at: datetime,
) -> str:
    hotel_cards = "\n".join(
        render_hotel_card(hotel, rank=index + 1, focus_label=article.focus_label)
        for index, hotel in enumerate(article.hotels)
    )
    notes = "\n".join(f"<li>{escape(note)}</li>" for note in article.notes)
    mode_copy = "楽天APIの実データです。" if build_mode == "live" else "サンプルデータです。"
    return f"""
<main class="shell article-shell">
  <section class="hero compact">
    <p class="eyebrow">Travel Snapshot</p>
    <h1>{escape(article.title)}</h1>
    <p class="hero-copy">{escape(article.description)}</p>
    <div class="hero-meta">
      {render_condition_pills(article)}
    </div>
  </section>
  <section class="info-grid">
    <article class="panel">
      <h2>選定ロジック</h2>
      <p>{escape(topic.description)}</p>
      <p>{escape(topic.focus_label)}、総合評価、口コミ件数、料金感をまとめて比較しています。</p>
    </article>
    <article class="panel">
      <h2>更新状態</h2>
      <p>{escape(mode_copy)}</p>
      <p>{escape(format_jp_datetime(article.generated_at))} 時点のホテル候補です。</p>
      <p>サイト生成日時: {escape(format_jp_datetime(generated_at))}</p>
    </article>
  </section>
  <section class="section-head">
    <div>
      <p class="eyebrow">Hotels</p>
      <h2>候補ホテル</h2>
    </div>
  </section>
  <section class="hotel-list">
    {hotel_cards}
  </section>
  <section class="panel">
    <h2>注意事項</h2>
    <ul class="notes">
      {notes}
    </ul>
  </section>
</main>
"""


def render_unavailable_body(
    topic: TopicConfig,
    topic_error: str | None,
    build_mode: str,
    generated_at: datetime,
) -> str:
    reason = topic_error or "今回は条件に合う候補を取得できませんでした。"
    mode_copy = "サンプルモード" if build_mode == "sample" else "ライブ取得モード"
    return f"""
<main class="shell article-shell">
  <section class="hero compact">
    <p class="eyebrow">Travel Snapshot</p>
    <h1>{escape(topic.headline)}</h1>
    <p class="hero-copy">{escape(topic.description)}</p>
    <div class="hero-meta">
      <span>{escape(mode_copy)}</span>
      <span>生成日時 {escape(format_jp_datetime(generated_at))}</span>
    </div>
  </section>
  <section class="info-grid">
    <article class="panel">
      <h2>このテーマについて</h2>
      <p>{escape(topic.description)}</p>
      <p>{escape(topic.focus_label)} を軸に候補を絞る設定です。</p>
    </article>
    <article class="panel error-card">
      <h2>今回は候補なし</h2>
      <p>最新の公開用HTMLは作れましたが、このテーマだけホテル候補を出せませんでした。</p>
      <p class="error-detail">{escape(reason)}</p>
      <p class="error-hint">楽天APIの応答や空室状況で一時的に起きることがあります。次回の自動更新で戻る場合があります。</p>
    </article>
  </section>
</main>
"""


def render_page(
    title: str,
    description: str,
    body: str,
    site_config: dict[str, object],
    css_href: str,
    home_href: str,
    canonical_url: str,
) -> str:
    disclosure = escape(str(site_config["affiliate_disclosure"]))
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}"/>
  <link rel="canonical" href="{escape(canonical_url)}"/>
  <link rel="stylesheet" href="{escape(css_href)}"/>
</head>
<body>
  <header class="topbar">
    <a class="home-link" href="{escape(home_href)}">{escape(str(site_config["site_name"]))}</a>
    <p>{disclosure}</p>
  </header>
  {body}
  <footer class="footer">
    <p>{escape(str(site_config["footer_note"]))}</p>
    <div class="credit">{RAKUTEN_CREDIT_HTML}</div>
  </footer>
</body>
</html>
"""


def render_topic_card(
    topic: TopicConfig,
    article: Article | None,
    topic_error: str | None,
    build_mode: str,
) -> str:
    topic_labels = [
        topic.focus_label,
        "静的記事",
        "PC取得" if build_mode == "live" else "サンプル",
    ]
    badges = "".join(f"<span>{escape(label)}</span>" for label in topic_labels)
    subtitle = article.description if article else topic.description
    meta = (
        f"<p class=\"muted-note\">更新済み: {escape(format_jp_date(article.checkin_date))} チェックイン</p>"
        if article
        else f"<p class=\"muted-note\">未取得: {escape(topic_error or '次回更新待ち')}</p>"
    )
    title = article.title if article else topic.headline
    return f"""
<article class="article-card">
  <p class="eyebrow">Static Page</p>
  <h3><a href="posts/{escape(topic.slug)}/">{escape(title)}</a></h3>
  <p>{escape(subtitle)}</p>
  {meta}
  <div class="topic-pills">
    {badges}
  </div>
  <a class="ghost-link" href="posts/{escape(topic.slug)}/">詳細を見る</a>
</article>
"""


def render_hotel_card(hotel: HotelRecord, rank: int, focus_label: str) -> str:
    badges = []
    if hotel.review_average is not None:
        badges.append(metric_badge("総合", f"{hotel.review_average:.1f}"))
    focus_value = pick_focus_value(hotel, focus_label)
    if focus_value is not None:
        badges.append(metric_badge(focus_label, f"{focus_value:.1f}"))
    if hotel.displayed_charge:
        badges.append(metric_badge("料金目安", f"{hotel.displayed_charge:,}円〜"))

    image_html = (
        f'<img src="{escape(hotel.image_url)}" alt="{escape(hotel.name)}のイメージ"/>'
        if hotel.image_url
        else '<div class="image-fallback">No Image</div>'
    )
    access_text = hotel.access or hotel.address
    area_name = hotel.area_name or "Rakuten Travel"
    detail_text = hotel.special or "詳細は予約ページでご確認ください。"
    return f"""
<article class="hotel-card">
  <div class="hotel-media">
    <span class="rank-badge">#{rank}</span>
    {image_html}
  </div>
  <div class="hotel-content">
    <p class="eyebrow">{escape(area_name)}</p>
    <h3>{escape(hotel.name)}</h3>
    <div class="badge-row">{"".join(badges)}</div>
    <p class="selection-reason">{escape(hotel.selection_reason or "")}</p>
    <p>{escape(detail_text)}</p>
    {f'<div class="hotel-meta"><p>{escape(access_text)}</p></div>' if access_text else ''}
    <a class="primary-link" href="{escape(hotel.booking_url)}" target="_blank" rel="noopener noreferrer">楽天トラベルで確認</a>
  </div>
</article>
"""


def render_condition_pills(article: Article) -> str:
    items = [
        f"チェックイン {format_jp_date(article.checkin_date)}",
        f"チェックアウト {format_jp_date(article.checkout_date)}",
        f"大人{article.adult_num}名",
    ]
    if article.child_num:
        items.append(f"子ども{article.child_num}名")
    return "".join(f"<span>{escape(item)}</span>" for item in items)


def pick_focus_value(hotel: HotelRecord, focus_label: str) -> float | None:
    if focus_label == "食事評価":
        return hotel.meal_average
    if focus_label == "風呂評価":
        return hotel.bath_average
    return hotel.review_average


def metric_badge(label: str, value: str) -> str:
    return f'<span class="metric-badge">{escape(label)} {escape(value)}</span>'


def write_sitemap(output_dir: Path, site_config: dict[str, object], topics: list[TopicConfig]) -> None:
    base_url = str(site_config["base_url"]).rstrip("/")
    urls = [f"{base_url}/"]
    urls.extend(f"{base_url}/posts/{topic.slug}/" for topic in topics)
    body = "\n".join(f"  <url><loc>{xml_escape(url)}</loc></url>" for url in urls)
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
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


def format_jp_date(value: datetime | object) -> str:
    year = getattr(value, "year")
    month = getattr(value, "month")
    day = getattr(value, "day")
    return f"{year}年{month}月{day}日"
