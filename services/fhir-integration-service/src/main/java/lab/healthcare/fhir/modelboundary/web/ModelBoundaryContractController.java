package lab.healthcare.fhir.modelboundary.web;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractProvider;
import lab.healthcare.fhir.modelboundary.ModelBoundaryHttpStatuses;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Versioned machine surface for {@link ModelBoundaryContract} v1. Not a
 * laboratory page, not an agent, and not a clinical API. Logs counts only.
 */
@RestController
public class ModelBoundaryContractController {

    private static final Logger log = LoggerFactory.getLogger(ModelBoundaryContractController.class);

    private final ModelBoundaryContractProvider provider;

    public ModelBoundaryContractController(ModelBoundaryContractProvider provider) {
        if (provider == null) {
            throw new IllegalArgumentException("Model boundary contract provider must be provided");
        }
        this.provider = provider;
    }

    @GetMapping(path = "/api/model-boundary/v1", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ModelBoundaryContract> contract() {
        ModelBoundaryContract contract = provider.currentContract();
        log.info(
                "Model boundary consumer surface contractVersion={} destination={} outcome={} patient={} conditions={} observations={} diagnosticReports={} medicationRequests={}",
                contract.contractVersion(),
                contract.destination(),
                contract.outcome(),
                contract.patient() == null ? "" : contract.patient().status(),
                collectionLog(contract.conditions()),
                collectionLog(contract.observations()),
                collectionLog(contract.diagnosticReports()),
                collectionLog(contract.medicationRequests()));
        return ResponseEntity.status(ModelBoundaryHttpStatuses.of(contract.outcome())).body(contract);
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
