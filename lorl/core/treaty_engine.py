"""
LORL-9.1 Treaty Engine — State machine for inter-lab collaboration agreements.

Treaties are formal agreements between labs that define terms for resource
sharing, revenue splits, data access, and governance rules. The engine
manages the full lifecycle: propose → accept/reject → active → expired.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class TreatyStatus(str, Enum):
    """States in the treaty lifecycle."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TreatyTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_status: TreatyStatus, attempted_action: str):
        super().__init__(
            f"Cannot {attempted_action} a treaty in '{current_status.value}' state"
        )
        self.current_status = current_status
        self.attempted_action = attempted_action


@dataclass
class Treaty:
    """A formal agreement between two labs."""

    treaty_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    proposer_id: str = ""
    responder_id: str = ""
    terms: dict = field(default_factory=dict)
    status: TreatyStatus = TreatyStatus.PROPOSED
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    accepted_at: Optional[str] = None
    rejected_at: Optional[str] = None
    expires_at: Optional[str] = None

    # Valid transitions from each status
    _VALID_TRANSITIONS = {
        TreatyStatus.PROPOSED: {TreatyStatus.ACCEPTED, TreatyStatus.REJECTED, TreatyStatus.CANCELLED},
        TreatyStatus.ACCEPTED: {TreatyStatus.EXPIRED, TreatyStatus.CANCELLED},
        TreatyStatus.REJECTED: set(),
        TreatyStatus.EXPIRED: set(),
        TreatyStatus.CANCELLED: set(),
    }

    def can_transition_to(self, new_status: TreatyStatus) -> bool:
        """Check if a transition is valid."""
        return new_status in self._VALID_TRANSITIONS.get(self.status, set())

    def to_dict(self) -> dict:
        """Serialize treaty to dict."""
        return {
            "treaty_id": self.treaty_id,
            "title": self.title,
            "proposer_id": self.proposer_id,
            "responder_id": self.responder_id,
            "terms": self.terms,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "accepted_at": self.accepted_at,
            "rejected_at": self.rejected_at,
            "expires_at": self.expires_at,
        }


class TreatyEngine:
    """
    Manages the treaty lifecycle — propose, accept, reject, expire, cancel.

    Each operation validates the state transition and returns the updated treaty.
    The engine is stateless between calls (treaties are passed in and returned).
    """

    def propose(
        self,
        title: str,
        proposer_id: str,
        responder_id: str,
        terms: dict,
    ) -> Treaty:
        """Create a new treaty proposal."""
        if not title:
            raise ValueError("Treaty title is required")
        if not proposer_id or not responder_id:
            raise ValueError("Both proposer_id and responder_id are required")
        if proposer_id == responder_id:
            raise ValueError("Proposer and responder cannot be the same lab")
        if not terms:
            raise ValueError("Treaty terms are required")

        return Treaty(
            title=title,
            proposer_id=proposer_id,
            responder_id=responder_id,
            terms=terms,
            status=TreatyStatus.PROPOSED,
        )

    def accept(self, treaty: Treaty, responder_id: str) -> Treaty:
        """Accept a proposed treaty. Only the responder can accept."""
        if treaty.status != TreatyStatus.PROPOSED:
            raise TreatyTransitionError(treaty.status, "accept")

        if responder_id != treaty.responder_id:
            raise ValueError(
                f"Only responder '{treaty.responder_id}' can accept this treaty, "
                f"not '{responder_id}'"
            )

        treaty.status = TreatyStatus.ACCEPTED
        treaty.accepted_at = datetime.now(timezone.utc).isoformat()
        treaty.updated_at = treaty.accepted_at
        return treaty

    def reject(self, treaty: Treaty, responder_id: str) -> Treaty:
        """Reject a proposed treaty. Only the responder can reject."""
        if treaty.status != TreatyStatus.PROPOSED:
            raise TreatyTransitionError(treaty.status, "reject")

        if responder_id != treaty.responder_id:
            raise ValueError(
                f"Only responder '{treaty.responder_id}' can reject this treaty"
            )

        treaty.status = TreatyStatus.REJECTED
        treaty.rejected_at = datetime.now(timezone.utc).isoformat()
        treaty.updated_at = treaty.rejected_at
        return treaty

    def expire(self, treaty: Treaty) -> Treaty:
        """Expire an accepted treaty (e.g., after the terms duration ends)."""
        if treaty.status != TreatyStatus.ACCEPTED:
            raise TreatyTransitionError(treaty.status, "expire")

        treaty.status = TreatyStatus.EXPIRED
        treaty.updated_at = datetime.now(timezone.utc).isoformat()
        return treaty

    def cancel(self, treaty: Treaty, requesting_id: str) -> Treaty:
        """Cancel a proposed or accepted treaty. Either party can cancel."""
        if treaty.status not in (TreatyStatus.PROPOSED, TreatyStatus.ACCEPTED):
            raise TreatyTransitionError(treaty.status, "cancel")

        if requesting_id not in (treaty.proposer_id, treaty.responder_id):
            raise ValueError(
                "Only the proposer or responder can cancel a treaty"
            )

        treaty.status = TreatyStatus.CANCELLED
        treaty.updated_at = datetime.now(timezone.utc).isoformat()
        return treaty

    def get_status(self, treaty: Treaty) -> TreatyStatus:
        """Get the current status of a treaty."""
        return treaty.status
