package lab.healthcare.fhir.clinicalread;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.routing.RoutingException;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;

import ca.uhn.fhir.context.FhirContext;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Resource;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.function.Supplier;
import java.util.regex.Pattern;

@Service
public class ClinicalReadService {

    private static final FhirContext FHIR = FhirContext.forR4();
    private static final Pattern LOGICAL_ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");
    private static final Pattern STATUS = Pattern.compile("[A-Za-z0-9\\-]{1,64}");
    private static final int MAX_TOKEN_LENGTH = 200;

    private final RoutingService routing;
    private final FhirServersProperties servers;
    private final ObjectMapper json;

    public ClinicalReadService(RoutingService routing, FhirServersProperties servers, ObjectMapper json) {
        if (routing == null) {
            throw new IllegalArgumentException("Routing service must be provided");
        }
        if (servers == null) {
            throw new IllegalArgumentException("FHIR server properties must be provided");
        }
        if (json == null) {
            throw new IllegalArgumentException("JSON mapper must be provided");
        }
        this.routing = routing;
        this.servers = servers;
        this.json = json;
    }

    public JsonNode readPatient(String logicalId) {
        String id = logicalId(logicalId);
        return readResource("Patient", () -> routing.readPatientByLogicalId(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchPatients(String identifierSystem, String identifierValue) {
        String system = token(identifierSystem);
        String value = token(identifierValue);
        return search(
                "Patient",
                () -> routing.searchPatientsByIdentifier(
                        ClinicalReadLimits.DESTINATION, system, value, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readEncounter(String logicalId) {
        String id = logicalId(logicalId);
        return readResource("Encounter", () -> routing.readEncounter(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchEncounters(String patientId, String status) {
        String patient = logicalId(patientId);
        String encounterStatus = status(status);
        return search(
                "Encounter",
                () -> routing.searchEncountersByPatientAndStatus(
                        ClinicalReadLimits.DESTINATION, patient, encounterStatus, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readObservation(String logicalId) {
        String id = logicalId(logicalId);
        return readResource(
                "Observation", () -> routing.readObservationByLogicalId(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchObservations(String patientId, String status) {
        String patient = logicalId(patientId);
        String observationStatus = status(status);
        return search(
                "Observation",
                () -> routing.searchObservationsByPatientAndStatus(
                        ClinicalReadLimits.DESTINATION, patient, observationStatus, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readAppointment(String logicalId) {
        String id = logicalId(logicalId);
        return readResource("Appointment", () -> routing.readAppointment(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchAppointments(String patientId) {
        String patient = logicalId(patientId);
        return search(
                "Appointment",
                () -> routing.searchAppointmentsByPatient(
                        ClinicalReadLimits.DESTINATION, patient, ClinicalReadLimits.PAGE_SIZE));
    }

    private JsonNode readResource(String resourceType, Supplier<Resource> read, String logicalId) {
        requireLocalHapi();
        Resource resource = call(read, true);
        if (resource == null
                || !resourceType.equals(resource.fhirType())
                || !logicalId.equals(resource.getIdElement().getIdPart())) {
            throw ClinicalReadException.unavailable();
        }
        ObjectNode body = envelope();
        body.set("resource", encode(resource));
        return body;
    }

    private JsonNode search(String resourceType, Supplier<Bundle> firstPage) {
        requireLocalHapi();
        Bundle page = call(firstPage, false);
        List<Resource> collected = new ArrayList<>();
        Set<String> seenIds = new HashSet<>();
        Set<String> seenNext = new HashSet<>();
        int pagesRead = 0;
        boolean incomplete = false;
        while (true) {
            if (page == null) {
                throw ClinicalReadException.unavailable();
            }
            pagesRead++;
            boolean capped = false;
            for (Resource resource : matching(page, resourceType)) {
                String id = resource.getIdElement().getIdPart();
                if (id == null || id.isBlank()) {
                    throw ClinicalReadException.unavailable();
                }
                if (!seenIds.add(resourceType + "/" + id)) {
                    continue;
                }
                if (collected.size() == ClinicalReadLimits.MAX_RESOURCES) {
                    incomplete = true;
                    capped = true;
                    break;
                }
                collected.add(resource);
            }
            if (capped || !hasNext(page)) {
                break;
            }
            String nextUrl = page.getLink(Bundle.LINK_NEXT).getUrl();
            if (!seenNext.add(nextUrl)) {
                throw ClinicalReadException.unavailable();
            }
            if (pagesRead >= ClinicalReadLimits.MAX_PAGES) {
                incomplete = true;
                break;
            }
            Bundle current = page;
            page = call(
                    () -> routing.loadNextSearchPage(ClinicalReadLimits.DESTINATION, resourceType, current),
                    false);
        }
        ObjectNode body = envelope();
        body.put("collectionStatus", incomplete ? "incomplete" : "complete");
        body.put("resourceType", resourceType);
        ArrayNode resources = body.putArray("resources");
        for (Resource resource : collected) {
            resources.add(encode(resource));
        }
        return body;
    }

    private void requireLocalHapi() {
        String active = servers.activeServer() == null ? "" : servers.activeServer().trim();
        if (!ClinicalReadLimits.DESTINATION.equals(active)) {
            throw ClinicalReadException.destinationNotSupported();
        }
    }

    private <T> T call(Supplier<T> operation, boolean notFoundIsAbsence) {
        try {
            return operation.get();
        } catch (ClinicalReadException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            if (notFoundIsAbsence && notFound(ex)) {
                throw ClinicalReadException.notFound();
            }
            throw ClinicalReadException.unavailable();
        }
    }

    private ObjectNode envelope() {
        ObjectNode body = json.createObjectNode();
        body.put("contractVersion", ClinicalReadLimits.CONTRACT_VERSION);
        body.put("destination", ClinicalReadLimits.DESTINATION);
        return body;
    }

    private JsonNode encode(Resource resource) {
        try {
            String encoded = FHIR.newJsonParser().setPrettyPrint(false).encodeResourceToString(resource);
            return json.readTree(encoded);
        } catch (RuntimeException | java.io.IOException ex) {
            throw ClinicalReadException.unavailable();
        }
    }

    private static List<Resource> matching(Bundle bundle, String resourceType) {
        List<Resource> resources = new ArrayList<>();
        if (bundle == null || !bundle.hasEntry()) {
            return resources;
        }
        for (Bundle.BundleEntryComponent entry : bundle.getEntry()) {
            Resource resource = entry.getResource();
            if (resource != null && resourceType.equals(resource.fhirType())) {
                resources.add(resource);
            }
        }
        return resources;
    }

    private static boolean hasNext(Bundle bundle) {
        if (bundle == null) {
            return false;
        }
        Bundle.BundleLinkComponent link = bundle.getLink(Bundle.LINK_NEXT);
        return link != null && link.hasUrl() && !link.getUrl().isBlank();
    }

    private static boolean notFound(RuntimeException ex) {
        if (ex instanceof FhirClientException fhir) {
            return fhir.category() == FhirErrorCategory.NOT_FOUND;
        }
        if (ex instanceof RoutingException routing && routing.details() != null) {
            return routing.details().category() == FhirErrorCategory.NOT_FOUND;
        }
        return FhirErrorClassifier.classify(ex).category() == FhirErrorCategory.NOT_FOUND;
    }

    private static String logicalId(String value) {
        if (value == null || !LOGICAL_ID.matcher(value).matches()) {
            throw ClinicalReadException.invalidRequest();
        }
        return value;
    }

    private static String status(String value) {
        if (value == null || !STATUS.matcher(value).matches()) {
            throw ClinicalReadException.invalidRequest();
        }
        return value;
    }

    private static String token(String value) {
        if (value == null || value.isBlank() || value.length() > MAX_TOKEN_LENGTH || value.indexOf('|') >= 0) {
            throw ClinicalReadException.invalidRequest();
        }
        String trimmed = value.trim();
        if (trimmed.isEmpty() || trimmed.length() > MAX_TOKEN_LENGTH || trimmed.indexOf('|') >= 0) {
            throw ClinicalReadException.invalidRequest();
        }
        return trimmed;
    }
}
