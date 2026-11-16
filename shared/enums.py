"""Shared domain enumerations for House-Telecom."""

from enum import Enum


class BuildingStage(str, Enum):
    """Lifecycle stage of a new/permitted building for telecom sales targeting."""

    PERMITTED = "PERMITTED"
    START_SCHEDULED = "START_SCHEDULED"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"
    NEAR_COMPLETION = "NEAR_COMPLETION"
    USE_APPROVED = "USE_APPROVED"

    @property
    def label_ko(self) -> str:
        return BUILDING_STAGE_LABELS[self]


BUILDING_STAGE_LABELS: dict[BuildingStage, str] = {
    BuildingStage.PERMITTED: "건축허가",
    BuildingStage.START_SCHEDULED: "착공예정",
    BuildingStage.UNDER_CONSTRUCTION: "착공진행",
    BuildingStage.NEAR_COMPLETION: "준공임박",
    BuildingStage.USE_APPROVED: "사용승인",
}


class ExclusionStatus(str, Enum):
    """Reason/category for excluding a building from active telecom sales targets."""

    TELECOM_DONE_FIELD = "TELECOM_DONE_FIELD"
    TELECOM_DONE_SYSTEM = "TELECOM_DONE_SYSTEM"
    NOT_TARGET = "NOT_TARGET"
    ON_HOLD = "ON_HOLD"

    @property
    def label_ko(self) -> str:
        return EXCLUSION_STATUS_LABELS[self]


EXCLUSION_STATUS_LABELS: dict[ExclusionStatus, str] = {
    ExclusionStatus.TELECOM_DONE_FIELD: "현장 개통완료",
    ExclusionStatus.TELECOM_DONE_SYSTEM: "자사 시스템 개통완료",
    ExclusionStatus.NOT_TARGET: "영업 비대상",
    ExclusionStatus.ON_HOLD: "보류",
}
