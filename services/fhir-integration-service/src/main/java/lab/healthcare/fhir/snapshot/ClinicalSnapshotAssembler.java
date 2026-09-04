package lab.healthcare.fhir.snapshot;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.RoutingService;

import org.hl7.fhir.r4.model.Bundle;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Instant;
import java.util.function.Supplier;

/**
 * Sequential vendor-neutral snapshot assembly. Calls existing
 * {@link RoutingService} operations. Does not keep FHIR resources, invent
 * tokens, or interpret clinical values.
 */
@Component
public class ClinicalSnapshotAssembler {

    private final RoutingService routingService;
    private final Clock clock;

    @Autowired
    public ClinicalSnapshotAssembler(RoutingService routingService) {
        this(routingService, Clock.systemUTC());
    }

    ClinicalSnapshotAssembler(RoutingService routingService, Clock clock) {
        if (routingService == null) {
            throw new IllegalArgumentException("Routing service must be provided");
        }
        this.routingService = routingService;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public ClinicalSnapshotResult assemble(
            String destination,
            AccessTokenProvider tokenProvider,
            String patientId,
            FhirServerCapabilities capabilities) {
        if (destination == null || destination.isBlank()) {
            throw new IllegalArgumentException("Destination must be provided");
        }
        if (tokenProvider == null) {
            throw new IllegalArgumentException("Access token provider must be provided");
        }
        if (patientId == null || patientId.isBlank()) {
            throw new IllegalArgumentException("Patient logical ID must be provided");
        }
        if (capabilities == null) {
            throw new IllegalArgumentException("Runtime capabilities must be provided");
        }
        String dest = destination.trim();
        Instant generatedAt = Instant.now(clock);
        ClinicalSnapshotResourceStatus patientStatus = readPatient(dest, tokenProvider, patientId, capabilities);
        if (patientStatus != ClinicalSnapshotResourceStatus.SUCCESS) {
            return ClinicalSnapshotResult.unavailable(
                    dest, generatedAt, patientStatus, "Patient context could not be established");
        }
        CollectionResult conditions = search(
                capabilities,
                "Condition",
                () -> routingService.searchConditions(dest, tokenProvider, patientId));
        CollectionResult observations = search(
                capabilities,
                "Observation",
                () -> routingService.searchObservations(dest, tokenProvider, patientId));
        CollectionResult diagnosticReports = search(
                capabilities,
                "DiagnosticReport",
                () -> routingService.searchDiagnosticReports(dest, tokenProvider, patientId));
        CollectionResult medicationRequests = search(
                capabilities,
                "MedicationRequest",
                () -> routingService.searchMedicationRequests(dest, tokenProvider, patientId));
        boolean complete = conditions.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && observations.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && diagnosticReports.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && medicationRequests.status() == ClinicalSnapshotResourceStatus.SUCCESS;
        return new ClinicalSnapshotResult(
                complete
                        ? ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE
                        : ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                dest,
                PatientContextSource.CONFIGURED,
                generatedAt,
                ClinicalSnapshotResourceStatus.SUCCESS,
                conditions.status(),
                conditions.count(),
                observations.status(),
                observations.count(),
                diagnosticReports.status(),
                diagnosticReports.count(),
                medicationRequests.status(),
                medicationRequests.count(),
                complete
                        ? "Controlled clinical snapshot succeeded"
                        : "Controlled clinical snapshot is partial");
    }

    private ClinicalSnapshotResourceStatus readPatient(
            String destination,
            AccessTokenProvider tokenProvider,
            String patientId,
            FhirServerCapabilities capabilities) {
        if (!capabilities.supports("Patient", FhirInteraction.READ)) {
            return ClinicalSnapshotResourceStatus.UNAVAILABLE;
        }
        try {
            routingService.readPatient(destination, tokenProvider, patientId);
            return ClinicalSnapshotResourceStatus.SUCCESS;
        } catch (RuntimeException ex) {
            return ClinicalSnapshotStatuses.fromFailure(ex);
        }
    }

    private CollectionResult search(
            FhirServerCapabilities capabilities,
            String resourceType,
            Supplier<Bundle> operation) {
        if (!capabilities.supports(resourceType, FhirInteraction.SEARCH_TYPE)) {
            return new CollectionResult(ClinicalSnapshotResourceStatus.UNAVAILABLE, null);
        }
        try {
            return new CollectionResult(ClinicalSnapshotResourceStatus.SUCCESS, entryCount(operation.get()));
        } catch (RuntimeException ex) {
            return new CollectionResult(ClinicalSnapshotStatuses.fromFailure(ex), null);
        }
    }

    private static int entryCount(Bundle bundle) {
        if (bundle == null || !bundle.hasEntry()) {
            return 0;
        }
        return bundle.getEntry().size();
    }

    private record CollectionResult(ClinicalSnapshotResourceStatus status, Integer count) {
    }
}
