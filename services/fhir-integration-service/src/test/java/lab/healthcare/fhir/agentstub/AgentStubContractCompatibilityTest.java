package lab.healthcare.fhir.agentstub;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryDiagnosticReport;
import lab.healthcare.fhir.modelboundary.BoundaryMedicationRequest;
import lab.healthcare.fhir.modelboundary.BoundaryObservation;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.modelboundary.ModelBoundaryMapper;
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
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AgentStubContractCompatibilityTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T19:00:00Z");

    @Test
    void epicContractWithoutMedicationRequestsIsConsumed() {
        ModelBoundaryContract contract = ModelBoundaryMapper.from(epicProjection());

        AgentStubObservation observation = AgentStub.observe(contract);

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.medicationRequests()).isNull();
        assertThat(observation.consumed()).isTrue();
        assertThat(observation.modelCalled()).isFalse();
        assertThat(observation.hasClinicalData()).isTrue();
        assertThat(observation.destination()).isEqualTo("epic-sandbox");
        assertThat(observation.conditions().receivedCount()).isEqualTo(1);
        assertThat(observation.conditions().retainedCount()).isEqualTo(1);
        assertThat(observation.conditions().truncated()).isFalse();
        assertThat(observation.observations().retainedCount()).isEqualTo(5);
        assertThat(observation.diagnosticReports().retainedCount()).isEqualTo(5);
        assertThat(observation.medicationRequests()).isNull();
        assertThat(observation.toString()).doesNotContain("active");
        assertThat(observation.toString()).doesNotContain("final");
    }

    @Test
    void oracleContractWithMedicationRequestsIsConsumedWithoutVendorBranch() {
        ModelBoundaryContract contract = ModelBoundaryMapper.from(oracleProjection());

        AgentStubObservation observation = AgentStub.observe(contract);

        assertThat(contract.contractVersion()).isEqualTo(ModelBoundaryContractVersion.V1);
        assertThat(contract.medicationRequests()).isNotNull();
        assertThat(observation.consumed()).isTrue();
        assertThat(observation.modelCalled()).isFalse();
        assertThat(observation.hasClinicalData()).isTrue();
        assertThat(observation.destination()).isEqualTo("oracle-health-sandbox");
        assertThat(observation.medicationRequests().receivedCount()).isEqualTo(2);
        assertThat(observation.medicationRequests().retainedCount()).isEqualTo(2);
        assertThat(observation.medicationRequests().truncated()).isFalse();
        assertThat(observation.toString()).doesNotContain("order");
        assertThat(source("AgentStub.java")).doesNotContain("if Epic");
        assertThat(source("AgentStub.java")).doesNotContain("if Oracle");
        assertThat(source("AgentStub.java")).doesNotContain("epic-sandbox");
        assertThat(source("AgentStub.java")).doesNotContain("oracle-health-sandbox");
    }

    @Test
    void unsupportedContractVersionIsRejectedWithoutFetchingFhir() {
        assertThatThrownBy(() -> AgentStub.observe(new ModelBoundaryContract(
                        "v2",
                        "epic-sandbox",
                        PatientContextSource.CONFIGURED,
                        GENERATED_AT,
                        ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                        new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                        emptySuccess(),
                        emptySuccess(),
                        emptySuccess(),
                        null)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("v1");
        assertThat(source("AgentStub.java")).doesNotContain("FhirService");
        assertThat(source("AgentStub.java")).doesNotContain("RoutingService");
    }

    @Test
    void missingRequiredSectionIsRejected() {
        assertThatThrownBy(() -> AgentStub.observe(new ModelBoundaryContract(
                        ModelBoundaryContractVersion.V1,
                        "epic-sandbox",
                        PatientContextSource.CONFIGURED,
                        GENERATED_AT,
                        ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                        new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                        emptySuccess(),
                        null,
                        emptySuccess(),
                        null)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("included collections");
    }

    @Test
    void allowlistedBoundaryRecordsDoNotExposeForbiddenFields() {
        assertThat(componentNames(BoundaryPatient.class)).containsExactly("status", "resourceType");
        assertThat(componentNames(BoundaryCondition.class)).containsExactly("resourceType", "clinicalStatusCode");
        assertThat(componentNames(BoundaryObservation.class)).containsExactly("resourceType", "status");
        assertThat(componentNames(BoundaryDiagnosticReport.class)).containsExactly("resourceType", "status");
        assertThat(componentNames(BoundaryMedicationRequest.class)).containsExactly("resourceType", "status", "intent");
        assertThat(componentNames(AgentStubObservation.class))
                .doesNotContain("records", "patientId", "code", "value", "narrative");
    }

    @Test
    void emptySuccessfulCollectionsHaveNoClinicalData() {
        AgentStubObservation observation = AgentStub.observe(new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                emptySuccess(),
                emptySuccess(),
                emptySuccess(),
                null));

        assertThat(observation.hasClinicalData()).isFalse();
        assertThat(observation.consumed()).isTrue();
        assertThat(observation.medicationRequests()).isNull();
    }

    private static ClinicalProjectionResult epicProjection() {
        return new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.retained(
                        5,
                        5,
                        false,
                        List.of(
                                new RetainedObservation("Observation", "final"),
                                new RetainedObservation("Observation", "final"),
                                new RetainedObservation("Observation", "final"),
                                new RetainedObservation("Observation", "final"),
                                new RetainedObservation("Observation", "final"))),
                ProjectedCollection.retained(
                        5,
                        5,
                        false,
                        List.of(
                                new RetainedDiagnosticReport("DiagnosticReport", "final"),
                                new RetainedDiagnosticReport("DiagnosticReport", "final"),
                                new RetainedDiagnosticReport("DiagnosticReport", "final"),
                                new RetainedDiagnosticReport("DiagnosticReport", "final"),
                                new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                null,
                "Controlled clinical projection succeeded");
    }

    private static ClinicalProjectionResult oracleProjection() {
        return new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedCondition("Condition", "active"))),
                ProjectedCollection.retained(1, 1, false, List.of(new RetainedObservation("Observation", "final"))),
                ProjectedCollection.retained(
                        1, 1, false, List.of(new RetainedDiagnosticReport("DiagnosticReport", "final"))),
                ProjectedCollection.retained(
                        2,
                        2,
                        false,
                        List.of(
                                new RetainedMedicationRequest("MedicationRequest", "active", "order"),
                                new RetainedMedicationRequest("MedicationRequest", "active", "order"))),
                "Controlled clinical projection succeeded");
    }

    private static <T> BoundaryCollection<T> emptySuccess() {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of());
    }

    private static List<String> componentNames(Class<?> type) {
        return Arrays.stream(type.getRecordComponents()).map(RecordComponent::getName).toList();
    }

    private static String source(String fileName) {
        try {
            return java.nio.file.Files.readString(
                    java.nio.file.Path.of("src/main/java/lab/healthcare/fhir/agentstub/" + fileName));
        } catch (Exception ex) {
            throw new IllegalStateException(fileName, ex);
        }
    }
}
