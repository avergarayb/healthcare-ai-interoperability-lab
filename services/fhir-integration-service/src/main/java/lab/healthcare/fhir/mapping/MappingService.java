package lab.healthcare.fhir.mapping;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.hl7.fhir.r4.model.DateType;
import org.hl7.fhir.r4.model.Observation;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Quantity;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.Resource;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;

@Service
public class MappingService {

    private final ObjectMapper objectMapper;

    public MappingService() {
        this(new ObjectMapper());
    }

    MappingService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper == null ? new ObjectMapper() : objectMapper;
    }

    public Patient mapPatient(String json, MappingDefinition definition) {
        Resource resource = map(json, definition);
        if (!(resource instanceof Patient patient)) {
            throw new MappingException("Mapped resource is not a Patient");
        }
        return patient;
    }

    public Observation mapObservation(String json, MappingDefinition definition) {
        Resource resource = map(json, definition);
        if (!(resource instanceof Observation observation)) {
            throw new MappingException("Mapped resource is not an Observation");
        }
        return observation;
    }

    public Resource map(String json, MappingDefinition definition) {
        if (definition == null) {
            throw new IllegalArgumentException("Mapping definition must be provided");
        }
        JsonNode payload = parseObject(json);
        Resource resource = newResource(definition.resourceType());
        for (FieldMapping field : definition.fields()) {
            apply(resource, definition.resourceType(), field, payload);
        }
        return resource;
    }

    private JsonNode parseObject(String json) {
        if (json == null || json.isBlank()) {
            throw new MappingException("JSON payload must be provided");
        }
        JsonNode root;
        try {
            root = objectMapper.readTree(json);
        } catch (JsonProcessingException ex) {
            throw new MappingException("JSON payload is not valid JSON", ex);
        }
        if (root == null || !root.isObject()) {
            throw new MappingException("JSON payload must be an object");
        }
        return root;
    }

    private static Resource newResource(String resourceType) {
        return switch (resourceType) {
            case "Patient" -> new Patient();
            case "Observation" -> new Observation();
            default -> throw new MappingException("Unsupported mapping resource type: " + resourceType);
        };
    }

    private void apply(Resource resource, String resourceType, FieldMapping field, JsonNode payload) {
        Object value = field.isConstant()
                ? convertText(field.constant(), field.target(), field.conversion())
                : convert(sourceNode(payload, field.source()), field.source(), field.conversion());
        write(resource, resourceType, field.target(), value);
    }

    private static JsonNode sourceNode(JsonNode payload, String source) {
        JsonNode node = payload;
        for (String part : source.split("\\.")) {
            node = node.path(part);
        }
        if (node.isMissingNode() || node.isNull()) {
            throw new MappingException("Required source field missing: " + source);
        }
        return node;
    }

    private static Object convert(JsonNode node, String source, MappingConversion conversion) {
        return convertText(scalarText(node, source), source, conversion);
    }

    private static String scalarText(JsonNode node, String source) {
        if (node.isTextual() || node.isNumber()) {
            String text = node.asText().trim();
            if (text.isBlank()) {
                throw new MappingException("Required source field missing: " + source);
            }
            return text;
        }
        throw new MappingException("Source field " + source + " must be a string or number");
    }

    private static Object convertText(String text, String field, MappingConversion conversion) {
        if (text == null || text.isBlank()) {
            throw new MappingException("Required source field missing: " + field);
        }
        return switch (conversion) {
            case STRING -> text;
            case DATE -> parseDate(text, field);
            case DECIMAL -> parseDecimal(text, field);
            case PATIENT_REFERENCE -> patientReference(text);
        };
    }

    private static String parseDate(String text, String field) {
        try {
            return LocalDate.parse(text).toString();
        } catch (DateTimeParseException ex) {
            throw new MappingException("Invalid date for source field " + field + ": " + text, ex);
        }
    }

    private static BigDecimal parseDecimal(String text, String field) {
        try {
            return new BigDecimal(text);
        } catch (NumberFormatException ex) {
            throw new MappingException("Invalid decimal for source field " + field + ": " + text, ex);
        }
    }

    private static String patientReference(String value) {
        if (value.startsWith("Patient/")) {
            return value;
        }
        return "Patient/" + value;
    }

    private static void write(Resource resource, String resourceType, String target, Object value) {
        String path = normalize(target);
        if ("Patient".equals(resourceType) && resource instanceof Patient patient) {
            writePatient(patient, path, value);
            return;
        }
        if ("Observation".equals(resourceType) && resource instanceof Observation observation) {
            writeObservation(observation, path, value);
            return;
        }
        throw new MappingException("Unsupported target path: " + target);
    }

    private static void writePatient(Patient patient, String path, Object value) {
        switch (path) {
            case "identifier.value" -> patient.getIdentifierFirstRep().setValue((String) value);
            case "name.family" -> patient.getNameFirstRep().setFamily((String) value);
            case "name.given", "name.given[0]" -> setGiven(patient, (String) value);
            case "birthdate" -> patient.setBirthDateElement(new DateType((String) value));
            default -> throw new MappingException("Unsupported target path: " + path);
        }
    }

    private static void setGiven(Patient patient, String given) {
        if (patient.getNameFirstRep().hasGiven()) {
            patient.getNameFirstRep().getGiven().getFirst().setValue(given);
        } else {
            patient.getNameFirstRep().addGiven(given);
        }
    }

    private static void writeObservation(Observation observation, String path, Object value) {
        switch (path) {
            case "subject.reference" -> observation.setSubject(new Reference((String) value));
            case "code.coding[0].code" -> observation.getCode().getCodingFirstRep().setCode((String) value);
            case "code.coding[0].system" -> observation.getCode().getCodingFirstRep().setSystem((String) value);
            case "valuequantity.value" -> quantity(observation).setValue((BigDecimal) value);
            case "valuequantity.unit" -> quantity(observation).setUnit((String) value);
            case "status" -> setStatus(observation, (String) value);
            default -> throw new MappingException("Unsupported target path: " + path);
        }
    }

    private static Quantity quantity(Observation observation) {
        if (!observation.hasValueQuantity()) {
            observation.setValue(new Quantity());
        }
        return observation.getValueQuantity();
    }

    private static void setStatus(Observation observation, String status) {
        Observation.ObservationStatus coded;
        try {
            coded = Observation.ObservationStatus.fromCode(status);
        } catch (RuntimeException ex) {
            throw new MappingException("Invalid Observation status: " + status, ex);
        }
        if (coded == null) {
            throw new MappingException("Invalid Observation status: " + status);
        }
        observation.setStatus(coded);
    }

    private static String normalize(String target) {
        return target.replace("_", "").toLowerCase();
    }
}
