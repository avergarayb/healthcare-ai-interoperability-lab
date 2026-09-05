package lab.healthcare.fhir.vendor.oracle;

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
public class OracleSandboxClinicalProjectionController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxClinicalProjectionController.class);

    private final OracleSandboxClinicalProjectionService projectionService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxClinicalProjectionController(
            OracleSandboxClinicalProjectionService projectionService,
            OracleHealthIntegrationProfile profile) {
        this.projectionService = projectionService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/clinical-projection", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> clinicalProjection() {
        ClinicalProjectionResult result = projectionService.assemble(profile);
        log.info(
                "Oracle controlled clinical projection destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={} medicationRequests={}",
                result.destination(),
                result.outcome(),
                result.patientStatus(),
                collectionLog(result.conditions()),
                collectionLog(result.observations()),
                collectionLog(result.diagnosticReports()),
                collectionLog(result.medicationRequests()));
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

    private static String page(ClinicalProjectionResult result) {
        return SmartLabPages.error(
                "Oracle Health controlled clinical projection",
                "outcome=" + result.outcome()
                        + " destination=" + result.destination()
                        + " contextSource=" + result.contextSource()
                        + " patient=" + result.patientStatus()
                        + " " + collectionLine("conditions", result.conditions())
                        + " " + collectionLine("observations", result.observations())
                        + " " + collectionLine("diagnosticReports", result.diagnosticReports())
                        + " " + collectionLine("medicationRequests", result.medicationRequests())
                        + " detail=" + result.detail());
    }

    private static String collectionLine(String name, ProjectedCollection<?> collection) {
        if (collection == null || collection.status() == null) {
            return name + "=";
        }
        return name + "=" + collection.status()
                + " " + name + "ReceivedCount=" + collection.receivedCount()
                + " " + name + "RetainedCount=" + collection.retainedCount()
                + " " + name + "Truncated=" + collection.truncated();
    }

    private static String collectionLog(ProjectedCollection<?> collection) {
        if (collection == null || collection.status() == null) {
            return "";
        }
        return collection.status()
                + " receivedCount=" + collection.receivedCount()
                + " retainedCount=" + collection.retainedCount()
                + " truncated=" + collection.truncated();
    }
}
