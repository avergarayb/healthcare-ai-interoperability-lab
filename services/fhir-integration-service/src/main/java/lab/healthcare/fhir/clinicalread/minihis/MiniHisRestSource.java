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
        if (!MiniHisNormalizer.PATIENT_SYSTEM.equals(identifierSystem)) {
            requireAvailable();
            return collection("Patient", json.createArrayNode(), false);
        }
        MiniHisResponse response = client.getOne("/patients/" + MiniHisClient.encode(identifierValue));
        if (response.status() == 404) {
            return collection("Patient", json.createArrayNode(), false);
        }
        ObjectNode resource = normalizer.patient(response.body());
        if (!identifierValue.equals(resource.path("id").asText())) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode resources = json.createArrayNode().add(resource);
        return collection("Patient", resources, false);
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
        throw ClinicalReadException.operationNotSupported();
    }

    @Override
    public JsonNode searchAppointments(String patientId) {
        throw ClinicalReadException.operationNotSupported();
    }

    private void requireAvailable() {
        MiniHisResponse response = client.getList("/patients");
        if (response.status() != 200) {
            throw ClinicalReadException.unavailable();
        }
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
