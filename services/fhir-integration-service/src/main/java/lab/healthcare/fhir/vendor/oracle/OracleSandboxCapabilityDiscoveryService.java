package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.capability.FhirCapabilityDiscoveryService;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.client.FhirClientFactory;
import lab.healthcare.fhir.server.FhirServerProfile;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Retrieves the Oracle sandbox CapabilityStatement through the existing
 * provider-neutral discovery service. Does not read Patient, does not persist
 * tokens, and does not invent Oracle hosts.
 */
@Component
public class OracleSandboxCapabilityDiscoveryService {

    private final OracleSandboxReadinessService readinessService;
    private final OracleSandboxProfileValidator validator;
    private final FhirClientFactory clientFactory;
    private final FhirCapabilityDiscoveryService capabilityDiscovery;

    @Autowired
    public OracleSandboxCapabilityDiscoveryService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxProfileValidator validator,
            FhirClientFactory clientFactory) {
        this(readinessService, validator, clientFactory, new FhirCapabilityDiscoveryService());
    }

    OracleSandboxCapabilityDiscoveryService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxProfileValidator validator,
            FhirClientFactory clientFactory,
            FhirCapabilityDiscoveryService capabilityDiscovery) {
        if (readinessService == null) {
            throw new IllegalArgumentException("Oracle sandbox readiness service must be provided");
        }
        if (validator == null) {
            throw new IllegalArgumentException("Oracle sandbox profile validator must be provided");
        }
        if (clientFactory == null) {
            throw new IllegalArgumentException("FHIR client factory must be provided");
        }
        if (capabilityDiscovery == null) {
            throw new IllegalArgumentException("FHIR capability discovery service must be provided");
        }
        this.readinessService = readinessService;
        this.validator = validator;
        this.clientFactory = clientFactory;
        this.capabilityDiscovery = capabilityDiscovery;
    }

    public OracleSandboxReadiness inspect(OracleHealthIntegrationProfile profile) {
        return readinessService.inspect(profile);
    }

    public FhirServerCapabilities discover(OracleHealthIntegrationProfile profile) {
        OracleSandboxReadiness readiness = inspect(profile);
        if (readiness.state() == OracleSandboxReadinessState.DISABLED
                || readiness.state() == OracleSandboxReadinessState.NOT_CONFIGURED) {
            throw new OracleHealthProfileException("Oracle Health sandbox profile is disabled");
        }
        if (readiness.state() == OracleSandboxReadinessState.CONFIGURED) {
            throw new OracleHealthProfileException(
                    "Oracle Health capability discovery is only supported for SANDBOX");
        }
        if (readiness.state() == OracleSandboxReadinessState.INVALID_CONFIGURATION) {
            throw new OracleHealthProfileException(readiness.detail());
        }
        validator.validateForConnectivity(profile);
        FhirServerProfile unauthenticated = profile.toUnauthenticatedMetadataProfile();
        return capabilityDiscovery.discover(
                profile.serverProfileName(),
                clientFactory.createClient(clientFactory.createContext(unauthenticated), unauthenticated));
    }
}
