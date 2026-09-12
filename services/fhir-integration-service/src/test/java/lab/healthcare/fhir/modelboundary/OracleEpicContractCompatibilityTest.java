package lab.healthcare.fhir.modelboundary;

import lab.healthcare.fhir.agentstub.AgentStub;
import lab.healthcare.fhir.agentstub.AgentStubObservation;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.projection.ClinicalProjectionResult;
import lab.healthcare.fhir.projection.ProjectedCollection;
import lab.healthcare.fhir.projection.RetentionCeiling;
import lab.healthcare.fhir.projection.RetainedCondition;
import lab.healthcare.fhir.projection.RetainedDiagnosticReport;
import lab.healthcare.fhir.projection.RetainedMedicationRequest;
import lab.healthcare.fhir.projection.RetainedObservation;
import lab.healthcare.fhir.projection.RetainedPatient;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class OracleEpicContractCompatibilityTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T19:20:00Z");

    static Stream<Arguments> vendorProjections() {
        return Stream.of(
                Arguments.of("epic-sandbox", false, truncatedProjection("epic-sandbox", null)),
                Arguments.of(
                        "oracle-health-sandbox",
                        true,
                        truncatedProjection(
                                "oracle-health-sandbox",
                                ProjectedCollection.retained(
                                        8,
                                        5,
                                        true,
                                        List.of(
                                                new RetainedMedicationRequest("MedicationRequest", "active", "order"),
                                                new RetainedMedicationRequest("MedicationRequest", "active", "order"),
                                                new RetainedMedicationRequest("MedicationRequest", "active", "order"),
                                                new RetainedMedicationRequest("MedicationRequest", "active", "order"),
                                                new RetainedMedicationRequest(
                                                        "MedicationRequest", "active", "order"))))));
    }

    @ParameterizedTest
    @MethodSource("vendorProjections")
    void sharedV1InvariantsHoldForBothVendors(
            String destination, boolean medicationPresent, ClinicalProjectionResult projection) {
        ModelBoundaryContract contract = ModelBoundaryMapper.from(projection);
        AgentStubObservation observation = ModelBoundaryContractAssertions.assertSharedV1(contract);

        assertThat(contract.destination()).isEqualTo(destination);
        assertThat(observation.destination()).isEqualTo(destination);
        assertThat(observation.hasClinicalData()).isTrue();
        ModelBoundaryContractAssertions.assertRetention(contract.conditions(), 1489, 5, true);
        ModelBoundaryContractAssertions.assertRetention(contract.observations(), 6, 5, true);
        ModelBoundaryContractAssertions.assertRetention(contract.diagnosticReports(), 5, 5, false);
        assertThat(RetentionCeiling.DEFAULT_LIMIT).isEqualTo(5);
        if (medicationPresent) {
            assertThat(contract.medicationRequests()).isNotNull();
            ModelBoundaryContractAssertions.assertRetention(contract.medicationRequests(), 8, 5, true);
        } else {
            assertThat(contract.medicationRequests()).isNull();
            assertThat(observation.medicationRequests()).isNull();
        }
    }

    @Test
    void sameStubConsumesEpicAbsenceAndOraclePresence() {
        AgentStubObservation epic = AgentStub.observe(ModelBoundaryMapper.from(truncatedProjection("epic-sandbox", null)));
        AgentStubObservation oracle = AgentStub.observe(ModelBoundaryMapper.from(truncatedProjection(
                "oracle-health-sandbox",
                ProjectedCollection.retained(
                        2,
                        2,
                        false,
                        List.of(
                                new RetainedMedicationRequest("MedicationRequest", "active", "order"),
                                new RetainedMedicationRequest("MedicationRequest", "active", "order"))))));

        assertThat(epic.consumed()).isTrue();
        assertThat(oracle.consumed()).isTrue();
        assertThat(epic.modelCalled()).isFalse();
        assertThat(oracle.modelCalled()).isFalse();
        assertThat(epic.medicationRequests()).isNull();
        assertThat(oracle.medicationRequests()).isNotNull();
        assertThat(epic.contractVersion()).isEqualTo(oracle.contractVersion()).isEqualTo("v1");
    }

    @Test
    void missingPatientOnCompleteContractIsRejected() {
        assertThatThrownBy(() -> AgentStub.observe(new ModelBoundaryContract(
                        ModelBoundaryContractVersion.V1,
                        "epic-sandbox",
                        PatientContextSource.CONFIGURED,
                        GENERATED_AT,
                        ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                        null,
                        emptySuccess(),
                        emptySuccess(),
                        emptySuccess(),
                        null)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("included collections");
    }

    @Test
    void partialContractMissingRequiredCollectionIsRejected() {
        assertThatThrownBy(() -> AgentStub.observe(new ModelBoundaryContract(
                        ModelBoundaryContractVersion.V1,
                        "oracle-health-sandbox",
                        PatientContextSource.CONFIGURED,
                        GENERATED_AT,
                        ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                        new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                        emptySuccess(),
                        emptySuccess(),
                        null,
                        emptySuccess())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("included collections");
    }

    @Test
    void unsupportedVersionIsRejectedForBothDestinationNames() {
        for (String destination : List.of("epic-sandbox", "oracle-health-sandbox")) {
            assertThatThrownBy(() -> AgentStub.observe(new ModelBoundaryContract(
                            "v0",
                            destination,
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
        }
    }

    @Test
    void mapperAndStubSourcesDoNotBranchOnVendor() throws Exception {
        String mapper = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/modelboundary/ModelBoundaryMapper.java"));
        String stub = Files.readString(Path.of("src/main/java/lab/healthcare/fhir/agentstub/AgentStub.java"));
        for (String text : List.of(mapper, stub)) {
            assertThat(text).doesNotContain("if Epic");
            assertThat(text).doesNotContain("if Oracle");
            assertThat(text).doesNotContain("provider.equals(\"epic\")");
            assertThat(text).doesNotContain("provider.equals(\"oracle\")");
            assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.epic");
            assertThat(text).doesNotContain("lab.healthcare.fhir.vendor.oracle");
            assertThat(text).doesNotContain("FhirService");
            assertThat(text).doesNotContain("RoutingService");
        }
    }

    private static ClinicalProjectionResult truncatedProjection(
            String destination, ProjectedCollection<RetainedMedicationRequest> medicationRequests) {
        return new ClinicalProjectionResult(
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                destination,
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotResourceStatus.SUCCESS,
                new RetainedPatient("Patient"),
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
                ProjectedCollection.retained(
                        6,
                        5,
                        true,
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
                medicationRequests,
                "Controlled clinical projection succeeded");
    }

    private static <T> BoundaryCollection<T> emptySuccess() {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of());
    }
}
