"""Synthetic critical-result index. A query cites a section or abstains."""
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "knowledge" / "critical-lab"


def retrieve(organization_id, on=None, query=""):
    tokens = [token for token in re.findall(r"[a-z0-9-]{4,}", str(query).lower())]
    if not tokens:
        return []
    today = on or date.today()
    found = []
    for path in sorted(ROOT.glob("*.md")):
        item = _parse(path)
        if item["organization"] != organization_id or item["status"] != "active":
            continue
        if not item["valid_from"] <= today <= item["valid_until"]:
            continue
        haystack = " ".join((item["topic"], item["id"], item["section"], item["text"])).lower()
        if not any(token in haystack for token in tokens):
            continue
        reference = f"{item['id']}@{item['version']}#{item['section']}"
        found.append({
            "id": item["id"],
            "version": item["version"],
            "section": item["section"],
            "reference": reference,
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
        "status": fields.get("status", ""),
        "topic": fields.get("topic", ""),
        "valid_from": date.fromisoformat(fields["valid_from"]),
        "valid_until": date.fromisoformat(fields["valid_until"]),
        "section": fields["section"],
        "text": body.strip(),
    }
