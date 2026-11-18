"""Read an isolated backup. Does not open the live databases."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def _open(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"missing:{path.name}")
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)


def _review(path: Path) -> dict:
    connection = _open(path)
    try:
        decision = connection.execute(
            "SELECT decision, organization_id, role FROM lab_summary_decision "
            "JOIN lab_summary_decision_identity USING (review_id)"
        ).fetchone()
        evidence = connection.execute(
            "SELECT organization_id, code, ucum_code, absolute_difference, direction "
            "FROM lab_summary_longitudinal_evidence"
        ).fetchone()
        audits = connection.execute("SELECT count(*) FROM lab_summary_decision_audit").fetchone()[0]
    finally:
        connection.close()
    if decision is None or evidence is None or audits < 1:
        raise SystemExit("review_incomplete")
    return {
        "decision": decision[0],
        "organization": decision[1],
        "role": decision[2],
        "evidence_organization": evidence[0],
        "code": evidence[1],
        "unit": evidence[2],
        "difference": evidence[3],
        "direction": evidence[4],
        "decision_audits": audits,
    }


def _ledger(path: Path) -> dict:
    connection = _open(path)
    try:
        version = connection.execute("SELECT schema_version FROM aip_store WHERE singleton=1").fetchone()
        rows = connection.execute(
            "SELECT authorization_id, status FROM aip_remote_execution_reservation"
        ).fetchall()
    finally:
        connection.close()
    found = {row[0]: row[1] for row in rows}
    return {"schema": None if version is None else int(version[0]), "reservations": found}


def _audit(path: Path) -> int:
    connection = _open(path)
    try:
        return int(connection.execute("SELECT count(*) FROM federation_security_audit_events").fetchone()[0])
    finally:
        connection.close()


def main() -> None:
    root = Path(sys.argv[1])
    peru = _review(root / "pe-review" / "lab-summary.sqlite3")
    spain = _review(root / "es-review" / "lab-summary.sqlite3")
    pe_ledger = _ledger(root / "pe-ledger" / "processing.sqlite3")
    es_ledger = _ledger(root / "es-ledger" / "processing.sqlite3")
    report = {
        "peru_review": peru,
        "spain_review": spain,
        "peru_ledger": pe_ledger,
        "spain_ledger": es_ledger,
        "peru_federation_audit": _audit(root / "pe-federation-audit" / "security-audit.sqlite"),
        "spain_federation_audit": _audit(root / "es-federation-audit" / "security-audit.sqlite"),
    }
    ok = (
        peru["decision"] == "approved" and peru["organization"] == "org-pe-lab-demo"
        and peru["difference"] == "+0.6" and peru["role"] == "clinical-reviewer"
        and spain["decision"] == "approved" and spain["organization"] == "org-es-lab-demo"
        and spain["difference"] == "-5" and spain["role"] == "clinical-reviewer"
        and pe_ledger["schema"] == 9 and es_ledger["schema"] == 9
        and pe_ledger["reservations"].get("pe-longitudinal-001") == "consumed"
        and pe_ledger["reservations"].get("linux-held-001") == "held"
        and es_ledger["reservations"].get("es-longitudinal-001") == "consumed"
        and es_ledger["reservations"].get("linux-held-001") == "held"
        and report["peru_federation_audit"] >= 1 and report["spain_federation_audit"] >= 1
    )
    report["outcome"] = "passed" if ok else "failed"
    print(json.dumps(report, ensure_ascii=True))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
