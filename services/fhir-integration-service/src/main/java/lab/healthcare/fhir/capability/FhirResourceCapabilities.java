package lab.healthcare.fhir.capability;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;

/**
 * Interactions declared for one resource type on one server.
 */
public record FhirResourceCapabilities(String resourceType, Set<FhirInteraction> interactions) {

    public FhirResourceCapabilities {
        if (resourceType == null || resourceType.isBlank()) {
            throw new IllegalArgumentException("Resource type must be provided");
        }
        resourceType = resourceType.trim();
        Set<FhirInteraction> copy = new LinkedHashSet<>();
        if (interactions != null) {
            for (FhirInteraction interaction : interactions) {
                if (interaction != null) {
                    copy.add(interaction);
                }
            }
        }
        interactions = Collections.unmodifiableSet(copy);
    }

    public boolean supports(FhirInteraction interaction) {
        return interaction != null && interactions.contains(interaction);
    }

    FhirResourceCapabilities merge(FhirResourceCapabilities other) {
        if (other == null || !resourceType.equals(other.resourceType)) {
            return this;
        }
        Set<FhirInteraction> combined = new LinkedHashSet<>(interactions);
        combined.addAll(other.interactions);
        return new FhirResourceCapabilities(resourceType, combined);
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) {
            return true;
        }
        if (!(other instanceof FhirResourceCapabilities that)) {
            return false;
        }
        return resourceType.equals(that.resourceType) && interactions.equals(that.interactions);
    }

    @Override
    public int hashCode() {
        return Objects.hash(resourceType, interactions);
    }
}
