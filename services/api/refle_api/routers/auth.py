"""Authentication and organization membership endpoints (built-in password provider)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from refle_core.models import (
    Invitation,
    InvitationStatus,
    Membership,
    Organization,
    Role,
    User,
)
from refle_core.security import create_access_token, hash_password, verify_password
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from refle_api.cookies import clear_session_cookie, set_session_cookie
from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.schemas import (
    AcceptInviteRequest,
    AuthToken,
    InvitationCreate,
    InvitationOut,
    LoginRequest,
    MembershipOut,
    MeResponse,
    OrgOut,
    RegisterRequest,
)
from refle_api.services import bootstrap_org_controls, new_invite_token, unique_org_slug

router = APIRouter(prefix="/auth", tags=["auth"])

INVITE_TTL_DAYS = 14


def _token_for(user: User, org_id: uuid.UUID, role: Role) -> AuthToken:
    access = create_access_token(str(user.id), extra={"org_id": str(org_id)})
    return AuthToken(access_token=access, organization_id=org_id, role=role)


@router.post("/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response, session: SessionDep) -> AuthToken:
    """Create a new organization with the registering user as its owner."""
    email = body.email.lower()
    if (await session.execute(select(User.id).where(User.email == email))).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    org = Organization(name=body.org_name, slug=await unique_org_slug(session, body.org_name))
    session.add(org)
    await session.flush()

    user = User(
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    await session.flush()

    session.add(Membership(organization_id=org.id, user_id=user.id, role=Role.owner))
    await bootstrap_org_controls(session, org.id)
    await session.commit()
    token = _token_for(user, org.id, Role.owner)
    set_session_cookie(response, token.access_token)
    return token


@router.post("/login", response_model=AuthToken)
async def login(body: LoginRequest, response: Response, session: SessionDep) -> AuthToken:
    user = (
        await session.execute(select(User).where(User.email == body.email.lower()))
    ).scalar_one_or_none()
    if (
        user is None
        or not user.hashed_password
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    membership = (
        (
            await session.execute(
                select(Membership)
                .where(Membership.user_id == user.id)
                .order_by(Membership.created_at)
            )
        )
        .scalars()
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="user has no organization"
        )
    token = _token_for(user, membership.organization_id, membership.role)
    set_session_cookie(response, token.access_token)
    return token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_session_cookie(response)


@router.get("/me", response_model=MeResponse)
async def me(ctx: AuthDep, session: SessionDep) -> MeResponse:
    rows = (
        await session.execute(
            select(Membership, Organization)
            .join(Organization, Membership.organization_id == Organization.id)
            .where(Membership.user_id == ctx.user.id)
        )
    ).all()
    memberships = [
        MembershipOut(organization=OrgOut.model_validate(org), role=m.role) for m, org in rows
    ]
    return MeResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        full_name=ctx.user.full_name,
        organization_id=ctx.organization.id,
        role=ctx.role,
        memberships=memberships,
    )


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> InvitationOut:
    email = body.email.lower()
    already_member = (
        await session.execute(
            select(Membership.id)
            .join(User, Membership.user_id == User.id)
            .where(User.email == email, Membership.organization_id == ctx.organization.id)
        )
    ).first()
    if already_member is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user is already a member")

    invite = Invitation(
        organization_id=ctx.organization.id,
        email=email,
        role=body.role,
        token=new_invite_token(),
        status=InvitationStatus.pending,
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
        invited_by_id=ctx.user.id,
    )
    session.add(invite)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="an invitation for this email already exists",
        ) from exc
    await session.refresh(invite)
    return InvitationOut.model_validate(invite)


@router.get("/invitations", response_model=list[InvitationOut])
async def list_invitations(
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> list[InvitationOut]:
    invites = (
        (
            await session.execute(
                select(Invitation)
                .where(
                    Invitation.organization_id == ctx.organization.id,
                    Invitation.status == InvitationStatus.pending,
                )
                .order_by(Invitation.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [InvitationOut.model_validate(i) for i in invites]


@router.post("/accept-invite", response_model=AuthToken)
async def accept_invite(
    body: AcceptInviteRequest, response: Response, session: SessionDep
) -> AuthToken:
    invite = (
        await session.execute(select(Invitation).where(Invitation.token == body.token))
    ).scalar_one_or_none()
    if invite is None or invite.status != InvitationStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="invitation not found or already used",
        )
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="invitation expired")

    user = (
        await session.execute(select(User).where(User.email == invite.email))
    ).scalar_one_or_none()
    if user is None:
        if not body.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="password required to create a new account",
            )
        user = User(
            email=invite.email,
            full_name=body.full_name,
            hashed_password=hash_password(body.password),
        )
        session.add(user)
        await session.flush()

    existing = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == invite.organization_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            Membership(organization_id=invite.organization_id, user_id=user.id, role=invite.role)
        )
    invite.status = InvitationStatus.accepted
    invite.accepted_at = datetime.now(UTC)
    await session.commit()
    token = _token_for(user, invite.organization_id, invite.role)
    set_session_cookie(response, token.access_token)
    return token
