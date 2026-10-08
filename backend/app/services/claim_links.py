from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pymongo.errors import DuplicateKeyError

from app.db.mongo import get_db

COLLECTION = "claim_links"

# No 0/O, 1/I/L — the code is read off an SMS and sometimes retyped by hand.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
# The lookup endpoint is public and returns a NIC + plate, so the code has to
# be unguessable, not just short: 31^8 ≈ 8.5e11 possibilities.
CODE_LENGTH = 8

_indexes_ready = False


async def _ensure_indexes() -> None:
    # Created lazily on first write rather than at app startup, so an
    # unreachable MongoDB can't block the whole API from booting.
    global _indexes_ready
    if _indexes_ready:
        return
    collection = get_db()[COLLECTION]
    await collection.create_index("code", unique=True)
    # TTL index: MongoDB deletes expired links on its own (within ~60s of
    # expiry) — resolve_short_link still checks expires_at itself for that gap.
    await collection.create_index("expires_at", expireAfterSeconds=0)
    _indexes_ready = True


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


async def create_short_link(data: Dict[str, Any], expire_hours: int) -> str:
    await _ensure_indexes()
    collection = get_db()[COLLECTION]
    now = datetime.now(timezone.utc)
    for _ in range(5):
        code = _new_code()
        try:
            await collection.insert_one(
                {
                    **data,
                    "code": code,
                    "created_at": now,
                    "expires_at": now + timedelta(hours=expire_hours),
                }
            )
            return code
        except DuplicateKeyError:
            continue
    raise RuntimeError("Could not generate a unique claim-link code.")


async def resolve_short_link(code: str) -> Optional[Dict[str, Any]]:
    doc = await get_db()[COLLECTION].find_one({"code": code.strip().upper()})
    if not doc:
        return None
    expires_at = doc["expires_at"]
    if expires_at.tzinfo is None:
        # Motor returns naive datetimes (stored as UTC) unless tz_aware is set.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        return None
    return doc
