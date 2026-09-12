package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for a controlled clinical projection. Not a
 * clinical API and not a product UI. Never renders retained field values.
 */
@RestController
public class EpicSandboxClinicalProjectionController {

    private static final Logger log = LoggerFactory.getLogger(EpicSandboxClinicalProjectionController.class);

    private final EpicSandboxClinicalProjectionService projectionService;
    private final EpicIntegrationProfile profile;

    public EpicSandboxClinicalProjectionController(
            EpicSandboxClinicalProjectionService projectionService, EpicIntegrationProfile profile) {
        this.projectionService = projectionService;
        this.profile = profile;
    }

    @GetMapping(path = "/epic/sandbox/fhir/clinical-projection", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> clinicalProjection() {
        ClinicalProjectionResult result = projectionService.assemble(profile);
        log.info(
                "Epic controlled clinical projection destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={}",
                result.destination(),
                result.outcome(),
                result.patientStatus(),
                collectionLog(result.conditions()),
                collectionLog(result.observations()),
                collectionLog(result.diagnosticReports()));
        return ResponseEntity.status(httpStatus(result.outcome())).body(SmartLabPages.epicClinicalProjection(result));
    }

    private static int httpStatus(ClinicalSnapshotOutcome outcome) {
        return switch (outcome) {
            case SNAPSHOT_COMPLETE, SNAPSHOT_PARTIAL -> 200;
            case AUTHENTICATION_REQUIRED -> 401;
            case PATIENT_CONTEXT_NOT_CONFIGURED -> 409;
            case SNAPSHOT_UNAVAILABLE -> 502;
        };
    }

    private static String collectionLog(ProjectedCollection<?> collection) {
        if (collection == null || collection.status() == null) {
            return "";
        }
        return collection.status()
                + " receivedCount="
                + collection.receivedCount()
                + " retainedCount="
                + collection.retainedCount()
                + " truncated="
                + collection.truncated();
    }
}
