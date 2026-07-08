"""
Authentication + authorization for the refund module.

This is a DELIBERATELY SIMPLE stand-in for a real identity system. In production the
bearer token would be a signed JWT / opaque token validated against an auth service,
and permissions/merchant-scope would come from that service. We model the *decisions*
(authenticated? has refund permission? merchant in scope?) so the business logic and
tests are realistic, without pulling in real infrastructure (anti-overengineering).
"""

from dataclasses import dataclass, field
from typing import List

from fastapi import Header, HTTPException, status


@dataclass
class User:
    user_id: str
    role: str
    permissions: List[str] = field(default_factory=list)
    merchant_scope: List[str] = field(default_factory=list)  # merchant_ids this user may act on

    def has_refund_permission(self) -> bool:
        return "refund:create" in self.permissions

    def can_access_merchant(self, merchant_id: str) -> bool:
        # "*" means all merchants (e.g. a super-admin). Otherwise must be in scope.
        return "*" in self.merchant_scope or merchant_id in self.merchant_scope


# Fake token table. Key = bearer token, value = the user it authenticates.
# Real system: replace this lookup with token validation against your auth provider.
_TOKENS = {
    "admin-token": User(
        user_id="ADMIN-1",
        role="admin",
        permissions=["refund:create"],
        merchant_scope=["MER-900"],           # scoped to merchant MER-900 only
    ),
    "superadmin-token": User(
        user_id="ADMIN-0",
        role="admin",
        permissions=["refund:create"],
        merchant_scope=["*"],                  # all merchants
    ),
    "support-noperm-token": User(
        user_id="SUPPORT-2",
        role="support",
        permissions=["transaction:read"],     # can view, but NOT refund
        merchant_scope=["MER-900"],
    ),
    "other-merchant-token": User(
        user_id="ADMIN-3",
        role="admin",
        permissions=["refund:create"],
        merchant_scope=["MER-111"],            # scoped to a DIFFERENT merchant
    ),
}


def get_current_user(authorization: str = Header(default=None)) -> User:
    """FastAPI dependency. Reads the `Authorization: Bearer <token>` header and returns
    the authenticated User, or raises 401. This runs BEFORE the endpoint body."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    token = authorization.split(" ", 1)[1].strip()
    user = _TOKENS.get(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user
