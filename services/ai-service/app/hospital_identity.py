"""Delegated human authority for a hospital decision.

The service token only proves that Mini HIS called this process. The access
token, audience hospital-ai, proves the person and the permission. An ID token
issued to the web client is not an access token. Organization and role come
from the server binding and must also be in the signed access token.
"""
import json
from dataclasses import dataclass
from importlib.resources import files

import jwt
from jwt import PyJWKClient


class HospitalRejected(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class HospitalIdentity:
    username: str
    organization_id: str
    role: str
    issuer: str
    subject: str

    @property
    def session_id(self):
        return "oidc-" + self.subject.replace("-", "")[:20]


RESOURCE_AUDIENCE = "hospital-ai"
_AUTHORIZED_PARTIES = {"mini-his-web", "mini-lis-web"}


def bindings():
    return json.loads(files("app").joinpath("hospital_bindings.json").read_text(encoding="utf-8"))


def bearer(headers):
    """Read one access token. An identity header from the browser is ignored."""
    value = headers.get("authorization", "")
    if not isinstance(value, str) or not value.startswith("Bearer ") or value.count(" ") != 1:
        return ""
    token = value[7:]
    if token.count(".") != 2 or len(token) > 4000:
        return ""
    return token


def verify_token(token, *, issuer, audience, bindings_map, key=None, jwks_uri=""):
    if audience != RESOURCE_AUDIENCE:
        raise HospitalRejected("invalid_token", 401)
    if not isinstance(token, str) or token.count(".") != 2 or len(token) > 4000:
        raise HospitalRejected("invalid_token", 401)
    if not issuer.startswith("http://127.0.0.1:") and not issuer.startswith("https://"):
        raise HospitalRejected("invalid_token", 401)
    try:
        if key is None:
            if not jwks_uri.startswith(issuer + "/"):
                raise HospitalRejected("identity_unavailable", 503)
            key = PyJWKClient(jwks_uri, timeout=3).get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=audience, issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=0)
    except HospitalRejected:
        raise
    except jwt.exceptions.PyJWKClientError:
        raise HospitalRejected("identity_unavailable", 503) from None
    except (jwt.exceptions.InvalidTokenError, jwt.exceptions.PyJWTError):
        raise HospitalRejected("invalid_token", 401) from None
    if claims.get("typ") != "Bearer" or claims.get("azp") not in _AUTHORIZED_PARTIES:
        raise HospitalRejected("invalid_token", 401)
    username = claims.get("preferred_username")
    bound = bindings_map.get(username) if isinstance(username, str) else None
    if bound is None or claims.get("organization") != bound.get("organization"):
        raise HospitalRejected("organization_denied", 403)
    roles = (claims.get("realm_access") or {}).get("roles") if isinstance(claims.get("realm_access"), dict) else None
    if not isinstance(roles, list) or bound.get("role") not in roles:
        raise HospitalRejected("role_denied", 403)
    subject = claims.get("sub")
    if not isinstance(subject, str) or subject == "":
        raise HospitalRejected("invalid_token", 401)
    return HospitalIdentity(username, bound["organization"], bound["role"], issuer, subject)


def persistent_actor(actor_id, organization_id):
    """Actors the discharge record may store. The browser does not choose them."""
    if organization_id != "org-mini-his" or not isinstance(actor_id, str):
        return False
    if actor_id == "clinica":
        return True
    bound = bindings().get(actor_id)
    return (
        isinstance(bound, dict)
        and bound.get("organization") == organization_id
        and bound.get("role") in {"clinician", "clinical-reviewer"})


def gate(headers, settings, allowed, *, key=None):
    identity = authority(headers, settings, key=key)
    if isinstance(identity, dict):
        return identity
    if identity is not None and identity.role not in allowed:
        return {"error": "role_denied", "status": 403}
    return identity


def authority(headers, settings, *, key=None):
    """Return the identity, or a response dict when the human token is required."""
    if not settings.hospital_oidc_required:
        return None
    token = bearer(headers)
    if token == "":
        return {"error": "unauthorized", "status": 401}
    try:
        return verify_token(
            token, issuer=settings.hospital_oidc_issuer, audience=settings.hospital_oidc_audience,
            bindings_map=bindings(), key=key, jwks_uri=settings.hospital_oidc_jwks_uri)
    except HospitalRejected as error:
        return {"error": error.code, "status": error.status}
