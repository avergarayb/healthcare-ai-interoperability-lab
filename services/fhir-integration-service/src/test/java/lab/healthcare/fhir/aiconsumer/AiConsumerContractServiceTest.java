package lab.healthcare.fhir.aiconsumer;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.agent.AgentReasonCodes;
import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
import lab.healthcare.fhir.aigateway.AiExecutionGate;
import lab.healthcare.fhir.aigateway.AiExecutionInput;
import lab.healthcare.fhir.aigateway.AiExecutionReasonCodes;
import lab.healthcare.fhir.aigateway.AiExecutionStatus;
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

class AiConsumerContractServiceTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T21:50:00Z");

    @Test
    void eligibleInputPreparesContractWithoutDispatch() {
        AiConsumerContract result = prepare(completeOracle());

        assertThat(result.contractVersion()).isEqualTo(AiConsumerContractVersion.V1);
        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.READY);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED);
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.toString()).doesNotContain("active");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
    }

    @Test
    void blockedDecisionIsPreserved() {
        AiConsumerContract result = prepare(new ModelBoundaryContract(
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

        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.BLOCKED);
        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.BLOCKED);
        assertThat(result.reasonCodes()).contains(AgentReasonCodes.CONTRACT_REJECTED);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
    }

    @Test
    void humanReviewIsPreservedAndNotDispatched() {
        AiConsumerContract result = prepare(emptyClinicalData());

        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
    }

    @Test
    void notEligibleDecisionIsPreserved() {
        AiConsumerContract result = AiConsumerContractService.prepare(
                AiExecutionGate.evaluate(readyWithoutClinicalData()));

        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.NOT_ELIGIBLE);
        assertThat(result.executionDecision()).isEqualTo(AiExecutionStatus.NOT_ELIGIBLE);
        assertThat(result.reasonCodes()).contains(AiExecutionReasonCodes.NOT_ELIGIBLE);
        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.modelCalled()).isFalse();
    }

    @Test
    void prematureAuthorizationIsRejected() {
        assertThatThrownBy(() -> new AiConsumerContract(
                        AiConsumerContractVersion.V1,
                        AiConsumerContractStatus.READY,
                        AiConsumerDispatchStatus.NOT_DISPATCHED,
                        PipelineStageStatus.SUCCESS,
                        true,
                        AgentDecision.READY,
                        FirstAiComponentStatus.PREPARED,
                        AiExecutionStatus.ELIGIBLE_BUT_NOT_AUTHORIZED,
                        true,
                        false,
                        true,
                        FirstAiProcessingStatus.NOT_EXECUTED,
                        List.of(),
                        List.of(),
                        "NOT_REQUESTED",
                        true,
                        true,
                        "epic-sandbox",
                        "corr-061"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage(AiConsumerReasonCodes.PREMATURE_MODEL_AUTHORIZATION);
    }

    @Test
    void missingClinicalDataIsNotInvented() {
        AiConsumerContract result = prepare(emptyClinicalData());

        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.toString()).doesNotContain("Observation");
    }

    @Test
    void partialPipelineIsPreserved() {
        AiConsumerContract result = prepare(partialTimeout());

        assertThat(result.pipelineStatus()).isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.warnings()).contains("timeout:observations", "not-requested:medicationRequests");
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
    }

    @Test
    void epicMedicationRequestsStayNotRequested() {
        AiConsumerContract result = prepare(completeEpic());

        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.READY);
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
    }

    @Test
    void missingInputIsRejected() {
        assertThatThrownBy(() -> AiConsumerContractService.prepare(null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> AiConsumerContractMapper.from(null)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void mapperDoesNotRecomputeEligibility() {
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
                AiBoundaryInput.of(contract, PipelineDiagnoses.fromContract(contract), injected), "corr-061"));
        AiConsumerContract result = AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));

        assertThat(result.contractStatus()).isEqualTo(AiConsumerContractStatus.READY);
        assertThat(result.warnings()).containsExactly("not-requested:medicationRequests");
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
        assertThat(result.correlationId()).isEqualTo("corr-061");
        assertThat(result.dispatchStatus()).isEqualTo(AiConsumerDispatchStatus.NOT_DISPATCHED);
        assertThat(result.modelCallAuthorized()).isFalse();
    }

    private static AiConsumerContract prepare(ModelBoundaryContract contract) {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        FirstAiResult firstAi = FirstAiComponent.process(
                AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent), "corr-lab"));
        return AiConsumerContractService.prepare(AiExecutionGate.evaluate(firstAi));
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

    private static <T> BoundaryCollection<T> collection(T record) {
        return new BoundaryCollection<>(ClinicalSnapshotResourceStatus.SUCCESS, 1, 1, false, List.of(record));
    }
}
