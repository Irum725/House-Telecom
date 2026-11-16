"""건축HUB 건축인허가정보 서비스 (`ArchPmsHubService`) collector client."""

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
from sqlalchemy.orm import Session

from backend.collector.cache import RawResponseCache
from backend.collector.exceptions import CollectorError
from backend.collector.parser import normalize_items, parse_ap_basis_item
from backend.collector.traffic import TrafficLimiter
from shared.models import Building, Region
from shared.schemas import BuildingSyncRequest, BuildingSyncResponse

ARCH_PMS_BASE_URL = "https://apis.data.go.kr/1613000/ArchPmsHubService"
GET_AP_BASIS_OP = "getApBasisOulnInfo"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ArchHubCollector:
    """Collector for 국토교통부 건축HUB 건축인허가정보 서비스."""

    def __init__(
        self,
        db: Session,
        service_key: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        cache: Optional[RawResponseCache] = None,
        traffic_limiter: Optional[TrafficLimiter] = None,
        max_retries: int = 3,
        base_backoff_seconds: float = 0.5,
        sleep_fn: Callable[[float], None] = time.sleep,
        fixtures_dir: Optional[Path] = None,
    ) -> None:
        self.db = db
        self.service_key = service_key if service_key is not None else os.getenv("DATA_GO_KR_SERVICE_KEY", "")
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(timeout=15.0)
        self.cache = cache or RawResponseCache()
        self.traffic = traffic_limiter or TrafficLimiter(db)
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self.sleep_fn = sleep_fn
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def _fetch_page_live(
        self,
        sigungu_cd: str,
        bjdong_cd: str,
        page_no: int,
        num_of_rows: int,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> tuple[dict[str, Any], int]:
        """Fetch one page from cache or live API with traffic tracking and exponential backoff."""
        if use_cache and not force_refresh:
            cached = self.cache.get(GET_AP_BASIS_OP, sigungu_cd, bjdong_cd, page_no, num_of_rows)
            if cached is not None:
                return cached, 0

        if not self.service_key:
            raise CollectorError(
                "DATA_GO_KR_SERVICE_KEY is not configured. Set the key or use use_fixture=True."
            )

        url = f"{ARCH_PMS_BASE_URL}/{GET_AP_BASIS_OP}"
        params: dict[str, Any] = {
            "serviceKey": self.service_key,
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd or "00000",
            "numOfRows": num_of_rows,
            "pageNo": page_no,
            "_type": "json",
        }

        api_calls_used = 0
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            self.traffic.consume(1)
            api_calls_used += 1
            try:
                resp = self.http_client.get(url, params=params)
                if resp.status_code in RETRYABLE_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                payload = resp.json()
                if use_cache:
                    self.cache.set(GET_AP_BASIS_OP, sigungu_cd, bjdong_cd, page_no, num_of_rows, payload)
                return payload, api_calls_used
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = exc
                is_retryable = isinstance(exc, httpx.RequestError) or (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code in RETRYABLE_STATUS_CODES
                )
                if not is_retryable or attempt >= self.max_retries:
                    break
                delay = self.base_backoff_seconds * (2**attempt)
                self.sleep_fn(delay)

        raise CollectorError(f"Failed to fetch page {page_no} after {self.max_retries + 1} attempts: {last_error}")

    def _load_fixture_pages(self, sigungu_cd: str, bjdong_cd: str) -> list[dict[str, Any]]:
        """Load recorded fixture pages for the requested sigungu/bjdong, or synthesize from template."""
        pattern = f"*{sigungu_cd}*page*.json"
        files = sorted(self.fixtures_dir.glob(pattern))
        is_synthesized = False
        if not files:
            files = sorted(self.fixtures_dir.glob("*41135*page*.json"))
            if not files:
                raise CollectorError(f"No fixture files found for sigungu_cd={sigungu_cd} in {self.fixtures_dir}")
            is_synthesized = True

        region_label = f"시군구({sigungu_cd})"
        default_bjdong = bjdong_cd if (bjdong_cd and bjdong_cd != "00000") else "10100"
        if is_synthesized:
            q = self.db.query(Region).filter(Region.sigungu_cd == sigungu_cd, Region.is_active.is_(True))
            if bjdong_cd and bjdong_cd != "00000":
                matched = q.filter(Region.bjdong_cd == bjdong_cd).first() or q.first()
            else:
                matched = q.filter(Region.bjdong_cd == "00000").first() or q.first()
            if matched:
                parts = [p for p in (matched.sido_name, matched.sigungu_name, matched.emd_name) if p]
                region_label = " ".join(parts)
                if (not bjdong_cd or bjdong_cd == "00000") and matched.bjdong_cd != "00000":
                    default_bjdong = matched.bjdong_cd

        pages: list[dict[str, Any]] = []
        item_seq = 1
        for path in files:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if is_synthesized:
                items, total = normalize_items(payload)
                adapted: list[dict[str, Any]] = []
                for it in items:
                    copy_it = dict(it)
                    orig_pk = str(copy_it.get("mgmPmsrgstPk", f"item-{item_seq}"))
                    suffix = orig_pk.split("-", 1)[1] if "-" in orig_pk else orig_pk
                    copy_it["mgmPmsrgstPk"] = f"{sigungu_cd}-{suffix}"
                    copy_it["sigunguCd"] = sigungu_cd
                    copy_it["bjdongCd"] = default_bjdong
                    copy_it["platPlc"] = f"{region_label} {100 + item_seq}번지"
                    if copy_it.get("bldNm"):
                        copy_it["bldNm"] = f"[{region_label.split()[-1]}] {copy_it['bldNm']}"
                    adapted.append(copy_it)
                    item_seq += 1
                payload = {
                    "response": {
                        "header": payload["response"]["header"],
                        "body": {
                            "items": {"item": adapted} if adapted else "",
                            "numOfRows": payload["response"]["body"].get("numOfRows", len(adapted)),
                            "pageNo": payload["response"]["body"].get("pageNo", 1),
                            "totalCount": total,
                        },
                    }
                }
            elif bjdong_cd and bjdong_cd != "00000":
                items, total = normalize_items(payload)
                filtered = [it for it in items if str(it.get("bjdongCd", "")) == bjdong_cd]
                payload = {
                    "response": {
                        "header": payload["response"]["header"],
                        "body": {
                            "items": {"item": filtered} if filtered else "",
                            "numOfRows": payload["response"]["body"].get("numOfRows", len(filtered)),
                            "pageNo": payload["response"]["body"].get("pageNo", 1),
                            "totalCount": len(filtered) if len(files) == 1 else total,
                        },
                    }
                }
            pages.append(payload)
        return pages

    def _upsert_building(self, mapped: dict[str, Any]) -> tuple[bool, bool]:
        """Upsert a parsed building dict into `buildings`. Returns (created, updated)."""
        pk = mapped["mgm_pmsrgst_pk"]
        existing = self.db.get(Building, pk)
        if existing is None:
            building = Building(**mapped)
            self.db.add(building)
            return True, False

        if existing.raw_json == mapped["raw_json"]:
            return False, False

        for key, value in mapped.items():
            if key != "mgm_pmsrgst_pk":
                setattr(existing, key, value)
        return False, True

    def _resolve_target_bjdongs(self, sigungu_cd: str, bjdong_cd: str) -> list[str]:
        """Resolve target bjdong_cd list; expands '00000' to known sub-dongs for live API."""
        if bjdong_cd and bjdong_cd != "00000":
            return [bjdong_cd]
        rows = (
            self.db.query(Region.bjdong_cd)
            .filter(
                Region.sigungu_cd == sigungu_cd,
                Region.is_active.is_(True),
                Region.bjdong_cd != "00000",
            )
            .distinct()
            .order_by(Region.bjdong_cd.asc())
            .all()
        )
        codes = [r[0] for r in rows if r[0]]
        return codes if codes else ["00000"]

    @staticmethod
    def _is_recent_new_construction(raw_item: dict[str, Any], min_date: str = "20230101") -> bool:
        """Filter live API items to recent (2023+) new construction permits."""
        arch_gb = str(raw_item.get("archGbCdNm") or "").strip()
        if arch_gb and "신축" not in arch_gb:
            return False
        for key in ("useAprDay", "realStcnsDay", "stcnsSchedDay", "archPmsDay"):
            val = str(raw_item.get(key) or "").strip()
            if len(val) == 8 and val.isdigit() and val >= min_date:
                return True
        return False

    def sync(
        self,
        request: BuildingSyncRequest,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> BuildingSyncResponse:
        """Collect buildings for a region (live API or fixture) and upsert into DB."""
        all_items: list[dict[str, Any]] = []
        api_calls_used = 0

        if request.use_fixture:
            pages = self._load_fixture_pages(request.sigungu_cd, request.bjdong_cd)
            if request.max_pages is not None:
                pages = pages[: request.max_pages]
            for payload in pages:
                items, _ = normalize_items(payload)
                all_items.extend(items)
        else:
            target_bjdongs = self._resolve_target_bjdongs(request.sigungu_cd, request.bjdong_cd)
            for target_bjdong in target_bjdongs:
                page_no = 1
                while True:
                    payload, calls = self._fetch_page_live(
                        sigungu_cd=request.sigungu_cd,
                        bjdong_cd=target_bjdong,
                        page_no=page_no,
                        num_of_rows=request.num_of_rows,
                        use_cache=use_cache,
                        force_refresh=force_refresh,
                    )
                    api_calls_used += calls
                    items, total_count = normalize_items(payload)
                    all_items.extend(it for it in items if self._is_recent_new_construction(it))

                    total_pages = max(1, math.ceil(total_count / request.num_of_rows)) if total_count > 0 else 1
                    if page_no >= total_pages:
                        break
                    if request.max_pages is not None and page_no >= request.max_pages:
                        break
                    page_no += 1

        created_count = 0
        updated_count = 0
        for raw_item in all_items:
            mapped = parse_ap_basis_item(raw_item)
            created, updated = self._upsert_building(mapped)
            if created:
                created_count += 1
            elif updated:
                updated_count += 1

        self.db.commit()
        remaining_quota = self.traffic.get_remaining_quota()

        return BuildingSyncResponse(
            sigungu_cd=request.sigungu_cd,
            bjdong_cd=request.bjdong_cd,
            fetched_count=len(all_items),
            created_count=created_count,
            updated_count=updated_count,
            api_calls_used=api_calls_used,
            remaining_daily_quota=remaining_quota,
        )


def sync_buildings(
    db: Session,
    request: BuildingSyncRequest,
    service_key: Optional[str] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> BuildingSyncResponse:
    """Convenience function to run a building sync and close the HTTP client."""
    collector = ArchHubCollector(db=db, service_key=service_key)
    try:
        return collector.sync(request, use_cache=use_cache, force_refresh=force_refresh)
    finally:
        collector.close()
