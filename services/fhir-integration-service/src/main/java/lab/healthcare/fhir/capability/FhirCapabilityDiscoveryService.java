package lab.healthcare.fhir.capability;

import lab.healthcare.fhir.client.FhirService;

import ca.uhn.fhir.rest.client.api.IGenericClient;
import org.hl7.fhir.r4.model.CapabilityStatement;
import org.hl7.fhir.r4.model.Enumerations;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/**
 * Turns GET /metadata into an internal capability snapshot. Does not cache,
 * does not invent resources, and does not add FhirService write methods.
 */
public class FhirCapabilityDiscoveryService {

    public FhirServerCapabilities discover(String destination, IGenericClient client) {
        if (client == null) {
            throw new FhirCapabilityException("FHIR client must be provided for capability discovery");
        }
        return interpret(destination, new FhirService(client).retrieveCapabilityStatement());
    }

    public FhirServerCapabilities interpret(String destination, CapabilityStatement statement) {
        if (destination == null || destination.isBlank()) {
            throw new FhirCapabilityException("Capability discovery destination must be provided");
        }
        if (statement == null) {
            throw new FhirCapabilityException("CapabilityStatement is missing");
        }
        String fhirVersion = fhirVersionOf(statement);
        if (fhirVersion == null) {
            throw new FhirCapabilityException("CapabilityStatement is missing fhirVersion");
        }
        return new FhirServerCapabilities(
                destination.trim(),
                fhirVersion,
                softwareNameOf(statement),
                implementationUrlOf(statement),
                resourcesOf(statement));
    }

    private static String fhirVersionOf(CapabilityStatement statement) {
        Enumerations.FHIRVersion version = statement.getFhirVersion();
        if (version == null || version == Enumerations.FHIRVersion.NULL) {
            return null;
        }
        String code = version.toCode();
        return code == null || code.isBlank() ? null : code;
    }

    private static String softwareNameOf(CapabilityStatement statement) {
        if (!statement.hasSoftware() || !statement.getSoftware().hasName()) {
            return "";
        }
        return statement.getSoftware().getName();
    }

    private static String implementationUrlOf(CapabilityStatement statement) {
        if (!statement.hasImplementation() || !statement.getImplementation().hasUrl()) {
            return "";
        }
        return statement.getImplementation().getUrl();
    }

    private static Map<String, FhirResourceCapabilities> resourcesOf(CapabilityStatement statement) {
        Map<String, FhirResourceCapabilities> resources = new LinkedHashMap<>();
        for (CapabilityStatement.CapabilityStatementRestComponent rest : statement.getRest()) {
            if (rest == null) {
                continue;
            }
            for (CapabilityStatement.CapabilityStatementRestResourceComponent resource : rest.getResource()) {
                if (resource == null || !resource.hasType()) {
                    continue;
                }
                String type = resource.getType();
                if (type == null || type.isBlank()) {
                    continue;
                }
                Set<FhirInteraction> interactions = new LinkedHashSet<>();
                for (CapabilityStatement.ResourceInteractionComponent interaction : resource.getInteraction()) {
                    if (interaction == null || !interaction.hasCode()) {
                        continue;
                    }
                    FhirInteraction.fromCode(interaction.getCode().toCode()).ifPresent(interactions::add);
                }
                FhirResourceCapabilities parsed = new FhirResourceCapabilities(type, interactions);
                resources.merge(parsed.resourceType(), parsed, FhirResourceCapabilities::merge);
            }
        }
        return resources;
    }
}
