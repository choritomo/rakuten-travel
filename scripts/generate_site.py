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
from rakuten_travel_blog.models import Article, HotelRecord
from rakuten_travel_blog.site import build_site


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the static GitHub Pages shell for the Rakuten Travel site.")
    parser.add_argument("--output-dir", default="dist", help="Output directory for the static site.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = (ROOT / args.output_dir).resolve()
    jst = timezone(timedelta(hours=9), name="JST")
    generated_at = datetime.now(jst)

    site_config = load_site_config(ROOT)
    site_config["base_url"] = os.getenv("SITE_BASE_URL", str(site_config["base_url"]))

    topics = load_topics(ROOT)
    demo_articles = load_demo_articles(ROOT)
    runtime_config = {
        "applicationId": os.getenv("RAKUTEN_APPLICATION_ID", ""),
        "accessKey": os.getenv("RAKUTEN_ACCESS_KEY", ""),
        "affiliateId": os.getenv("RAKUTEN_AFFILIATE_ID", ""),
    }
    runtime_config["is_configured"] = bool(runtime_config["applicationId"] and runtime_config["accessKey"])

    build_site(
        ROOT,
        output_dir,
        site_config,
        topics,
        demo_articles,
        runtime_config,
        generated_at,
    )

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "runtime_configured": runtime_config["is_configured"],
                "topic_count": len(topics),
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


if __name__ == "__main__":
    raise SystemExit(main())
