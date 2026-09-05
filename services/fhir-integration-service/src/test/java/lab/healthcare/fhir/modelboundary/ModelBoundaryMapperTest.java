package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedMedicationRequest;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.lang.reflect.RecordComponent;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ModelBoundaryMapperTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-04T03:00:00Z");

    @Test
    void mapsProjectionAllowlistAndPreservesCounts() {
        ClinicalProjectionResult projection = complete(
                "oracle-health-sandbox",
                ProjectedCollection.retained(
                        1489,
                        5,
                        true,
                        List.of(
                                new RetainedCondition("Condition", "active"),
                                new RetainedCondition("Condition", "active"),
                                new RetainedCondition("Condition", "active"),
                                new RetainedCondition("Condition", "active"),
                                new RetainedCondition("Condition", "active"))),
                ProjectedCollection.retained(20, 5, true, List.of(new RetainedObservation("Observation", "final"))),
                ProjectedCollection.retained(5, 5, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                ProjectedCollection.retained(
                        5, 5, false, List.of(new RetainedMedicationRequest("MedicationRequest", "active", "order"))));

        ModelBoundaryContract contract = ModelBoundaryMapper.from(projection);

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(contract.destination()).isEqualTo("oracle-health-sandbox");
        assertThat(contract.contextSource()).isEqualTo(PatientContextSource.CONFIGURED);
        assertThat(contract.generatedAt()).isEqualTo(GENERATED_AT);
        assertThat(contract.patient().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(contract.patient().resourceType()).isEqualTo("Patient");
        assertThat(contract.conditions().receivedCount()).isEqualTo(1489);
        assertThat(contract.conditions().retainedCount()).isEqualTo(5);
        assertThat(contract.conditions().truncated()).isTrue();
        assertThat(contract.conditions().records()).hasSize(5);
        assertThat(contract.conditions().records())
                .extracting(BoundaryCondition::clinicalStatusCode)
                .containsOnly("active");
        assertThat(contract.observations().receivedCount()).isEqualTo(20);
        assertThat(contract.observations().retainedCount()).isEqualTo(5);
        assertThat(contract.observations().truncated()).isTrue();
        assertThat(componentNames(BoundaryCondition.class)).containsExactly("resourceType", "clinicalStatusCode");
        assertThat(componentNames(BoundaryObservation.class)).containsExactly("resourceType", "status");
        assertThat(componentNames(BoundaryDiagnosticReport.class)).containsExactly("resourceType", "status");
        assertThat(componentNames(BoundaryMedicationRequest.class)).containsExactly("resourceType", "status", "intent");
        assertThat(componentNames(BoundaryPatient.class)).containsExactly("status", "resourceType");
        assertThat(contract.toString()).doesNotContain("active");
        assertThat(contract.toString()).contains("receivedCount=1489");
        assertThat(contract.toString()).contains("retainedCount=5");
    }

    @Test
    void sameContractShapeForEpicDestinationName() {
        ClinicalProjectionResult projection = complete(
                "epic-sandbox",
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()));

        ModelBoundaryContract contract = ModelBoundaryMapper.from(projection);

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.destination()).isEqualTo("epic-sandbox");
        assertThat(contract.conditions().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(contract.conditions().receivedCount()).isZero();
        assertThat(contract.conditions().retainedCount()).isZero();
        assertThat(contract.conditions().truncated()).isFalse();
        assertThat(contract.conditions().records()).isEmpty();
    }

    @Test
    void emptySuccessfulCollectionRemainsEmptySuccess() {
        ClinicalProjectionResult projection = complete(
                "future-fhir-destination",
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()),
                ProjectedCollection.retained(0, 0, false, List.of()));

        ModelBoundaryContract contract = ModelBoundaryMapper.from(projection);

        assertThat(contract.observations().status()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(contract.observations().receivedCount()).isZero();
        assertThat(contract.observations().retainedCount()).isZero();
        assertThat(contract.observations().truncated()).isFalse();
        assertThat(contract.observations().records()).isEmpty();
    }

    @Test
    void failedCollectionIsNotRewrittenAsEmptySuccess() {
        ClinicalProjectionResult projection = new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.failed(ClinicalSnapshotResourceStatus.FAILED),
                ProjectedCollection.unavailable(),
                ProjectedCollection.failed(ClinicalSnapshotResourceStatus.UNAUTHORIZED),
                "Controlled clinical projection is partial");

        ModelBoundaryContract contract = ModelBoundaryMapper.from(projection);

        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL);
        assertThat(contract.observations().status()).isEqualTo(ClinicalSnapshotResourceStatus.FAILED);
        assertThat(contract.observations().receivedCount()).isNull();
        assertThat(contract.observations().records()).isEmpty();
        assertThat(contract.diagnosticReports().status()).isEqualTo(ClinicalSnapshotResourceStatus.UNAVAILABLE);
        assertThat(contract.medicationRequests().status()).isEqualTo(ClinicalSnapshotResourceStatus.UNAUTHORIZED);
        assertThat(contract.observations().status()).isNotEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
    }

    @Test
    void authenticationRequiredDoesNotInventCollections() {
        ModelBoundaryContract contract =
                ModelBoundaryMapper.from(ClinicalProjectionResult.authenticationRequired("oracle-health-sandbox", "No usable access token"));

        assertThat(contract.outcome()).isEqualTo(ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED);
        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.patient()).isNull();
        assertThat(contract.conditions()).isNull();
        assertThat(contract.toString()).doesNotContain("access_token");
    }

    private static ClinicalProjectionResult complete(
            String destination,
            ProjectedCollection<RetainedCondition> conditions,
            ProjectedCollection<RetainedObservation> observations,
            ProjectedCollection<RetainedDiagnosticReport> diagnosticReports,
            ProjectedCollection<RetainedMedicationRequest> medicationRequests) {
        return new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                destination,
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                conditions,
                observations,
                diagnosticReports,
                medicationRequests,
                "Controlled clinical projection succeeded");
    }

    private static List<String> componentNames(Class<?> type) {
        return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).toList();
    }
}
