package lab.healthcare.fhir.federation;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.minihis.MiniHisClinicalSource;
import lab.healthcare.fhir.clinicalread.minilis.MiniLisClinicalSource;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.ArrayList;
import java.util.List;

/**
 * Adapters over the connectors that already exist. They do not add a second
 * FHIR server and they do not search by name or birth date.
 */
final class ExistingClinicalConnectors {

    private ExistingClinicalConnectors() {
    }

    static ClinicalConnector miniHis(MiniHisClinicalSource source) {
        return new ClinicalConnector() {
            @Override
            public String key() {
                return "mini-his";
            }

            @Override
            public String resolvePatient(String identifierSystem, String identifierValue) {
                return singleId(source.searchPatients(identifierSystem, identifierValue));
            }

            @Override
            public ClinicalConnector.Collected collect(String resourceType, String patientId) {
                return switch (resourceType) {
                    case "Patient" -> readOne(source.readPatient(patientId));
                    case "Observation" -> mergeStatuses(patientId, List.of("final", "preliminary", "corrected"),
                            source::searchObservations);
                    case "Encounter" -> mergeStatuses(patientId, List.of("finished", "in-progress", "planned", "cancelled"),
                            source::searchEncounters);
                    case "Appointment" -> collectionOrEmpty(source.searchAppointments(patientId));
                    case "ServiceRequest" -> collectionOrEmpty(source.searchServiceRequests(patientId));
                    default -> new ClinicalConnector.Collected(List.of(), false);
                };
            }
        };
    }

    static ClinicalConnector miniLis(MiniLisClinicalSource source) {
        return new ClinicalConnector() {
            @Override
            public String key() {
                return "mini-lis";
            }

            @Override
            public String resolvePatient(String identifierSystem, String identifierValue) {
                return singleId(source.searchPatients(identifierSystem, identifierValue));
            }

            @Override
            public ClinicalConnector.Collected collect(String resourceType, String patientId) {
                return switch (resourceType) {
                    case "Patient" -> readOne(source.readPatient(patientId));
                    case "Observation" -> collectionOrEmpty(source.searchObservations(patientId, null));
                    case "ServiceRequest" -> collectionOrEmpty(source.searchServiceRequests(patientId, null));
                    case "DiagnosticReport" -> collectionOrEmpty(source.searchDiagnosticReports(patientId, null));
                    default -> new ClinicalConnector.Collected(List.of(), false);
                };
            }
        };
    }

    private static String singleId(JsonNode envelope) {
        JsonNode resources = envelope.path("resources");
        if (!resources.isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        if (resources.isEmpty()) {
            return null;
        }
        if (resources.size() != 1) {
            throw ClinicalReadException.invalidSource();
        }
        String id = resources.get(0).path("id").asText("");
        if (id.isBlank()) {
            throw ClinicalReadException.invalidSource();
        }
        return id;
    }

    private static ClinicalConnector.Collected readOne(JsonNode envelope) {
        JsonNode resource = envelope.path("resource");
        if (!resource.isObject() || resource.path("id").asText("").isBlank()) {
            throw ClinicalReadException.invalidSource();
        }
        return new ClinicalConnector.Collected(List.of(resource), false);
    }

    private static ClinicalConnector.Collected collectionOrEmpty(JsonNode envelope) {
        try {
            return collection(envelope);
        } catch (ClinicalReadException ex) {
            if ("not_found".equals(ex.code())) {
                return new ClinicalConnector.Collected(List.of(), false);
            }
            throw ex;
        }
    }

    private static ClinicalConnector.Collected mergeStatuses(
            String patientId, List<String> statuses, StatusSearch search) {
        List<JsonNode> resources = new ArrayList<>();
        boolean truncated = false;
        for (String status : statuses) {
            ClinicalConnector.Collected page;
            try {
                page = collection(search.search(patientId, status));
            } catch (ClinicalReadException ex) {
                if ("not_found".equals(ex.code())) {
                    continue;
                }
                throw ex;
            }
            resources.addAll(page.resources());
            truncated = truncated || page.truncated();
        }
        return new ClinicalConnector.Collected(List.copyOf(resources), truncated);
    }

    private static ClinicalConnector.Collected collection(JsonNode envelope) {
        JsonNode resources = envelope.path("resources");
        if (!resources.isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        List<JsonNode> copy = new ArrayList<>();
        resources.forEach(copy::add);
        boolean truncated = "incomplete".equals(envelope.path("collectionStatus").asText());
        return new ClinicalConnector.Collected(List.copyOf(copy), truncated);
    }

    @FunctionalInterface
    private interface StatusSearch {
        JsonNode search(String patientId, String status);
    }
}
