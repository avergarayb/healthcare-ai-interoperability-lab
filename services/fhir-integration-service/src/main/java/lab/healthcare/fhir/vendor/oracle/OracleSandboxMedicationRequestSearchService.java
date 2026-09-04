package lab.healthcare.fhir.vendor.oracle;

import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContext;
import lab.healthcare.fhir.patient.PatientContexts;
import lab.healthcare.fhir.routing.FhirMedicationRequestSearchResult;
import lab.healthcare.fhir.routing.FhirMedicationRequestSearchResults;
import lab.healthcare.fhir.routing.RoutingService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Uses a Task 036 Patient context, a Task 033 issued token, and Task 034
 * runtime capabilities to run a generic MedicationRequest SEARCH_TYPE. Does not
 * invent hosts, tokens, or Patient identifiers.
 */
@Component
public class OracleSandboxMedicationRequestSearchService {

    private final OracleSandboxReadinessService readinessService;
    private final OracleSandboxAuthenticationService authenticationService;
    private final OracleSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final RoutingService routingService;
    private final Clock clock;

    @Autowired
    public OracleSandboxMedicationRequestSearchService(
            OracleSandboxReadinessService readinessService,
            OracleSandboxAuthenticationService authenticationService,
            OracleSandboxCapabilityDiscoveryService capabilityDiscovery,
            RoutingService routingService) {
        this(readinessService, authenticationService, capabilityDiscovery, routingService, Clock.systemUTC());
    }

    OracleSandboxMedicationRequestSearchService(
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

    public FhirMedicationRequestSearchResult searchMedicationRequests(OracleHealthIntegrationProfile profile) {
        if (profile == null) {
            return FhirMedicationRequestSearchResult.authenticationRequired(
                    OracleHealthIntegrationProfile.SANDBOX_SERVER,
                    "Oracle Health sandbox profile is disabled");
        }
        OracleSandboxReadiness readiness = readinessService.inspect(profile);
        if (readiness.state() != OracleSandboxReadinessState.READY_FOR_CONNECTIVITY_CHECK) {
            return FhirMedicationRequestSearchResult.authenticationRequired(
                    profile.serverProfileName(),
                    readiness.detail());
        }
        Optional<PatientContext> context = PatientContexts.configured(
                profile.serverProfileName(), profile.configuredPatientId());
        if (context.isEmpty()) {
            return FhirMedicationRequestSearchResult.contextNotConfigured(profile.serverProfileName());
        }
        Optional<IssuedAccessTokenProvider> issued = authenticationService.issuedProviderIfPresent();
        if (issued.isEmpty()) {
            return FhirMedicationRequestSearchResult.authenticationRequired(
                    profile.serverProfileName(), "No usable access token");
        }
        if (!issued.get().isUsableAt(Instant.now(clock), Duration.ZERO)) {
            return FhirMedicationRequestSearchResult.authenticationRequired(
                    profile.serverProfileName(), "Access token is expired");
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = capabilityDiscovery.discover(profile);
        } catch (RuntimeException ex) {
            return FhirMedicationRequestSearchResults.fromFailure(profile.serverProfileName(), ex);
        }
        if (!capabilities.supports("MedicationRequest", FhirInteraction.SEARCH_TYPE)) {
            return FhirMedicationRequestSearchResult.capabilityUnsupported(
                    profile.serverProfileName(), "MedicationRequest", FhirInteraction.SEARCH_TYPE.code());
        }
        try {
            return FhirMedicationRequestSearchResults.succeeded(
                    profile.serverProfileName(),
                    routingService.searchMedicationRequests(
                            profile.serverProfileName(), issued.get(), context.get().patientId()));
        } catch (RuntimeException ex) {
            return FhirMedicationRequestSearchResults.fromFailure(profile.serverProfileName(), ex);
        }
    }
}
