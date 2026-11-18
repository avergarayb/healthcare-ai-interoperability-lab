"""Write the PLATFORM-001 realm and local secrets outside the repository.

Passwords and tokens are not printed. This script does not start Keycloak and
does not touch the historical lab-review-iam realm.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

from profiles import BINDINGS, CLIENT_ID, ISSUER, REALM


def _outside_repository(run: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    if run.resolve().is_relative_to(repo.resolve()):
        raise SystemExit("run directory must stay outside the repository")


def _keep(path: Path, factory) -> str:
    if path.is_file() and path.stat().st_size > 0 and "--rotate" not in sys.argv:
        return path.read_text(encoding="utf-8").strip()
    value = factory()
    path.write_text(value, encoding="utf-8")
    return value


def main() -> None:
    raw = os.environ.get("PLATFORM_RUN_DIR")
    run = Path(raw) if raw else Path(os.environ.get("TEMP", "/tmp")) / "platform-001" / "run"
    run.mkdir(parents=True, exist_ok=True)
    _outside_repository(run)
    _keep(run / "federation-token", lambda: secrets.token_urlsafe(32))
    _keep(run / "boundary-token", lambda: secrets.token_urlsafe(32))
    _keep(run / "signing-secret", lambda: secrets.token_urlsafe(32))
    _keep(run / "bootstrap-password.txt", lambda: secrets.token_urlsafe(24))
    realm_path = run / "realm.json"
    password_path = run / "user-passwords.json"
    if realm_path.is_file() and password_path.is_file() and "--rotate" not in sys.argv:
        passwords = json.loads(password_path.read_text(encoding="utf-8"))
    else:
        passwords = {item["username"]: secrets.token_urlsafe(18) for item in BINDINGS}
        password_path.write_text(json.dumps(passwords), encoding="utf-8")
        realm_path.write_text(json.dumps(_realm(passwords)), encoding="utf-8")
    bindings = {
        "issuer": ISSUER,
        "bindings": [
            {
                "sub": item["sub"],
                "organization_id": item["organization_id"],
                "role": item["role"],
                "display_name": item["display_name"],
            }
            for item in BINDINGS
        ],
    }
    (run / "bindings.json").write_text(json.dumps(bindings), encoding="utf-8")
    print(run)


def _realm(passwords: dict) -> dict:
    redirects = [
        "http://127.0.0.1:18493/lab-review-iam/callback",
        "http://127.0.0.1:18495/lab-review-iam/callback",
    ]
    logouts = [
        "http://127.0.0.1:18493/lab-review-iam/login",
        "http://127.0.0.1:18495/lab-review-iam/login",
    ]
    return {
        "realm": REALM,
        "enabled": True,
        "sslRequired": "none",
        "registrationAllowed": False,
        "resetPasswordAllowed": False,
        "loginWithEmailAllowed": False,
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 3600,
        "defaultSignatureAlgorithm": "RS256",
        "requiredActions": [{
            "alias": "VERIFY_PROFILE",
            "name": "Verify Profile",
            "providerId": "VERIFY_PROFILE",
            "enabled": False,
            "defaultAction": False,
            "priority": 10,
        }],
        "roles": {"realm": [
            {"name": "clinical-reviewer"},
            {"name": "clinical-auditor"},
        ]},
        "clients": [{
            "clientId": CLIENT_ID,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": True,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "fullScopeAllowed": False,
            "redirectUris": redirects,
            "webOrigins": ["http://127.0.0.1:18493", "http://127.0.0.1:18495"],
            "attributes": {
                "pkce.code.challenge.method": "S256",
                "post.logout.redirect.uris": "##".join(logouts),
            },
        }],
        "users": [{
            "id": item["sub"],
            "username": item["username"],
            "enabled": True,
            "emailVerified": True,
            "firstName": item["display_name"].split()[0],
            "lastName": "Lab",
            "email": item["username"] + "@platform-001.invalid",
            "realmRoles": [item["role"]],
            "credentials": [{
                "type": "password",
                "value": passwords[item["username"]],
                "temporary": False,
            }],
        } for item in BINDINGS],
    }


if __name__ == "__main__":
    main()
