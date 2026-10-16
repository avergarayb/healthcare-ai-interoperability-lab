package lab.healthcare.fhir.clinicalread.minihis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Maps proprietary Mini HIS JSON to FHIR R4. Missing required values fail;
 * fields the source does not have are omitted.
 */
final class MiniHisNormalizer {

    static final String SOURCE = "https://lab.local/mini-his";
    static final String PATIENT_SYSTEM = "https://lab.local/mini-his/patient";
    static final String CONSULTATION_SYSTEM = "https://lab.local/mini-his/consultation";
    static final String RESULT_SYSTEM = "https://lab.local/mini-his/result";
    static final String CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category";
    static final String ENCOUNTER_CLASS_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-ActCode";
    private static final String AMBULATORY_CARE = "ambulatory";
    private static final String AMBULATORY_CODE = "AMB";
    private static final String FINAL_RESULT = "final";

    private static final Pattern DECIMAL = Pattern.compile("-?(?:0|[1-9]\\d*)(?:\\.\\d+)?");
    private static final Set<String> SEX = Set.of("female", "male", "unknown");

    private final ObjectMapper json;

    MiniHisNormalizer(ObjectMapper json) {
        this.json = json;
    }

    ObjectNode patient(JsonNode source) {
        String id = required(source, "patientId");
        String family = required(source, "familyName");
        String given = required(source, "givenName");
        String sex = required(source, "administrativeSex");
        if (!SEX.contains(sex)) {
            throw ClinicalReadException.invalidSource();
        }
        ObjectNode resource = resource("Patient", id, PATIENT_SYSTEM);
        ObjectNode name = resource.putArray("name").addObject();
        name.put("family", family);
        name.putArray("given").add(given);
        resource.put("gender", sex);
        String birthDate = optional(source, "birthDate");
        if (birthDate != null) {
            try {
                resource.put("birthDate", LocalDate.parse(birthDate).toString());
            } catch (DateTimeParseException ex) {
                throw ClinicalReadException.invalidSource();
            }
        }
        return resource;
    }

    ObjectNode encounter(JsonNode source) {
        String id = required(source, "consultationId");
        String patientId = required(source, "patientId");
        String occurredAt = instant(required(source, "occurredAt"));
        ObjectNode resource = resource("Encounter", id, CONSULTATION_SYSTEM);
        resource.put("status", encounterStatus(required(source, "status")));
        resource.set("class", encounterClass(required(source, "careClass")));
        resource.putObject("subject").put("reference", "Patient/" + patientId);
        resource.putObject("period").put("start", occurredAt);
        String reason = optional(source, "reason");
        if (reason != null) {
            resource.putArray("reasonCode").addObject().put("text", reason);
        }
        String clinician = optional(source, "clinicianName");
        if (clinician != null) {
            resource.putArray("participant").addObject().putObject("individual").put("display", clinician);
        }
        return resource;
    }

    ObjectNode observation(JsonNode source) {
        String id = required(source, "resultId");
        String consultationId = required(source, "consultationId");
        String patientId = required(source, "patientId");
        String resultType = required(source, "resultType");
        String displayName = required(source, "displayName");
        ObjectNode resource = resource("Observation", id, RESULT_SYSTEM);
        resource.put("status", observationStatus(required(source, "status")));
        ObjectNode coding = resource.putArray("category").addObject().putArray("coding").addObject();
        coding.put("system", CATEGORY_SYSTEM);
        coding.put("code", category(resultType));
        resource.putObject("code").put("text", displayName);
        resource.putObject("subject").put("reference", "Patient/" + patientId);
        resource.putObject("encounter").put("reference", "Encounter/" + consultationId);
        String observedAt = optional(source, "observedAt");
        if (observedAt != null) {
            resource.put("effectiveDateTime", instant(observedAt));
        }
        putValue(resource, optional(source, "valueText"), optional(source, "unit"));
        return resource;
    }

    private ObjectNode resource(String resourceType, String id, String system) {
        ObjectNode resource = json.createObjectNode();
        resource.put("resourceType", resourceType);
        resource.put("id", id);
        resource.putObject("meta").put("source", SOURCE);
        ObjectNode identifier = resource.putArray("identifier").addObject();
        identifier.put("system", system);
        identifier.put("value", id);
        return resource;
    }

    private static void putValue(ObjectNode resource, String valueText, String unit) {
        if (valueText == null && unit == null) {
            return;
        }
        if (valueText != null && DECIMAL.matcher(valueText).matches()) {
            ObjectNode quantity = resource.putObject("valueQuantity");
            quantity.put("value", new BigDecimal(valueText));
            if (unit != null) {
                quantity.put("unit", unit);
            }
            return;
        }
        if (valueText != null && unit == null) {
            resource.put("valueString", valueText);
            return;
        }
        throw ClinicalReadException.invalidSource();
    }

    private ObjectNode encounterClass(String careClass) {
        if (!AMBULATORY_CARE.equals(careClass)) {
            throw ClinicalReadException.invalidSource();
        }
        ObjectNode coding = json.createObjectNode();
        coding.put("system", ENCOUNTER_CLASS_SYSTEM);
        coding.put("code", AMBULATORY_CODE);
        coding.put("display", AMBULATORY_CARE);
        return coding;
    }

    private static String observationStatus(String status) {
        if (!FINAL_RESULT.equals(status)) {
            throw ClinicalReadException.invalidSource();
        }
        return FINAL_RESULT;
    }

    private static String encounterStatus(String status) {
        return switch (status) {
            case "completed" -> "finished";
            case "in_progress" -> "in-progress";
            default -> throw ClinicalReadException.invalidSource();
        };
    }

    private static String category(String resultType) {
        return switch (resultType) {
            case "laboratory" -> "laboratory";
            case "vital_sign" -> "vital-signs";
            default -> throw ClinicalReadException.invalidSource();
        };
    }

    private static String instant(String value) {
        try {
            return OffsetDateTime.parse(value).toInstant().toString();
        } catch (DateTimeParseException ex) {
            throw ClinicalReadException.invalidSource();
        }
    }

    static String required(JsonNode source, String field) {
        String value = optional(source, field);
        if (value == null) {
            throw ClinicalReadException.invalidSource();
        }
        return value;
    }

    static String optional(JsonNode source, String field) {
        if (source == null || !source.isObject()) {
            throw ClinicalReadException.invalidSource();
        }
        JsonNode node = source.get(field);
        if (node == null || node.isNull()) {
            return null;
        }
        if (!node.isTextual()) {
            throw ClinicalReadException.invalidSource();
        }
        String value = node.asText().trim();
        return value.isEmpty() ? null : value;
    }
}
