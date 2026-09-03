import logging
import secrets
from dataclasses import dataclass
from typing import Optional, Dict
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from backend.app.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


@dataclass
class AccountContext:
    account_id: str
    is_authenticated: bool


def _parse_token_account_mapping(expected_config: str) -> Dict[str, str]:
    """
    Parses configured API_AUTH_TOKEN strings.
    Supports either:
      - Single token: "secret_token" -> {"secret_token": "primary_personal_account"}
      - Comma-separated token:account pairs: "token_a:account_A,token_b:account_B"
    """
    mapping: Dict[str, str] = {}
    tokens = [t.strip() for t in expected_config.split(",") if t.strip()]
    for t in tokens:
        if ":" in t:
            tok, acc = t.split(":", 1)
            mapping[tok.strip()] = acc.strip()
        else:
            mapping[t] = "primary_personal_account"
    return mapping


def authorize_account_access(auth: AccountContext, target_account_id: Optional[str]) -> None:
    """
    Enforces strict tenant/account isolation:
    If a target account is specified, it MUST match the authenticated caller's account_id.
    Cross-account access attempts fail with HTTP 403 Forbidden.
    """
    if target_account_id and target_account_id.strip():
        clean_target = target_account_id.strip()
        if clean_target != auth.account_id:
            logger.warning(
                f"[SECURITY ISOLATION] Cross-account violation: Authenticated '{auth.account_id}' attempted to access/mutate '{clean_target}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Authorization failure: Account '{auth.account_id}' is not authorized to access or mutate account '{clean_target}'."
            )


async def verify_api_key(
    header_key: Optional[str] = Security(api_key_header),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> AccountContext:
    """
    Verifies the API key or Bearer token for state-mutating endpoints.
    Enforces fail-closed authentication server-side:
    If API_AUTH_TOKEN is not configured or missing, state mutations are strictly rejected with 401.
    """
    expected_config = (settings.api_auth_token or "").strip()

    # Fail-Closed: If server has no API_AUTH_TOKEN configured, mutations are disabled
    if not expected_config:
        logger.error("[SECURITY FAIL-CLOSED] State mutation rejected: API_AUTH_TOKEN is not configured on server.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="State mutations are disabled: API_AUTH_TOKEN is not configured on the server. Server fails closed.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract client token from either X-API-Key header or Authorization: Bearer <token>
    provided_token = None
    if header_key:
        provided_token = header_key.strip()
    elif bearer_token and bearer_token.credentials:
        provided_token = bearer_token.credentials.strip()

    if not provided_token:
        logger.warning("[SECURITY] Missing authentication credentials on state-mutating endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_map = _parse_token_account_mapping(expected_config)

    # Constant-time comparison across configured tokens to prevent timing attacks
    matched_account = None
    for valid_tok, bound_account in token_map.items():
        if secrets.compare_digest(provided_token, valid_tok):
            matched_account = bound_account
            break

    if not matched_account:
        logger.warning("[SECURITY] Invalid authentication token provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AccountContext(account_id=matched_account, is_authenticated=True)


async def verify_api_key_optional(
    header_key: Optional[str] = Security(api_key_header),
    bearer_token: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> Optional[AccountContext]:
    """
    Optional authentication for read endpoints that support scoped account views.
    If valid credentials are provided, returns AccountContext; otherwise returns None without error.
    """
    expected_config = (settings.api_auth_token or "").strip()
    if not expected_config:
        return None

    provided_token = None
    if header_key:
        provided_token = header_key.strip()
    elif bearer_token and bearer_token.credentials:
        provided_token = bearer_token.credentials.strip()

    if not provided_token:
        return None

    token_map = _parse_token_account_mapping(expected_config)
    for valid_tok, bound_account in token_map.items():
        if secrets.compare_digest(provided_token, valid_tok):
            return AccountContext(account_id=bound_account, is_authenticated=True)

    return None
