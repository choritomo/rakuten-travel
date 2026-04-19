from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class HotelRecord:
    hotel_no: str
    name: str
    area_name: str = ""
    address: str = ""
    access: str = ""
    nearest_station: str = ""
    special: str = ""
    review_average: float | None = None
    review_count: int | None = None
    meal_average: float | None = None
    bath_average: float | None = None
    room_average: float | None = None
    service_average: float | None = None
    min_charge: int | None = None
    room_charge: int | None = None
    hotel_information_url: str = ""
    plan_list_url: str = ""
    check_available_url: str = ""
    review_url: str = ""
    image_url: str = ""
    selection_reason: str = ""
    score: float = 0.0
    seed_rank: int | None = None
    raw: Any = field(default_factory=dict)

    @property
    def booking_url(self) -> str:
        return (
            self.hotel_information_url
            or self.plan_list_url
            or self.check_available_url
            or self.review_url
        )

    @property
    def displayed_charge(self) -> int | None:
        return self.room_charge or self.min_charge

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["booking_url"] = self.booking_url
        data["displayed_charge"] = self.displayed_charge
        return data


@dataclass
class TopicConfig:
    slug: str
    title_template: str
    headline: str
    description: str
    source: str
    ranking_genre: str | None = None
    keywords: list[str] = field(default_factory=list)
    focus_metric: str = "review_average"
    focus_label: str = "総合評価"
    focus_min: float = 0.0
    top_n: int = 3
    max_candidates: int = 8
    stay_strategy: str = "next_saturday"
    adult_num: int = 2
    child_num: int = 0
    squeeze_conditions: list[str] = field(default_factory=list)


@dataclass
class Article:
    slug: str
    title: str
    headline: str
    description: str
    topic_description: str
    checkin_date: date
    checkout_date: date
    adult_num: int
    child_num: int
    focus_label: str
    generated_at: datetime
    hotels: list[HotelRecord]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "headline": self.headline,
            "description": self.description,
            "topic_description": self.topic_description,
            "checkin_date": self.checkin_date.isoformat(),
            "checkout_date": self.checkout_date.isoformat(),
            "adult_num": self.adult_num,
            "child_num": self.child_num,
            "focus_label": self.focus_label,
            "generated_at": self.generated_at.isoformat(),
            "notes": list(self.notes),
            "hotels": [hotel.to_dict() for hotel in self.hotels],
        }
