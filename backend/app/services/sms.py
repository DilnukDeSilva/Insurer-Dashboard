from __future__ import annotations

import re

import httpx

from app.config import settings

NOTIFY_LK_SEND_URL = "https://app.notify.lk/api/v1/send"


def _normalize_lk_phone(phone: str) -> str:
    """Notify.lk expects a bare international-format number (94771234567,
    no leading +) — accepts common local input shapes (0771234567,
    +94771234567, 771234567) and normalizes them to that."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0"):
        digits = "94" + digits[1:]
    elif len(digits) == 9:
        digits = "94" + digits
    return digits


async def send_sms(phone: str, message: str) -> None:
    """Sends a text via Notify.lk. Raises RuntimeError (caller turns this into
    an HTTP error) if SMS isn't configured or the provider rejects it —
    callers should never treat a failed send as if it silently succeeded."""
    if not settings.notify_lk_user_id or not settings.notify_lk_api_key:
        raise RuntimeError("SMS sending isn't configured on this server yet.")

    to = _normalize_lk_phone(phone)
    if len(to) != 11 or not to.startswith("94"):
        raise RuntimeError("That doesn't look like a valid Sri Lankan phone number.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                NOTIFY_LK_SEND_URL,
                params={
                    "user_id": settings.notify_lk_user_id,
                    "api_key": settings.notify_lk_api_key,
                    "sender_id": settings.notify_lk_sender_id,
                    "to": to,
                    "message": message,
                },
            )
    except httpx.RequestError as exc:
        raise RuntimeError("Could not reach the SMS provider.") from exc

    if response.status_code >= 400:
        raise RuntimeError(f"The SMS provider returned an error ({response.status_code}).")

    # Notify.lk's own docs disagree on the success shape — a plain empty 200
    # in one place, {"status": "success", "data": "Sent"} in another — so a
    # 2xx with no parseable/relevant body is treated as success, and only a
    # body that explicitly says otherwise is treated as a failure.
    try:
        data = response.json()
    except ValueError:
        return
    if isinstance(data, dict) and data.get("status") not in (None, "success"):
        raise RuntimeError(data.get("message") or "The SMS provider rejected the message.")
