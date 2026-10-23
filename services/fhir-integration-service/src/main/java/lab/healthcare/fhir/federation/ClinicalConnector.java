package lab.healthcare.fhir.federation;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

/**
 * One implemented reader. A registry row without one of these does not
 * participate as a successful source.
 */
public interface ClinicalConnector {

    String key();

    /**
     * Exact identifier search on this connector. Returns the logical id, or
     * null when that identifier is absent. Does not search by name or birth date.
     */
    String resolvePatient(String identifierSystem, String identifierValue);

    Collected collect(String resourceType, String patientId);

    record Collected(List<JsonNode> resources, boolean truncated) {
    }
}
