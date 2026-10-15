package lab.healthcare.fhir.vendor;

import lab.healthcare.fhir.auth.AccessTokenProvider;
import lab.healthcare.fhir.capability.FhirServerCapabilities;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.projection.ClinicalProjectionAssembler;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedMedicationRequest;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;
import lab.healthcare.fhir.routing.RoutingService;
import lab.healthcare.fhir.server.FhirServersProperties;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class LocalHapiModelBoundaryTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T19:20:00Z");

    @Mock
    private RoutingService routingService;

    @Mock
    private ClinicalProjectionAssembler assembler;

    @Mock
    private FhirServerCapabilities capabilities;

    @Test
    void configuredPatientReusesSharedProjectionAndKeepsV1() {
        when(routingService.discoverCapabilities(LocalHapiModelBoundary.DESTINATION)).thenReturn(capabilities);
        when(assembler.assemble(
                        eq(LocalHapiModelBoundary.DESTINATION),
                        any(AccessTokenProvider.class),
                        eq("patient-1"),
                        same(capabilities)))
                .thenReturn(projection(
                        ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                        ProjectedCollection.retained(0, 0, false, List.of()),
                        ProjectedCollection.retained(
                                1,
                                1,
                                false,
                                List.of(new RetainedMedicationRequest("MedicationRequest", "active", "order")))));

        ModelBoundaryContract contract = boundary("patient-1").currentContract();

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.destination()).isEqualTo("local-hapi");
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(contract.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(contract.observations().receivedCount()).isZero();
        assertThat(contract.observations().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(contract.medicationRequests()).isNotNull();
        assertThat(contract.medicationRequests().records()).hasSize(1);
        verify(routingService).discoverCapabilities(LocalHapiModelBoundary.DESTINATION);
    }

    @Test
    void missingPatientDoesNotReadFhir() {
        ModelBoundaryContract contract = boundary("").currentContract();

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.PATIENT_CONTEXT_NOT_CONFIGURED);
        assertThat(contract.patient()).isNull();
        assertThat(contract.conditions()).isNull();
        verifyNoInteractions(routingService, assembler);
    }

    @Test
    void capabilityFailureStaysUnavailableWithoutProjection() {
        when(routingService.discoverCapabilities(LocalHapiModelBoundary.DESTINATION))
                .thenThrow(new IllegalStateException("connection refused"));

        ModelBoundaryContract contract = boundary("patient-1").currentContract();

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(contract.patient().status()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(contract.conditions()).isNull();
        verifyNoInteractions(assembler);
    }

    @Test
    void missingPatientResourceStaysUnavailable() {
        when(routingService.discoverCapabilities(LocalHapiModelBoundary.DESTINATION)).thenReturn(capabilities);
        when(assembler.assemble(
                        eq(LocalHapiModelBoundary.DESTINATION),
                        any(AccessTokenProvider.class),
                        eq("patient-1"),
                        same(capabilities)))
                .thenReturn(ClinicalProjectionResult.unavailable(
                        "local-hapi",
                        GENERATED_AT,
                        ClinicalSnapshotResourceStatus.FAILED,
                        "Patient context could not be established"));

        ModelBoundaryContract contract = boundary("patient-1").currentContract();

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_UNAVAILABLE);
        assertThat(contract.patient().status()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(contract.conditions()).isNull();
    }

    private LocalHapiModelBoundary boundary(String patientId) {
        return new LocalHapiModelBoundary(
                new FhirServersProperties(
                        LocalHapiModelBoundary.DESTINATION,
                        Map.of(
                                LocalHapiModelBoundary.DESTINATION,
                                new FhirServersProperties.ServerSettings(
                                        "http://localhost:8080/fhir",
                                        "R4",
                                        true,
                                        null,
                                        null,
                                        new FhirServersProperties.VendorIntegrationSettings(
                                                null, null, null, null, patientId)))),
                routingService,
                assembler);
    }

    private static ClinicalProjectionResult projection(
            ClinicalSnapshotOutcome outcome,
            ProjectedCollection<RetainedObservation> observations,
            ProjectedCollection<RetainedMedicationRequest> medicationRequests) {
        return new ClinicalProjectionResult(
                outcome,
                "local-hapi",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                observations,
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                medicationRequests,
                "");
    }
}
