package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContext;
import lab.healthcare.fhir.patient.PatientContexts;
import lab.healthcare.fhir.routing.FhirConditionSearchResult;
import lab.healthcare.fhir.routing.FhirConditionSearchResults;
import lab.healthcare.fhir.routing.RoutingService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Uses a Task 036 Patient context, a Task 033 issued token, and Task 034
 * runtime capabilities to run a generic Condition SEARCH_TYPE. Does not invent
 * hosts, tokens, or Patient identifiers.
 */
@Component
public class OracleSandboxConditionSearchService {

    private final OracleSandboxReadinessService readinessService;
    private final OracleSandboxAuthenticationService authenticationService;
    private final OracleSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final RoutingService routingService;
    private final Clock clock;

    @Autowired
    public OracleSandboxConditionSearchService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxAuthenticationService authenticationService,
            OracleSandboxCapabilityDiscoveryService capabilityDiscovery,
            RoutingService routingService) {
        this(readinessService, authenticationService, capabilityDiscovery, routingService, Clock.systemUTC());
    }

    OracleSandboxConditionSearchService(
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

    public FhirConditionSearchResult searchConditions(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            return FhirConditionSearchResult.authenticationRequired(
                    OracleHealthIntegrationProfile.SANDBOX_SERVER,
                    "Oracle Health sandbox profile is disabled");
        }
        OracleSandboxReadiness readiness = readinessService.inspect(profile);
        if (readiness.state() != OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK) {
            return FhirConditionSearchResult.authenticationRequired(
                    profile.serverProfileName(),
                    readiness.detail());
        }
        Optional<PatientContext> context = PatientContexts.configured(
                profile.serverProfileName(), profile.configuredPatientId());
        if (context.isEmpty()) {
            return FhirConditionSearchResult.contextNotConfigured(profile.serverProfileName());
        }
        Optional<IssuedAccessTokenProvider> issued = authenticationService.issuedProviderIfPresent();
        if (issued.isEmpty()) {
            return FhirConditionSearchResult.authenticationRequired(
                    profile.serverProfileName(), "No usable access token");
        }
        if (!issued.get().isUsableAt(Instant.now(clock), Duration.ZERO)) {
            return FhirConditionSearchResult.authenticationRequired(
                    profile.serverProfileName(), "Access token is expired");
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = capabilityDiscovery.discover(profile);
        } catch (RuntimeException ex) {
            return FhirConditionSearchResults.fromFailure(profile.serverProfileName(), ex);
        }
        if (!capabilities.supports("Condition", FhirInteraction.SEARCH_TYPE)) {
            return FhirConditionSearchResult.capabilityUnsupported(
                    profile.serverProfileName(), "Condition", FhirInteraction.SEARCH_TYPE.code());
        }
        try {
            return FhirConditionSearchResults.succeeded(
                    profile.serverProfileName(),
                    routingService.searchConditions(
                            profile.serverProfileName(), issued.get(), context.get().patientId()));
        } catch (RuntimeException ex) {
            return FhirConditionSearchResults.fromFailure(profile.serverProfileName(), ex);
        }
    }
}
