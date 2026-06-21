"""Shared FastAPI dependencies: DB session, current user, org context, RBAC."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from refle_core.db import session_scope
from refle_core.models import Membership, Organization, Role, User
from refle_core.security import decode_access_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from refle_api.cookies import COOKIE_NAME


async def get_session() -> AsyncIterator[AsyncSession]:
    async for session in session_scope():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Bearer is optional: the browser uses the httpOnly cookie, API clients use the header.
_bearer = HTTPBearer(auto_error=False)
_CredsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


@dataclass
class AuthContext:
    """The authenticated user plus their active organization + membership."""

    user: User
    organization: Organization
    membership: Membership

    @property
    def role(self) -> Role:
        return self.membership.role


def _extract_token(request: Request, creds: HTTPAuthorizationCredentials | None) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token and creds is not None:
        token = creds.credentials
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return token


async def get_auth_context(
    request: Request, session: SessionDep, creds: _CredsDep = None
) -> AuthContext:
    try:
        claims = decode_access_token(_extract_token(request, creds))
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        ) from exc

    user_id = claims.get("sub")
    org_id = claims.get("org_id")
    if not user_id or not org_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed token")

    user = await session.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user inactive or not found"
        )

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == uuid.UUID(org_id),
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="not a member of this organization"
        )

    organization = await session.get(Organization, uuid.UUID(org_id))
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")

    return AuthContext(user=user, organization=organization, membership=membership)


AuthDep = Annotated[AuthContext, Depends(get_auth_context)]


def require_role(*roles: Role):
    """Dependency factory enforcing that the caller holds one of ``roles``."""

    async def _check(ctx: AuthDep) -> AuthContext:
        if ctx.membership.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires role in {[r.value for r in roles]}",
            )
        return ctx

    return _check


# Reusable role-guard dependencies.
OwnerOrAdmin = Annotated[AuthContext, Depends(require_role(Role.owner, Role.admin))]
# Any writing member (everyone except read-only auditors).
Members = Annotated[AuthContext, Depends(require_role(Role.owner, Role.admin, Role.member))]
