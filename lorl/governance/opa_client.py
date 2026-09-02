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
    """Async client for querying OPA policy server.

    Fail-closed semantics (v0.2.0+): if OPA is unavailable, returns a DENY
    decision. This aligns LORL-9.1 with CUSTOS-CORE's enforcement model:
    no authoritative policy decision → no governed execution.
    """

    def __init__(self, opa_url: str = "http://localhost:8181") -> None:
        self.opa_url = opa_url.rstrip("/")

    async def check_policy(self, input_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Query OPA policy endpoint and return (allowed, deny_messages).

        Fail-closed: if OPA server is unavailable (connection error, timeout,
        HTTP error), returns (False, ["OPA policy server unavailable"]) with
        a warning log. This ensures no governed action proceeds without an
        authoritative policy decision.
        """
        url = f"{self.opa_url}/v1/data/lorl/governance/allow"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"input": input_data}, timeout=5.0)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("OPA policy server unavailable at %s (failing closed): %s", url, exc)
            return False, ["OPA policy server unavailable"]

        res = data.get("result")
        if isinstance(res, dict):
            allowed = bool(res.get("allow", False))
            deny_messages = list(res.get("deny") or res.get("deny_messages") or [])
        elif isinstance(res, bool):
            allowed = res
            deny_messages = list(data.get("deny") or data.get("deny_messages") or [])
        else:
            # Malformed response — fail closed
            logger.warning("OPA returned malformed response: %s", data)
            return False, ["OPA returned malformed response"]

        return allowed, deny_messages
