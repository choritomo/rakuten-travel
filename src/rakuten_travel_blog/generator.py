from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .models import Article, HotelRecord, TopicConfig
from .rakuten_api import RakutenAPIError, RakutenTravelClient


def build_live_articles(
    topics: list[TopicConfig],
    client: RakutenTravelClient,
    today: date,
    generated_at: datetime,
) -> list[Article]:
    articles: list[Article] = []
    for topic in topics:
        article = build_article_for_topic(topic, client, today, generated_at)
        if article:
            articles.append(article)
    return articles


def build_article_for_topic(
    topic: TopicConfig,
    client: RakutenTravelClient,
    today: date,
    generated_at: datetime,
) -> Article | None:
    checkin_date, checkout_date = determine_stay_dates(today, topic.stay_strategy)
    seed_nodes = fetch_seed_nodes(topic, client)
    selected: list[HotelRecord] = []

    for seed_rank, raw_hotel in enumerate(seed_nodes, start=1):
        seed_record = normalize_hotel_record(raw_hotel, seed_rank=seed_rank)
        if not seed_record or not seed_record.hotel_no:
            continue

        record = seed_record

        try:
            detail_payload = client.hotel_detail_search(seed_record.hotel_no)
            detail_nodes = extract_hotel_nodes(detail_payload)
            if detail_nodes:
                record = merge_records(
                    record,
                    normalize_hotel_record(detail_nodes[0], seed_rank=seed_rank),
                )
        except RakutenAPIError:
            pass

        try:
            vacant_payload = client.vacant_hotel_search(
                hotel_no=seed_record.hotel_no,
                checkin_date=checkin_date,
                checkout_date=checkout_date,
                adult_num=topic.adult_num,
                child_num=topic.child_num,
                squeeze_conditions=topic.squeeze_conditions,
            )
        except RakutenAPIError as exc:
            if exc.status == 404 or exc.error == "not_found":
                continue
            continue

        vacant_nodes = extract_hotel_nodes(vacant_payload)
        if not vacant_nodes:
            continue

        record = merge_records(
            record,
            normalize_hotel_record(vacant_nodes[0], seed_rank=seed_rank),
        )
        if not record.booking_url:
            continue

        record.score = compute_topic_score(record, topic)
        record.selection_reason = build_selection_reason(record, topic, checkin_date)
        selected.append(record)

    if not selected:
        return None

    selected.sort(key=lambda item: (-item.score, item.displayed_charge or 999999))
    hotels = selected[: topic.top_n]
    title = topic.title_template.format(
        month=checkin_date.month,
        month_label=f"{checkin_date.month}月",
        checkin_date=checkin_date.isoformat(),
        checkout_date=checkout_date.isoformat(),
        checkin_md=f"{checkin_date.month}/{checkin_date.day}",
    )
    description = (
        f"{checkin_date.month}/{checkin_date.day}チェックインで空室を確認できた"
        f"{topic.headline}を、楽天トラベルAPIの最新データから毎日更新しています。"
    )
    notes = [
        f"空室と料金は {generated_at.strftime('%Y-%m-%d %H:%M')} JST 時点のAPI結果です。",
        "予約前に楽天トラベル側の最新情報を必ず確認してください。",
        "本ページはアフィリエイト広告を利用しています。",
    ]

    return Article(
        slug=topic.slug,
        title=title,
        headline=topic.headline,
        description=description,
        topic_description=topic.description,
        checkin_date=checkin_date,
        checkout_date=checkout_date,
        adult_num=topic.adult_num,
        child_num=topic.child_num,
        focus_label=topic.focus_label,
        generated_at=generated_at,
        hotels=hotels,
        notes=notes,
    )


def fetch_seed_nodes(topic: TopicConfig, client: RakutenTravelClient) -> list[Any]:
    if topic.source == "ranking":
        payload = client.hotel_ranking(topic.ranking_genre or "all")
        rankings = extract_ranking_nodes(payload)
        hotels: list[Any] = []
        for ranking in rankings:
            genre = str(find_first_value(ranking, "genre") or "")
            if topic.ranking_genre and genre and genre != topic.ranking_genre:
                continue
            hotels.extend(extract_hotel_nodes(ranking))
            if hotels:
                break
        return unique_seed_nodes(hotels, topic.max_candidates)

    if topic.source == "keyword":
        hotels = []
        for keyword in topic.keywords:
            payload = client.keyword_hotel_search(keyword, hits=min(topic.max_candidates, 10))
            hotels.extend(extract_hotel_nodes(payload))
        return unique_seed_nodes(hotels, topic.max_candidates)

    raise ValueError(f"Unsupported topic source: {topic.source}")


def determine_stay_dates(today: date, stay_strategy: str) -> tuple[date, date]:
    weekdays = {
        "next_friday": 4,
        "next_saturday": 5,
    }
    target_weekday = weekdays.get(stay_strategy, 5)
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    checkin_date = today + timedelta(days=days_ahead)
    checkout_date = checkin_date + timedelta(days=1)
    return checkin_date, checkout_date


def unique_seed_nodes(nodes: list[Any], max_items: int) -> list[Any]:
    seen: set[str] = set()
    unique_nodes: list[Any] = []
    for node in nodes:
        hotel_no = str(find_first_value(node, "hotelNo") or "").strip()
        if not hotel_no or hotel_no in seen:
            continue
        seen.add(hotel_no)
        unique_nodes.append(node)
        if len(unique_nodes) >= max_items:
            break
    return unique_nodes


def extract_ranking_nodes(payload: Any) -> list[Any]:
    rankings: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            lowered = {key.lower() for key in node}
            if "genre" in lowered and "hotels" in lowered:
                rankings.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return rankings


def extract_hotel_nodes(payload: Any) -> list[Any]:
    hotels: list[Any] = []

    def walk(node: Any) -> None:
        if is_hotel_wrapper(node):
            hotels.append(node)
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return hotels


def is_hotel_wrapper(node: Any) -> bool:
    if isinstance(node, list):
        return any(
            isinstance(item, dict)
            and any(
                key in item
                for key in (
                    "hotelBasicInfo",
                    "hotelRatingInfo",
                    "hotelDetailInfo",
                    "hotelFacilitiesInfo",
                )
            )
            for item in node
        )

    if isinstance(node, dict):
        if any(
            key in node
            for key in (
                "hotelBasicInfo",
                "hotelRatingInfo",
                "hotelDetailInfo",
                "hotelFacilitiesInfo",
            )
        ):
            return True
        keys = {key.lower() for key in node}
        return "hotelno" in keys and "hotelname" in keys

    return False


def normalize_hotel_record(raw_hotel: Any, seed_rank: int | None = None) -> HotelRecord | None:
    hotel_no = str(find_first_value(raw_hotel, "hotelNo") or "").strip()
    hotel_name = collapse_whitespace(str(find_first_value(raw_hotel, "hotelName") or ""))
    if not hotel_no or not hotel_name:
        return None

    address = " ".join(
        part
        for part in (
            collapse_whitespace(str(find_first_value(raw_hotel, "address1") or "")),
            collapse_whitespace(str(find_first_value(raw_hotel, "address2") or "")),
        )
        if part
    ).strip()

    room_charges = [value for value in map(coerce_int, find_all_values(raw_hotel, "roomCharge")) if value]

    return HotelRecord(
        hotel_no=hotel_no,
        name=hotel_name,
        area_name=collapse_whitespace(
            str(find_first_value(raw_hotel, "areaName", "middleClassName") or "")
        ),
        address=address,
        access=collapse_whitespace(str(find_first_value(raw_hotel, "access") or "")),
        nearest_station=collapse_whitespace(str(find_first_value(raw_hotel, "nearestStation") or "")),
        special=shorten_text(
            collapse_whitespace(
                str(find_first_value(raw_hotel, "hotelSpecial", "userReview", "otherInformation") or "")
            ),
            150,
        ),
        review_average=coerce_float(find_first_value(raw_hotel, "reviewAverage")),
        review_count=coerce_int(find_first_value(raw_hotel, "reviewCount")),
        meal_average=coerce_float(find_first_value(raw_hotel, "mealAverage")),
        bath_average=coerce_float(find_first_value(raw_hotel, "bathAverage")),
        room_average=coerce_float(find_first_value(raw_hotel, "roomAverage")),
        service_average=coerce_float(find_first_value(raw_hotel, "serviceAverage")),
        min_charge=coerce_int(find_first_value(raw_hotel, "hotelMinCharge")),
        room_charge=min(room_charges) if room_charges else None,
        hotel_information_url=str(find_first_value(raw_hotel, "hotelInformationUrl") or ""),
        plan_list_url=str(find_first_value(raw_hotel, "planListUrl") or ""),
        check_available_url=str(find_first_value(raw_hotel, "checkAvailableUrl") or ""),
        review_url=str(find_first_value(raw_hotel, "reviewUrl") or ""),
        image_url=str(
            find_first_value(
                raw_hotel,
                "hotelImageUrl",
                "hotelThumbnailUrl",
                "roomImageUrl",
                "roomThumbnailUrl",
            )
            or ""
        ),
        seed_rank=seed_rank,
        raw=raw_hotel,
    )


def merge_records(base: HotelRecord | None, update: HotelRecord | None) -> HotelRecord:
    if base is None and update is None:
        raise ValueError("Cannot merge two empty hotel records")
    if base is None:
        return update  # type: ignore[return-value]
    if update is None:
        return base

    values: dict[str, Any] = {}
    for field_name in HotelRecord.__dataclass_fields__:
        base_value = getattr(base, field_name)
        update_value = getattr(update, field_name)
        if field_name == "raw":
            values[field_name] = update_value or base_value
            continue
        if field_name == "score":
            values[field_name] = update_value or base_value
            continue
        values[field_name] = update_value if is_present(update_value) else base_value
    return HotelRecord(**values)


def compute_topic_score(record: HotelRecord, topic: TopicConfig) -> float:
    focus_value = getattr(record, topic.focus_metric, None) or 0.0
    review_average = record.review_average or 0.0
    review_count = record.review_count or 0
    displayed_charge = record.displayed_charge or 25000
    seed_rank = record.seed_rank or topic.max_candidates

    score = 0.0
    score += max(0, 12 - seed_rank) * 2.5
    score += review_average * 8.0
    score += focus_value * 10.0
    score += min(review_count, 400) / 30.0
    score += max(0, 25000 - min(displayed_charge, 25000)) / 2500.0

    if topic.focus_min and focus_value < topic.focus_min:
        score -= 12.0

    if topic.source == "keyword":
        haystack = f"{record.name} {record.special} {record.area_name}"
        for keyword in topic.keywords:
            if keyword and keyword in haystack:
                score += 2.0

    return round(score, 2)


def build_selection_reason(record: HotelRecord, topic: TopicConfig, checkin_date: date) -> str:
    parts: list[str] = []
    focus_value = getattr(record, topic.focus_metric, None)
    if focus_value is not None:
        parts.append(f"{topic.focus_label}{focus_value:.1f}")
    if record.review_average is not None and topic.focus_metric != "review_average":
        parts.append(f"総合{record.review_average:.1f}")
    if record.review_count:
        parts.append(f"口コミ{record.review_count}件")
    if record.displayed_charge:
        parts.append(f"{checkin_date.month}/{checkin_date.day}時点で{record.displayed_charge:,}円前後から")
    if record.nearest_station:
        parts.append(f"{record.nearest_station}アクセス")
    return " / ".join(parts[:4]) or "空室確認が取れた宿です。"


def find_first_value(node: Any, *keys: str) -> Any:
    lowered = {key.lower() for key in keys}

    def walk(item: Any) -> Any:
        if isinstance(item, dict):
            for key, value in item.items():
                if key.lower() in lowered and is_present(value):
                    return value
            for value in item.values():
                found = walk(value)
                if is_present(found):
                    return found
        elif isinstance(item, list):
            for child in item:
                found = walk(child)
                if is_present(found):
                    return found
        return None

    return walk(node)


def find_all_values(node: Any, key_name: str) -> list[Any]:
    values: list[Any] = []
    lowered = key_name.lower()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, value in item.items():
                if key.lower() == lowered and is_present(value):
                    values.append(value)
                walk(value)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(node)
    return values


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def shorten_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def coerce_float(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def coerce_int(value: Any) -> int | None:
    if value in (None, "", [], {}):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except ValueError:
        return None


def is_present(value: Any) -> bool:
    return value not in (None, "", [], {})
