package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContext;
import lab.healthcare.fhir.patient.PatientContexts;
import lab.healthcare.fhir.routing.FhirObservationSearchResult;
import lab.healthcare.fhir.routing.FhirObservationSearchResults;
import lab.healthcare.fhir.routing.RoutingService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Uses a Task 036 Patient context, a Task 033 issued token, and Task 034
 * runtime capabilities to run a generic Observation SEARCH_TYPE. Does not invent
 * hosts, tokens, or Patient identifiers.
 */
@Component
public class OracleSandboxObservationSearchService {

    private final OracleSandboxReadinessService readinessService;
    private final OracleSandboxAuthenticationService authenticationService;
    private final OracleSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final RoutingService routingService;
    private final Clock clock;

    @Autowired
    public OracleSandboxObservationSearchService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxAuthenticationService authenticationService,
            OracleSandboxCapabilityDiscoveryService capabilityDiscovery,
            RoutingService routingService) {
        this(readinessService, authenticationService, capabilityDiscovery, routingService, Clock.systemUTC());
    }

    OracleSandboxObservationSearchService(
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

    public FhirObservationSearchResult searchObservations(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            return FhirObservationSearchResult.authenticationRequired(
                    OracleHealthIntegrationProfile.SANDBOX_SERVER,
                    "Oracle Health sandbox profile is disabled");
        }
        OracleSandboxReadiness readiness = readinessService.inspect(profile);
        if (readiness.state() != OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK) {
            return FhirObservationSearchResult.authenticationRequired(
                    profile.serverProfileName(),
                    readiness.detail());
        }
        Optional<PatientContext> context = PatientContexts.configured(
                profile.serverProfileName(), profile.configuredPatientId());
        if (context.isEmpty()) {
            return FhirObservationSearchResult.contextNotConfigured(profile.serverProfileName());
        }
        Optional<IssuedAccessTokenProvider> issued = authenticationService.issuedProviderIfPresent();
        if (issued.isEmpty()) {
            return FhirObservationSearchResult.authenticationRequired(
                    profile.serverProfileName(), "No usable access token");
        }
        if (!issued.get().isUsableAt(Instant.now(clock), Duration.ZERO)) {
            return FhirObservationSearchResult.authenticationRequired(
                    profile.serverProfileName(), "Access token is expired");
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = capabilityDiscovery.discover(profile);
        } catch (RuntimeException ex) {
            return FhirObservationSearchResults.fromFailure(profile.serverProfileName(), ex);
        }
        if (!capabilities.supports("Observation", FhirInteraction.SEARCH_TYPE)) {
            return FhirObservationSearchResult.capabilityUnsupported(
                    profile.serverProfileName(), "Observation", FhirInteraction.SEARCH_TYPE.code());
        }
        try {
            return FhirObservationSearchResults.succeeded(
                    profile.serverProfileName(),
                    routingService.searchObservations(
                            profile.serverProfileName(), issued.get(), context.get().patientId()));
        } catch (RuntimeException ex) {
            return FhirObservationSearchResults.fromFailure(profile.serverProfileName(), ex);
        }
    }
}
