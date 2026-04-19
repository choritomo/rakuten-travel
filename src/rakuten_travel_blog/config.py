from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import TopicConfig


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_site_config(root: Path) -> dict[str, Any]:
    return load_json(root / "config" / "site.json")


def load_topics(root: Path) -> list[TopicConfig]:
    raw_topics = load_json(root / "config" / "topics.json")
    return [TopicConfig(**item) for item in raw_topics]
