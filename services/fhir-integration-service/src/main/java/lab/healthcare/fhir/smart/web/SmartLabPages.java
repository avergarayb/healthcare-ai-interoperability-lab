package lab.healthcare.fhir.smart.web;

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
                        + "If Oracle rejects the token POST, the callback page will name the required confidential method. "
                        + "No client secret or JWT will be invented.</p>"
                : "<p>Discovered token_endpoint_auth_methods_supported: "
                        + (start.tokenEndpointAuthMethodsSupported().isEmpty()
                                ? "(undeclared)"
                                : escape(String.join(", ", start.tokenEndpointAuthMethodsSupported())))
                        + "</p>";
        return page(
                "Oracle Health SMART start",
                """
                <p>Open this authorization URL in a browser, complete Oracle login, then wait for the redirect to
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
                </ol>
                """);
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
