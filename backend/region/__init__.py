"""Korean 법정동코드 (행정표준코드) loader, hierarchy lookup, and API param converter."""

from backend.region.parser import (
    ParsedRegion,
    load_legal_dong_file,
    parse_legal_dong_row,
    parse_legal_dong_rows,
)
from backend.region.seed_data import SEED_LEGAL_DONG_ROWS
from backend.region.service import (
    ensure_regions_seeded,
    get_region_by_code,
    list_emd,
    list_sido,
    list_sigungu,
    load_regions_from_file,
    seed_regions,
    to_api_params,
    upsert_parsed_regions,
)

__all__ = [
    "ParsedRegion",
    "SEED_LEGAL_DONG_ROWS",
    "ensure_regions_seeded",
    "get_region_by_code",
    "list_emd",
    "list_sido",
    "list_sigungu",
    "load_legal_dong_file",
    "load_regions_from_file",
    "parse_legal_dong_row",
    "parse_legal_dong_rows",
    "seed_regions",
    "to_api_params",
    "upsert_parsed_regions",
]
