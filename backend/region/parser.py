"""Parser and file loader for Korean 법정동코드 (행정표준코드) TSV/CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ParsedRegion:
    """Normalized representation of a single active 법정동코드 entry."""

    code: str
    sido_cd: str
    sigungu_cd: str
    bjdong_cd: str
    sido_name: str
    sigungu_name: str | None
    emd_name: str | None
    is_active: bool = True


def _split_korean_region_name(code: str, full_name: str) -> tuple[str, str | None, str | None]:
    """Split full 법정동명 into (sido_name, sigungu_name, emd_name)."""
    parts = full_name.strip().split()
    if not parts:
        raise ValueError(f"Empty region name for code {code!r}")

    sido_cd = code[:2]
    bjdong_cd = code[5:10]
    sido_name = parts[0]

    # 시/도 level (e.g. 1100000000 서울특별시, 3611000000 세종특별자치시)
    if bjdong_cd == "00000" and (code[2:5] == "000" or code == "3611000000"):
        return sido_name, None, None

    # 시/군/구 level (e.g. 4113500000 경기도 성남시 분당구)
    if bjdong_cd == "00000":
        sigungu_name = " ".join(parts[1:]) if len(parts) > 1 else None
        return sido_name, sigungu_name, None

    # 읍/면/동/리 level
    if sido_cd == "36":
        # 세종특별자치시 has no separate 구: "세종특별자치시 반곡동"
        return sido_name, sido_name, " ".join(parts[1:]) if len(parts) > 1 else None

    # Handle 2-token sigungu like "성남시 분당구" vs 1-token like "강남구" or "가평군"
    if len(parts) >= 4 and parts[1].endswith("시") and parts[2].endswith("구"):
        sigungu_name = f"{parts[1]} {parts[2]}"
        emd_name = " ".join(parts[3:])
    elif len(parts) >= 3:
        sigungu_name = parts[1]
        emd_name = " ".join(parts[2:])
    elif len(parts) == 2:
        sigungu_name = None
        emd_name = parts[1]
    else:
        sigungu_name = None
        emd_name = None

    return sido_name, sigungu_name, emd_name


def parse_legal_dong_row(code: str, full_name: str, status: str) -> ParsedRegion | None:
    """Parse a single 법정동코드 row, returning None if abolished (폐지) or invalid."""
    clean_status = status.strip()
    if clean_status != "존재":
        return None

    clean_code = code.strip()
    if len(clean_code) != 10 or not clean_code.isdigit():
        return None

    sido_name, sigungu_name, emd_name = _split_korean_region_name(clean_code, full_name)
    return ParsedRegion(
        code=clean_code,
        sido_cd=clean_code[:2],
        sigungu_cd=clean_code[:5],
        bjdong_cd=clean_code[5:10],
        sido_name=sido_name,
        sigungu_name=sigungu_name,
        emd_name=emd_name,
        is_active=True,
    )


def parse_legal_dong_rows(rows: Iterable[tuple[str, str, str]]) -> list[ParsedRegion]:
    """Parse an iterable of (code, full_name, status) tuples, excluding 폐지 rows."""
    parsed: list[ParsedRegion] = []
    for code, full_name, status in rows:
        item = parse_legal_dong_row(code, full_name, status)
        if item is not None:
            parsed.append(item)
    return parsed


def _read_text_auto_encoding(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", raw, 0, len(raw), f"Unable to decode {path}")


def load_legal_dong_file(file_path: str | Path) -> list[ParsedRegion]:
    """Load and parse a full 법정동코드 TSV or CSV file, excluding abolished codes."""
    path = Path(file_path)
    text = _read_text_auto_encoding(path)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.reader(lines, delimiter=delimiter)

    rows: list[tuple[str, str, str]] = []
    for row in reader:
        if len(row) < 3:
            continue
        code_val, name_val, status_val = row[0].strip(), row[1].strip(), row[2].strip()
        # Skip header row (e.g. "법정동코드\t법정동명\t폐지여부")
        if not code_val.isdigit():
            continue
        rows.append((code_val, name_val, status_val))

    return parse_legal_dong_rows(rows)
