package lab.healthcare.fhir.externalfhir;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.federation.ClinicalConnector;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;

/**
 * Federation reader for the allowlisted sandbox. It does not resolve a patient
 * by identifier equality. The logical id comes from the explicit link store.
 */
public final class ExternalFhirConnector implements ClinicalConnector {

    private final ExternalFhirClient client;

    public ExternalFhirConnector(ExternalFhirClient client) {
        this.client = client;
    }

    @Override
    public String key() {
        return ExternalFhirProperties.SOURCE_KEY;
    }

    @Override
    public String resolvePatient(String identifierSystem, String identifierValue) {
        return null;
    }

    @Override
    public Collected collect(String resourceType, String patientId) {
        if (patientId == null || patientId.isBlank()) {
            throw ClinicalReadException.notFound();
        }
        return switch (resourceType) {
            case "Patient" -> {
                JsonNode patient = client.readPatient(patientId);
                if (patient == null) {
                    throw ClinicalReadException.notFound();
                }
                yield new Collected(List.of(patient), false);
            }
            case "Observation", "DiagnosticReport" -> {
                ExternalFhirClient.SearchResult result = client.search(resourceType, patientId);
                yield new Collected(result.resources(), result.truncated());
            }
            default -> new Collected(List.of(), false);
        };
    }
}
