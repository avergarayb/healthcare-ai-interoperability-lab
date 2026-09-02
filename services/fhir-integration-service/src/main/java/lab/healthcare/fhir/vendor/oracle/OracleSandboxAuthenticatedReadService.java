package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.routing.FhirAuthenticatedReadResult;
import lab.healthcare.fhir.routing.FhirAuthenticatedReadResults;
import lab.healthcare.fhir.routing.RoutingService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Uses a Task 033 issued token and Task 034 runtime capabilities to run a
 * generic Patient SEARCH_TYPE. Does not invent hosts, tokens, or Patient IDs.
 */
@Component
public class OracleSandboxAuthenticatedReadService {

    /**
     * Qualifying Patient {@code name} for the lab search. Oracle rejects an
     * unqualified {@code GET /Patient?_count=1} with HTTP 400. This value is not
     * a real patient identifier and is not a vendor host.
     */
    static final String SAFE_PATIENT_SEARCH_NAME = "LabNoMatch";

    private final OracleSandboxReadinessService readinessService;
    private final OracleSandboxAuthenticationService authenticationService;
    private final OracleSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final RoutingService routingService;
    private final Clock clock;

    @Autowired
    public OracleSandboxAuthenticatedReadService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxAuthenticationService authenticationService,
            OracleSandboxCapabilityDiscoveryService capabilityDiscovery,
            RoutingService routingService) {
        this(readinessService, authenticationService, capabilityDiscovery, routingService, Clock.systemUTC());
    }

    OracleSandboxAuthenticatedReadService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxAuthenticationService authenticationService,
            OracleSandboxCapabilityDiscoveryService capabilityDiscovery,
            RoutingService routingService,
            Clock clock) {
        if (readinessService == null) {
            throw new IllegalArgumentException("Oracle sandbox readiness service must be provided");
        }
        if (authenticationService == null) {
            throw new IllegalArgumentException("Oracle sandbox authentication service must be provided");
        }
        if (capabilityDiscovery == null) {
            throw new IllegalArgumentException("Oracle sandbox capability discovery must be provided");
        }
        if (routingService == null) {
            throw new IllegalArgumentException("Routing service must be provided");
        }
        this.readinessService = readinessService;
        this.authenticationService = authenticationService;
        this.capabilityDiscovery = capabilityDiscovery;
        this.routingService = routingService;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public FhirAuthenticatedReadResult searchPatients(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            return FhirAuthenticatedReadResult.authenticationRequired(
                    OracleHealthIntegrationProfile.SANDBOX_SERVER,
                    "Oracle Health sandbox profile is disabled");
        }
        OracleSandboxReadiness readiness = readinessService.inspect(profile);
        if (readiness.state() != OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK) {
            return FhirAuthenticatedReadResult.authenticationRequired(
                    profile.serverProfileName(),
                    readiness.detail());
        }
        Optional<IssuedAccessTokenProvider> issued = authenticationService.issuedProviderIfPresent();
        if (issued.isEmpty()) {
            return FhirAuthenticatedReadResult.authenticationRequired(
                    profile.serverProfileName(), "No usable access token");
        }
        if (!issued.get().isUsableAt(Instant.now(clock), Duration.ZERO)) {
            return FhirAuthenticatedReadResult.authenticationRequired(
                    profile.serverProfileName(), "Access token is expired");
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = capabilityDiscovery.discover(profile);
        } catch (RuntimeException ex) {
            return FhirAuthenticatedReadResults.fromFailure(profile.serverProfileName(), ex);
        }
        if (!capabilities.supports("Patient", FhirInteraction.SEARCH_TYPE)) {
            return FhirAuthenticatedReadResult.capabilityUnsupported(
                    profile.serverProfileName(), "Patient", FhirInteraction.SEARCH_TYPE.code());
        }
        try {
            return FhirAuthenticatedReadResults.succeeded(
                    profile.serverProfileName(),
                    routingService.searchPatients(
                            profile.serverProfileName(), issued.get(), SAFE_PATIENT_SEARCH_NAME));
        } catch (RuntimeException ex) {
            return FhirAuthenticatedReadResults.fromFailure(profile.serverProfileName(), ex);
        }
    }
}
