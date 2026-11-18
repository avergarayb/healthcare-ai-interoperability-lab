"""Closed demonstration hosts. A free-form public name is not a default."""

REALM = "demo-deploy"
CLIENT_ID = "lab-review-web"
ISSUER = "https://demo.localhost:18443/realms/demo-deploy"

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
