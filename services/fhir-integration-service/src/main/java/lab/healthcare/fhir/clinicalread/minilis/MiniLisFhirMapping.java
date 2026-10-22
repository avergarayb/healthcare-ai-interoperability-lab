package lab.healthcare.fhir.clinicalread.minilis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

/**
 * Read-side FHIR mapping for a Mini LIS order and its results. The code system
 * stays the Mini LIS test system. This class does not invent LOINC or UCUM.
 */
public final class MiniLisFhirMapping {

    private final MiniLisNormalizer normalizer;

    public MiniLisFhirMapping(ObjectMapper json) {
        this.normalizer = new MiniLisNormalizer(json);
    }

    public ObjectNode serviceRequest(JsonNode order) {
        return normalizer.serviceRequest(order);
    }

    public ObjectNode observation(JsonNode result) {
        return normalizer.observation(result);
    }

    public ObjectNode diagnosticReport(JsonNode order, JsonNode results) {
        return normalizer.diagnosticReport(order, results, order.path("patientId").asText());
    }
}
