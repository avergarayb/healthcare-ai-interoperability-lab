package lab.healthcare.fhir.clinicalread;

import lab.healthcare.fhir.exception.FhirClientException;
import lab.healthcare.fhir.exception.FhirErrorCategory;
import lab.healthcare.fhir.exception.FhirErrorClassifier;
import lab.healthcare.fhir.clinicalread.minihis.MiniHisClinicalSource;
import lab.healthcare.fhir.clinicalread.minilis.MiniLisClinicalSource;
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
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
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

    private static final String MINI_HIS = "mini-his";
    private static final String MINI_LIS = "mini-lis";

    private final RoutingService routing;
    private final FhirServersProperties servers;
    private final ObjectMapper json;
    private final String source;
    private final MiniHisClinicalSource miniHis;
    private final MiniLisClinicalSource miniLis;

    public ClinicalReadService(RoutingService routing, FhirServersProperties servers, ObjectMapper json) {
        this(routing, servers, json, ClinicalReadLimits.DESTINATION, (MiniHisClinicalSource) null, (MiniLisClinicalSource) null);
    }

    @Autowired
    public ClinicalReadService(
            RoutingService routing,
            FhirServersProperties servers,
            ObjectMapper json,
            @Value("${clinical-read.source:local-hapi}") String source,
            ObjectProvider<MiniHisClinicalSource> miniHis,
            ObjectProvider<MiniLisClinicalSource> miniLis) {
        this(routing, servers, json, source, miniHis.getIfAvailable(), miniLis.getIfAvailable());
    }

    public ClinicalReadService(
            RoutingService routing,
            FhirServersProperties servers,
            ObjectMapper json,
            String source,
            MiniHisClinicalSource miniHis) {
        this(routing, servers, json, source, miniHis, null);
    }

    public ClinicalReadService(
            RoutingService routing,
            FhirServersProperties servers,
            ObjectMapper json,
            String source,
            MiniHisClinicalSource miniHis,
            MiniLisClinicalSource miniLis) {
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
        String selected = source == null ? "" : source.trim();
        this.source = selected.isEmpty() ? ClinicalReadLimits.DESTINATION : selected;
        this.miniHis = miniHis;
        this.miniLis = miniLis;
    }

    public JsonNode readPatient(String logicalId) {
        String id = logicalId(logicalId);
        if (miniHisSelected()) {
            return miniHis().readPatient(id);
        }
        if (miniLisSelected()) {
            return miniLis().readPatient(id);
        }
        return readResource("Patient", () -> routing.readPatientByLogicalId(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchPatients(String identifierSystem, String identifierValue) {
        String system = token(identifierSystem);
        String value = token(identifierValue);
        if (miniHisSelected()) {
            return miniHis().searchPatients(system, value);
        }
        if (miniLisSelected()) {
            return miniLis().searchPatients(system, value);
        }
        return search(
                "Patient",
                () -> routing.searchPatientsByIdentifier(
                        ClinicalReadLimits.DESTINATION, system, value, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readEncounter(String logicalId) {
        String id = logicalId(logicalId);
        if (miniHisSelected()) {
            return miniHis().readEncounter(id);
        }
        if (miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return readResource("Encounter", () -> routing.readEncounter(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchEncounters(String patientId, String status) {
        String patient = logicalId(patientId);
        String encounterStatus = status(status);
        if (miniHisSelected()) {
            return miniHis().searchEncounters(patient, encounterStatus);
        }
        if (miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return search(
                "Encounter",
                () -> routing.searchEncountersByPatientAndStatus(
                        ClinicalReadLimits.DESTINATION, patient, encounterStatus, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readObservation(String logicalId) {
        String id = logicalId(logicalId);
        if (miniHisSelected()) {
            return miniHis().readObservation(id);
        }
        if (miniLisSelected()) {
            return miniLis().readObservation(id);
        }
        return readResource(
                "Observation", () -> routing.readObservationByLogicalId(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchObservations(String patientId, String status) {
        String patient = logicalId(patientId);
        String observationStatus = status(status);
        if (miniHisSelected()) {
            return miniHis().searchObservations(patient, observationStatus);
        }
        if (miniLisSelected()) {
            return miniLis().searchObservations(patient, observationStatus);
        }
        return search(
                "Observation",
                () -> routing.searchObservationsByPatientAndStatus(
                        ClinicalReadLimits.DESTINATION, patient, observationStatus, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readAppointment(String logicalId) {
        String id = logicalId(logicalId);
        if (miniHisSelected()) {
            return miniHis().readAppointment(id);
        }
        if (miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return readResource("Appointment", () -> routing.readAppointment(ClinicalReadLimits.DESTINATION, id), id);
    }

    public JsonNode searchAppointments(String patientId) {
        String patient = logicalId(patientId);
        if (miniHisSelected()) {
            return miniHis().searchAppointments(patient);
        }
        if (miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return search(
                "Appointment",
                () -> routing.searchAppointmentsByPatient(
                        ClinicalReadLimits.DESTINATION, patient, ClinicalReadLimits.PAGE_SIZE));
    }

    public JsonNode readServiceRequest(String logicalId) {
        String id = logicalId(logicalId);
        if (!miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return miniLis().readServiceRequest(id);
    }

    public JsonNode searchServiceRequests(String patientId, String status) {
        String patient = logicalId(patientId);
        String requestStatus = optionalStatus(status);
        if (!miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return miniLis().searchServiceRequests(patient, requestStatus);
    }

    public JsonNode readDiagnosticReport(String logicalId) {
        String id = logicalId(logicalId);
        if (!miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return miniLis().readDiagnosticReport(id);
    }

    public JsonNode searchDiagnosticReports(String patientId, String status) {
        String patient = logicalId(patientId);
        String reportStatus = optionalStatus(status);
        if (!miniLisSelected()) {
            throw ClinicalReadException.operationNotSupported();
        }
        return miniLis().searchDiagnosticReports(patient, reportStatus);
    }

    private boolean miniHisSelected() {
        return MINI_HIS.equals(source);
    }

    private boolean miniLisSelected() {
        return MINI_LIS.equals(source);
    }

    private MiniLisClinicalSource miniLis() {
        if (!miniLisSelected() || miniLis == null) {
            throw ClinicalReadException.unavailable();
        }
        return miniLis;
    }

    private static String optionalStatus(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return status(value);
    }

    private MiniHisClinicalSource miniHis() {
        if (!miniHisSelected() || miniHis == null) {
            throw ClinicalReadException.unavailable();
        }
        return miniHis;
    }

    private JsonNode readResource(String resourceType, Supplier<Resource> read, String logicalId) {
        requireHapiSource();
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
        requireHapiSource();
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

    private void requireHapiSource() {
        if (!ClinicalReadLimits.DESTINATION.equals(source)) {
            throw ClinicalReadException.destinationNotSupported();
        }
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
