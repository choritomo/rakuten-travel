from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rakuten_travel_blog.config import load_json, load_site_config, load_topics
from rakuten_travel_blog.generator import build_live_articles
from rakuten_travel_blog.models import Article, HotelRecord
from rakuten_travel_blog.rakuten_api import RakutenTravelClient
from rakuten_travel_blog.runtime_env import load_env_file
from rakuten_travel_blog.site import build_site


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Rakuten Travel static site from live API data or bundled sample data."
    )
    parser.add_argument("--output-dir", default="dist", help="Output directory for the generated site.")
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Use bundled demo data instead of calling the Rakuten Travel API.",
    )
    return parser.parse_args()


def main() -> int:
    load_env_file(ROOT / ".env")
    args = parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    jst = timezone(timedelta(hours=9), name="JST")
    generated_at = datetime.now(jst)

    site_config = load_site_config(ROOT)
    site_config["base_url"] = os.getenv("SITE_BASE_URL", str(site_config["base_url"]))
    topics = load_topics(ROOT)

    build_mode = "sample" if args.sample_data else "live"
    topic_errors: dict[str, str] = {}
    build_notice: str | None = None

    if args.sample_data:
        articles = load_demo_articles(ROOT)
        build_notice = "この出力はサンプルデータです。本番の楽天データはまだ取得していません。"
    else:
        application_id = os.getenv("RAKUTEN_APPLICATION_ID", "").strip()
        access_key = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()
        affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()
        if not application_id or not access_key:
            print(
                json.dumps(
                    {
                        "error": "RAKUTEN_APPLICATION_ID と RAKUTEN_ACCESS_KEY が必要です。",
                        "hint": "ローカル確認だけなら --sample-data を付けてください。",
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2

        client = RakutenTravelClient(
            application_id=application_id,
            access_key=access_key,
            affiliate_id=affiliate_id or None,
        )
        articles, topic_errors = build_live_articles(
            topics=topics,
            client=client,
            today=generated_at.date(),
            generated_at=generated_at,
        )
        if not articles:
            hint = detect_rakuten_hint(topic_errors)
            print(
                json.dumps(
                    {
                        "error": "楽天APIから記事を生成できませんでした。",
                        "topic_errors": topic_errors,
                        "hint": hint,
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 3
        if topic_errors:
            build_notice = f"{len(topic_errors)}本のテーマで候補取得に失敗したため、未取得ページには案内文を表示しています。"

    build_site(
        root=ROOT,
        output_dir=output_dir,
        site_config=site_config,
        topics=topics,
        articles=articles,
        topic_errors=topic_errors,
        build_mode=build_mode,
        build_notice=build_notice,
        generated_at=generated_at,
    )

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "build_mode": build_mode,
                "article_count": len(articles),
                "topic_count": len(topics),
                "topic_errors": topic_errors,
            },
            ensure_ascii=False,
        )
    )
    return 0


def load_demo_articles(root: Path) -> list[Article]:
    raw_articles = load_json(root / "sample_data" / "demo_articles.json")
    articles: list[Article] = []
    for item in raw_articles:
        hotels = [HotelRecord(**hotel) for hotel in item["hotels"]]
        articles.append(
            Article(
                slug=item["slug"],
                title=item["title"],
                headline=item["headline"],
                description=item["description"],
                topic_description=item["topic_description"],
                checkin_date=datetime.fromisoformat(item["checkin_date"]).date(),
                checkout_date=datetime.fromisoformat(item["checkout_date"]).date(),
                adult_num=item["adult_num"],
                child_num=item["child_num"],
                focus_label=item["focus_label"],
                generated_at=datetime.fromisoformat(item["generated_at"]),
                hotels=hotels,
                notes=item["notes"],
            )
        )
    return articles


def detect_rakuten_hint(topic_errors: dict[str, str]) -> str | None:
    joined = "\n".join(topic_errors.values())
    if "REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING" in joined:
        return (
            "現在の楽天キーは Webアプリ用として扱われています。"
            "このPC実行型では API/バックエンドサービス の Application ID / Access Key を .env に入れてください。"
        )
    return None


if __name__ == "__main__":
    raise SystemExit(main())
