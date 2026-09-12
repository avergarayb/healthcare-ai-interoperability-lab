package lab.healthcare.fhir.vendor.epic;

import lab.healthcare.fhir.auth.IssuedAccessTokenProvider;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContext;
import lab.healthcare.fhir.patient.PatientContexts;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotAssembler;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotContents;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResult;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

/**
 * Uses a Task 048 Patient context, a Task 046 issued token, and one Task 047
 * CapabilityStatement to assemble a generic clinical snapshot. Does not invent
 * hosts, tokens, Patient identifiers, or per-resource Epic clients.
 */
@Component
public class EpicSandboxClinicalSnapshotService {

    private final EpicSandboxAuthenticationService authenticationService;
    private final EpicSandboxCapabilityDiscoveryService capabilityDiscovery;
    private final ClinicalSnapshotAssembler assembler;
    private final Clock clock;

    @Autowired
    public EpicSandboxClinicalSnapshotService(
            EpicSandboxAuthenticationService authenticationService,
            EpicSandboxCapabilityDiscoveryService capabilityDiscovery,
            ClinicalSnapshotAssembler assembler) {
        this(authenticationService, capabilityDiscovery, assembler, Clock.systemUTC());
    }

    EpicSandboxClinicalSnapshotService(
            EpicSandboxAuthenticationService authenticationService,
            EpicSandboxCapabilityDiscoveryService capabilityDiscovery,
            ClinicalSnapshotAssembler assembler,
            Clock clock) {
        if (authenticationService == null) {
            throw new IllegalArgumentException("Epic sandbox authentication service must be provided");
        }
        if (capabilityDiscovery == null) {
            throw new IllegalArgumentException("Epic sandbox capability discovery must be provided");
        }
        if (assembler == null) {
            throw new IllegalArgumentException("Clinical snapshot assembler must be provided");
        }
        this.authenticationService = authenticationService;
        this.capabilityDiscovery = capabilityDiscovery;
        this.assembler = assembler;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public ClinicalSnapshotResult assemble(EpicIntegrationProfile profile) {
        if (profile == null) {
            return ClinicalSnapshotResult.authenticationRequired(
                    EpicIntegrationProfile.SANDBOX_SERVER, "Epic sandbox profile is disabled");
        }
        EpicSandboxAuthReadiness readiness = authenticationService.inspect(profile);
        if (readiness.state() != EpicSandboxAuthReadinessState.READY_FOR_AUTHORIZATION) {
            return ClinicalSnapshotResult.authenticationRequired(
                    profile.serverProfileName(), readiness.detail());
        }
        Optional<PatientContext> context = PatientContexts.configured(
                profile.serverProfileName(), profile.configuredPatientId());
        if (context.isEmpty()) {
            return ClinicalSnapshotResult.contextNotConfigured(profile.serverProfileName());
        }
        Optional<IssuedAccessTokenProvider> issued = authenticationService.issuedProviderIfPresent();
        if (issued.isEmpty()) {
            return ClinicalSnapshotResult.authenticationRequired(
                    profile.serverProfileName(), "No usable access token");
        }
        if (!issued.get().isUsableAt(Instant.now(clock), Duration.ZERO)) {
            return ClinicalSnapshotResult.authenticationRequired(
                    profile.serverProfileName(), "Access token is expired");
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = capabilityDiscovery.discover(profile);
        } catch (RuntimeException ex) {
            return ClinicalSnapshotResult.unavailable(
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
