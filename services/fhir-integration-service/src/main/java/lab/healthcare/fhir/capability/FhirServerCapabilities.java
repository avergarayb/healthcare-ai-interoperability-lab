package lab.healthcare.fhir.capability;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Destination-specific snapshot of a CapabilityStatement. Does not cache and
 * does not expose HAPI types to callers.
 */
public record FhirServerCapabilities(
        String destination,
        String fhirVersion,
        String softwareName,
        String implementationUrl,
        Map<String, FhirResourceCapabilities> resources) {

    public FhirServerCapabilities {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (fhirVersion == null || fhirVersion.isBlank()) {
            throw new IllegalArgumentException("FHIR version must be provided");
        }
        destination = destination.trim();
        fhirVersion = fhirVersion.trim();
        softwareName = softwareName == null ? "" : softwareName.trim();
        implementationUrl = implementationUrl == null ? "" : implementationUrl.trim();
        Map<String, FhirResourceCapabilities> copy = new LinkedHashMap<>();
        if (resources != null) {
            for (Map.Entry<String, FhirResourceCapabilities> entry : resources.entrySet()) {
                if (entry.getKey() == null || entry.getKey().isBlank() || entry.getValue() == null) {
                    continue;
                }
                copy.put(entry.getValue().resourceType(), entry.getValue());
            }
        }
        resources = Collections.unmodifiableMap(copy);
    }

    public boolean supportsResource(String resourceType) {
        return resource(resourceType).isPresent();
    }

    public boolean supports(String resourceType, FhirInteraction interaction) {
        return resource(resourceType).map(capabilities -> capabilities.supports(interaction)).orElse(false);
    }

    public Optional<FhirResourceCapabilities> resource(String resourceType) {
        if (resourceType == null || resourceType.isBlank()) {
            return Optional.empty();
        }
        return Optional.ofNullable(resources.get(resourceType.trim()));
    }
}
