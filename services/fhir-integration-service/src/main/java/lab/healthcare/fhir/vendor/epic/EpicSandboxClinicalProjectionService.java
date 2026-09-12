package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContext;
import lab.healthcare.fhir.patient.PatientContexts;
import lab.healthcare.fhir.projection.ClinicalProjectionAssembler;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotContents;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Uses a Task 048 Patient context, a Task 046 issued token, and one Task 047
 * CapabilityStatement to assemble a generic controlled projection. Does not
 * invent hosts, tokens, Patient identifiers, or an Epic projection client.
 */
@Component
public class EpicSandboxClinicalProjectionService {

    private final EpicSandboxAuthenticationService authenticationService;
    private final EpicSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final ClinicalProjectionAssembler assembler;
    private final Clock clock;

    @Autowired
    public EpicSandboxClinicalProjectionService(
            EpicSandboxAuthenticationService authenticationService,
            EpicSandboxCapabilityDiscoveryService capabilityDiscovery,
            ClinicalProjectionAssembler assembler) {
        this(authenticationService, capabilityDiscovery, assembler, Clock.systemUTC());
    }

    EpicSandboxClinicalProjectionService(
            EpicSandboxAuthenticationService authenticationService,
            EpicSandboxCapabilityDiscoveryService capabilityDiscovery,
            ClinicalProjectionAssembler assembler,
            Clock clock) {
        if (authenticationService == null) {
            throw new IllegalArgumentException("Epic sandbox authentication service must be provided");
        }
        if (capabilityDiscovery == null) {
            throw new IllegalArgumentException("Epic sandbox capability discovery must be provided");
        }
        if (assembler == null) {
            throw new IllegalArgumentException("Clinical projection assembler must be provided");
        }
        this.authenticationService = authenticationService;
        this.capabilityDiscovery = capabilityDiscovery;
        this.assembler = assembler;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public ClinicalProjectionResult assemble(EpicIntegrationProfile profile) {
        if (profile == null) {
            return ClinicalProjectionResult.authenticationRequired(
                    EpicIntegrationProfile.SANDBOX_SERVER, "Epic sandbox profile is disabled");
        }
        EpicSandboxAuthReadiness readiness = authenticationService.inspect(profile);
        if (readiness.state() != EpicSandboxAuthReadinessState.READY_FOR_AUTHORIZATION) {
            return ClinicalProjectionResult.authenticationRequired(
                    profile.serverProfileName(), readiness.detail());
        }
        Optional<PatientContext> context = PatientContexts.configured(
                profile.serverProfileName(), profile.configuredPatientId());
        if (context.isEmpty()) {
            return ClinicalProjectionResult.contextNotConfigured(profile.serverProfileName());
        }
        Optional<IssuedAccessTokenProvider> issued = authenticationService.issuedProviderIfPresent();
        if (issued.isEmpty()) {
            return ClinicalProjectionResult.authenticationRequired(
                    profile.serverProfileName(), "No usable access token");
        }
        if (!issued.get().isUsableAt(Instant.now(clock), Duration.ZERO)) {
            return ClinicalProjectionResult.authenticationRequired(
                    profile.serverProfileName(), "Access token is expired");
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = capabilityDiscovery.discover(profile);
        } catch (RuntimeException ex) {
            return ClinicalProjectionResult.unavailable(
                    profile.serverProfileName(),
                    Instant.now(clock),
                    ClinicalSnapshotResourceStatus.FAILED,
                    "Runtime CapabilityStatement could not be discovered");
        }
        return assembler.assemble(
                profile.serverProfileName(),
                issued.get(),
                context.get().patientId(),
                capabilities,
                ClinicalSnapshotContents.withoutMedicationRequests());
    }
}
