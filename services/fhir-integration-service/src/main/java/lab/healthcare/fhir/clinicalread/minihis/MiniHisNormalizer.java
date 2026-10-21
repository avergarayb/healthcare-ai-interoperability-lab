package lab.healthcare.fhir.clinicalread.minihis;

import lab.healthcare.fhir.clinicalread.ClinicalReadException;
import lab.healthcare.fhir.terminology.QuantityUnitMapping;
import lab.healthcare.fhir.terminology.QuantityUnitRegistry;
import lab.healthcare.fhir.terminology.StaticQuantityUnitRegistry;
import lab.healthcare.fhir.terminology.StaticTerminologyRegistry;
import lab.healthcare.fhir.terminology.TerminologyDomain;
import lab.healthcare.fhir.terminology.TerminologyMapping;
import lab.healthcare.fhir.terminology.TerminologyMappingNotFound;
import lab.healthcare.fhir.terminology.TerminologyRegistry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.HashSet;
import java.util.Optional;
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
    static final String APPOINTMENT_SYSTEM = "https://lab.local/mini-his/appointment";
    /**
     * FHIR requires participant.status. Mini HIS does not record an individual
     * response, so the participant stays needs-action. Appointment status is
     * not copied onto the participant: confirmed does not become accepted.
     */
    static final String PARTICIPANT_NEEDS_ACTION = "needs-action";
    private static final String AMBULATORY_CARE = "ambulatory";
    private static final TerminologyRegistry TERMINOLOGY = StaticTerminologyRegistry.miniHis();
    private static final QuantityUnitRegistry UNITS = StaticQuantityUnitRegistry.miniHis();

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
        appendIdentifiers(resource, id, source.get("identifiers"));
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
        String status = encounterStatus(required(source, "status"));
        ObjectNode resource = resource("Encounter", id, CONSULTATION_SYSTEM);
        resource.put("status", status);
        resource.set("class", encounterClass(required(source, "careClass")));
        resource.putObject("subject").put("reference", "Patient/" + patientId);
        ObjectNode period = resource.putObject("period");
        period.put("start", occurredAt);
        if ("finished".equals(status)) {
            period.put("end", occurredAt);
        }
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
            String observed = instant(observedAt);
            resource.put("effectiveDateTime", observed);
            resource.put("issued", observed);
        }
        JsonNode components = source.get("components");
        if (components == null || components.isNull() || (components.isArray() && components.isEmpty())) {
            putValue(resource, optional(source, "valueText"), optional(source, "unit"));
        } else {
            putComponents(resource, components);
        }
        return resource;
    }

    ObjectNode appointment(JsonNode source) {
        String id = required(source, "appointmentId");
        String patientId = required(source, "patientId");
        ObjectNode resource = resource("Appointment", id, APPOINTMENT_SYSTEM);
        resource.put("status", appointmentStatus(required(source, "status")));
        resource.put("start", instant(required(source, "start")));
        ObjectNode participant = resource.putArray("participant").addObject();
        participant.put("status", PARTICIPANT_NEEDS_ACTION);
        participant.putObject("actor").put("reference", "Patient/" + patientId);
        return resource;
    }

    private static void appendIdentifiers(ObjectNode resource, String patientId, JsonNode extra) {
        if (extra == null || extra.isNull()) {
            return;
        }
        if (!extra.isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        ArrayNode identifiers = (ArrayNode) resource.get("identifier");
        Set<String> seen = new HashSet<>();
        seen.add(PATIENT_SYSTEM + "\n" + patientId);
        for (JsonNode item : extra) {
            if (item == null || !item.isObject()) {
                throw ClinicalReadException.invalidSource();
            }
            String system = required(item, "system");
            String value = required(item, "value");
            if (PATIENT_SYSTEM.equals(system) || !seen.add(system + "\n" + value)) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode identifier = identifiers.addObject();
            identifier.put("system", system);
            identifier.put("value", value);
        }
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
            applyQuantity(resource.putObject("valueQuantity"), new BigDecimal(valueText), unit);
            return;
        }
        if (valueText != null && unit == null) {
            resource.put("valueString", valueText);
            return;
        }
        throw ClinicalReadException.invalidSource();
    }

    private static void putComponents(ObjectNode resource, JsonNode components) {
        if (!components.isArray()) {
            throw ClinicalReadException.invalidSource();
        }
        Set<String> ids = new HashSet<>();
        Set<String> names = new HashSet<>();
        ArrayNode target = resource.putArray("component");
        for (JsonNode item : components) {
            if (item == null || !item.isObject()) {
                throw ClinicalReadException.invalidSource();
            }
            String componentId = required(item, "componentId");
            String name = required(item, "name");
            String value = required(item, "valueDecimal");
            String unit = required(item, "unit");
            if (!DECIMAL.matcher(value).matches() || !ids.add(componentId) || !names.add(name)) {
                throw ClinicalReadException.invalidSource();
            }
            ObjectNode component = target.addObject();
            component.putObject("code").put("text", name);
            applyQuantity(component.putObject("valueQuantity"), new BigDecimal(value), unit);
        }
    }

    private static void applyQuantity(ObjectNode quantity, BigDecimal value, String unit) {
        quantity.put("value", value);
        if (unit == null) {
            return;
        }
        Optional<QuantityUnitMapping> coding = UNITS.find(StaticQuantityUnitRegistry.MINI_HIS, unit);
        if (coding.isEmpty()) {
            quantity.put("unit", unit);
            return;
        }
        QuantityUnitMapping mapping = coding.get();
        quantity.put("unit", mapping.unitText());
        quantity.put("system", mapping.system());
        quantity.put("code", mapping.code());
    }

    private ObjectNode encounterClass(String careClass) {
        TerminologyMapping mapping = mapped(TerminologyDomain.ENCOUNTER_CLASS, careClass);
        if (!ENCOUNTER_CLASS_SYSTEM.equals(mapping.targetSystem())) {
            throw ClinicalReadException.invalidSource();
        }
        ObjectNode coding = json.createObjectNode();
        coding.put("system", ENCOUNTER_CLASS_SYSTEM);
        coding.put("code", mapping.targetCode());
        coding.put("display", AMBULATORY_CARE);
        return coding;
    }

    private static String observationStatus(String status) {
        return statusCode(TerminologyDomain.OBSERVATION_STATUS, status);
    }

    private static String appointmentStatus(String status) {
        return statusCode(TerminologyDomain.APPOINTMENT_STATUS, status);
    }

    private static String encounterStatus(String status) {
        return statusCode(TerminologyDomain.ENCOUNTER_STATUS, status);
    }

    private static String category(String resultType) {
        TerminologyMapping mapping = mapped(TerminologyDomain.OBSERVATION_CATEGORY, resultType);
        if (!CATEGORY_SYSTEM.equals(mapping.targetSystem())) {
            throw ClinicalReadException.invalidSource();
        }
        return mapping.targetCode();
    }

    private static String statusCode(TerminologyDomain domain, String sourceCode) {
        TerminologyMapping mapping = mapped(domain, sourceCode);
        if (mapping.targetSystem() != null) {
            throw ClinicalReadException.invalidSource();
        }
        return mapping.targetCode();
    }

    private static TerminologyMapping mapped(TerminologyDomain domain, String sourceCode) {
        try {
            return TERMINOLOGY.resolve(StaticTerminologyRegistry.MINI_HIS, domain, sourceCode);
        } catch (TerminologyMappingNotFound ex) {
            throw ClinicalReadException.invalidSource();
        }
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
