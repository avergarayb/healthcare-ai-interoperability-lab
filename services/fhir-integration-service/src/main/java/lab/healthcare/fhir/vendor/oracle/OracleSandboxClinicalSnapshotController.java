package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for a controlled clinical snapshot. Not a clinical
 * API and not a product UI.
 */
@RestController
public class OracleSandboxClinicalSnapshotController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxClinicalSnapshotController.class);

    private final OracleSandboxClinicalSnapshotService snapshotService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxClinicalSnapshotController(
            OracleSandboxClinicalSnapshotService snapshotService,
            OracleHealthIntegrationProfile profile) {
        this.snapshotService = snapshotService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/clinical-snapshot", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> clinicalSnapshot() {
        ClinicalSnapshotResult result = snapshotService.assemble(profile);
        log.info(
                "Oracle controlled clinical snapshot destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={} medicationRequests={}",
                result.destination(),
                result.outcome(),
                result.patientStatus(),
                result.conditionStatus(),
                result.observationStatus(),
                result.diagnosticReportStatus(),
                result.medicationRequestStatus());
        return ResponseEntity.status(httpStatus(result.outcome())).body(page(result));
    }

    private static int httpStatus(ClinicalSnapshotOutcome outcome) {
        return switch (outcome) {
            case SNAPSHOT_COMPLETE, SNAPSHOT_PARTIAL -> 200;
            case AUTHENTICATION_REQUIRED -> 401;
            case PATIENT_CONTEXT_NOT_CONFIGURED -> 409;
            case SNAPSHOT_UNAVAILABLE -> 502;
        };
    }

    private static String page(ClinicalSnapshotResult result) {
        return SmartLabPages.error(
                "Oracle Health controlled clinical snapshot",
                "outcome=" + result.outcome()
                        + " destination=" + result.destination()
                        + " contextSource=" + result.contextSource()
                        + " patient=" + result.patientStatus()
                        + " conditions=" + result.conditionStatus()
                        + " conditionCount=" + result.conditionCount()
                        + " observations=" + result.observationStatus()
                        + " observationCount=" + result.observationCount()
                        + " diagnosticReports=" + result.diagnosticReportStatus()
                        + " diagnosticReportCount=" + result.diagnosticReportCount()
                        + " medicationRequests=" + result.medicationRequestStatus()
                        + " medicationRequestCount=" + result.medicationRequestCount()
                        + " detail=" + result.detail());
    }
}
