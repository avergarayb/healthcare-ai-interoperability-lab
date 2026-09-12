package lab.healthcare.fhir.smart.web;

import lab.healthcare.fhir.routing.FhirConditionSearchOutcome;
import lab.healthcare.fhir.routing.FhirConditionSearchResult;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchOutcome;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchResult;
import lab.healthcare.fhir.routing.FhirObservationSearchOutcome;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;
import lab.healthcare.fhir.routing.FhirPatientReadOutcome;
import lab.healthcare.fhir.routing.FhirPatientReadResult;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;
import lab.healthcare.fhir.smart.SmartAuthorizationStart;
import lab.healthcare.fhir.smart.SmartTokenExchangeDiagnosis;
import lab.healthcare.fhir.smart.SmartTokenExchangeResult;

public final class SmartLabPages {

    private SmartLabPages() {
    }

    public static String start(SmartAuthorizationStart start) {
        String warning = start.advertisesConfidentialTokenAuth()
                ? "<p><strong>Discovery warning:</strong> token_endpoint_auth_methods_supported is "
                        + escape(String.join(", ", start.tokenEndpointAuthMethodsSupported()))
                        + " and does not include <code>none</code>. This lab still attempts public PKCE. "
                        + "If the token POST is rejected, the callback page will name the required confidential method. "
                        + "No client secret or JWT will be invented.</p>"
                : "<p>Discovered token_endpoint_auth_methods_supported: "
                        + (start.tokenEndpointAuthMethodsSupported().isEmpty()
                                ? "(undeclared)"
                                : escape(String.join(", ", start.tokenEndpointAuthMethodsSupported())))
                        + "</p>";
        return page(
                "SMART start",
                """
                <p>Open this authorization URL in a browser, complete the sandbox login, then wait for the redirect to
                <code>/smart/callback</code>.</p>
                <p><a href="%s">%s</a></p>
                <p>destination=%s expiresAt=%s</p>
                %s
                """
                        .formatted(
                                escape(start.authorizationUrl()),
                                escape(start.authorizationUrl()),
                                escape(start.destination()),
                                escape(String.valueOf(start.expiresAt())),
                                warning));
    }

    public static String result(SmartTokenExchangeResult result) {
        SmartTokenExchangeDiagnosis diagnosis = result.diagnosis();
        if (result.succeeded()) {
            return page(
                    "SMART token exchange succeeded",
                    """
                    <p>Result A: access token issued. The token value is not shown.</p>
                    <pre>%s</pre>
                    <p>hasAccessToken=true expiresAt=%s hasScope=%s hasPatient=%s</p>
                    """
                            .formatted(
                                    escape(diagnosis.toString()),
                                    escape(String.valueOf(result.token().expiresAt())),
                                    result.token().scope() != null && !result.token().scope().isBlank(),
                                    result.token().patient() != null && !result.token().patient().isBlank()));
        }
        return page(
                "SMART token exchange diagnosis",
                """
                <p>Result B: authorization callback was received and the token endpoint rejected public PKCE,
                or authorization failed before exchange.</p>
                <pre>%s</pre>
                <p>incompatibility=%s</p>
                <p>nextArchitecturalChange=%s</p>
                """
                        .formatted(
                                escape(diagnosis.toString()),
                                escape(diagnosis.incompatibility().name()),
                                escape(diagnosis.nextArchitecturalChange())));
    }

    public static String error(String title, String detail) {
        return page(title, "<p>" + escape(detail) + "</p>");
    }

    public static String instructions() {
        return page(
                "Oracle Health SMART lab",
                """
                <ol>
                  <li>Configure a local <code>.env</code> from <code>.env.example</code> (never commit it).</li>
                  <li>Open <a href="/oracle/sandbox/smart/start">/oracle/sandbox/smart/start</a> to discover SMART and get the authorization URL.</li>
                  <li>Log in at Oracle in the browser.</li>
                  <li>Oracle redirects to <code>/smart/callback</code>. This process validates state and attempts token exchange.</li>
                  <li>After a token is issued, open <a href="/oracle/sandbox/fhir/patient-search">/oracle/sandbox/fhir/patient-search</a> for a safe authenticated Patient search diagnosis. The page does not show the token or Patient JSON.</li>
                  <li>With <code>ORACLE_HEALTH_SANDBOX_PATIENT_ID</code> set, open <a href="/oracle/sandbox/fhir/patient">/oracle/sandbox/fhir/patient</a> for a controlled Patient read diagnosis. The page does not show Patient JSON.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/condition-search">/oracle/sandbox/fhir/condition-search</a> for a safe authenticated Condition search. The page does not show Condition JSON.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/observation-search">/oracle/sandbox/fhir/observation-search</a> for a safe authenticated Observation search. The page does not show Observation JSON.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/diagnostic-report-search">/oracle/sandbox/fhir/diagnostic-report-search</a> for a safe authenticated DiagnosticReport search. The page does not show DiagnosticReport JSON.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/medication-request-search">/oracle/sandbox/fhir/medication-request-search</a> for a safe authenticated MedicationRequest search. The page does not show MedicationRequest JSON.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/clinical-snapshot">/oracle/sandbox/fhir/clinical-snapshot</a> for a controlled clinical snapshot. The page shows only status and counts.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/clinical-projection">/oracle/sandbox/fhir/clinical-projection</a> for a controlled projection. The page shows only status, received/retained counts, and truncated. It does not show projected field values.</li>
                  <li>Then open <a href="/oracle/sandbox/fhir/model-boundary">/oracle/sandbox/fhir/model-boundary</a> for the vendor-neutral model boundary contract. The page shows only version, outcome, status, and counts. It does not show record values and does not call a model.</li>
                  <li>A machine consumer uses <code>GET /api/model-boundary/v1</code> for the exact v1 JSON contract. That is not this HTML page and not an agent.</li>
                  <li>Then open <a href="/lab/agent-stub">/lab/agent-stub</a> for the contract-consuming stub. The page shows only observation counts and <code>modelCalled=false</code>. JSON: <code>GET /api/agent-stub/v1</code>.</li>
                  <li>Epic sandbox SMART (Task 046) starts at <a href="/epic/sandbox/smart/start">/epic/sandbox/smart/start</a>. It issues a token only. It does not read Patient.</li>
                  <li>Epic public capability discovery (Task 047) is <a href="/epic/sandbox/fhir/capabilities">/epic/sandbox/fhir/capabilities</a>. It does not use the SMART token and does not read Patient.</li>
                  <li>With a SMART token and <code>EPIC_SANDBOX_PATIENT_ID</code> set, open
                  <a href="/epic/sandbox/fhir/patient">/epic/sandbox/fhir/patient</a> for a controlled Patient read.
                  The page does not show the token, Patient ID, or Patient JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/condition-search">/epic/sandbox/fhir/condition-search</a>
                  for a safe authenticated Condition search. The page does not show Condition JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/observation-search">/epic/sandbox/fhir/observation-search</a>
                  for a safe authenticated Observation search. The page does not show Observation JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/diagnostic-report-search">/epic/sandbox/fhir/diagnostic-report-search</a>
                  for a safe authenticated DiagnosticReport search. The page does not show DiagnosticReport JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/clinical-snapshot">/epic/sandbox/fhir/clinical-snapshot</a>
                  for a controlled clinical snapshot. The page shows only status and counts.</li>
                </ol>
                """);
    }

    public static String epicInstructions() {
        return page(
                "Epic SMART lab",
                """
                <ol>
                  <li>Configure Epic placeholders in the local <code>.env</code> (never commit real client IDs).</li>
                  <li>Set <code>EPIC_SANDBOX_ENABLED=true</code> and restart the process.</li>
                  <li>Open <a href="/epic/sandbox/smart/start">/epic/sandbox/smart/start</a> to discover SMART and get the authorization URL.</li>
                  <li>Log in at the Epic sandbox in the browser.</li>
                  <li>Epic redirects to <code>/smart/callback</code>. This process validates state and attempts token exchange.</li>
                  <li>Task 046 stops after a token is issued. It does not read Patient.</li>
                  <li>Open <a href="/epic/sandbox/fhir/capabilities">/epic/sandbox/fhir/capabilities</a> for a public
                  <code>GET /metadata</code>. That page does not use the SMART token and does not read Patient.</li>
                  <li>With a SMART token and <code>EPIC_SANDBOX_PATIENT_ID</code> set, open
                  <a href="/epic/sandbox/fhir/patient">/epic/sandbox/fhir/patient</a> for a controlled Patient read.
                  The page does not show the token, Patient ID, or Patient JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/condition-search">/epic/sandbox/fhir/condition-search</a>
                  for a safe authenticated Condition search. The page does not show Condition JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/observation-search">/epic/sandbox/fhir/observation-search</a>
                  for a safe authenticated Observation search. The page does not show Observation JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/diagnostic-report-search">/epic/sandbox/fhir/diagnostic-report-search</a>
                  for a safe authenticated DiagnosticReport search. The page does not show DiagnosticReport JSON.</li>
                  <li>Then open <a href="/epic/sandbox/fhir/clinical-snapshot">/epic/sandbox/fhir/clinical-snapshot</a>
                  for a controlled clinical snapshot. The page shows only status and counts.</li>
                </ol>
                """);
    }

    public static String epicCapabilities(
            String status,
            Integer httpStatus,
            String destination,
            String fhirVersion,
            int resourceTypes,
            String detail) {
        String extra = detail == null || detail.isBlank() ? "" : "<p>detail=" + escape(detail) + "</p>";
        return page(
                "Epic sandbox capability discovery",
                """
                <p>Public FHIR CapabilityStatement discovery. No token and no Patient JSON are shown.</p>
                <pre>%s</pre>
                %s
                """
                        .formatted(
                                escape("status="
                                        + nullToEmpty(status)
                                        + "\nhttpStatus="
                                        + (httpStatus == null ? "" : httpStatus)
                                        + "\ndestination="
                                        + nullToEmpty(destination)
                                        + "\nfhirVersion="
                                        + nullToEmpty(fhirVersion)
                                        + "\nresourceTypes="
                                        + resourceTypes),
                                extra));
    }

    public static String epicPatient(FhirPatientReadResult result) {
        boolean succeeded = result.outcome() == FhirPatientReadOutcome.PATIENT_READ_SUCCEEDED;
        String extra = result.detail() == null || result.detail().isBlank()
                ? ""
                : "<p>detail=" + escape(result.detail()) + "</p>";
        return page(
                "Epic sandbox controlled Patient read",
                """
                <p>Controlled authenticated Patient read. No token, Patient ID, or Patient JSON are shown.</p>
                <pre>%s</pre>
                %s
                """
                        .formatted(
                                escape("status="
                                        + (succeeded ? "SUCCESS" : "FAILED")
                                        + "\nhttpStatus="
                                        + (result.httpStatus() == null ? "" : result.httpStatus())
                                        + "\ndestination="
                                        + nullToEmpty(result.destination())
                                        + "\npatientRead="
                                        + (succeeded ? "SUCCEEDED" : result.outcome().name())
                                        + "\ncontextSource="
                                        + (result.contextSource() == null ? "" : result.contextSource().name())
                                        + "\nhasPatientContext="
                                        + result.hasPatientContext()),
                                extra));
    }

    public static String epicCondition(FhirConditionSearchResult result) {
        boolean succeeded = result.outcome() == FhirConditionSearchOutcome.CONDITION_SEARCH_SUCCEEDED;
        String extra = result.detail() == null || result.detail().isBlank()
                ? ""
                : "<p>detail=" + escape(result.detail()) + "</p>";
        return page(
                "Epic sandbox authenticated Condition search",
                """
                <p>Authenticated Condition search by the configured Patient. No token, Patient ID, or Condition JSON are shown.</p>
                <pre>%s</pre>
                %s
                """
                        .formatted(
                                escape("status="
                                        + (succeeded ? "SUCCESS" : "FAILED")
                                        + "\nhttpStatus="
                                        + (result.httpStatus() == null ? "" : result.httpStatus())
                                        + "\ndestination="
                                        + nullToEmpty(result.destination())
                                        + "\nconditionSearch="
                                        + (succeeded ? "SUCCEEDED" : result.outcome().name())
                                        + "\nresourceType="
                                        + nullToEmpty(result.resourceType())
                                        + "\ncontextSource="
                                        + (result.contextSource() == null ? "" : result.contextSource().name())
                                        + "\nhasPatientContext="
                                        + result.hasPatientContext()
                                        + "\nhasEntries="
                                        + result.hasEntries()),
                                extra));
    }

    public static String epicObservation(FhirObservationSearchResult result) {
        boolean succeeded = result.outcome() == FhirObservationSearchOutcome.OBSERVATION_SEARCH_SUCCEEDED;
        String extra = result.detail() == null || result.detail().isBlank()
                ? ""
                : "<p>detail=" + escape(result.detail()) + "</p>";
        return page(
                "Epic sandbox authenticated Observation search",
                """
                <p>Authenticated Observation search by the configured Patient. No token, Patient ID, or Observation JSON are shown.</p>
                <pre>%s</pre>
                %s
                """
                        .formatted(
                                escape("status="
                                        + (succeeded ? "SUCCESS" : "FAILED")
                                        + "\nhttpStatus="
                                        + (result.httpStatus() == null ? "" : result.httpStatus())
                                        + "\ndestination="
                                        + nullToEmpty(result.destination())
                                        + "\nobservationSearch="
                                        + (succeeded ? "SUCCEEDED" : result.outcome().name())
                                        + "\nresourceType="
                                        + nullToEmpty(result.resourceType())
                                        + "\ncontextSource="
                                        + (result.contextSource() == null ? "" : result.contextSource().name())
                                        + "\nhasPatientContext="
                                        + result.hasPatientContext()
                                        + "\nhasEntries="
                                        + result.hasEntries()),
                                extra));
    }

    public static String epicDiagnosticReport(FhirDiagnosticReportSearchResult result) {
        boolean succeeded = result.outcome() == FhirDiagnosticReportSearchOutcome.DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED;
        String extra = result.detail() == null || result.detail().isBlank()
                ? ""
                : "<p>detail=" + escape(result.detail()) + "</p>";
        return page(
                "Epic sandbox authenticated DiagnosticReport search",
                """
                <p>Authenticated DiagnosticReport search by the configured Patient. No token, Patient ID, or DiagnosticReport JSON are shown.</p>
                <pre>%s</pre>
                %s
                """
                        .formatted(
                                escape("status="
                                        + (succeeded ? "SUCCESS" : "FAILED")
                                        + "\nhttpStatus="
                                        + (result.httpStatus() == null ? "" : result.httpStatus())
                                        + "\ndestination="
                                        + nullToEmpty(result.destination())
                                        + "\ndiagnosticReportSearch="
                                        + (succeeded ? "SUCCEEDED" : result.outcome().name())
                                        + "\nresourceType="
                                        + nullToEmpty(result.resourceType())
                                        + "\ncontextSource="
                                        + (result.contextSource() == null ? "" : result.contextSource().name())
                                        + "\nhasPatientContext="
                                        + result.hasPatientContext()
                                        + "\nhasEntries="
                                        + result.hasEntries()),
                                extra));
    }

    public static String epicClinicalSnapshot(ClinicalSnapshotResult result) {
        boolean succeeded = result.outcome() == ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE
                || result.outcome() == ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL;
        String snapshot = switch (result.outcome()) {
            case SNAPSHOT_COMPLETE -> "SUCCEEDED";
            case SNAPSHOT_PARTIAL -> "PARTIAL";
            default -> result.outcome().name();
        };
        boolean hasClinicalData = positive(result.conditionCount())
                || positive(result.observationCount())
                || positive(result.diagnosticReportCount());
        String extra = result.detail() == null || result.detail().isBlank()
                ? ""
                : "<p>detail=" + escape(result.detail()) + "</p>";
        return page(
                "Epic sandbox controlled clinical snapshot",
                """
                <p>Controlled clinical snapshot by the configured Patient. No token, Patient ID, or FHIR JSON are shown.</p>
                <pre>%s</pre>
                %s
                """
                        .formatted(
                                escape("status="
                                        + (succeeded ? "SUCCESS" : "FAILED")
                                        + "\nhttpStatus="
                                        + (succeeded ? "200" : "")
                                        + "\ndestination="
                                        + nullToEmpty(result.destination())
                                        + "\nclinicalSnapshot="
                                        + snapshot
                                        + "\npatientRead="
                                        + statusName(result.patientStatus())
                                        + "\nconditionSearch="
                                        + statusName(result.conditionStatus())
                                        + "\nobservationSearch="
                                        + statusName(result.observationStatus())
                                        + "\ndiagnosticReportSearch="
                                        + statusName(result.diagnosticReportStatus())
                                        + "\nhasClinicalData="
                                        + hasClinicalData
                                        + "\ncontextSource="
                                        + (result.contextSource() == null ? "" : result.contextSource().name())
                                        + "\nconditionCount="
                                        + nullToEmptyCount(result.conditionCount())
                                        + "\nobservationCount="
                                        + nullToEmptyCount(result.observationCount())
                                        + "\ndiagnosticReportCount="
                                        + nullToEmptyCount(result.diagnosticReportCount())),
                                extra));
    }

    private static boolean positive(Integer count) {
        return count != null && count > 0;
    }

    private static String statusName(ClinicalSnapshotResourceStatus status) {
        if (status == null) {
            return "";
        }
        return status == ClinicalSnapshotResourceStatus.SUCCESS ? "SUCCEEDED" : status.name();
    }

    private static String nullToEmptyCount(Integer count) {
        return count == null ? "" : count.toString();
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private static String page(String title, String body) {
        return """
                <!DOCTYPE html>
                <html lang="en"><head><meta charset="utf-8"><title>%s</title></head>
                <body>
                <h1>%s</h1>
                %s
                </body></html>
                """
                .formatted(escape(title), escape(title), body);
    }

    private static String escape(String value) {
        if (value == null) {
            return "";
        }
        return value.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;");
    }
}
