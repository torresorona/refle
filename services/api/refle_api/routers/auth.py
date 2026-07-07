"""Authentication and organization membership endpoints (built-in password provider)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status
from refle_core.config import get_settings
from refle_core.models import (
    AccessRequest,
    AccessRequestStatus,
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
    AccessRequestCreate,
    AccessRequestOut,
    AuthToken,
    InvitationCreate,
    InvitationOut,
    LoginRequest,
    MembershipOut,
    MeResponse,
    OrganizationCreateRequest,
    OrgOut,
    OrgUserOut,
    RegisterRequest,
    SwitchOrgRequest,
    UserCreateRequest,
)
from refle_api.services import bootstrap_org_controls, new_invite_token, unique_org_slug

router = APIRouter(prefix="/auth", tags=["auth"])

INVITE_TTL_DAYS = 14
CORE_MANAGED_ROLES = {Role.owner, Role.member, Role.auditor}


def _token_for(user: User, org_id: uuid.UUID, role: Role) -> AuthToken:
    access = create_access_token(str(user.id), extra={"org_id": str(org_id)})
    return AuthToken(access_token=access, organization_id=org_id, role=role)


async def _create_owned_org(session: SessionDep, user: User, org_name: str) -> Organization:
    org = Organization(name=org_name, slug=await unique_org_slug(session, org_name))
    session.add(org)
    await session.flush()
    session.add(Membership(organization_id=org.id, user_id=user.id, role=Role.owner))
    await bootstrap_org_controls(session, org.id)
    return org


async def _first_org(session: SessionDep) -> Organization | None:
    return (
        (
            await session.execute(select(Organization).order_by(Organization.created_at).limit(1))
        )
        .scalars()
        .first()
    )


def _ensure_core_role(role: Role) -> None:
    if role not in CORE_MANAGED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="self-hosted core supports owner, member, and auditor roles",
        )


@router.post("/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, response: Response, session: SessionDep) -> AuthToken:
    """Create the initial self-hosted Core organization and owner account."""
    if get_settings().is_self_hosted_core and await _first_org(session) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="organization already configured; request access or sign in",
        )

    email = body.email.lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=body.full_name,
            hashed_password=hash_password(body.password),
        )
        session.add(user)
        await session.flush()
    elif not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )
    elif body.full_name and not user.full_name:
        user.full_name = body.full_name

    org = await _create_owned_org(session, user, body.org_name)
    await session.commit()
    token = _token_for(user, org.id, Role.owner)
    set_session_cookie(response, token.access_token)
    return token


@router.post("/organizations", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreateRequest, response: Response, ctx: AuthDep, session: SessionDep
) -> AuthToken:
    """Create another independent organization when the deployment mode allows it."""
    if get_settings().is_self_hosted_core:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="self-hosted core supports one organization per instance",
        )
    org = await _create_owned_org(session, ctx.user, body.name)
    await session.commit()
    token = _token_for(ctx.user, org.id, Role.owner)
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
    if body.organization_id is not None:
        membership = (
            await session.execute(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.organization_id == body.organization_id,
                )
            )
        ).scalar_one_or_none()
    else:
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
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "not a member of that organization"
                if body.organization_id is not None
                else "user has no organization"
            ),
        )
    token = _token_for(user, membership.organization_id, membership.role)
    set_session_cookie(response, token.access_token)
    return token


@router.post("/switch-org", response_model=AuthToken)
async def switch_org(
    body: SwitchOrgRequest, response: Response, ctx: AuthDep, session: SessionDep
) -> AuthToken:
    """Re-issue the session for another org the user belongs to."""
    if get_settings().is_self_hosted_core and body.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="self-hosted core supports one organization per instance",
        )
    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == ctx.user.id,
                Membership.organization_id == body.organization_id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="not a member of that organization"
        )
    token = _token_for(ctx.user, body.organization_id, membership.role)
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


@router.get("/users", response_model=list[OrgUserOut])
async def list_users(session: SessionDep, ctx: OwnerOrAdmin) -> list[OrgUserOut]:
    rows = (
        await session.execute(
            select(User, Membership)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organization_id == ctx.organization.id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [
        OrgUserOut(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            created_at=membership.created_at,
        )
        for user, membership in rows
    ]


@router.post("/users", response_model=OrgUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> OrgUserOut:
    _ensure_core_role(body.role)
    email = body.email.lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=body.full_name,
            hashed_password=hash_password(body.password),
        )
        session.add(user)
        await session.flush()
    elif body.full_name and not user.full_name:
        user.full_name = body.full_name
    elif not user.hashed_password:
        user.hashed_password = hash_password(body.password)

    existing = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user is already a member")

    membership = Membership(organization_id=ctx.organization.id, user_id=user.id, role=body.role)
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return OrgUserOut(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.post(
    "/request-access",
    response_model=AccessRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_access(
    body: AccessRequestCreate,
    session: SessionDep,
) -> AccessRequestOut:
    org = await _first_org(session)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="create the organization before requesting access",
        )

    email = body.email.lower()
    existing_member = (
        await session.execute(
            select(Membership.id)
            .join(User, Membership.user_id == User.id)
            .where(User.email == email, Membership.organization_id == org.id)
        )
    ).first()
    if existing_member is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="user is already a member")

    existing_user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing_user and (
        not existing_user.hashed_password
        or not verify_password(body.password, existing_user.hashed_password)
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")

    pending = (
        await session.execute(
            select(AccessRequest).where(
                AccessRequest.organization_id == org.id,
                AccessRequest.email == email,
                AccessRequest.status == AccessRequestStatus.pending,
            )
        )
    ).scalar_one_or_none()
    if pending is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="access request already pending",
        )

    req = AccessRequest(
        organization_id=org.id,
        email=email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=Role.member,
        status=AccessRequestStatus.pending,
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return AccessRequestOut.model_validate(req)


@router.get("/access-requests", response_model=list[AccessRequestOut])
async def list_access_requests(
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> list[AccessRequestOut]:
    requests = (
        (
            await session.execute(
                select(AccessRequest)
                .where(
                    AccessRequest.organization_id == ctx.organization.id,
                    AccessRequest.status == AccessRequestStatus.pending,
                )
                .order_by(AccessRequest.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [AccessRequestOut.model_validate(req) for req in requests]


@router.post("/access-requests/{request_id}/approve", response_model=AccessRequestOut)
async def approve_access_request(
    request_id: uuid.UUID,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> AccessRequestOut:
    req = (
        await session.execute(
            select(AccessRequest).where(
                AccessRequest.id == request_id,
                AccessRequest.organization_id == ctx.organization.id,
                AccessRequest.status == AccessRequestStatus.pending,
            )
        )
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="access request not found",
        )

    user = (
        await session.execute(select(User).where(User.email == req.email))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=req.email,
            full_name=req.full_name,
            hashed_password=req.hashed_password,
        )
        session.add(user)
        await session.flush()
    else:
        if req.full_name and not user.full_name:
            user.full_name = req.full_name
        if not user.hashed_password:
            user.hashed_password = req.hashed_password

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        session.add(Membership(organization_id=ctx.organization.id, user_id=user.id, role=req.role))

    req.status = AccessRequestStatus.approved
    req.reviewed_by_id = ctx.user.id
    req.reviewed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(req)
    return AccessRequestOut.model_validate(req)


@router.post("/access-requests/{request_id}/reject", response_model=AccessRequestOut)
async def reject_access_request(
    request_id: uuid.UUID,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> AccessRequestOut:
    req = (
        await session.execute(
            select(AccessRequest).where(
                AccessRequest.id == request_id,
                AccessRequest.organization_id == ctx.organization.id,
                AccessRequest.status == AccessRequestStatus.pending,
            )
        )
    ).scalar_one_or_none()
    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="access request not found",
        )

    req.status = AccessRequestStatus.rejected
    req.reviewed_by_id = ctx.user.id
    req.reviewed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(req)
    return AccessRequestOut.model_validate(req)


@router.post("/invitations", response_model=InvitationOut, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    body: InvitationCreate,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> InvitationOut:
    _ensure_core_role(body.role)
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
