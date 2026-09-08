package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.server.FhirServerProfile;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Retrieves the Epic sandbox CapabilityStatement through the existing
 * provider-neutral discovery service. Does not read Patient, does not persist
 * tokens, and does not invent Epic hosts.
 */
@Component
public class EpicSandboxCapabilityDiscoveryService {

    private final EpicProfileValidator validator;
    private final FhirClientFactory clientFactory;
    private final FhirCapabilityDiscoveryService capabilityDiscovery;

    @Autowired
    public EpicSandboxCapabilityDiscoveryService(
            EpicProfileValidator validator, FhirClientFactory clientFactory) {
        this(validator, clientFactory, new FhirCapabilityDiscoveryService());
    }

    EpicSandboxCapabilityDiscoveryService(
            EpicProfileValidator validator,
            FhirClientFactory clientFactory,
            FhirCapabilityDiscoveryService capabilityDiscovery) {
        if (validator == null) {
            throw new IllegalArgumentException("Epic profile validator must be provided");
        }
        if (clientFactory == null) {
            throw new IllegalArgumentException("FHIR client factory must be provided");
        }
        if (capabilityDiscovery == null) {
            throw new IllegalArgumentException("FHIR capability discovery service must be provided");
        }
        this.validator = validator;
        this.clientFactory = clientFactory;
        this.capabilityDiscovery = capabilityDiscovery;
    }

    public FhirServerCapabilities discover(EpicIntegrationProfile profile) {
        if (profile == null) {
            throw new EpicProfileException("Epic integration profile is missing");
        }
        if (!profile.enabled()) {
            throw new EpicProfileException("Epic sandbox profile is disabled");
        }
        if (profile.environment() != EpicEnvironment.SANDBOX) {
            throw new EpicProfileException("Epic capability discovery is only supported for SANDBOX");
        }
        validator.validateForConnectivity(profile);
        FhirServerProfile unauthenticated = profile.toUnauthenticatedMetadataProfile();
        return capabilityDiscovery.discover(
                profile.serverProfileName(),
                clientFactory.createClient(clientFactory.createContext(unauthenticated), unauthenticated));
    }
}
