"""Write DEMO-DEPLOY-001 secrets and a local test certificate outside Git.

Nothing printed by this script is a password, a token, or a key.
"""
from __future__ import annotations

import datetime
import json
import os
import secrets
import stat
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from profiles import BINDINGS, CLIENT_ID, ISSUER, REALM


HOSTS = ("demo.localhost", "pe.demo.localhost", "es.demo.localhost")


def _outside(run: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    if run.resolve().is_relative_to(repo.resolve()):
        raise SystemExit("run directory must stay outside the repository")


def _keep(path: Path, factory) -> str:
    if path.is_file() and path.stat().st_size > 0 and "--rotate" not in sys.argv:
        _tighten(path)
        return path.read_text(encoding="utf-8").strip()
    value = factory()
    path.write_text(value, encoding="utf-8")
    _tighten(path)
    return value


def _tighten(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        return


def _certificate(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    cert = directory / "cert.pem"
    key = directory / "key.pem"
    ca = directory / "ca.crt"
    if cert.is_file() and key.is_file() and ca.is_file() and "--rotate" not in sys.argv:
        return
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "demo.localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host) for host in HOSTS]),
            critical=False)
    )
    signed = builder.sign(private, hashes.SHA256())
    key.write_bytes(private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    pem = signed.public_bytes(serialization.Encoding.PEM)
    cert.write_bytes(pem)
    ca.write_bytes(pem)
    for path in (cert, key, ca):
        _tighten(path)


def _realm(passwords: dict) -> dict:
    redirects = [
        "https://pe.demo.localhost:18443/lab-review-iam/callback",
        "https://es.demo.localhost:18443/lab-review-iam/callback",
    ]
    logouts = [
        "https://pe.demo.localhost:18443/lab-review-iam/login",
        "https://es.demo.localhost:18443/lab-review-iam/login",
    ]
    return {
        "realm": REALM,
        "enabled": True,
        "sslRequired": "external",
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
            "webOrigins": [
                "https://pe.demo.localhost:18443",
                "https://es.demo.localhost:18443",
            ],
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
            "email": item["username"] + "@demo-deploy.invalid",
            "realmRoles": [item["role"]],
            "credentials": [{
                "type": "password",
                "value": passwords[item["username"]],
                "temporary": False,
            }],
        } for item in BINDINGS],
    }


def main() -> None:
    raw = os.environ.get("DEMO_RUN_DIR")
    run = Path(raw) if raw else Path(os.environ.get("TEMP", "/tmp")) / "demo-deploy-001" / "run"
    run.mkdir(parents=True, exist_ok=True)
    _outside(run)
    if os.environ.get("DEMO_MODE", "local") == "vm" and os.environ.get("DEMO_VM_AUTHORIZED") != "true":
        raise SystemExit("vm_not_authorized")
    _keep(run / "federation-token", lambda: secrets.token_urlsafe(32))
    _keep(run / "boundary-token", lambda: secrets.token_urlsafe(32))
    _keep(run / "signing-secret", lambda: secrets.token_urlsafe(32))
    _keep(run / "bootstrap-password.txt", lambda: secrets.token_urlsafe(24))
    _keep(run / "db-password.txt", lambda: secrets.token_urlsafe(24))
    _certificate(run / "certs")
    realm_path = run / "realm.json"
    password_path = run / "user-passwords.json"
    if realm_path.is_file() and password_path.is_file() and "--rotate" not in sys.argv:
        passwords = json.loads(password_path.read_text(encoding="utf-8"))
    else:
        passwords = {item["username"]: secrets.token_urlsafe(18) for item in BINDINGS}
        password_path.write_text(json.dumps(passwords), encoding="utf-8")
        _tighten(password_path)
        realm_path.write_text(json.dumps(_realm(passwords)), encoding="utf-8")
        _tighten(realm_path)
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
    _tighten(run / "bindings.json")
    print(run)


if __name__ == "__main__":
    main()
