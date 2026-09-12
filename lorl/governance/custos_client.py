"""
LORL-9.1 CUSTOS-Core Client — Async client for CUSTOS governance evaluation.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

from datetime import datetime, timezone

import httpx
import jwt


import os

class CustosClient:
    """Async client for interacting with CUSTOS-Core governance evaluation service."""

    _DEV_DEFAULT_SECRET = "custos-secret-key-at-least-32-bytes-long!"

    def __init__(
        self,
        custos_url: str = "http://localhost:8000",
        jwt_secret: str | None = None,
        tenant_id: str = "default",
    ):
        self.custos_url = custos_url.rstrip("/")
        # Resolve from env first (LORL_CUSTOS_JWT_SECRET); dev fallback only.
        self.jwt_secret = jwt_secret or os.getenv("LORL_CUSTOS_JWT_SECRET", self._DEV_DEFAULT_SECRET)
        self.tenant_id = tenant_id

    def create_token(self) -> str:
        """Generate a JWT token signed with secret using HS256 algorithm."""
        # Security: JWT sub claim is bound to tenant_id to prevent cross-tenant access (fixes CUSTOS-CORE audit finding)
        payload = {
            "sub": self.tenant_id,
            "tenant_id": self.tenant_id,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    async def evaluate(self, content: str, client_id: str = "lorl") -> dict:
        """Submit content to CUSTOS /v1/evaluate endpoint for governance approval."""
        url = f"{self.custos_url}/v1/evaluate"
        token = self.create_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "client_id": client_id,
            "content": content,
            "tenant_id": self.tenant_id,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=5.0)
                if response.status_code == 200:
                    return response.json()
                return {
                    "allowed": False,
                    "reason": f"CUSTOS returned HTTP {response.status_code}",
                }
        except Exception:
            return {"allowed": False, "reason": "CUSTOS unavailable"}


def validate_production_secrets() -> None:
    """Fail closed: refuse to run in production with a dev-default JWT secret."""
    import os as _os
    if _os.getenv("CUSTOS_ENV", "development").lower() != "production":
        return
    secret = _os.getenv("LORL_CUSTOS_JWT_SECRET")
    if not secret or secret == CustosClient._DEV_DEFAULT_SECRET:
        raise RuntimeError(
            "LORL_CUSTOS_JWT_SECRET is unset or set to the dev default while "
            "CUSTOS_ENV=production. Set a strong unique secret (fail-closed)."
        )
