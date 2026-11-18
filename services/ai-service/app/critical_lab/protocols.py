"""Synthetic critical-result protocols. Retrieval cites a section or abstains."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "knowledge" / "critical-lab"
ACTIVE = (
    "critical-communication",
    "alert-acknowledgement",
    "internal-escalation",
    "laboratory-responsibilities",
    "corrected-results",
)


def retrieve(organization_id, on=None):
    today = on or date.today()
    found = []
    for path in sorted(ROOT.glob("*.md")):
        item = _parse(path)
        if item["organization"] != organization_id:
            continue
        if item["valid_from"] <= today <= item["valid_until"] and item["id"] in ACTIVE:
            found.append({
                "id": item["id"],
                "version": item["version"],
                "section": item["section"],
                "text": item["text"],
            })
    return found


def _parse(path):
    raw = path.read_text(encoding="utf-8")
    header, _, body = raw.partition("\n---\n")
    fields = {}
    for line in header.splitlines():
        if line.startswith("---") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return {
        "id": fields["id"],
        "version": fields["version"],
        "organization": fields["organization"],
        "valid_from": date.fromisoformat(fields["valid_from"]),
        "valid_until": date.fromisoformat(fields["valid_until"]),
        "section": fields["section"],
        "text": body.strip(),
    }
