"""Response normalization and field mapping for 건축HUB ArchPmsHubService."""

from datetime import date, datetime, timezone
from typing import Any, Optional

from backend.collector.exceptions import ApiResponseError, CollectorError
from shared.enums import BuildingStage


def _clean_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _clean_date_str(value: Any) -> Optional[str]:
    text = _clean_str(value)
    if text is None:
        return None
    digits = text.replace("-", "").replace(".", "")
    if len(digits) == 8 and digits.isdigit():
        return digits
    return None


def _to_float(value: Any) -> Optional[float]:
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    text = _clean_str(value)
    if text is None:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default


def normalize_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Extract (items, total_count) from a data.go.kr JSON response envelope."""
    if "OpenAPI_ServiceResponse" in payload and "response" not in payload:
        svc_err = payload.get("OpenAPI_ServiceResponse") or {}
        cmm = svc_err.get("cmmMsgHeader") or {}
        code = str(cmm.get("returnReasonCode") or "OPENAPI_ERROR")
        msg = str(cmm.get("returnAuthMsg") or cmm.get("errMsg") or "OpenAPI service error")
        raise ApiResponseError(code, msg)

    response = payload.get("response")
    if not isinstance(response, dict):
        raise CollectorError("Invalid API response: missing 'response' object.")

    header = response.get("header") or {}
    result_code = str(header.get("resultCode", ""))
    result_msg = str(header.get("resultMsg", ""))
    if result_code and result_code != "00":
        raise ApiResponseError(result_code, result_msg)

    body = response.get("body") or {}
    total_count = _to_int(body.get("totalCount"), default=0) or 0
    items_container = body.get("items")

    if not items_container or not isinstance(items_container, dict):
        return [], total_count

    raw_item = items_container.get("item")
    if raw_item is None or raw_item == "":
        return [], total_count
    if isinstance(raw_item, dict):
        return [raw_item], total_count
    if isinstance(raw_item, list):
        return [x for x in raw_item if isinstance(x, dict)], total_count

    raise CollectorError(f"Unexpected 'items.item' type: {type(raw_item).__name__}")


def infer_initial_stage(
    arch_pms_day: Optional[str],
    stcns_sched_day: Optional[str],
    real_stcns_day: Optional[str],
    use_apr_day: Optional[str],
    reference_date: Optional[date] = None,
) -> BuildingStage:
    """Determine initial BuildingStage from permit/construction/approval dates."""
    if use_apr_day:
        return BuildingStage.USE_APPROVED
    if real_stcns_day:
        ref = reference_date or datetime.now(timezone.utc).date()
        try:
            start_dt = datetime.strptime(real_stcns_day, "%Y%m%d").date()
            if (ref - start_dt).days >= 365:
                return BuildingStage.NEAR_COMPLETION
        except ValueError:
            pass
        return BuildingStage.UNDER_CONSTRUCTION
    if stcns_sched_day:
        return BuildingStage.START_SCHEDULED
    return BuildingStage.PERMITTED


def parse_ap_basis_item(
    item: dict[str, Any],
    reference_date: Optional[date] = None,
) -> dict[str, Any]:
    """Map one `getApBasisOulnInfo` JSON item to `Building` column values."""
    pk = _clean_str(item.get("mgmPmsrgstPk"))
    if not pk:
        raise CollectorError("Missing required field 'mgmPmsrgstPk' in API item.")

    sigungu_cd = _clean_str(item.get("sigunguCd")) or pk.split("-")[0][:5]
    bjdong_cd = _clean_str(item.get("bjdongCd")) or "00000"
    plat_plc = _clean_str(item.get("platPlc")) or _clean_str(item.get("newPlatPlc"))

    arch_pms_day = _clean_date_str(item.get("archPmsDay"))
    stcns_sched_day = _clean_date_str(item.get("stcnsSchedDay"))
    real_stcns_day = _clean_date_str(item.get("realStcnsDay"))
    use_apr_day = _clean_date_str(item.get("useAprDay"))

    return {
        "mgm_pmsrgst_pk": pk,
        "bld_rgst_pk": _clean_str(item.get("mgmBldrgstPk")),
        "sigungu_cd": sigungu_cd,
        "bjdong_cd": bjdong_cd,
        "plat_plc": plat_plc,
        "bld_nm": _clean_str(item.get("bldNm")),
        "main_purps_cd_nm": _clean_str(item.get("mainPurpsCdNm")),
        "tot_area": _to_float(item.get("totArea")),
        "hhld_cnt": _to_int(item.get("hhldCnt"), default=0),
        "dong_cnt": _to_int(item.get("dongCnt"), default=0),
        "arch_pms_day": arch_pms_day,
        "stcns_sched_day": stcns_sched_day,
        "real_stcns_day": real_stcns_day,
        "use_apr_day": use_apr_day,
        "stage": infer_initial_stage(
            arch_pms_day,
            stcns_sched_day,
            real_stcns_day,
            use_apr_day,
            reference_date=reference_date,
        ),
        "raw_json": item,
    }
