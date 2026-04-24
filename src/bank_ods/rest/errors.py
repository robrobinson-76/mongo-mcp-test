from typing import Any

from fastapi import HTTPException


def check(result: dict[str, Any]) -> dict[str, Any]:
    """Raise HTTPException for service-layer error envelopes."""
    if "error" not in result:
        return result
    code = result.get("code", "")
    status = 404 if code == "NOT_FOUND" else 500
    raise HTTPException(status_code=status, detail=result["error"])
