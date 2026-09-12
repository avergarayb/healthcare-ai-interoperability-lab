package lab.healthcare.fhir.agent;

import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryDiagnosticReport;
import lab.healthcare.fhir.modelboundary.BoundaryMedicationRequest;
import lab.healthcare.fhir.modelboundary.BoundaryObservation;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DeterministicAgentTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T21:00:00Z");

    @Test
    void validCompleteContractIsReadyAndDeterministic() {
        ModelBoundaryContract contract = completeOracle();
        DeterministicAgentResult first = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract));
        DeterministicAgentResult second = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract));

        assertThat(first.decision()).isEqualTo(AgentDecision.READY);
        assertThat(first.reasonCode()).isEqualTo(AgentReasonCodes.READY_FOR_BOUNDARY);
        assertThat(first.requiresHumanReview()).isTrue();
        assertThat(first.modelCalled()).isFalse();
        assertThat(first.pipelineStatus()).isEqualTo(PipelineStageStatus.SUCCESS);
        assertThat(first.warnings()).isEmpty();
        assertThat(first.findings()).isEmpty();
        assertThat(first).isEqualTo(second);
        assertThat(first.toString()).doesNotContain("active");
        assertThat(first.toString()).doesNotContain("order");
        assertThat(first.toString()).doesNotContain("access_token");
    }

    @Test
    void invalidContractIsBlocked() {
        ModelBoundaryContract contract = new ModelBoundaryContract(
                "v2",
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                null,
                null,
                null,
                null,
                null);

        DeterministicAgentResult result = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract));

        assertThat(result.decision()).isEqualTo(AgentDecision.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.CONTRACT_REJECTED);
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCalled()).isFalse();
    }

    @Test
    void failedPipelineIsBlocked() {
        PipelineDiagnosis failed = new PipelineDiagnosis(
                PipelineStageStatus.FAILED,
                false,
                false,
                List.of(PipelineStageDiagnosis.of("patient", PipelineStageStatus.FAILED, true)));

        DeterministicAgentResult result =
                DeterministicAgent.evaluate(DeterministicAgentInput.of(completeOracle(), failed));

        assertThat(result.decision()).isEqualTo(AgentDecision.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.PIPELINE_NOT_USABLE);
        assertThat(result.usable()).isFalse();
        assertThat(result.modelCalled()).isFalse();
    }

    @Test
    void truncationIsReadyWithWarning() {
        ModelBoundaryContract contract = new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        8,
                        5,
                        true,
                        List.of(
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"),
                                new BoundaryCondition("Condition", "active"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryObservation("Observation", "final"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryDiagnosticReport("DiagnosticReport", "final"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryMedicationRequest("MedicationRequest", "active", "order"))));

        DeterministicAgentResult result = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract));

        assertThat(result.decision()).isEqualTo(AgentDecision.READY);
        assertThat(result.warnings()).contains("truncated:conditions");
        assertThat(result.toString()).doesNotContain("active");
    }

    @Test
    void emptyClinicalDataRequiresHumanReview() {
        ModelBoundaryContract contract = new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 0, 0, false, List.of()));

        DeterministicAgentResult result = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract));

        assertThat(result.decision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA);
        assertThat(result.requiresHumanReview()).isTrue();
    }

    @Test
    void partialPipelineRequiresHumanReview() {
        ModelBoundaryContract contract = new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryCondition("Condition", "active"))),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.TIMEOUT, null, null, null, List.of()),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryDiagnosticReport("DiagnosticReport", "final"))),
                null);

        DeterministicAgentResult result = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract));

        assertThat(result.decision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.PIPELINE_PARTIAL);
        assertThat(result.usable()).isTrue();
        assertThat(result.warnings()).contains("timeout:observations", "not-requested:medicationRequests");
        assertThat(result.toString()).doesNotContain("active");
    }

    @Test
    void missingInputIsRejected() {
        assertThatThrownBy(() -> DeterministicAgent.evaluate(null)).isInstanceOf(AgentValidationException.class);
        assertThatThrownBy(() -> DeterministicAgentInput.of(null)).isInstanceOf(AgentValidationException.class);
    }

    private static ModelBoundaryContract completeOracle() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryCondition("Condition", "active"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryObservation("Observation", "final"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryDiagnosticReport("DiagnosticReport", "final"))),
                new BoundaryCollection<>(
                        ClinicalSnapshotResourceStatus.SUCCESS,
                        1,
                        1,
                        false,
                        List.of(new BoundaryMedicationRequest("MedicationRequest", "active", "order"))));
    }
}
