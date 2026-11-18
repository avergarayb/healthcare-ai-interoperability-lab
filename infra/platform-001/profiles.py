"""Closed demonstration profiles. A free-form country name is not a profile."""

PROFILES = {
    "pe-lab-demo-v1": {
        "host": "federation-pe",
        "published_port": 18481,
        "ai_port": 18493,
        "source": "pe-lab-demo",
        "organization_id": "org-pe-lab-demo",
        "patient_system": "https://lab.local/jurisdiction/pe/patient",
        "other_patient": "ES-PAT-001",
    },
    "es-lab-demo-v1": {
        "host": "federation-es",
        "published_port": 18482,
        "ai_port": 18495,
        "source": "es-lab-demo",
        "organization_id": "org-es-lab-demo",
        "patient_system": "https://lab.local/jurisdiction/es/patient",
        "other_patient": "PE-PAT-001",
    },
}

ISSUER = "http://127.0.0.1:18340/realms/platform-001"
CLIENT_ID = "lab-review-web"
REALM = "platform-001"

BINDINGS = (
    {
        "username": "reviewer-pe",
        "sub": "00000000-0000-4000-8000-0000000000a1",
        "organization_id": "org-pe-lab-demo",
        "role": "clinical-reviewer",
        "display_name": "Revisor Peru",
    },
    {
        "username": "auditor-pe",
        "sub": "00000000-0000-4000-8000-0000000000a2",
        "organization_id": "org-pe-lab-demo",
        "role": "clinical-auditor",
        "display_name": "Auditor Peru",
    },
    {
        "username": "reviewer-es",
        "sub": "00000000-0000-4000-8000-0000000000b1",
        "organization_id": "org-es-lab-demo",
        "role": "clinical-reviewer",
        "display_name": "Revisor Espana",
    },
    {
        "username": "reviewer-other",
        "sub": "00000000-0000-4000-8000-0000000000c1",
        "organization_id": "org-other-lab",
        "role": "clinical-reviewer",
        "display_name": "Revisor Otra",
    },
)


def require_profile(value: str) -> str:
    if value not in PROFILES:
        raise ValueError("profile_rejected")
    return value


def binding(username: str) -> dict:
    for item in BINDINGS:
        if item["username"] == username:
            return item
    raise KeyError(username)
