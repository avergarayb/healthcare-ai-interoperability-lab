package lab.healthcare.fhir.aigateway;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.agent.AgentReasonCodes;
import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.firstai.FirstAiComponent;
import lab.healthcare.fhir.firstai.FirstAiComponentStatus;
import lab.healthcare.fhir.firstai.FirstAiProcessingStatus;
import lab.healthcare.fhir.firstai.FirstAiResult;
import lab.healthcare.fhir.modelboundary.BoundaryCollection;
import lab.healthcare.fhir.modelboundary.BoundaryCondition;
import lab.healthcare.fhir.modelboundary.BoundaryDiagnosticReport;
import lab.healthcare.fhir.modelboundary.BoundaryMedicationRequest;
import lab.healthcare.fhir.modelboundary.BoundaryObservation;
import lab.healthcare.fhir.modelboundary.BoundaryPatient;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContract;
import lab.healthcare.fhir.modelboundary.ModelBoundaryContractVersion;
import lab.healthcare.fhir.patient.PatientContextSource;
import lab.healthcare.fhir.pipeline.PipelineDiagnoses;
import lab.healthcare.fhir.pipeline.PipelineDiagnosis;
import lab.healthcare.fhir.pipeline.PipelineStageStatus;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotOutcome;
import lab.healthcare.fhir.snapshot.ClinicalSnapshotResourceStatus;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AiExecutionGateTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T21:40:00Z");

    @Test
    void readyPreparedInputIsEligibleButNotAuthorized() {
        AiExecutionDecision result = evaluate(completeOracle());

        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED);
        assertThat(result.executionReason()).isEqualTo(AiExecutionReasonCodes.ELIGIBLE_BUT_NOT_AUTHORIZED);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.componentStatus()).isEqualTo(FirstAiComponentStatus.PREPARED);
        assertThat(result.clinicalDataAvailable()).isTrue();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.toString()).doesNotContain("active");
        assertThat(result.toString()).doesNotContain("access_token");
    }

    @Test
    void blockedDecisionIsPreserved() {
        AiExecutionDecision result = evaluate(new ModelBoundaryContract(
                "v2",
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                null,
                null,
                null,
                null,
                null));

        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.BLOCKED);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.CONTRACT_REJECTED);
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
    }

    @Test
    void humanReviewIsPreservedAndDoesNotAuthorizeAModel() {
        AiExecutionDecision result = evaluate(emptyClinicalData());

        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA);
        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
    }

    @Test
    void missingClinicalDataOnReadyInputIsNotEligible() {
        AiExecutionDecision result = AiExecutionGate.evaluate(readyWithoutClinicalData());

        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.NOT_ELIGIBLE);
        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.toString()).doesNotContain("Observation");
    }

    @Test
    void partialPipelineIsPreserved() {
        AiExecutionDecision result = evaluate(partialTimeout());

        assertThat(result.pipelineStatus()).isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.warnings()).contains("timeout:observations", "not-requested:medicationRequests");
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
    }

    @Test
    void processingRemainsNotExecuted() {
        AiExecutionDecision result = evaluate(completeEpic());

        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
    }

    @Test
    void prematureAuthorizationIsRejected() {
        assertThatThrownBy(() -> new AiExecutionInput(
                        AgentDecision.READY,
                        PipelineStageStatus.SUCCESS,
                        true,
                        FirstAiComponentStatus.PREPARED,
                        FirstAiProcessingStatus.NOT_EXECUTED,
                        true,
                        false,
                        true,
                        AgentReasonCodes.READY_FOR_BOUNDARY,
                        List.of(),
                        "NOT_REQUESTED",
                        true,
                        true,
                        "epic-sandbox",
                        "corr-060"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage(AiExecutionReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
    }

    @Test
    void operationalWarningsArePreserved() {
        AiExecutionDecision result = evaluate(truncatedOracle());

        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED);
        assertThat(result.warnings()).contains("truncated:conditions");
        assertThat(result.medicationRequestsStatus()).isEqualTo("SUCCESS");
        assertThat(result.modelCallAuthorized()).isFalse();
    }

    @Test
    void missingInputIsRejected() {
        assertThatThrownBy(() -> AiExecutionGate.evaluate((AiExecutionInput) null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> AiExecutionGate.evaluate((FirstAiResult) null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> AiExecutionMapper.from(null)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void mapperDoesNotRecomputeAReadyDecision() {
        DeterministicAgentResult injected = new DeterministicAgentResult(
                AgentDecision.READY,
                AgentReasonCodes.READY_FOR_BOUNDARY,
                List.of(),
                List.of("not-requested:medicationRequests"),
                true,
                false,
                PipelineStageStatus.SUCCESS,
                true,
                true);
        ModelBoundaryContract contract = completeEpic();
        FirstAiResult firstAi = FirstAiComponent.process(AiBoundaryService.prepare(
                AiBoundaryInput.of(contract, PipelineDiagnoses.fromContract(contract), injected), "corr-060"));
        AiExecutionDecision result = AiExecutionGate.evaluate(firstAi);

        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED);
        assertThat(result.warnings()).containsExactly("not-requested:medicationRequests");
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
        assertThat(result.correlationId()).isEqualTo("corr-060");
        assertThat(result.modelCallAuthorized()).isFalse();
    }

    private static AiExecutionDecision evaluate(ModelBoundaryContract contract) {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent), "corr-lab"));
        return AiExecutionGate.evaluate(firstAi);
    }

    private static AiExecutionInput readyWithoutClinicalData() {
        return new AiExecutionInput(
                AgentDecision.READY,
                PipelineStageStatus.SUCCESS,
                false,
                FirstAiComponentStatus.PREPARED,
                FirstAiProcessingStatus.NOT_EXECUTED,
                true,
                false,
                false,
                AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA,
                List.of(),
                "NOT_REQUESTED",
                true,
                true,
                "epic-sandbox",
                "corr-lab");
    }

    private static ModelBoundaryContract completeOracle() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "oracle-health-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                collection(new BoundaryCondition("Condition", "active")),
                collection(new BoundaryObservation("Observation", "final")),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                collection(new BoundaryMedicationRequest("MedicationRequest", "active", "order")));
    }

    private static ModelBoundaryContract completeEpic() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_COMPLETE,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                collection(new BoundaryCondition("Condition", "active")),
                collection(new BoundaryObservation("Observation", "final")),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                null);
    }

    private static ModelBoundaryContract emptyClinicalData() {
        return new ModelBoundaryContract(
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
    }

    private static ModelBoundaryContract partialTimeout() {
        return new ModelBoundaryContract(
                ModelBoundaryContractVersion.V1,
                "epic-sandbox",
                PatientContextSource.CONFIGURED,
                GENERATED_AT,
                ClinicalSnapshotOutcome.SNAPSHOT_PARTIAL,
                new BoundaryPatient(ClinicalSnapshotResourceStatus.SUCCESS, "Patient"),
                collection(new BoundaryCondition("Condition", "active")),
                new BoundaryCollection<>(ClinicalSnapshotResourceStatus.TIMEOUT, null, null, null, List.of()),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                null);
    }

    private static ModelBoundaryContract truncatedOracle() {
        return new ModelBoundaryContract(
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
                collection(new BoundaryObservation("Observation", "final")),
                collection(new BoundaryDiagnosticReport("DiagnosticReport", "final")),
                collection(new BoundaryMedicationRequest("MedicationRequest", "active", "order")));
    }

    private static <T> BoundaryCollection<T> collection(T record) {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 1, 1, false, List.of(record));
    }
}
