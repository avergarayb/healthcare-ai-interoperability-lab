package lab.healthcare.fhir.mapping;

import java.util.List;

public record MappingDefinition(String resourceType, List<FieldMapping> fields) {

    public MappingDefinition {
        if (resourceType == null || resourceType.isBlank()) {
            throw new IllegalArgumentException("Mapping definition resource type must be provided");
        }
        if (fields == null || fields.isEmpty()) {
            throw new IllegalArgumentException("Mapping definition fields must be provided");
        }
        resourceType = resourceType.trim();
        fields = List.copyOf(fields);
    }
}
