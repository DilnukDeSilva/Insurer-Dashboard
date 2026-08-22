from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

TABLE = "insurance_companies"


def _headers() -> Dict[str, str]:
    return {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base() -> str:
    return f"{settings.supabase_url}/rest/v1"


async def sb_get(table: str, params: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{_base()}/{table}", headers=_headers(), params=params or {})
        r.raise_for_status()
        return r.json()


async def sb_post(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{_base()}/{table}", headers=_headers(), json=data)
        r.raise_for_status()
        result = r.json()
        return result[0] if isinstance(result, list) else result


async def sb_patch(table: str, match_col: str, match_val: str, data: Dict[str, Any]) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.patch(
            f"{_base()}/{table}",
            headers=_headers(),
            json=data,
            params={match_col: f"eq.{match_val}"},
        )
        r.raise_for_status()
