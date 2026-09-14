"""TRUST TRANSITION: untrusted request → trusted tenant context (CTL-004, CTL-005; ADR-002).

Tenant authority comes from exactly two sources:
  1. claims that the API edge has already verified (issuer, audience, signature, expiry, scope), found only at
     event["requestContext"]["authorizer"]["jwt"]["claims"];
  2. the tenant registry, read on every request, which must say the tenant exists and is ENABLED.

This module never reads the request body, query string, path, headers or question text. A caller can put
"tenant-b" in any of those places; it is ordinary untrusted content and cannot change the result below.
"""
from dataclasses import dataclass

from shared.reason_codes import (TENANT_CLAIM_MISSING, TENANT_DISABLED, TENANT_REGISTRY_UNAVAILABLE, TENANT_UNKNOWN,
                                 Denied)
from shared.registry import RegistryUnavailable
from shared.tenant_claims import parse_tenant_group_claim


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    user_id: str
    client_id: str
    issuer: str


def verified_claims(event):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        raise Denied(TENANT_CLAIM_MISSING, "no verified claims in the request context") from None
    if not isinstance(claims, dict):
        raise Denied(TENANT_CLAIM_MISSING, "verified claims are not a mapping")
    return claims


def resolve(event, registry, expected_client_id, expected_issuer):
    """Return the TenantContext for this request, or raise Denied. Fails closed on every doubt."""
    claims = verified_claims(event)
    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise Denied(TENANT_CLAIM_MISSING, "no subject")
    if claims.get("token_use") != "access":
        raise Denied(TENANT_CLAIM_MISSING, "not an access token")
    if claims.get("client_id") != expected_client_id or claims.get("iss") != expected_issuer:
        raise Denied(TENANT_CLAIM_MISSING, "token not issued for this application")

    tenant_id = parse_tenant_group_claim(claims.get("cognito:groups"))

    try:
        tenant = registry.get_tenant(tenant_id)
    except RegistryUnavailable as error:
        raise Denied(TENANT_REGISTRY_UNAVAILABLE, str(error)) from error
    if tenant is None:
        raise Denied(TENANT_UNKNOWN, "tenant not in registry")
    if tenant.get("status") != "ENABLED":
        raise Denied(TENANT_DISABLED, "tenant not enabled")
    return TenantContext(tenant_id=tenant_id, user_id=user_id, client_id=expected_client_id, issuer=expected_issuer)
