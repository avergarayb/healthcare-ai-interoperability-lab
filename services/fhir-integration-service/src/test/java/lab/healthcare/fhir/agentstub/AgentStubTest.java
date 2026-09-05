package lab.healthcare.fhir.agentstub;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.lang.reflect.RecordComponent;
import java.time.Instant;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AgentStubTest {

    @Test
    void consumesContractWithoutRepublishingRecordsOrCallingAModel() {
        ModelBoundaryContract contract = new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-05T03:00:00Z"),
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1489,
                        5,
                        true,
                        List.of(
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "resolved"))),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                null,
                null);

        AgentStubObservation observation = AgentStub.observe(contract);

        assertThat(observation.consumed()).isTrue();
        assertThat(observation.modelCalled()).isFalse();
        assertThat(observation.contractVersion()).isEqualTo("v1");
        assertThat(observation.outcome()).isEqualTo(ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE);
        assertThat(observation.patientStatus()).isEqualTo(ClinicalSnapshotResourceStatus.SUCCESS);
        assertThat(observation.conditions().receivedCount()).isEqualTo(1489);
        assertThat(observation.conditions().retainedCount()).isEqualTo(5);
        assertThat(observation.conditions().truncated()).isTrue();
        assertThat(observation.observations().receivedCount()).isZero();
        assertThat(observation.observations().truncated()).isFalse();
        assertThat(componentNames(AgentStubObservation.class))
                .doesNotContain("records", "clinicalStatusCode", "intent");
        assertThat(observation.toString()).doesNotContain("active");
        assertThat(observation.toString()).doesNotContain("resolved");
        assertThat(observation.toString()).contains("modelCalled=false");
    }

    @Test
    void authenticationRequiredDoesNotInventSuccessCollections() {
        AgentStubObservation observation = AgentStub.observe(new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                null,
                null,
                ClinicalSnapshotOutcome.AUTHENTICATION_REQUIRED,
                null,
                null,
                null,
                null,
                null));

        assertThat(observation.consumed()).isTrue();
        assertThat(observation.modelCalled()).isFalse();
        assertThat(observation.patientStatus()).isNull();
        assertThat(observation.conditions()).isNull();
        assertThat(observation.toString()).doesNotContain("access_token");
    }

    @Test
    void mismatchedRetainedCountIsRejected() {
        ModelBoundaryContract contract = new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                Instant.parse("2026-09-05T03:00:00Z"),
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        6,
                        5,
                        true,
                        List.of(new BoundaryCondition("Condition", "active"))),
                null,
                null,
                null);

        assertThatThrownBy(() -> AgentStub.observe(contract)).isInstanceOf(IllegalStateException.class);
    }

    private static List<String> componentNames(Class<?> type) {
        return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).toList();
    }
}
