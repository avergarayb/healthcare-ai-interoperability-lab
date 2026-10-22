package lab.healthcare.fhir.clinicalread.minilis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadLimits;
import lab.healthcare.fhir.clinicalread.minilis.MiniLisClient.MiniLisResponse;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

final class MiniLisRestSource implements MiniLisClinicalSource {

    static final String DESTINATION = "mini-lis";

    private final MiniLisClient client;
    private final MiniLisNormalizer normalizer;
    private final ObjectMapper json;

    MiniLisRestSource(MiniLisClient client, ObjectMapper json) {
        if (client == null || json == null) {
            throw new IllegalArgumentException("Mini LIS client and JSON mapper must be provided");
        }
        this.client = client;
        this.normalizer = new MiniLisNormalizer(json);
        this.json = json;
    }

    @Override
    public JsonNode readPatient(String logicalId) {
        MiniLisResponse response = client.getOne("/patients/" + MiniLisClient.encode(logicalId));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        ObjectNode resource = normalizer.patient(response.body());
        if (!logicalId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        return readEnvelope(resource);
    }

    @Override
    public JsonNode searchPatients(String identifierSystem, String identifierValue) {
        String path = patientSearchPath(identifierSystem, identifierValue);
        MiniLisResponse response = path.startsWith("/patients/")
                ? client.getOne(path)
                : client.getList(path);
        if (response.status() == 404) {
            return collection("Patient", json.createArrayNode(), false);
        }
        ArrayNode resources = json.createArrayNode();
        if (response.body().isArray()) {
            if (response.truncated() || response.body().size() > 1) {
                throw ClinicalReadException.invalidSource();
            }
            if (!response.body().isEmpty()) {
                resources.add(checkedPatient(response.body().get(0), identifierSystem, identifierValue));
            }
        } else {
            resources.add(checkedPatient(response.body(), identifierSystem, identifierValue));
        }
        return collection("Patient", resources, false);
    }

    @Override
    public JsonNode readServiceRequest(String logicalId) {
        MiniLisResponse response = client.getOne("/orders/" + MiniLisClient.encode(logicalId));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        ObjectNode resource = normalizer.serviceRequest(response.body());
        if (!logicalId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        return readEnvelope(resource);
    }

    @Override
    public JsonNode searchServiceRequests(String patientId, String status) {
        MiniLisResponse response = client.getList("/patients/" + MiniLisClient.encode(patientId) + "/orders");
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        return collection("ServiceRequest", mapOrders(response, patientId, status), response.truncated());
    }

    @Override
    public JsonNode readObservation(String logicalId) {
        MiniLisResponse response = client.getOne("/results/" + MiniLisClient.encode(logicalId));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        ObjectNode resource = normalizer.observation(response.body());
        if (!logicalId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        return readEnvelope(resource);
    }

    @Override
    public JsonNode searchObservations(String patientId, String status) {
        MiniLisResponse response = client.getList("/patients/" + MiniLisClient.encode(patientId) + "/results");
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        if (!response.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode();
        for (JsonNode item : response.body()) {
            if (!(item instanceof ObjectNode object)) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode copy = object.deepCopy();
            copy.put("patientId", patientId);
            ObjectNode observation = normalizer.observation(copy);
            if (status == null || status.equals(observation.path("status").asText())) {
                resources.add(observation);
            }
        }
        return collection("Observation", resources, response.truncated());
    }

    @Override
    public JsonNode readDiagnosticReport(String logicalId) {
        MiniLisResponse order = client.getOne("/orders/" + MiniLisClient.encode(logicalId));
        if (order.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        String patientId = order.body().path("patientId").asText();
        MiniLisResponse results = client.getList("/orders/" + MiniLisClient.encode(logicalId) + "/results");
        if (results.status() == 404 || !results.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ObjectNode resource = normalizer.diagnosticReport(order.body(), results.body(), patientId);
        if (!logicalId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        return readEnvelope(resource);
    }

    @Override
    public JsonNode searchDiagnosticReports(String patientId, String status) {
        MiniLisResponse orders = client.getList("/patients/" + MiniLisClient.encode(patientId) + "/orders");
        if (orders.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        if (!orders.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode();
        for (JsonNode order : orders.body()) {
            if (!patientId.equals(order.path("patientId").asText())) {
                throw ClinicalReadException.invalidSource();
            }
            String orderId = order.path("orderId").asText();
            MiniLisResponse results = client.getOne("/orders/" + MiniLisClient.encode(orderId) + "/results");
            if (results.status() != 200 || !results.body().isArray()) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode report = normalizer.diagnosticReport(order, results.body(), patientId);
            if (status == null || status.equals(report.path("status").asText())) {
                resources.add(report);
            }
        }
        return collection("DiagnosticReport", resources, orders.truncated());
    }

    private ArrayNode mapOrders(MiniLisResponse response, String patientId, String status) {
        if (!response.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode();
        for (JsonNode item : response.body()) {
            if (!patientId.equals(item.path("patientId").asText())) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode request = normalizer.serviceRequest(item);
            if (status == null || status.equals(request.path("status").asText())) {
                resources.add(request);
            }
        }
        return resources;
    }

    private ObjectNode checkedPatient(JsonNode source, String system, String value) {
        ObjectNode resource = normalizer.patient(source);
        if (!containsIdentifier(resource, system, value)) {
            throw ClinicalReadException.invalidSource();
        }
        return resource;
    }

    private static String patientSearchPath(String system, String value) {
        if (MiniLisNormalizer.PATIENT_SYSTEM.equals(system)) {
            return "/patients/" + MiniLisClient.encode(value);
        }
        String prefix = MiniLisNormalizer.SOURCE + "/organization/";
        String suffix = "/patient";
        if (system.startsWith(prefix) && system.endsWith(suffix) && system.length() > prefix.length() + suffix.length()) {
            String organizationId = system.substring(prefix.length(), system.length() - suffix.length());
            return "/patients?organizationId=" + MiniLisClient.encode(organizationId)
                    + "&externalId=" + MiniLisClient.encode(value);
        }
        throw ClinicalReadException.invalidRequest();
    }

    private static boolean containsIdentifier(ObjectNode resource, String system, String value) {
        for (JsonNode identifier : resource.path("identifier")) {
            if (system.equals(identifier.path("system").asText()) && value.equals(identifier.path("value").asText())) {
                return true;
            }
        }
        return false;
    }

    private ObjectNode readEnvelope(ObjectNode resource) {
        ObjectNode body = envelope();
        body.set("resource", resource);
        return body;
    }

    private ObjectNode collection(String resourceType, ArrayNode resources, boolean incomplete) {
        ObjectNode body = envelope();
        body.put("collectionStatus", incomplete ? "incomplete" : "complete");
        body.put("resourceType", resourceType);
        body.set("resources", resources);
        return body;
    }

    private ObjectNode envelope() {
        ObjectNode body = json.createObjectNode();
        body.put("contractVersion", ClinicalReadLimits.CONTRACT_VERSION);
        body.put("destination", DESTINATION);
        return body;
    }
}
