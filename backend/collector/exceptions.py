"""Custom exceptions for the 건축HUB collector."""


class CollectorError(Exception):
    """Base exception for collector failures."""


class DailyQuotaExceededError(CollectorError):
    """Raised when the daily data.go.kr API traffic limit is reached."""


class ApiResponseError(CollectorError):
    """Raised when the data.go.kr API returns a non-00 resultCode."""

    def __init__(self, result_code: str, result_msg: str) -> None:
        self.result_code = result_code
        self.result_msg = result_msg
        super().__init__(f"건축HUB API error [{result_code}]: {result_msg}")
