package lab.healthcare.fhir.projection;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.capability.FhirInteraction;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotStatuses;

import org.hl7.fhir.r4.model.Bundle;
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.Resource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import java.util.function.Supplier;

/**
 * Sequential fetch plus application retention and allowlist mapping. Does not
 * keep unused Bundle entries or invent Oracle-specific models.
 */
@Component
public class ClinicalProjectionAssembler {

    private final RoutingService routingService;
    private final RetentionCeiling ceiling;
    private final Clock clock;

    @Autowired
    public ClinicalProjectionAssembler(RoutingService routingService) {
        this(routingService, new RetentionCeiling(), Clock.systemUTC());
    }

    ClinicalProjectionAssembler(RoutingService routingService, RetentionCeiling ceiling, Clock clock) {
        if (routingService == null) {
            throw new IllegalArgumentException("Routing service must be provided");
        }
        this.routingService = routingService;
        this.ceiling = ceiling == null ? new RetentionCeiling() : ceiling;
        this.clock = clock == null ? Clock.systemUTC() : clock;
    }

    public ClinicalProjectionResult assemble(
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
        PatientRead patientRead = readPatient(dest, tokenProvider, patientId, capabilities);
        if (patientRead.status() != ClinicalSnapshotResourceStatus.SUCCESS) {
            return ClinicalProjectionResult.unavailable(
                    dest, generatedAt, patientRead.status(), "Patient context could not be established");
        }
        ProjectedCollection<RetainedCondition> conditions = project(
                capabilities,
                "Condition",
                () -> routingService.searchConditions(dest, tokenProvider, patientId),
                ClinicalProjectionMapper::condition);
        ProjectedCollection<RetainedObservation> observations = project(
                capabilities,
                "Observation",
                () -> routingService.searchObservations(dest, tokenProvider, patientId),
                ClinicalProjectionMapper::observation);
        ProjectedCollection<RetainedDiagnosticReport> diagnosticReports = project(
                capabilities,
                "DiagnosticReport",
                () -> routingService.searchDiagnosticReports(dest, tokenProvider, patientId),
                ClinicalProjectionMapper::diagnosticReport);
        ProjectedCollection<RetainedMedicationRequest> medicationRequests = project(
                capabilities,
                "MedicationRequest",
                () -> routingService.searchMedicationRequests(dest, tokenProvider, patientId),
                ClinicalProjectionMapper::medicationRequest);
        boolean complete = conditions.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && observations.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && diagnosticReports.status() == ClinicalSnapshotResourceStatus.SUCCESS
                && medicationRequests.status() == ClinicalSnapshotResourceStatus.SUCCESS;
        return new ClinicalProjectionResult(
                complete
                        ? ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE
                        : ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                dest,
                PatientContextSource.CONFIGURED,
                generatedAt,
                ClinicalSnapshotResourceStatus.SUCCESS,
                patientRead.patient(),
                conditions,
                observations,
                diagnosticReports,
                medicationRequests,
                complete
                        ? "Controlled clinical projection succeeded"
                        : "Controlled clinical projection is partial");
    }

    private PatientRead readPatient(
            String destination,
            AccessTokenProvider tokenProvider,
            String patientId,
            FhirServerCapabilities capabilities) {
        if (!capabilities.supports("Patient", FhirInteraction.READ)) {
            return new PatientRead(ClinicalSnapshotResourceStatus.UNAVAILABLE, null);
        }
        try {
            Patient patient = routingService.readPatient(destination, tokenProvider, patientId);
            return new PatientRead(
                    ClinicalSnapshotResourceStatus.SUCCESS, ClinicalProjectionMapper.patient(patient));
        } catch (RuntimeException ex) {
            return new PatientRead(ClinicalSnapshotStatuses.fromFailure(ex), null);
        }
    }

    private <T> ProjectedCollection<T> project(
            FhirServerCapabilities capabilities,
            String resourceType,
            Supplier<Bundle> operation,
            Function<Resource, T> mapper) {
        if (!capabilities.supports(resourceType, FhirInteraction.SEARCH_TYPE)) {
            return ProjectedCollection.unavailable();
        }
        try {
            Bundle bundle = operation.get();
            int received = entryCount(bundle);
            int retained = ceiling.retain(received);
            boolean truncated = ceiling.truncated(received);
            List<T> items = new ArrayList<>(retained);
            if (bundle != null && bundle.hasEntry()) {
                for (int i = 0; i < retained; i++) {
                    items.add(mapper.apply(bundle.getEntry().get(i).getResource()));
                }
            }
            return ProjectedCollection.retained(received, retained, truncated, items);
        } catch (RuntimeException ex) {
            return ProjectedCollection.failed(ClinicalSnapshotStatuses.fromFailure(ex));
        }
    }

    private static int entryCount(Bundle bundle) {
        if (bundle == null || !bundle.hasEntry()) {
            return 0;
        }
        return bundle.getEntry().size();
    }

    private record PatientRead(ClinicalSnapshotResourceStatus status, RetainedPatient patient) {
    }
}
