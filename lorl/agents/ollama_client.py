"""
LORL-9.1 Ollama Client — Async HTTP client for Ollama/Llama3 local inference.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async HTTP client for local Ollama/Llama3 inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self, prompt: str, model: Optional[str] = None
    ) -> Optional[str]:
        """Call Ollama /api/generate endpoint with prompt.

        Returns text response string if successful, or None on error or fallback.
        """
        target_model = model or self.model
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response")
        except Exception as e:
            logger.warning("Ollama generation failed: %s", e)
            return None
