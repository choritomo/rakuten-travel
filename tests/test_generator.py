from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rakuten_travel_blog.generator import determine_stay_dates, merge_records, normalize_hotel_record


class GeneratorTests(unittest.TestCase):
    def test_determine_next_saturday(self) -> None:
        checkin, checkout = determine_stay_dates(date(2026, 4, 19), "next_saturday")
        self.assertEqual(checkin.isoformat(), "2026-04-25")
        self.assertEqual(checkout.isoformat(), "2026-04-26")

    def test_normalize_nested_hotel_record(self) -> None:
        raw = [
            {
                "hotelBasicInfo": {
                    "hotelNo": 12345,
                    "hotelName": "テストホテル",
                    "reviewAverage": "4.4",
                    "reviewCount": "210",
                    "hotelMinCharge": "16800"
                }
            },
            {
                "hotelRatingInfo": {
                    "mealAverage": "4.6",
                    "bathAverage": "4.3"
                }
            },
            {
                "hotelDetailInfo": {
                    "access": "駅から徒歩5分",
                    "nearestStation": "テスト駅"
                }
            }
        ]
        record = normalize_hotel_record(raw, seed_rank=1)
        assert record is not None
        self.assertEqual(record.hotel_no, "12345")
        self.assertEqual(record.name, "テストホテル")
        self.assertEqual(record.nearest_station, "テスト駅")
        self.assertAlmostEqual(record.meal_average or 0, 4.6)
        self.assertEqual(record.min_charge, 16800)

    def test_merge_keeps_new_non_empty_values(self) -> None:
        base = normalize_hotel_record(
            {"hotelNo": 1, "hotelName": "Aホテル", "reviewAverage": 4.1},
            seed_rank=1,
        )
        update = normalize_hotel_record(
            {"hotelNo": 1, "hotelName": "Aホテル", "bathAverage": 4.7},
            seed_rank=1,
        )
        assert base is not None
        assert update is not None
        merged = merge_records(base, update)
        self.assertAlmostEqual(merged.review_average or 0, 4.1)
        self.assertAlmostEqual(merged.bath_average or 0, 4.7)


if __name__ == "__main__":
    unittest.main()
