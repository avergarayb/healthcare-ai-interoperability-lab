package lab.healthcare.fhir.clinicalread.minilis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Maps proprietary Mini LIS JSON to FHIR R4. Test codes stay in the Mini LIS
 * code system. This class does not invent LOINC or UCUM equivalences.
 */
final class MiniLisNormalizer {

    static final String SOURCE = "https://lab.local/mini-lis";
    static final String PATIENT_SYSTEM = "https://lab.local/mini-lis/patient";
    static final String ORDER_SYSTEM = "https://lab.local/mini-lis/order";
    static final String RESULT_SYSTEM = "https://lab.local/mini-lis/result";
    static final String TEST_SYSTEM = "https://lab.local/mini-lis/test";
    static final String ORGANIZATION_SYSTEM = "https://lab.local/mini-lis/organization";
    static final String CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category";
    private static final Pattern DECIMAL = Pattern.compile("-?(?:0|[1-9]\\d*)(?:\\.\\d+)?");
    private static final Pattern LOGICAL_ID = Pattern.compile("[A-Za-z0-9\\-.]{1,64}");

    private final ObjectMapper json;

    MiniLisNormalizer(ObjectMapper json) {
        this.json = json;
    }

    static String externalPatientSystem(String organizationId) {
        return SOURCE + "/organization/" + organizationId + "/patient";
    }

    ObjectNode patient(JsonNode source) {
        String id = requiredId(source, "patientId");
        String organizationId = requiredId(source, "organizationId");
        String externalId = requiredId(source, "externalId");
        String family = requiredText(source, "familyName");
        String given = requiredText(source, "givenName");
        String sex = requiredText(source, "administrativeSex");
        if (!List.of("female", "male", "unknown").contains(sex)) {
            throw ClinicalReadException.invalidSource();
        }
        ObjectNode resource = resource("Patient", id, PATIENT_SYSTEM, id);
        resource.withArray("identifier").add(identifier(externalPatientSystem(organizationId), externalId));
        ObjectNode name = resource.putArray("name").addObject();
        name.put("family", family);
        name.putArray("given").add(given);
        resource.put("gender", sex);
        String birthDate = requiredText(source, "birthDate");
        try {
            resource.put("birthDate", LocalDate.parse(birthDate).toString());
        } catch (DateTimeParseException ex) {
            throw ClinicalReadException.invalidSource();
        }
        resource.putObject("managingOrganization").set("identifier", identifier(ORGANIZATION_SYSTEM, organizationId));
        return resource;
    }

    ObjectNode serviceRequest(JsonNode source) {
        String id = requiredId(source, "orderId");
        String patientId = requiredId(source, "patientId");
        String requester = requiredId(source, "requestingOrganizationId");
        String externalRequestId = requiredId(source, "externalRequestId");
        ObjectNode resource = resource("ServiceRequest", id, ORDER_SYSTEM, externalRequestId);
        resource.put("status", serviceRequestStatus(requiredText(source, "status")));
        resource.put("intent", "order");
        resource.putObject("subject").put("reference", "Patient/" + patientId);
        resource.set("code", testCode(requiredId(source, "testCode"), requiredText(source, "testDescription")));
        resource.put("authoredOn", instant(requiredText(source, "requestedAt")));
        resource.putObject("requester").set("identifier", identifier(ORGANIZATION_SYSTEM, requester));
        return resource;
    }

    ObjectNode observation(JsonNode source) {
        String id = requiredId(source, "resultId");
        String orderId = requiredId(source, "orderId");
        String patientId = text(source, "patientId");
        ObjectNode resource = resource("Observation", id, RESULT_SYSTEM, requiredId(source, "externalResultId"));
        resource.put("status", observationStatus(requiredText(source, "status")));
        ObjectNode category = resource.putArray("category").addObject().putArray("coding").addObject();
        category.put("system", CATEGORY_SYSTEM);
        category.put("code", "laboratory");
        resource.set("code", testCode(requiredId(source, "testCode"), null));
        if (patientId != null) {
            resource.putObject("subject").put("reference", "Patient/" + patientId);
        }
        resource.putArray("basedOn").addObject().put("reference", "ServiceRequest/" + orderId);
        resource.put("effectiveDateTime", instant(requiredText(source, "resultedAt")));
        putValue(resource, requiredText(source, "value"), text(source, "unit"));
        String range = text(source, "referenceRange");
        if (range != null) {
            resource.putArray("referenceRange").addObject().put("text", range);
        }
        return resource;
    }

    ObjectNode diagnosticReport(JsonNode order, JsonNode results, String patientId) {
        String id = requiredId(order, "orderId");
        if (results == null || !results.isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ObjectNode resource = resource("DiagnosticReport", id, ORDER_SYSTEM, requiredId(order, "externalRequestId"));
        resource.put("status", reportStatus(requiredText(order, "status")));
        resource.set("code", testCode(requiredId(order, "testCode"), requiredText(order, "testDescription")));
        resource.putObject("subject").put("reference", "Patient/" + patientId);
        resource.putArray("basedOn").addObject().put("reference", "ServiceRequest/" + id);
        resource.put("effectiveDateTime", instant(requiredText(order, "requestedAt")));
        var resultReferences = resource.putArray("result");
        for (JsonNode result : results) {
            if (!id.equals(requiredId(result, "orderId"))) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode observation = observation(withPatient(result, patientId));
            resultReferences.addObject().put("reference", "Observation/" + observation.path("id").asText());
        }
        return resource;
    }

    private ObjectNode withPatient(JsonNode result, String patientId) {
        if (result instanceof ObjectNode object && text(object, "patientId") == null) {
            object.put("patientId", patientId);
        }
        return (ObjectNode) result;
    }

    private void putValue(ObjectNode resource, String value, String unit) {
        if (unit != null && DECIMAL.matcher(value).matches()) {
            ObjectNode quantity = resource.putObject("valueQuantity");
            quantity.put("value", new BigDecimal(value));
            quantity.put("unit", unit);
            return;
        }
        resource.put("valueString", value);
    }

    private ObjectNode testCode(String code, String description) {
        ObjectNode codeable = json.createObjectNode();
        ObjectNode coding = codeable.putArray("coding").addObject();
        coding.put("system", TEST_SYSTEM);
        coding.put("code", code);
        if (description != null) {
            codeable.put("text", description);
        }
        return codeable;
    }

    private ObjectNode resource(String type, String id, String system, String value) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", type);
        resource.put("id", id);
        resource.putObject("meta").put("source", SOURCE);
        resource.putArray("identifier").add(identifier(system, value));
        return resource;
    }

    private ObjectNode identifier(String system, String value) {
        ObjectNode identifier = json.createObjectNode();
        identifier.put("system", system);
        identifier.put("value", value);
        return identifier;
    }

    static String serviceRequestStatus(String status) {
        return switch (status) {
            case "ORDERED", "IN_PROGRESS" -> "active";
            case "COMPLETED" -> "completed";
            case "CANCELLED" -> "revoked";
            default -> throw ClinicalReadException.invalidSource();
        };
    }

    static String observationStatus(String status) {
        return switch (status) {
            case "PRELIMINARY" -> "preliminary";
            case "FINAL" -> "final";
            case "CANCELLED" -> "cancelled";
            default -> throw ClinicalReadException.invalidSource();
        };
    }

    static String reportStatus(String status) {
        return switch (status) {
            case "ORDERED" -> "registered";
            case "IN_PROGRESS" -> "partial";
            case "COMPLETED" -> "final";
            case "CANCELLED" -> "cancelled";
            default -> throw ClinicalReadException.invalidSource();
        };
    }

    private static String requiredId(JsonNode source, String field) {
        String value = requiredText(source, field);
        if (!LOGICAL_ID.matcher(value).matches()) {
            throw ClinicalReadException.invalidSource();
        }
        return value;
    }

    private static String requiredText(JsonNode source, String field) {
        String value = text(source, field);
        if (value == null) {
            throw ClinicalReadException.invalidSource();
        }
        return value;
    }

    private static String text(JsonNode source, String field) {
        if (source == null || !source.has(field) || source.get(field).isNull()) {
            return null;
        }
        String value = source.get(field).asText();
        if (value.isBlank()) {
            return null;
        }
        return value;
    }

    private static String instant(String value) {
        try {
            return OffsetDateTime.parse(value).toInstant().toString();
        } catch (DateTimeParseException ex) {
            throw ClinicalReadException.invalidSource();
        }
    }
}
