"""MetrCheck AI — Authentication & Admin User Provisioning API routes.

Endpoints:
  Public / Self-Service:
    POST /api/auth/register            — create MERCHANT_PUBLIC account
    POST /api/auth/login               — username+password → JWT token + user profile
    GET  /api/auth/me                  — current authenticated user profile
    PATCH /api/auth/me/email           — configure recovery email
    POST /api/auth/forgot-password     — request password reset
    POST /api/auth/verify-reset-token  — check reset token validity
    POST /api/auth/reset-password      — complete password reset
    POST /api/auth/verify-invitation   — check invitation token validity
    POST /api/auth/activate            — complete account activation & password creation
    GET  /api/auth/delivery-status     — delivery provider status check

  Administration (ADMIN only):
    GET    /api/admin/users                        — list all users & statuses
    POST   /api/admin/users                        — provision AUDIT_OFFICER or ENFORCEMENT_OFFICER (sends invitation)
    POST   /api/admin/users/{username}/resend-invitation — resend invitation email
    POST   /api/admin/users/{username}/suspend     — suspend account (invalidates sessions)
    POST   /api/admin/users/{username}/reactivate  — reactivate suspended account
    POST   /api/admin/users/{username}/change-role — change role between AUDIT and ENFORCEMENT
    DELETE /api/admin/users/{username}             — delete/revoke account
    GET    /api/admin/audit-logs                   — security audit trail
"""
import os
import re
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from config import settings
from auth.security import (
    ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT, ROLE_USER, ALL_ROLES, ROLE_LABELS,
    hash_password, verify_password, create_token, require_roles, get_current_user,
    generate_password_reset_token, generate_invitation_token, hash_reset_token,
    get_delivery_provider, get_delivery_provider_status
)
from auth.ratelimit import (
    get_client_ip,
    check_login_rate_limit,
    record_login_failure,
    record_login_success,
    check_forgot_password_rate_limit,
    record_forgot_password_attempt,
    check_register_rate_limit,
)
from database.db import (
    create_user, get_user_by_username, get_user_by_email, get_user_by_identifier,
    list_users, update_user, delete_user,
    create_password_reset_record, get_valid_password_reset, apply_password_reset,
    create_invited_user, get_valid_invitation, activate_user_account,
    resend_invitation_record, suspend_user, reactivate_user, change_user_role,
    revoke_invitation, log_account_audit_event, get_account_audit_logs,
    create_organization, get_organization,
    create_officer_access_request, get_officer_access_request_by_id,
    get_pending_officer_request_by_email_and_role, list_officer_access_requests,
    approve_officer_access_request, reject_officer_access_request
)

router = APIRouter(prefix="/auth", tags=["Auth"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
officer_access_router = APIRouter(prefix="/officer-access", tags=["Officer Access"])

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_format(email: str) -> bool:
    if not email or len(email) < 5 or len(email) > 100:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def normalize_email(email: Optional[str]) -> str:
    return email.strip().lower() if email else ""


# ── Schemas ──────────────────────────────────────────────────────────────
class RegisterUserRequest(BaseModel):
    """Payload for consumer / normal user registration."""
    full_name: str = Field(default="", max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    mobile_number: Optional[str] = Field(default="", max_length=20)


class RegisterMerchantRequest(BaseModel):
    """Payload for merchant / business organization registration."""
    # Section A: Account Information
    full_name: str = Field(default="", max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    mobile_number: Optional[str] = Field(default="", max_length=20)
    password: str = Field(min_length=8, max_length=128)
    
    # Section B: Business Information
    business_name: str = Field(min_length=1, max_length=150)
    business_type: str = Field(default="Manufacturer", max_length=50)
    trade_name: Optional[str] = Field(default="", max_length=150)
    
    # Section C: Business Address
    address_line1: str = Field(min_length=1, max_length=200)
    address_line2: Optional[str] = Field(default="", max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(min_length=3, max_length=20)
    country: str = Field(default="India", max_length=100)
    
    # Section D: Regulatory / Business Identifiers (Optional / Applicable)
    gstin: Optional[str] = Field(default="", max_length=30)
    fssai_license: Optional[str] = Field(default="", max_length=50)
    legal_metrology_license: Optional[str] = Field(default="", max_length=50)
    other_identifier: Optional[str] = Field(default="", max_length=100)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: Optional[str] = Field(default="", max_length=100)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""
    jurisdiction: str = ""
    organization_name: Optional[str] = ""
    role: Optional[str] = None  # Ignored by server for public registration


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    """Legacy or direct account creation payload."""
    username: str = Field(min_length=3, max_length=50)
    email: Optional[str] = ""
    password: str = Field(min_length=8, max_length=128)
    full_name: str = ""
    jurisdiction: str = ""
    organization_id: Optional[str] = ""
    role: str = ROLE_ENFORCEMENT


class AdminProvisionUserRequest(BaseModel):
    """Admin-only payload for provisioning an authorized user via invitation."""
    full_name: str = Field(default="", max_length=100)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=100)
    role: str = Field(default=ROLE_AUDIT)
    jurisdiction: Optional[str] = ""
    organization_id: Optional[str] = ""
    organization_name: Optional[str] = ""


class ChangeRoleRequest(BaseModel):
    role: str


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    email: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[str] = None
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UpdateMyEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=100)


class UserOut(BaseModel):
    username: str
    role: str
    role_label: str
    full_name: str = ""
    jurisdiction: str = ""
    email: Optional[str] = ""
    organization_id: Optional[str] = ""
    status: str = "ACTIVE"
    invited_at: Optional[str] = ""
    activated_at: Optional[str] = ""
    created_at: Optional[str] = ""
    is_admin: bool = False


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=100)


class ForgotPasswordResponse(BaseModel):
    message: str



class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str


class VerifyResetTokenRequest(BaseModel):
    token: str = Field(min_length=1)


class VerifyResetTokenResponse(BaseModel):
    valid: bool
    username: Optional[str] = None


class VerifyInvitationRequest(BaseModel):
    token: str = Field(min_length=1)


class VerifyInvitationResponse(BaseModel):
    valid: bool
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    role_label: Optional[str] = None


class ActivateAccountRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8, max_length=128)


class ActivateAccountResponse(BaseModel):
    message: str
    username: str


class AdminProvisionResponse(BaseModel):
    message: str
    user: UserOut
    dev_invitation_token: Optional[str] = None


class DownloadTicketRequest(BaseModel):
    resource_type: str  # "report" or "image"
    resource_id: str
    action: Optional[str] = "download"


class DownloadTicketResponse(BaseModel):
    ticket: str
    resource_type: str
    resource_id: str
    expires_in_seconds: int = 60
    download_url: str


class OfficerAccessRequestCreate(BaseModel):
    """Payload for submitting an official officer access request."""
    requested_role: str = Field(description="Must be AUDIT_OFFICER or ENFORCEMENT_OFFICER")
    full_name: str = Field(min_length=2, max_length=100)
    official_email: str = Field(min_length=5, max_length=100)
    mobile_number: str = Field(min_length=7, max_length=20)
    employee_officer_id: str = Field(min_length=2, max_length=50)
    designation: str = Field(min_length=2, max_length=100)
    department_organization: str = Field(min_length=2, max_length=150)
    state: str = Field(min_length=2, max_length=100)
    district_jurisdiction: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=5, max_length=500)
    office_address: Optional[str] = Field(default="", max_length=250)
    additional_information: Optional[str] = Field(default="", max_length=500)


class OfficerAccessRequestOut(BaseModel):
    id: int
    request_id: str
    requested_role: str
    role_label: str
    full_name: str
    official_email: str
    mobile_number: str
    employee_officer_id: str
    designation: str
    department_organization: str
    state: str
    district_jurisdiction: str
    office_address: Optional[str] = ""
    reason: str
    additional_information: Optional[str] = ""
    status: str
    submitted_at: str
    reviewed_at: Optional[str] = None
    reviewed_by: Optional[str] = ""
    rejection_reason: Optional[str] = ""
    created_user_id: Optional[str] = ""


class OfficerAccessRequestPublicStatus(BaseModel):
    request_id: str
    requested_role: str
    role_label: str
    status: str
    submitted_at: str
    reviewed_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    message: str


class AdminRejectOfficerRequest(BaseModel):
    rejection_reason: str = Field(min_length=3, max_length=500)


class AdminApproveOfficerRequestResponse(BaseModel):
    message: str
    request_id: str
    username: str
    user: UserOut
    dev_invitation_token: Optional[str] = None
    activation_url: Optional[str] = None


def _to_user_out(u: dict) -> UserOut:
    return UserOut(
        username=u["username"],
        role=u["role"],
        role_label=ROLE_LABELS.get(u["role"], u["role"]),
        full_name=u.get("full_name", "") or "",
        jurisdiction=u.get("jurisdiction", "") or "",
        email=u.get("email", "") or "",
        organization_id=u.get("organization_id", "") or "",
        status=u.get("status", "ACTIVE") or "ACTIVE",
        invited_at=u.get("invited_at", "") or "",
        activated_at=u.get("activated_at", "") or "",
        created_at=u.get("created_at", "") or "",
        is_admin=u["role"] == ROLE_ADMIN,
    )


def _to_officer_request_out(r: dict) -> OfficerAccessRequestOut:
    return OfficerAccessRequestOut(
        id=r["id"],
        request_id=r["request_id"],
        requested_role=r["requested_role"],
        role_label=ROLE_LABELS.get(r["requested_role"], r["requested_role"]),
        full_name=r["full_name"],
        official_email=r["official_email"],
        mobile_number=r["mobile_number"],
        employee_officer_id=r["employee_officer_id"],
        designation=r["designation"],
        department_organization=r["department_organization"],
        state=r["state"],
        district_jurisdiction=r["district_jurisdiction"],
        office_address=r.get("office_address", "") or "",
        reason=r["reason"],
        additional_information=r.get("additional_information", "") or "",
        status=r["status"],
        submitted_at=r["submitted_at"],
        reviewed_at=r.get("reviewed_at"),
        reviewed_by=r.get("reviewed_by", "") or "",
        rejection_reason=r.get("rejection_reason", "") or "",
        created_user_id=r.get("created_user_id", "") or "",
    )


# ══════════════════════════════════════════════════════════════════════════
# AUTH ROUTES (Public & Self-Service)
# ══════════════════════════════════════════════════════════════════════════

@router.post("/register-user", response_model=AuthResponse, status_code=201)
async def register_user(req: RegisterUserRequest, request: Request):
    """Consumer / Normal User self-registration.
    
    Security: Strictly assigns role=PUBLIC_USER and provisions dedicated personal tenant space.
    """
    client_ip = get_client_ip(request)
    
    # ── Rate limiting guard ──
    allowed, rate_msg = check_register_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    username = req.username.strip()
    norm_email = normalize_email(req.email)
    
    if not norm_email or not validate_email_format(norm_email):
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    
    existing_email = await get_user_by_email(norm_email)
    if existing_email:
        raise HTTPException(status_code=409, detail="Email address is already registered")

    existing = await get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    org_id = f"org_user_{username.lower()}"
    await create_organization(id=org_id, name=f"{req.full_name or username} Personal Space", org_type="USER", status="ACTIVE")

    pw_hash, salt = hash_password(req.password)
    ok = await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=ROLE_USER,
        full_name=req.full_name.strip(),
        jurisdiction="Consumer Self-Service",
        email=norm_email,
        organization_id=org_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not create user account")

    user = await get_user_by_username(username)
    token = create_token(user["username"], user["role"], user.get("token_version", 1) or 1)
    await log_account_audit_event(
        actor_username=username,
        target_username=username,
        event_type="USER_REGISTERED",
        details=f"Public self-registration as PUBLIC_USER under personal tenant '{org_id}'",
        ip_address=client_ip
    )
    return AuthResponse(token=token, user=_to_user_out(user))


@router.post("/register-merchant", response_model=AuthResponse, status_code=201)
async def register_merchant(req: RegisterMerchantRequest, request: Request):
    """Merchant / Business organization self-registration.
    
    Security: Strictly assigns role=MERCHANT_PUBLIC and provisions dedicated business tenant space.
    """
    client_ip = get_client_ip(request)
    
    # ── Rate limiting guard ──
    allowed, rate_msg = check_register_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    username = req.username.strip()
    norm_email = normalize_email(req.email)
    
    if not norm_email or not validate_email_format(norm_email):
        raise HTTPException(status_code=400, detail="A valid business email address is required.")
    
    existing_email = await get_user_by_email(norm_email)
    if existing_email:
        raise HTTPException(status_code=409, detail="Email address is already registered")

    existing = await get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    org_id = f"org_{username.lower()}"
    org_name = req.business_name.strip() if req.business_name else f"{username.capitalize()} Packagers Corp"
    jurisdiction_str = f"{req.city.strip()}, {req.state.strip()}, {req.country.strip()}" if req.city and req.state else "National"
    await create_organization(id=org_id, name=org_name, org_type="MERCHANT", jurisdiction=jurisdiction_str, status="ACTIVE")

    pw_hash, salt = hash_password(req.password)
    ok = await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=ROLE_MERCHANT,
        full_name=req.full_name.strip(),
        jurisdiction=jurisdiction_str,
        email=norm_email,
        organization_id=org_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not create merchant account")

    user = await get_user_by_username(username)
    token = create_token(user["username"], user["role"], user.get("token_version", 1) or 1)
    await log_account_audit_event(
        actor_username=username,
        target_username=username,
        event_type="MERCHANT_REGISTERED",
        details=f"Merchant self-registration for '{org_name}' (Type: {req.business_type}) under tenant '{org_id}'",
        ip_address=client_ip
    )
    return AuthResponse(token=token, user=_to_user_out(user))


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(req: RegisterRequest, request: Request):
    """Public merchant self-registration.
    
    Security: Strictly assigns role=MERCHANT_PUBLIC and provisions dedicated tenant organization.
    """
    client_ip = get_client_ip(request)
    
    # ── Rate limiting guard (SEC-AUD-06) ──
    allowed, rate_msg = check_register_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    username = req.username.strip()
    norm_email = normalize_email(req.email)
    
    if norm_email:
        if not validate_email_format(norm_email):
            raise HTTPException(status_code=400, detail="Invalid email address format.")
        existing_email = await get_user_by_email(norm_email)
        if existing_email:
            raise HTTPException(status_code=409, detail="Email address is already registered")

    existing = await get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    # Reject client attempt to request privileged roles
    assigned_role = ROLE_MERCHANT
    if req.role in (ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT):
        admins = await list_users(role=ROLE_ADMIN)
        first_boot = not admins
        if not first_boot:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can create privileged accounts"
            )
        assigned_role = req.role

    # Dedicated organization per merchant
    org_id = f"org_{username.lower()}"
    org_name = req.organization_name.strip() if req.organization_name else f"{username.capitalize()} Packagers Corp"
    await create_organization(id=org_id, name=org_name, status="ACTIVE")

    pw_hash, salt = hash_password(req.password)
    ok = await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=assigned_role,
        full_name=req.full_name,
        jurisdiction=req.jurisdiction,
        email=norm_email,
        organization_id=org_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not create user")

    user = await get_user_by_username(username)
    token = create_token(user["username"], user["role"], user.get("token_version", 1) or 1)
    await log_account_audit_event(
        actor_username=username,
        target_username=username,
        event_type="MERCHANT_REGISTERED",
        details=f"Public self-registration as MERCHANT_PUBLIC under tenant '{org_id}'",
        ip_address=client_ip
    )
    return AuthResponse(token=token, user=_to_user_out(user))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, request: Request):
    client_ip = get_client_ip(request)
    
    # ── Rate limiting guard ──
    allowed, rate_msg = check_login_rate_limit(client_ip, req.username)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    user = await get_user_by_username(req.username.strip())
    if not user:
        record_login_failure(client_ip, req.username)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password. Please check your credentials and try again."
        )

    user_status = user.get("status", "ACTIVE") or "ACTIVE"
    if user_status == "INVITED":
        record_login_failure(client_ip, req.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account invitation has not been activated. Please check your invitation email to set your password."
        )

    if user_status == "SUSPENDED":
        record_login_failure(client_ip, req.username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended. Please contact system administrator."
        )

    if not verify_password(req.password, user["salt"], user["password_hash"]):
        record_login_failure(client_ip, req.username)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password. Please check your credentials and try again."
        )
    
    # Successful login: reset failed attempt counter
    record_login_success(client_ip, req.username)
    token = create_token(user["username"], user["role"], user.get("token_version", 1) or 1)
    return AuthResponse(token=token, user=_to_user_out(user))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(req: ForgotPasswordRequest, request: Request):
    """Request a password reset link. Account enumeration resistant."""
    client_ip = get_client_ip(request)
    identifier = req.identifier.strip()
    
    allowed, rate_msg = check_forgot_password_rate_limit(client_ip, identifier)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )
    record_forgot_password_attempt(client_ip, identifier)

    user = await get_user_by_identifier(identifier)
    
    if user:
        recovery_email = user.get("email", "").strip()
        raw_token, token_hash, expires_at = generate_password_reset_token()
        ok = await create_password_reset_record(user["username"], token_hash, expires_at)
        if ok:
            configured_frontend = getattr(settings, "METRCHECK_FRONTEND_URL", "").strip()
            if configured_frontend:
                origin = configured_frontend.rstrip("/")
            else:
                base_url = str(request.base_url).rstrip("/")
                origin = request.headers.get("origin") or request.headers.get("referer") or base_url
                origin = origin.rstrip("/")
            reset_url = f"{origin}/reset-password?token={raw_token}"
            
            provider = get_delivery_provider()
            await provider.send_reset_instructions(user["username"], raw_token, reset_url, email=recovery_email)

    return ForgotPasswordResponse(
        message="If an account matches the information provided, password reset instructions have been sent."
    )



@router.get("/delivery-status")
async def delivery_status():
    """Safe internal check for delivery configuration (no secrets exposed)."""
    return get_delivery_provider_status()


@router.post("/verify-reset-token", response_model=VerifyResetTokenResponse)
async def verify_reset_token(req: VerifyResetTokenRequest):
    """Check if a password reset token is valid and not expired."""
    token = req.token.strip()
    if not token:
        return VerifyResetTokenResponse(valid=False)
    
    token_hash = hash_reset_token(token)
    record = await get_valid_password_reset(token_hash)
    if not record:
        return VerifyResetTokenResponse(valid=False)
    
    return VerifyResetTokenResponse(valid=True, username=record["username"])


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(req: ResetPasswordRequest):
    """Reset account password using a valid, unexpired token."""
    token = req.token.strip()
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired password reset link. Please request a new one."
        )
    
    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long."
        )
    
    token_hash = hash_reset_token(token)
    record = await get_valid_password_reset(token_hash)
    if not record:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired password reset link. Please request a new one."
        )
    
    new_pw_hash, new_salt = hash_password(req.new_password)
    ok = await apply_password_reset(
        username=record["username"],
        reset_id=record["id"],
        new_pw_hash=new_pw_hash,
        new_salt=new_salt
    )
    if not ok:
        raise HTTPException(
            status_code=500,
            detail="Could not update password. Please try requesting a new reset link."
        )
    
    return ResetPasswordResponse(
        message="Password has been successfully reset. You can now log in with your new password."
    )


# ── Account Invitation Verification & Activation ─────────────────────────

@router.post("/verify-invitation", response_model=VerifyInvitationResponse)
async def verify_invitation(req: VerifyInvitationRequest):
    """Verify validity of an account invitation token."""
    token = req.token.strip()
    if not token:
        return VerifyInvitationResponse(valid=False)

    token_hash = hash_reset_token(token)
    user = await get_valid_invitation(token_hash)
    if not user:
        return VerifyInvitationResponse(valid=False)

    return VerifyInvitationResponse(
        valid=True,
        username=user["username"],
        full_name=user.get("full_name", "") or "",
        email=user.get("email", "") or "",
        role=user["role"],
        role_label=ROLE_LABELS.get(user["role"], user["role"])
    )


@router.post("/activate", response_model=ActivateAccountResponse)
async def activate_account(req: ActivateAccountRequest, request: Request):
    """Set password and activate an invited account."""
    client_ip = get_client_ip(request)
    token = req.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or missing invitation token.")

    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long.")

    token_hash = hash_reset_token(token)
    user = await get_valid_invitation(token_hash)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already-used invitation link.")

    pw_hash, salt = hash_password(req.password)
    ok = await activate_user_account(user["username"], pw_hash, salt)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not activate account. Please contact administrator.")

    await log_account_audit_event(
        actor_username=user["username"],
        target_username=user["username"],
        event_type="INVITATION_ACTIVATED",
        details=f"Account activated with role {user['role']}",
        ip_address=client_ip
    )

    return ActivateAccountResponse(
        message="Account activated successfully. You can now log in.",
        username=user["username"]
    )


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return _to_user_out(user)


@router.post("/download-ticket", response_model=DownloadTicketResponse)
async def create_download_ticket_endpoint(
    req: DownloadTicketRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Issues a short-lived (60s), single-use cryptographically signed download ticket.
    Validates user authentication and resource authorization (tenant/ownership) before issuance.
    """
    import secrets
    import time
    from database.db import save_download_ticket, get_analysis, get_db
    from auth.security import generate_download_ticket_string, check_tenant_access
    from services.image_service import ensure_path_contained

    res_type = (req.resource_type or "").strip().lower()
    res_id = (req.resource_id or "").strip()

    if not res_type or not res_id:
        raise HTTPException(status_code=400, detail="resource_type and resource_id are required.")

    if res_type not in ("report", "image"):
        raise HTTPException(status_code=400, detail="Invalid resource_type. Must be 'report' or 'image'.")

    # Authorize access before issuing ticket
    if res_type == "report":
        if res_id.startswith("demo-") or res_id in ("1", "2", "3"):
            pass
        else:
            analysis = await get_analysis(res_id)
            if not analysis:
                raise HTTPException(status_code=404, detail="Analysis not found")
            check_tenant_access(current_user, analysis, raise_exception=True)
    elif res_type == "image":
        if not res_id or ".." in res_id or "/" in res_id or "\\" in res_id or "\x00" in res_id:
            raise HTTPException(status_code=400, detail="Invalid filename format.")
        target_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, res_id))
        ensure_path_contained(target_path, settings.UPLOAD_DIR)
        if not os.path.exists(target_path) or not os.path.isfile(target_path):
            raise HTTPException(status_code=404, detail="Requested file not found.")

        user_role = current_user.get("role", ROLE_MERCHANT)
        if user_role != ROLE_ADMIN:
            is_authorized = False
            db = await get_db()
            cursor = await db.execute(
                """
                SELECT id, owner_user_id, organization_id, image_filename, images
                FROM analyses
                WHERE image_filename = ?
                   OR images LIKE ?
                   OR id = ?
                   OR ? LIKE id || '%'
                """,
                (res_id, f'%{res_id}%', res_id, res_id)
            )
            analysis_rows = await cursor.fetchall()
            for row in analysis_rows:
                if check_tenant_access(current_user, dict(row)):
                    is_authorized = True
                    break

            if not is_authorized:
                cursor = await db.execute(
                    """
                    SELECT id, owner_user_id, organization_id, file_path, filename, pages_data
                    FROM artworks
                    WHERE file_path LIKE ?
                       OR filename = ?
                       OR pages_data LIKE ?
                       OR id = ?
                       OR ? LIKE id || '%'
                       OR ? LIKE 'preprint_' || id || '%'
                    """,
                    (f"%{res_id}", res_id, f"%{res_id}%", res_id, res_id, res_id)
                )
                artwork_rows = await cursor.fetchall()
                for row in artwork_rows:
                    if check_tenant_access(current_user, dict(row)):
                        is_authorized = True
                        break

            if not is_authorized:
                raise HTTPException(status_code=403, detail="Access denied. Cross-tenant or unauthorized image file.")

    ticket_id = secrets.token_hex(20)
    expires_at = time.time() + 60.0
    username = current_user.get("username", "")
    role = current_user.get("role", ROLE_MERCHANT)
    org_id = current_user.get("organization_id", "")
    user_id = str(current_user.get("id", ""))

    await save_download_ticket(
        ticket_id=ticket_id,
        user_id=user_id,
        username=username,
        role=role,
        organization_id=org_id,
        resource_type=res_type,
        resource_id=res_id,
        action=req.action or "download",
        expires_at=expires_at,
    )

    ticket_str = generate_download_ticket_string(ticket_id)
    if res_type == "report":
        download_url = f"/api/report/{res_id}?ticket={ticket_str}"
    else:
        download_url = f"/api/images/{res_id}?ticket={ticket_str}"

    return DownloadTicketResponse(
        ticket=ticket_str,
        resource_type=res_type,
        resource_id=res_id,
        expires_in_seconds=60,
        download_url=download_url,
    )



@router.patch("/me/email", response_model=UserOut)
@router.put("/me/email", response_model=UserOut)
async def update_my_email(
    req: UpdateMyEmailRequest,
    current_user: dict = Depends(get_current_user),
):
    """Authenticated user: configure or update account recovery email."""
    raw_email = req.email.strip()
    if not validate_email_format(raw_email):
        raise HTTPException(status_code=400, detail="Invalid email address format.")
    
    norm_email = normalize_email(raw_email)
    existing = await get_user_by_email(norm_email)
    if existing and existing["username"].lower() != current_user["username"].lower():
        raise HTTPException(status_code=409, detail="Email address is already registered to another account")
    
    ok = await update_user(username=current_user["username"], email=norm_email)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not update recovery email")
    
    refreshed = await get_user_by_username(current_user["username"])
    return _to_user_out(refreshed)


# Backward-compatible auth routes for user management (ADMIN only)
@router.get("/users", response_model=List[UserOut])
async def auth_users(user: dict = Depends(require_roles(ROLE_ADMIN))):
    rows = await list_users()
    return [_to_user_out(u) for u in rows]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user_admin_legacy(
    req: CreateUserRequest,
    admin: dict = Depends(require_roles(ROLE_ADMIN)),
):
    """Admin-only: direct creation of officer/merchant account (test/legacy compatibility)."""
    if req.role not in (ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT):
        raise HTTPException(
            status_code=400,
            detail="Role must be ENFORCEMENT_OFFICER, AUDIT_OFFICER, or MERCHANT_PUBLIC",
        )

    username = req.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    existing = await get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    org_id = (req.organization_id or "").strip()
    if req.role in (ROLE_ENFORCEMENT, ROLE_AUDIT):
        if not org_id:
            raise HTTPException(
                status_code=400,
                detail="Explicit organization_id is required for enforcement and audit officer provisioning."
            )
        org = await get_organization(org_id)
        if not org:
            raise HTTPException(
                status_code=400,
                detail=f"Organization '{org_id}' does not exist.",
            )
        if org.get("status") != "ACTIVE":
            raise HTTPException(
                status_code=400,
                detail=f"Organization '{org_id}' is inactive.",
            )
    elif req.role == ROLE_MERCHANT:
        if not org_id:
            org_id = f"org_{username.lower()}"
            await create_organization(id=org_id, name=f"{username.capitalize()} Merchant Org", status="ACTIVE")
        else:
            org = await get_organization(org_id)
            if not org:
                raise HTTPException(
                    status_code=400,
                    detail=f"Organization '{org_id}' does not exist.",
                )
            if org.get("status") != "ACTIVE":
                raise HTTPException(
                    status_code=400,
                    detail=f"Organization '{org_id}' is inactive.",
                )

    norm_email = normalize_email(req.email)
    if norm_email:
        if not validate_email_format(norm_email):
            raise HTTPException(status_code=400, detail="Invalid email address format.")
        existing_email = await get_user_by_email(norm_email)
        if existing_email:
            raise HTTPException(status_code=409, detail="Email address is already registered")

    pw_hash, salt = hash_password(req.password)
    ok = await create_user(
        username=username,
        password_hash=pw_hash,
        salt=salt,
        role=req.role,
        full_name=req.full_name,
        jurisdiction=req.jurisdiction,
        email=norm_email,
        organization_id=org_id,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not create user")

    user = await get_user_by_username(username)
    return _to_user_out(user)


@router.put("/users/{username}", response_model=UserOut)
async def update_user_admin_legacy(
    username: str,
    req: UpdateUserRequest,
    admin: dict = Depends(require_roles(ROLE_ADMIN)),
):
    """Admin-only: update an account."""
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == ROLE_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot modify an administrator account")

    if req.role is not None and req.role not in (ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT):
        raise HTTPException(
            status_code=400,
            detail="Role must be ENFORCEMENT_OFFICER, AUDIT_OFFICER, or MERCHANT_PUBLIC",
        )

    target_org = None
    if req.organization_id is not None:
        raw_org = req.organization_id.strip()
        effective_role = req.role if req.role is not None else target["role"]
        if not raw_org:
            if effective_role in (ROLE_ENFORCEMENT, ROLE_AUDIT, ROLE_MERCHANT):
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove organization from a tenant-scoped user.",
                )
            target_org = ""
        else:
            org = await get_organization(raw_org)
            if not org:
                raise HTTPException(
                    status_code=400,
                    detail=f"Organization '{raw_org}' does not exist.",
                )
            if org.get("status") != "ACTIVE":
                raise HTTPException(
                    status_code=400,
                    detail=f"Organization '{raw_org}' is inactive.",
                )
            target_org = raw_org

    norm_email = None
    if req.email is not None:
        raw_email = req.email.strip()
        if raw_email:
            if not validate_email_format(raw_email):
                raise HTTPException(status_code=400, detail="Invalid email address format.")
            norm_email = normalize_email(raw_email)
            existing_email = await get_user_by_email(norm_email)
            if existing_email and existing_email["username"].lower() != target["username"].lower():
                raise HTTPException(status_code=409, detail="Email address is already in use by another account")
        else:
            norm_email = ""

    pw_hash, salt = None, None
    if req.new_password:
        pw_hash, salt = hash_password(req.new_password)

    await update_user(
        username=target["username"],
        full_name=req.full_name,
        jurisdiction=req.jurisdiction,
        role=req.role,
        password_hash=pw_hash,
        salt=salt,
        email=norm_email,
        organization_id=target_org,
    )

    refreshed = await get_user_by_username(target["username"])
    return _to_user_out(refreshed)


@router.delete("/users/{username}", status_code=204)
async def delete_user_admin_legacy(
    username: str,
    admin: dict = Depends(require_roles(ROLE_ADMIN)),
):
    """Admin-only: delete an officer or merchant account."""
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == ROLE_ADMIN:
        raise HTTPException(status_code=400, detail="Cannot delete an administrator account")

    ok = await delete_user(target["username"])
    if not ok:
        raise HTTPException(status_code=400, detail="Could not delete user")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════════════════
# ADMIN USER PROVISIONING & MANAGEMENT (ADMIN ONLY)
# ══════════════════════════════════════════════════════════════════════════

@admin_router.get("/users", response_model=List[UserOut])
async def admin_get_users(admin: dict = Depends(require_roles(ROLE_ADMIN))):
    """Admin-only: list all accounts with role, status, and timestamps."""
    rows = await list_users()
    return [_to_user_out(u) for u in rows]


@admin_router.post("/users", response_model=AdminProvisionResponse, status_code=201)
async def admin_provision_user(
    req: AdminProvisionUserRequest,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: provision an authorized user (AUDIT_OFFICER or ENFORCEMENT_OFFICER).
    
    Generates single-use 24-hour invitation token, sends email, and creates user in INVITED status.
    Deliberately prevents creation of ADMIN accounts via standard provisioning.
    """
    client_ip = get_client_ip(request)
    target_role = req.role.strip()
    if target_role not in (ROLE_AUDIT, ROLE_ENFORCEMENT, ROLE_MERCHANT):
        raise HTTPException(
            status_code=400,
            detail="Role must be AUDIT_OFFICER, ENFORCEMENT_OFFICER, or MERCHANT_PUBLIC. Cannot provision ADMIN accounts.",
        )
    if target_role == ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Cannot create administrator accounts via provisioning.")

    username = req.username.strip()
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")

    existing = await get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    norm_email = normalize_email(req.email)
    if not validate_email_format(norm_email):
        raise HTTPException(status_code=400, detail="Valid email address is required for account invitation.")

    existing_email = await get_user_by_email(norm_email)
    if existing_email:
        raise HTTPException(status_code=409, detail="Email address is already registered")

    # Determine tenant organization
    if target_role in (ROLE_AUDIT, ROLE_ENFORCEMENT):
        if not req.organization_id or not req.organization_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Explicit organization_id is required for enforcement and audit officer provisioning."
            )
        org_id = req.organization_id.strip()
        if req.organization_name and req.organization_name.strip():
            await create_organization(id=org_id, name=req.organization_name.strip(), status="ACTIVE")
    else:
        if req.organization_id and req.organization_id.strip():
            org_id = req.organization_id.strip()
            if req.organization_name and req.organization_name.strip():
                await create_organization(id=org_id, name=req.organization_name.strip(), status="ACTIVE")
        else:
            org_id = f"org_{username.lower()}"
            org_name = req.organization_name.strip() if req.organization_name else f"{username.capitalize()} Packagers Corp"
            await create_organization(id=org_id, name=org_name, status="ACTIVE")

    # Strict active organization check
    org = await get_organization(org_id)
    if not org:
        raise HTTPException(
            status_code=400,
            detail=f"Organization '{org_id}' does not exist.",
        )
    if org.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail=f"Organization '{org_id}' is inactive.",
        )

    raw_token, token_hash, expires_at = generate_invitation_token(expire_hours=24)
    ok = await create_invited_user(
        username=username,
        email=norm_email,
        role=target_role,
        full_name=req.full_name,
        jurisdiction=req.jurisdiction or "",
        token_hash=token_hash,
        expires_at=expires_at,
        organization_id=org_id
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Could not provision user account.")

    # Build activation URL
    configured_frontend = getattr(settings, "METRCHECK_FRONTEND_URL", "").strip()
    if configured_frontend:
        origin = configured_frontend.rstrip("/")
    else:
        base_url = str(request.base_url).rstrip("/")
        origin = request.headers.get("origin") or request.headers.get("referer") or base_url
        origin = origin.rstrip("/")
    activation_url = f"{origin}/activate?token={raw_token}"

    provider = get_delivery_provider()
    await provider.send_invitation_email(
        full_name=req.full_name,
        username=username,
        role=target_role,
        raw_token=raw_token,
        activation_url=activation_url,
        email=norm_email
    )

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=username,
        event_type="ACCOUNT_INVITED",
        details=f"Provisioned {target_role} with email {norm_email}",
        ip_address=client_ip
    )

    dev_token: Optional[str] = None
    is_prod = (
        os.environ.get("METRCHECK_ENV") == "production" 
        or os.environ.get("ENVIRONMENT") == "production"
        or getattr(settings, "ENVIRONMENT", "") == "production"
    )
    is_dev = (
        settings.TEST_MODE 
        or os.environ.get("TEST_MODE") == "1" 
        or os.environ.get("DEV_MODE") == "1" 
        or os.environ.get("METRCHECK_ENV") == "development"
        or getattr(settings, "ENVIRONMENT", "") == "development"
        or getattr(settings, "METRCHECK_DEMO_MODE", False)
    )
    if is_dev and not is_prod:
        dev_token = raw_token

    created = await get_user_by_username(username)
    return AdminProvisionResponse(
        message=f"Invitation sent successfully to {norm_email}.",
        user=_to_user_out(created),
        dev_invitation_token=dev_token
    )


@admin_router.post("/users/{username}/resend-invitation")
async def admin_resend_invitation(
    username: str,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: regenerate invitation token and resend invitation email."""
    client_ip = get_client_ip(request)
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get("status") != "INVITED":
        raise HTTPException(status_code=400, detail="Only pending invited accounts can receive a new invitation.")

    norm_email = target.get("email", "").strip()
    if not norm_email:
        raise HTTPException(status_code=400, detail="Target account has no registered email address.")

    raw_token, token_hash, expires_at = generate_invitation_token(expire_hours=24)
    ok = await resend_invitation_record(target["username"], token_hash, expires_at)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not update invitation record.")

    configured_frontend = getattr(settings, "METRCHECK_FRONTEND_URL", "").strip()
    if configured_frontend:
        origin = configured_frontend.rstrip("/")
    else:
        base_url = str(request.base_url).rstrip("/")
        origin = request.headers.get("origin") or request.headers.get("referer") or base_url
        origin = origin.rstrip("/")
    activation_url = f"{origin}/activate?token={raw_token}"

    provider = get_delivery_provider()
    await provider.send_invitation_email(
        full_name=target.get("full_name", ""),
        username=target["username"],
        role=target["role"],
        raw_token=raw_token,
        activation_url=activation_url,
        email=norm_email
    )

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=target["username"],
        event_type="INVITATION_RESENT",
        details=f"Resent invitation for {target['role']} to {norm_email}",
        ip_address=client_ip
    )

    dev_token: Optional[str] = None
    is_prod = (
        os.environ.get("METRCHECK_ENV") == "production" 
        or os.environ.get("ENVIRONMENT") == "production"
        or getattr(settings, "ENVIRONMENT", "") == "production"
    )
    is_dev = (
        settings.TEST_MODE 
        or os.environ.get("TEST_MODE") == "1" 
        or os.environ.get("DEV_MODE") == "1" 
        or os.environ.get("METRCHECK_ENV") == "development"
        or getattr(settings, "ENVIRONMENT", "") == "development"
        or getattr(settings, "METRCHECK_DEMO_MODE", False)
    )
    if is_dev and not is_prod:
        dev_token = raw_token

    return {
        "message": f"Invitation resent to {norm_email}.",
        "username": target["username"],
        "dev_invitation_token": dev_token
    }


@admin_router.post("/users/{username}/suspend", response_model=UserOut)
async def admin_suspend_user(
    username: str,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: suspend account and immediately invalidate all active sessions."""
    client_ip = get_client_ip(request)
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target["username"].lower() == admin["username"].lower():
        raise HTTPException(status_code=400, detail="Cannot suspend your own administrator account.")

    if target["role"] == ROLE_ADMIN:
        admins = await list_users(role=ROLE_ADMIN)
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="Cannot suspend the last remaining administrator account.")

    ok = await suspend_user(target["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Could not suspend user.")

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=target["username"],
        event_type="ACCOUNT_SUSPENDED",
        details=f"Suspended {target['username']} (role: {target['role']})",
        ip_address=client_ip
    )

    refreshed = await get_user_by_username(target["username"])
    return _to_user_out(refreshed)


@admin_router.post("/users/{username}/reactivate", response_model=UserOut)
async def admin_reactivate_user(
    username: str,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: reactivate a suspended account."""
    client_ip = get_client_ip(request)
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get("status") != "SUSPENDED":
        raise HTTPException(status_code=400, detail="User account is not suspended.")

    ok = await reactivate_user(target["username"])
    if not ok:
        raise HTTPException(status_code=500, detail="Could not reactivate user.")

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=target["username"],
        event_type="ACCOUNT_REACTIVATED",
        details=f"Reactivated {target['username']} (role: {target['role']})",
        ip_address=client_ip
    )

    refreshed = await get_user_by_username(target["username"])
    return _to_user_out(refreshed)


@admin_router.post("/users/{username}/change-role", response_model=UserOut)
async def admin_change_role(
    username: str,
    req: ChangeRoleRequest,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: change role between AUDIT_OFFICER and ENFORCEMENT_OFFICER."""
    client_ip = get_client_ip(request)
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target["username"].lower() == admin["username"].lower():
        raise HTTPException(status_code=400, detail="Cannot change role of your own administrator account.")

    new_role = req.role.strip()
    if new_role not in (ROLE_AUDIT, ROLE_ENFORCEMENT):
        raise HTTPException(status_code=400, detail="Role can only be changed to AUDIT_OFFICER or ENFORCEMENT_OFFICER.")

    ok = await change_user_role(target["username"], new_role)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not change role.")

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=target["username"],
        event_type="ROLE_CHANGED",
        details=f"Changed role from {target['role']} to {new_role}",
        ip_address=client_ip
    )

    refreshed = await get_user_by_username(target["username"])
    return _to_user_out(refreshed)


@admin_router.delete("/users/{username}", status_code=204)
async def admin_delete_user(
    username: str,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: delete account or revoke pending invitation."""
    client_ip = get_client_ip(request)
    target = await get_user_by_username(username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target["username"].lower() == admin["username"].lower():
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")

    if target["role"] == ROLE_ADMIN:
        admins = await list_users(role=ROLE_ADMIN)
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last remaining administrator account.")

    ok = await delete_user(target["username"])
    if not ok:
        raise HTTPException(status_code=400, detail="Could not delete user.")

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=target["username"],
        event_type="ACCOUNT_DELETED",
        details=f"Deleted account {target['username']} (role: {target['role']}, status: {target.get('status')})",
        ip_address=client_ip
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/audit-logs")
async def admin_audit_logs(
    limit: int = 50,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: view account security audit logs."""
    return await get_account_audit_logs(limit=limit)


# ══════════════════════════════════════════════════════════════════════════
# OFFICER ACCESS REQUESTS (Public Submission & Status Check)
# ══════════════════════════════════════════════════════════════════════════

@officer_access_router.post("/requests", response_model=OfficerAccessRequestOut, status_code=status.HTTP_201_CREATED)
@router.post("/officer-requests", response_model=OfficerAccessRequestOut, status_code=status.HTTP_201_CREATED)
async def submit_officer_access_request(req: OfficerAccessRequestCreate, request: Request):
    """Public submission of an officer access request for Audit or Enforcement role.
    
    Security: Validates institutional credentials, ensures role is strictly AUDIT_OFFICER or
    ENFORCEMENT_OFFICER, enforces rate limits, and prevents duplicate pending submissions.
    """
    client_ip = get_client_ip(request)
    
    # Rate limit check
    allowed, rate_msg = check_register_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    requested_role = req.requested_role.strip()
    if requested_role not in (ROLE_AUDIT, ROLE_ENFORCEMENT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requested role must be AUDIT_OFFICER or ENFORCEMENT_OFFICER.",
        )

    norm_email = normalize_email(req.official_email)
    if not validate_email_format(norm_email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid official email address is required.")

    # Duplicate check for pending requests with same email and role
    pending_existing = await get_pending_officer_request_by_email_and_role(norm_email, requested_role)
    if pending_existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An access request for this officer type is already pending.",
        )

    # Active user check
    existing_user = await get_user_by_email(norm_email)
    if existing_user and existing_user.get("status") == "ACTIVE" and existing_user.get("role") == requested_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active officer account is already registered with this official email. Please log in directly.",
        )

    payload = req.model_dump()
    payload["official_email"] = norm_email
    payload["requested_role"] = requested_role

    created_req = await create_officer_access_request(payload)
    if not created_req:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not record officer access request.")

    await log_account_audit_event(
        actor_username=norm_email,
        target_username=norm_email,
        event_type="OFFICER_ACCESS_REQUESTED",
        details=f"Submitted {requested_role} access request ({created_req['request_id']}) from {req.department_organization}",
        ip_address=client_ip
    )

    return _to_officer_request_out(created_req)


@officer_access_router.get("/requests/{request_id}", response_model=OfficerAccessRequestPublicStatus)
@router.get("/officer-requests/{request_id}", response_model=OfficerAccessRequestPublicStatus)
async def get_officer_access_request_status(request_id: str):
    """Public status check for an officer access request using its non-sensitive request ID."""
    req_record = await get_officer_access_request_by_id(request_id.strip())
    if not req_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found.")

    status_str = req_record["status"]
    if status_str == "PENDING":
        msg = "Your access request is currently under review by system administrators."
    elif status_str == "APPROVED":
        msg = "Your access request has been approved. Please check your official email for the activation link."
    elif status_str == "REJECTED":
        msg = "Your access request was not approved."
    else:
        msg = f"Request status: {status_str}"

    return OfficerAccessRequestPublicStatus(
        request_id=req_record["request_id"],
        requested_role=req_record["requested_role"],
        role_label=ROLE_LABELS.get(req_record["requested_role"], req_record["requested_role"]),
        status=status_str,
        submitted_at=req_record["submitted_at"],
        reviewed_at=req_record.get("reviewed_at"),
        rejection_reason=req_record.get("rejection_reason") if status_str == "REJECTED" else None,
        message=msg
    )


# ══════════════════════════════════════════════════════════════════════════
# ADMIN OFFICER ACCESS REQUESTS GOVERNANCE (ADMIN ONLY)
# ══════════════════════════════════════════════════════════════════════════

@admin_router.get("/officer-requests", response_model=List[OfficerAccessRequestOut])
async def admin_list_officer_requests(
    status: Optional[str] = Query(default=None, description="Filter by PENDING, APPROVED, REJECTED, or ALL"),
    search: Optional[str] = Query(default=None, description="Search term across name, email, org, id"),
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: list officer access requests with optional status and text search filtering."""
    rows = await list_officer_access_requests(status_filter=status, search=search)
    return [_to_officer_request_out(r) for r in rows]


@admin_router.get("/officer-requests/{request_id}", response_model=OfficerAccessRequestOut)
async def admin_get_officer_request(
    request_id: str,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: inspect detailed submitted information for an officer access request."""
    row = await get_officer_access_request_by_id(request_id.strip())
    if not row:
        raise HTTPException(status_code=404, detail="Officer access request not found.")
    return _to_officer_request_out(row)


@admin_router.post("/officer-requests/{request_id}/approve", response_model=AdminApproveOfficerRequestResponse)
async def admin_approve_officer_request(
    request_id: str,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: approve a PENDING officer access request, provision the officer account in INVITED state,
    and generate a single-use 24-hour cryptographic activation token.
    """
    client_ip = get_client_ip(request)
    req_record = await get_officer_access_request_by_id(request_id.strip())
    if not req_record:
        raise HTTPException(status_code=404, detail="Officer access request not found.")

    if req_record.get("status") != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve request in '{req_record.get('status')}' status. Only PENDING requests can be approved."
        )

    target_role = req_record["requested_role"]
    if target_role not in (ROLE_AUDIT, ROLE_ENFORCEMENT):
        raise HTTPException(status_code=400, detail="Invalid officer role in access request.")

    norm_email = normalize_email(req_record["official_email"])
    existing_email_user = await get_user_by_email(norm_email)
    if existing_email_user:
        raise HTTPException(
            status_code=409,
            detail=f"An account with email '{norm_email}' already exists (Username: @{existing_email_user['username']})."
        )

    # Generate a clean, canonical unique officer username
    raw_ident = (req_record.get("employee_officer_id") or norm_email.split("@")[0]).strip()
    safe_slug = re.sub(r'[^a-zA-Z0-9_]', '', raw_ident.lower().replace("-", "_"))
    if not safe_slug:
        safe_slug = "officer"

    if target_role == ROLE_AUDIT:
        prefix = "audit_" if not safe_slug.startswith("audit_") else ""
        base_username = f"{prefix}{safe_slug}"
    else:
        prefix = "off_" if not safe_slug.startswith("off_") else ""
        base_username = f"{prefix}{safe_slug}"

    username = base_username
    counter = 1
    while await get_user_by_username(username):
        username = f"{base_username}_{counter}"
        counter += 1

    org_id = "org_ministry"
    org = await get_organization(org_id)
    if not org:
        await create_organization(id=org_id, name="Ministry of Consumer Affairs & Legal Metrology Directorate", org_type="REGULATOR", jurisdiction="National", status="ACTIVE")

    jurisdiction_str = f"{req_record.get('district_jurisdiction', '').strip()}, {req_record.get('state', '').strip()}".strip(", ")
    if not jurisdiction_str:
        jurisdiction_str = "National Directorate"

    raw_token, token_hash, expires_at = generate_invitation_token(expire_hours=24)
    ok = await create_invited_user(
        username=username,
        email=norm_email,
        role=target_role,
        full_name=req_record.get("full_name", "").strip(),
        jurisdiction=jurisdiction_str,
        token_hash=token_hash,
        expires_at=expires_at,
        organization_id=org_id
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Could not provision officer account in database.")

    # Mark request as APPROVED
    approved_ok = await approve_officer_access_request(request_id.strip(), admin["username"], username)
    if not approved_ok:
        raise HTTPException(status_code=500, detail="Could not update request status to APPROVED.")

    # Build activation URL
    configured_frontend = getattr(settings, "METRCHECK_FRONTEND_URL", "").strip()
    if configured_frontend:
        origin = configured_frontend.rstrip("/")
    else:
        base_url = str(request.base_url).rstrip("/")
        origin = request.headers.get("origin") or request.headers.get("referer") or base_url
        origin = origin.rstrip("/")
    activation_url = f"{origin}/activate?token={raw_token}"

    provider = get_delivery_provider()
    await provider.send_invitation_email(
        full_name=req_record.get("full_name", ""),
        username=username,
        role=target_role,
        raw_token=raw_token,
        activation_url=activation_url,
        email=norm_email
    )

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=username,
        event_type="OFFICER_REQUEST_APPROVED",
        details=f"Approved request {request_id}, provisioned {target_role} for {norm_email}",
        ip_address=client_ip
    )

    dev_token: Optional[str] = None
    is_prod = (
        os.environ.get("METRCHECK_ENV") == "production" 
        or os.environ.get("ENVIRONMENT") == "production"
        or getattr(settings, "ENVIRONMENT", "") == "production"
    )
    is_dev = (
        settings.TEST_MODE 
        or os.environ.get("TEST_MODE") == "1" 
        or os.environ.get("DEV_MODE") == "1" 
        or os.environ.get("METRCHECK_ENV") == "development"
        or getattr(settings, "ENVIRONMENT", "") == "development"
        or getattr(settings, "METRCHECK_DEMO_MODE", False)
    )
    if is_dev and not is_prod:
        dev_token = raw_token

    created_user = await get_user_by_username(username)
    return AdminApproveOfficerRequestResponse(
        message=f"Officer access request approved. Invitation sent to {norm_email}.",
        request_id=request_id.strip(),
        username=username,
        user=_to_user_out(created_user),
        dev_invitation_token=dev_token,
        activation_url=activation_url if dev_token else None
    )


@admin_router.post("/officer-requests/{request_id}/reject", response_model=OfficerAccessRequestOut)
async def admin_reject_officer_request(
    request_id: str,
    req: AdminRejectOfficerRequest,
    request: Request,
    admin: dict = Depends(require_roles(ROLE_ADMIN))
):
    """Admin-only: reject a PENDING officer access request with a recorded justification."""
    client_ip = get_client_ip(request)
    req_record = await get_officer_access_request_by_id(request_id.strip())
    if not req_record:
        raise HTTPException(status_code=404, detail="Officer access request not found.")

    if req_record.get("status") != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject request in '{req_record.get('status')}' status. Only PENDING requests can be rejected."
        )

    reason = req.rejection_reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required.")

    ok = await reject_officer_access_request(request_id.strip(), admin["username"], reason)
    if not ok:
        raise HTTPException(status_code=500, detail="Could not update request status to REJECTED.")

    await log_account_audit_event(
        actor_username=admin["username"],
        target_username=req_record.get("official_email", ""),
        event_type="OFFICER_REQUEST_REJECTED",
        details=f"Rejected request {request_id} ({req_record.get('requested_role')}). Reason: {reason}",
        ip_address=client_ip
    )

    updated = await get_officer_access_request_by_id(request_id.strip())
    return _to_officer_request_out(updated)