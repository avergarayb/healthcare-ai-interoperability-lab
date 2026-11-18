"""Re-check role and organization denial on a review backup, not the live file."""
from __future__ import annotations

import json
import os
import sqlite3
import sys

from app.clinical_lab_summary.review import IamReviewer, ReviewError, decide, iam_principal_id


def main() -> None:
    path = sys.argv[1]
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        review_id = connection.execute("SELECT review_id FROM lab_summary_review").fetchone()[0]
    finally:
        connection.close()
    issuer = os.environ["DEMO_ISSUER"]
    reasons = {}
    try:
        IamReviewer(
            iam_principal_id(issuer, "00000000-0000-4000-8000-0000000000a2"),
            issuer, "00000000-0000-4000-8000-0000000000a2",
            "org-pe-lab-demo", "clinical-auditor", "session-auditor")
        reasons["auditor"] = "permitted"
    except ReviewError as error:
        reasons["auditor"] = error.reason
    other = IamReviewer(
        iam_principal_id(issuer, "00000000-0000-4000-8000-0000000000c1"),
        issuer, "00000000-0000-4000-8000-0000000000c1",
        "org-other-lab", "clinical-reviewer", "session-other")
    checks = [("other_organization", other)]
    for name, reviewer in checks:
        try:
            decide(path, review_id, reviewer, "rejected", "sintetica", "2026-11-18T00:00:00.000000Z")
            reasons[name] = "permitted"
        except ReviewError as error:
            reasons[name] = error.reason
    reasons["outcome"] = "passed" if reasons["auditor"] == "role_denied" and reasons["other_organization"] == "organization_denied" else "failed"
    print(json.dumps(reasons))
    if reasons["outcome"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()