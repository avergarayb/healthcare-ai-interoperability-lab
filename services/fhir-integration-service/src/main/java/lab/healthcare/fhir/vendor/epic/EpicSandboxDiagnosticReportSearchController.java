package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchOutcome;
import lab.healthcare.fhir.routing.FhirDiagnosticReportSearchResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for an authenticated DiagnosticReport search by Patient.
 * Not a clinical API and not a product UI.
 */
@RestController
public class EpicSandboxDiagnosticReportSearchController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxDiagnosticReportSearchController.class);

    private final EpicSandboxDiagnosticReportSearchService diagnosticReportSearchService;
    private final EpicIntegrationProfile profile;

    public EpicSandboxDiagnosticReportSearchController(
            EpicSandboxDiagnosticReportSearchService diagnosticReportSearchService, EpicIntegrationProfile profile) {
        this.diagnosticReportSearchService = diagnosticReportSearchService;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/diagnostic-report-search", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> diagnosticReportSearch() {
        FhirDiagnosticReportSearchResult result = diagnosticReportSearchService.searchDiagnosticReports(profile);
        log.info(
                "Epic authenticated DiagnosticReport search destination={} outcome={} status={} hasEntries={}",
                result.destination(),
                result.outcome(),
                result.httpStatus(),
                result.hasEntries());
        return ResponseEntity.status(httpStatus(result.outcome())).body(SmartLabPages.epicDiagnosticReport(result));
    }

    private static int httpStatus(FhirDiagnosticReportSearchOutcome outcome) {
        return switch (outcome) {
            case DIAGNOSTIC_REPORT_SEARCH_SUCCEEDED -> 200;
            case AUTHENTICATION_REQUIRED, AUTHENTICATION_REJECTED -> 401;
            case AUTHORIZATION_DENIED -> 403;
            case PATIENT_CONTEXT_NOT_CONFIGURED, CAPABILITY_UNSUPPORTED -> 409;
            case DEPENDENCY_FAILURE -> 502;
        };
    }
}
