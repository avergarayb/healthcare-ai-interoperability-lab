package lab.healthcare.fhir.observability;

public record FhirOperationContext(
        String correlationId,
        String destination,
        FhirAuditOperation operation,
        String resourceType,
        String resourceId) {

    public FhirOperationContext {
        if (correlationId == null || correlationId.isBlank()) {
            throw new IllegalArgumentException("Correlation ID must be provided");
        }
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (operation == null) {
            throw new IllegalArgumentException("Operation must be provided");
        }
        if (resourceType == null || resourceType.isBlank()) {
            throw new IllegalArgumentException("Resource type must be provided");
        }
        correlationId = correlationId.trim();
        destination = destination.trim();
        resourceType = resourceType.trim();
        resourceId = resourceId == null || resourceId.isBlank() ? null : resourceId.trim();
    }
}
