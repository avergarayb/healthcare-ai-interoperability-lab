package lab.healthcare.fhir.vendor;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;
import lab.healthcare.fhir.patient.PatientContext;
import lab.healthcare.fhir.patient.PatientContexts;
import lab.healthcare.fhir.projection.ClinicalProjectionAssembler;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.Optional;

/**
 * Read-only local HAPI projection. Reuses capability discovery and the shared
 * clinical projection assembler. Does not search for a Patient and does not
 * copy the Epic or Oracle adapters.
 */
@Component
public class LocalHapiModelBoundary {

    public static final String DESTINATION = "local-hapi";

    private final FhirServersProperties servers;
    private final RoutingService routingService;
    private final ClinicalProjectionAssembler assembler;

    public LocalHapiModelBoundary(
            FhirServersProperties servers,
            RoutingService routingService,
            ClinicalProjectionAssembler assembler) {
        if (servers == null) {
            throw new IllegalArgumentException("FHIR server properties must be provided");
        }
        if (routingService == null) {
            throw new IllegalArgumentException("Routing service must be provided");
        }
        if (assembler == null) {
            throw new IllegalArgumentException("Clinical projection assembler must be provided");
        }
        this.servers = servers;
        this.routingService = routingService;
        this.assembler = assembler;
    }

    public ModelBoundaryContract currentContract() {
        Optional<PatientContext> context = PatientContexts.configured(DESTINATION, configuredPatientId());
        if (context.isEmpty()) {
            return ModelBoundaryMapper.from(ClinicalProjectionResult.contextNotConfigured(DESTINATION));
        }
        FhirServerCapabilities capabilities;
        try {
            capabilities = routingService.discoverCapabilities(DESTINATION);
        } catch (RuntimeException ex) {
            return ModelBoundaryMapper.from(ClinicalProjectionResult.unavailable(
                    DESTINATION,
                    Instant.now(),
                    ClinicalSnapshotResourceStatus.FAILED,
                    "Runtime CapabilityStatement could not be discovered"));
        }
        return ModelBoundaryMapper.from(assembler.assemble(
                DESTINATION,
                AccessTokenProvider.none(),
                context.get().patientId(),
                capabilities));
    }

    private String configuredPatientId() {
        FhirServersProperties.ServerSettings settings = servers.servers().get(DESTINATION);
        if (settings == null || settings.vendorIntegration() == null) {
            return "";
        }
        String patientId = settings.vendorIntegration().patientId();
        return patientId == null ? "" : patientId.trim();
    }
}
