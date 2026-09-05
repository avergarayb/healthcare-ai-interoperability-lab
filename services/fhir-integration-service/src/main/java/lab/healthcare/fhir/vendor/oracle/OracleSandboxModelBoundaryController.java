package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.smart.web.SmartLabPages;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Laboratory diagnosis page for the vendor-neutral model boundary. Not a
 * clinical API, not model input, and never renders retained record values.
 */
@RestController
public class OracleSandboxModelBoundaryController {

    private static final Logger log = LoggerFactory.getLogger(OracleSandboxModelBoundaryController.class);

    private final OracleSandboxModelBoundaryService modelBoundaryService;
    private final OracleHealthIntegrationProfile profile;

    public OracleSandboxModelBoundaryController(
            OracleSandboxModelBoundaryService modelBoundaryService,
            OracleHealthIntegrationProfile profile) {
        this.modelBoundaryService = modelBoundaryService;
        this.profile = profile;
    }

    @GetMapping(path = "/oracle/sandbox/fhir/model-boundary", produces = MediaType.TEXT_HTML_VALUE)
    public ResponseEntity<String> modelBoundary() {
        ModelBoundaryContract contract = modelBoundaryService.assemble(profile);
        log.info(
                "Oracle model boundary contractVersion={} destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={} medicationRequests={}",
                contract.contractVersion(),
                contract.destination(),
                contract.outcome(),
                contract.patient() == null ? "" : contract.patient().status(),
                collectionLog(contract.conditions()),
                collectionLog(contract.observations()),
                collectionLog(contract.diagnosticReports()),
                collectionLog(contract.medicationRequests()));
        return ResponseEntity.status(httpStatus(contract.outcome())).body(page(contract));
    }

    private static int httpStatus(ClinicalSnapshotOutcome outcome) {
        return switch (outcome) {
            case SNAPSHOT_COMPLETE, SNAPSHOT_PARTIAL -> 200;
            case AUTHENTICATION_REQUIRED -> 401;
            case PATIENT_CONTEXT_NOT_CONFIGURED -> 409;
            case SNAPSHOT_UNAVAILABLE -> 502;
        };
    }

    private static String page(ModelBoundaryContract contract) {
        return SmartLabPages.error(
                "Oracle Health vendor-neutral model boundary",
                "contractVersion=" + contract.contractVersion()
                        + " outcome=" + contract.outcome()
                        + " destination=" + contract.destination()
                        + " contextSource=" + contract.contextSource()
                        + " patient=" + (contract.patient() == null ? "" : contract.patient().status())
                        + " " + collectionLine("conditions", contract.conditions())
                        + " " + collectionLine("observations", contract.observations())
                        + " " + collectionLine("diagnosticReports", contract.diagnosticReports())
                        + " " + collectionLine("medicationRequests", contract.medicationRequests()));
    }

    private static String collectionLine(String name, BoundaryCollection<?> collection) {
        if (collection == null || collection.status() == null) {
            return name + "=";
        }
        return name + "=" + collection.status()
                + " " + name + "ReceivedCount=" + collection.receivedCount()
                + " " + name + "RetainedCount=" + collection.retainedCount()
                + " " + name + "Truncated=" + collection.truncated();
    }

    private static String collectionLog(BoundaryCollection<?> collection) {
        if (collection == null || collection.status() == null) {
            return "";
        }
        return collection.status()
                + " receivedCount=" + collection.receivedCount()
                + " retainedCount=" + collection.retainedCount()
                + " truncated=" + collection.truncated();
    }
}
