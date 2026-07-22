"""ChatGPT Codex usage and rate-limit reset-credit API client."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from . import auth

BASE_URL = "https://chatgpt.com/backend-api"
USAGE_URL = f"{BASE_URL}/wham/usage"
RESET_CREDITS_URL = f"{BASE_URL}/wham/rate-limit-reset-credits"


class ApiError(Exception):
    """Base API error."""


class UnauthorizedError(ApiError):
    """The access token was rejected."""


class ResponseError(ApiError):
    """The server response was not usable."""


@dataclass
class UsageWindow:
    used_percent: float
    reset_at: datetime
    window_seconds: int

    @property
    def remaining_percent(self) -> float:
        return max(0.0, min(100.0, 100.0 - self.used_percent))


@dataclass
class ResetCredit:
    id: str
    reset_type: str
    status: str
    title: Optional[str]
    description: Optional[str]
    expires_at: Optional[datetime]


@dataclass
class UsageData:
    weekly: UsageWindow
    plan_type: Optional[str] = None
    reset_credits: list[ResetCredit] = field(default_factory=list)
    available_reset_count: int = 0
    reset_credits_error: Optional[str] = None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _parse_window(value: Any) -> Optional[UsageWindow]:
    if not isinstance(value, dict):
        return None
    used = value.get("used_percent")
    reset_at = _parse_timestamp(value.get("reset_at"))
    seconds = value.get("limit_window_seconds")
    if isinstance(used, bool) or not isinstance(used, (int, float)):
        return None
    if reset_at is None or isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return None
    return UsageWindow(float(used), reset_at, int(seconds))


def parse_usage(data: Any) -> tuple[UsageWindow, Optional[str]]:
    if not isinstance(data, dict):
        raise ResponseError("Usage response is not an object.")
    rate_limit = data.get("rate_limit")
    if not isinstance(rate_limit, dict):
        raise ResponseError("Usage response has no rate_limit object.")
    primary = _parse_window(rate_limit.get("primary_window"))
    secondary = _parse_window(rate_limit.get("secondary_window"))
    candidates = [window for window in (primary, secondary) if window]
    if not candidates:
        raise ResponseError("Usage response has no valid rate-limit window.")
    weekly = max(candidates, key=lambda window: window.window_seconds)
    return weekly, data.get("plan_type") if isinstance(data.get("plan_type"), str) else None


def parse_reset_credits(data: Any) -> tuple[list[ResetCredit], int]:
    if not isinstance(data, dict):
        raise ResponseError("Reset-credit response is not an object.")
    raw_credits = data.get("credits") or []
    if not isinstance(raw_credits, list):
        raise ResponseError("Reset-credit list is invalid.")
    credits = []
    for value in raw_credits:
        if not isinstance(value, dict):
            continue
        credit_id = value.get("id")
        status = value.get("status")
        if not isinstance(credit_id, str) or not isinstance(status, str):
            continue
        credits.append(
            ResetCredit(
                id=credit_id,
                reset_type=str(value.get("reset_type") or "reset"),
                status=status,
                title=value.get("title") if isinstance(value.get("title"), str) else None,
                description=(
                    value.get("description") if isinstance(value.get("description"), str) else None
                ),
                expires_at=_parse_timestamp(value.get("expires_at")),
            )
        )
    default_count = sum(credit.status.lower() == "available" for credit in credits)
    count = data.get("available_count", default_count)
    if isinstance(count, bool) or not isinstance(count, (int, float)):
        count = default_count
    return credits, max(0, int(count))


def _get(
    url: str,
    credentials: auth.Credentials,
    extra_headers: Optional[dict[str, str]] = None,
    session: Optional[requests.Session] = None,
) -> Any:
    headers = {
        "Authorization": f"Bearer {credentials.access_token}",
        "Accept": "application/json",
        "User-Agent": "CodexMeter/1.0",
    }
    if credentials.account_id:
        headers["ChatGPT-Account-Id"] = credentials.account_id
    if extra_headers:
        headers.update(extra_headers)
    client = session or requests
    response = client.get(url, headers=headers, timeout=30)
    if response.status_code in (401, 403):
        raise UnauthorizedError(f"HTTP {response.status_code}")
    if not 200 <= response.status_code < 300:
        raise ResponseError(f"HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ResponseError("The API returned invalid JSON.") from exc


def fetch_usage(credentials: auth.Credentials, session: Optional[requests.Session] = None) -> UsageData:
    usage_payload = _get(USAGE_URL, credentials, session=session)
    weekly, plan_type = parse_usage(usage_payload)
    result = UsageData(weekly=weekly, plan_type=plan_type)
    try:
        credits_payload = _get(
            RESET_CREDITS_URL,
            credentials,
            extra_headers={"OpenAI-Beta": "codex-1", "originator": "Codex Desktop"},
            session=session,
        )
        result.reset_credits, result.available_reset_count = parse_reset_credits(credits_payload)
    except UnauthorizedError:
        raise
    except (ResponseError, requests.RequestException) as exc:
        result.reset_credits_error = str(exc)
    return result


def fetch_with_refresh(session: Optional[requests.Session] = None) -> UsageData:
    credentials = auth.valid_credentials()
    if credentials is None:
        raise UnauthorizedError("Not logged in.")
    try:
        return fetch_usage(credentials, session=session)
    except UnauthorizedError:
        credentials = auth.valid_credentials(force_refresh=True)
        if credentials is None:
            raise
        return fetch_usage(credentials, session=session)
