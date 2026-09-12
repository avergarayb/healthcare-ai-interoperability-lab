package lab.healthcare.fhir.vendor.epic;

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
public class EpicSandboxClinicalSnapshotController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxClinicalSnapshotController.class);

    private final EpicSandboxClinicalSnapshotService snapshotService;
    private final EpicIntegrationProfile profile;

    public EpicSandboxClinicalSnapshotController(
            EpicSandboxClinicalSnapshotService snapshotService, EpicIntegrationProfile profile) {
        this.snapshotService = snapshotService;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/clinical-snapshot", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> clinicalSnapshot() {
        ClinicalSnapshotResult result = snapshotService.assemble(profile);
        log.info(
                "Epic controlled clinical snapshot destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={}",
                result.destination(),
                result.outcome(),
                result.patientStatus(),
                result.conditionStatus(),
                result.observationStatus(),
                result.diagnosticReportStatus());
        return ResponseEntity.status(httpStatus(result.outcome())).body(SmartLabPages.epicClinicalSnapshot(result));
    }

    private static int httpStatus(ClinicalSnapshotOutcome outcome) {
        return switch (outcome) {
            case SNAPSHOT_COMPLETE, SNAPSHOT_PARTIAL -> 200;
            case AUTHENTICATION_REQUIRED -> 401;
            case PATIENT_CONTEXT_NOT_CONFIGURED -> 409;
            case SNAPSHOT_UNAVAILABLE -> 502;
        };
    }
}
