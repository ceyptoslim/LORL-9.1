"""
LORL-9.1 OPA Client — Async client for Open Policy Agent integration.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OPAClient:
    """Async client for querying OPA policy server."""

    def __init__(self, opa_url: str = "http://localhost:8181") -> None:
        self.opa_url = opa_url.rstrip("/")

    async def check_policy(self, input_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Query OPA policy endpoint and return (allowed, deny_messages).

        If OPA server is unavailable (connection error, timeout, HTTP error),
        fails open by returning (True, []) with a warning log.
        """
        url = f"{self.opa_url}/v1/data/lorl/governance/allow"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"input": input_data}, timeout=5.0)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("OPA policy server unavailable at %s (failing open): %s", url, exc)
            return True, []

        res = data.get("result")
        if isinstance(res, dict):
            allowed = bool(res.get("allow", False))
            deny_messages = list(res.get("deny") or res.get("deny_messages") or [])
        elif isinstance(res, bool):
            allowed = res
            deny_messages = list(data.get("deny") or data.get("deny_messages") or [])
        else:
            allowed = False
            deny_messages = list(data.get("deny") or data.get("deny_messages") or [])

        return allowed, deny_messages
