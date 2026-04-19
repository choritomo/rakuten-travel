from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class RakutenAPIError(RuntimeError):
    message: str
    status: int | None = None
    error: str | None = None
    description: str | None = None

    def __str__(self) -> str:
        detail = self.description or self.message
        if self.status:
            return f"{self.status}: {detail}"
        return detail


class RakutenTravelClient:
    BASE_URLS = {
        "ranking": "https://openapi.rakuten.co.jp/engine/api/Travel/HotelRanking/20170426",
        "keyword": "https://openapi.rakuten.co.jp/engine/api/Travel/KeywordHotelSearch/20170426",
        "detail": "https://openapi.rakuten.co.jp/engine/api/Travel/HotelDetailSearch/20170426",
        "vacant": "https://openapi.rakuten.co.jp/engine/api/Travel/VacantHotelSearch/20170426",
    }

    def __init__(
        self,
        application_id: str,
        access_key: str,
        affiliate_id: str | None = None,
        pause_seconds: float = 0.4,
    ) -> None:
        self.application_id = application_id
        self.access_key = access_key
        self.affiliate_id = affiliate_id
        self.pause_seconds = pause_seconds

    def hotel_ranking(self, genre: str) -> dict[str, Any]:
        return self._request(
            "ranking",
            {
                "carrier": 0,
                "genre": genre,
            },
        )

    def keyword_hotel_search(self, keyword: str, hits: int = 10) -> dict[str, Any]:
        return self._request(
            "keyword",
            {
                "carrier": 0,
                "keyword": keyword,
                "hits": hits,
            },
        )

    def hotel_detail_search(self, hotel_no: str) -> dict[str, Any]:
        return self._request(
            "detail",
            {
                "carrier": 0,
                "hotelNo": hotel_no,
            },
        )

    def vacant_hotel_search(
        self,
        hotel_no: str,
        checkin_date: date,
        checkout_date: date,
        adult_num: int = 2,
        child_num: int = 0,
        squeeze_conditions: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "carrier": 0,
            "hotelNo": hotel_no,
            "checkinDate": checkin_date.isoformat(),
            "checkoutDate": checkout_date.isoformat(),
            "adultNum": adult_num,
            "responseType": "large",
            "sort": "+roomCharge",
        }
        if child_num:
            params["childNum"] = child_num
        if squeeze_conditions:
            params["squeezeCondition"] = ",".join(squeeze_conditions)
        return self._request("vacant", params)

    def _request(self, api_name: str, params: dict[str, Any]) -> dict[str, Any]:
        url = self.BASE_URLS[api_name]
        query: dict[str, Any] = {
            "applicationId": self.application_id,
            "accessKey": self.access_key,
            "format": "json",
            "formatVersion": 2,
            **params,
        }
        if self.affiliate_id:
            query["affiliateId"] = self.affiliate_id

        query_string = urlencode(query)
        request = Request(
            f"{url}?{query_string}",
            headers={
                "User-Agent": "rakuten-travel-auto-blog/1.0",
            },
        )

        last_error: RakutenAPIError | None = None
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                time.sleep(self.pause_seconds)
                return payload
            except HTTPError as exc:
                error = self._parse_http_error(exc)
                last_error = error
                if exc.code == 429 and attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise error
            except URLError as exc:
                last_error = RakutenAPIError(f"Network error: {exc.reason}")
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise last_error

        raise last_error or RakutenAPIError("Unknown Rakuten API error")

    @staticmethod
    def _parse_http_error(exc: HTTPError) -> RakutenAPIError:
        raw_body = exc.read().decode("utf-8", errors="replace")
        error = None
        description = raw_body.strip()
        try:
            payload = json.loads(raw_body)
            error = payload.get("error")
            description = payload.get("error_description", description)
        except json.JSONDecodeError:
            pass
        return RakutenAPIError(
            message=f"Rakuten API request failed with status {exc.code}",
            status=exc.code,
            error=error,
            description=description,
        )
