"""Write a local Keycloak realm outside the repository and start it.

Passwords stay in the run directory. They are not printed and not committed.
"""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

PORT = "18294"
ORIGIN = f"http://127.0.0.1:{PORT}"
ISSUER = ORIGIN + "/realms/lab-review-iam"
USERS = (
    ("reviewer-a", "00000000-0000-4000-8000-0000000000a1", "org-lab-a", "clinical-reviewer", "Reviewer A", []),
    ("auditor-a", "00000000-0000-4000-8000-0000000000a2", "org-lab-a", "clinical-auditor", "Auditor A", []),
    ("admin-a", "00000000-0000-4000-8000-0000000000a3", "org-lab-a", "clinical-admin", "Admin A", ["read"]),
    ("reviewer-b", "00000000-0000-4000-8000-0000000000b1", "org-lab-b", "clinical-reviewer", "Reviewer B", []),
)


def main():
    run = Path(os.environ.get("LAB_REVIEW_IAM_RUN_DIR", r"C:\Temp\lab-review-iam\run"))
    run.mkdir(parents=True, exist_ok=True)
    passwords = {name: secrets.token_urlsafe(18) for name, *_rest in USERS}
    (run / "bootstrap-password.txt").write_text(secrets.token_urlsafe(24), encoding="utf-8")
    (run / "user-passwords.json").write_text(json.dumps(passwords), encoding="utf-8")
    realm = {
        "realm": "lab-review-iam",
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
        "clients": [{
            "clientId": "lab-review-web",
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": True,
            "standardFlowEnabled": True,
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": False,
            "serviceAccountsEnabled": False,
            "fullScopeAllowed": False,
            "redirectUris": ["http://127.0.0.1:18293/lab-review-iam/callback"],
            "webOrigins": ["http://127.0.0.1:18293"],
            "attributes": {
                "pkce.code.challenge.method": "S256",
                "post.logout.redirect.uris": "http://127.0.0.1:18293/lab-review-iam/login",
            },
        }],
        "users": [{
            "id": user_id,
            "username": name,
            "enabled": True,
            "emailVerified": True,
            "firstName": name.split("-")[0],
            "lastName": "Lab",
            "email": name + "@lab-review-iam.invalid",
            "credentials": [{"type": "password", "value": passwords[name], "temporary": False}],
        } for name, user_id, *_rest in USERS],
    }
    (run / "realm.json").write_text(json.dumps(realm), encoding="utf-8")
    bindings = {
        "issuer": ISSUER,
        "bindings": [{
            "sub": user_id,
            "organization_id": organization,
            "role": role,
            "display_name": display,
            **({"grants": grants} if grants else {}),
        } for _name, user_id, organization, role, display, grants in USERS],
    }
    (run / "bindings.json").write_text(json.dumps(bindings), encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "LAB_REVIEW_IAM_PROJECT": "lab-review-iam",
        "LAB_REVIEW_IAM_ORIGIN": ORIGIN,
        "LAB_REVIEW_IAM_PORT": PORT,
        "LAB_REVIEW_IAM_RUN_DIR": str(run),
    })
    compose = Path(__file__).with_name("compose.yaml")
    if "--up" in sys.argv:
        subprocess.run(
            ["docker", "compose", "-f", str(compose), "up", "-d"],
            check=True, env=env)
    print(run)


if __name__ == "__main__":
    main()
