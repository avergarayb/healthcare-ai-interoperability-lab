package lab.healthcare.fhir.clinicalread.minihis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.clinicalread.ClinicalReadLimits;
import lab.healthcare.fhir.clinicalread.minihis.MiniHisClient.MiniHisResponse;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

final class MiniHisRestSource implements MiniHisClinicalSource {

    static final String DESTINATION = "mini-his";

    private final MiniHisClient client;
    private final MiniHisNormalizer normalizer;
    private final ObjectMapper json;

    MiniHisRestSource(MiniHisClient client, ObjectMapper json) {
        if (client == null || json == null) {
            throw new IllegalArgumentException("Mini HIS client and JSON mapper must be provided");
        }
        this.client = client;
        this.normalizer = new MiniHisNormalizer(json);
        this.json = json;
    }

    @Override
    public JsonNode readPatient(String logicalId) {
        MiniHisResponse response = client.getOne("/patients/" + MiniHisClient.encode(logicalId));
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
        MiniHisResponse response = client.getList(
                "/patients?system=" + MiniHisClient.encode(identifierSystem)
                        + "&value=" + MiniHisClient.encode(identifierValue));
        if (response.status() == 404) {
            return collection("Patient", json.createArrayNode(), false);
        }
        JsonNode body = response.body();
        if (body == null || !body.isArray() || response.truncated() || body.size() > 1) {
            throw ClinicalReadException.invalidSource();
        }
        if (body.isEmpty()) {
            return collection("Patient", json.createArrayNode(), false);
        }
        ObjectNode resource = normalizer.patient(body.get(0));
        if (!containsIdentifier(resource, identifierSystem, identifierValue)) {
            throw ClinicalReadException.invalidSource();
        }
        return collection("Patient", json.createArrayNode().add(resource), false);
    }

    @Override
    public JsonNode readEncounter(String logicalId) {
        MiniHisResponse response = client.getOne("/consultations/" + MiniHisClient.encode(logicalId));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        ObjectNode resource = normalizer.encounter(response.body());
        if (!logicalId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        return readEnvelope(resource);
    }

    @Override
    public JsonNode searchEncounters(String patientId, String status) {
        MiniHisResponse response = client.getList(
                "/patients/" + MiniHisClient.encode(patientId) + "/consultations");
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        if (!response.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode();
        for (JsonNode item : response.body()) {
            if (!patientId.equals(MiniHisNormalizer.required(item, "patientId"))) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode encounter = normalizer.encounter(item);
            if (status.equals(encounter.path("status").asText())) {
                resources.add(encounter);
            }
        }
        return collection("Encounter", resources, response.truncated());
    }

    @Override
    public JsonNode readObservation(String logicalId) {
        MiniHisResponse response = client.getOne("/results/" + MiniHisClient.encode(logicalId));
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
        MiniHisResponse response = client.getList(
                "/results?patientId=" + MiniHisClient.encode(patientId) + "&status=" + MiniHisClient.encode(status));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        if (!response.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode();
        for (JsonNode item : response.body()) {
            if (!patientId.equals(MiniHisNormalizer.required(item, "patientId"))) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode observation = normalizer.observation(item);
            if (!status.equals(observation.path("status").asText())) {
                throw ClinicalReadException.invalidSource();
            }
            resources.add(observation);
        }
        return collection("Observation", resources, response.truncated());
    }

    @Override
    public JsonNode readAppointment(String logicalId) {
        MiniHisResponse response = client.getOne("/appointments/" + MiniHisClient.encode(logicalId));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        ObjectNode resource = normalizer.appointment(response.body());
        if (!logicalId.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        return readEnvelope(resource);
    }

    @Override
    public JsonNode searchAppointments(String patientId) {
        MiniHisResponse response = client.getList("/appointments?patientId=" + MiniHisClient.encode(patientId));
        if (response.status() == 404) {
            throw ClinicalReadException.notFound();
        }
        if (!response.body().isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode();
        for (JsonNode item : response.body()) {
            if (!patientId.equals(MiniHisNormalizer.required(item, "patientId"))) {
                throw ClinicalReadException.invalidSource();
            }
            resources.add(normalizer.appointment(item));
        }
        return collection("Appointment", resources, response.truncated());
    }

    private static boolean containsIdentifier(JsonNode resource, String system, String value) {
        JsonNode identifiers = resource.path("identifier");
        if (!identifiers.isArray()) {
            return false;
        }
        for (JsonNode identifier : identifiers) {
            if (system.equals(identifier.path("system").asText())
                    && value.equals(identifier.path("value").asText())) {
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
