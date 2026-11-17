"""Closed policy for one synthetic lab summary. It does not authorize vacation-days."""

OPERATION_ID = "lab-result-summary-v1"
POLICY_REF = "lab-result-summary-policy-v1"
DEPLOYMENT_ID = "gemini-sdk-a"
PURPOSE = "professional-lab-review"
CLASSIFICATION = "synthetic-clinical"
PATIENT_ID = "MHS-PAT-001"
SOURCES = frozenset({"mini-his", "mini-lis"})
RESOURCE_TYPES = frozenset({"Observation", "DiagnosticReport"})
