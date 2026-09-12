package lab.healthcare.fhir.firstai;

import lab.healthcare.fhir.agent.AgentDecision;
import lab.healthcare.fhir.agent.AgentReasonCodes;
import lab.healthcare.fhir.agent.DeterministicAgent;
import lab.healthcare.fhir.agent.DeterministicAgentInput;
import lab.healthcare.fhir.agent.DeterministicAgentResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryDecision;
import lab.healthcare.fhir.aiboundary.AiBoundaryInput;
import lab.healthcare.fhir.aiboundary.AiBoundaryResult;
import lab.healthcare.fhir.aiboundary.AiBoundaryService;
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

class FirstAiComponentTest {

    private static final Instant GENERATED_AT = Instant.parse("2026-09-12T21:30:00Z");

    @Test
    void readyKeepsPreparedAndDoesNotExecuteAModel() {
        FirstAiResult result = process(completeOracle());

        assertThat(result.componentStatus()).isEqualTo(FirstAiComponentStatus.PREPARED);
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.clinicalDataAvailable()).isTrue();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.READY_FOR_BOUNDARY);
        assertThat(result.toString()).doesNotContain("active");
        assertThat(result.toString()).doesNotContain("access_token");
        assertThat(result.toString()).doesNotContain("Patient/");
    }

    @Test
    void blockedDecisionIsPreserved() {
        FirstAiResult result = process(new ModelBoundaryContract(
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

        assertThat(result.componentStatus()).isEqualTo(FirstAiComponentStatus.BLOCKED);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.BLOCKED);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.CONTRACT_REJECTED);
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.clinicalDataAvailable()).isFalse();
    }

    @Test
    void humanReviewIsPreservedAndDoesNotAuthorizeAModel() {
        FirstAiResult result = process(emptyClinicalData());

        assertThat(result.componentStatus()).isEqualTo(FirstAiComponentStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.reasonCode()).isEqualTo(AgentReasonCodes.INSUFFICIENT_CLINICAL_DATA);
        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.toString()).doesNotContain("active");
    }

    @Test
    void partialPipelineIsPreserved() {
        FirstAiResult result = process(partialTimeout());

        assertThat(result.pipelineStatus()).isEqualTo(PipelineStageStatus.PARTIAL);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.REQUIRES_HUMAN_REVIEW);
        assertThat(result.componentStatus()).isEqualTo(FirstAiComponentStatus.REQUIRES_HUMAN_REVIEW);
        assertThat(result.warnings()).contains("timeout:observations", "not-requested:medicationRequests");
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
    }

    @Test
    void missingClinicalDataIsNotInvented() {
        FirstAiResult result = process(emptyClinicalData());

        assertThat(result.clinicalDataAvailable()).isFalse();
        assertThat(result.requiresHumanReview()).isTrue();
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.toString()).doesNotContain("condition");
        assertThat(result.toString()).doesNotContain("Observation");
    }

    @Test
    void operationalWarningsArePreserved() {
        FirstAiResult result = process(truncatedOracle());

        assertThat(result.agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.warnings()).contains("truncated:conditions");
        assertThat(result.medicationRequestsStatus()).isEqualTo("SUCCESS");
        assertThat(result.modelCalled()).isFalse();
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
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
        AiBoundaryResult boundary = AiBoundaryService.prepare(
                AiBoundaryInput.of(contract, PipelineDiagnoses.fromContract(contract), injected),
                "corr-059");
        FirstAiResult result = FirstAiComponent.process(boundary);

        assertThat(result.componentStatus()).isEqualTo(FirstAiComponentStatus.PREPARED);
        assertThat(result.agentDecision()).isEqualTo(AgentDecision.READY);
        assertThat(result.warnings()).containsExactly("not-requested:medicationRequests");
        assertThat(result.medicationRequestsStatus()).isEqualTo("NOT_REQUESTED");
        assertThat(result.correlationId()).isEqualTo("corr-059");
        assertThat(result.modelCallAuthorized()).isFalse();
        assertThat(result.processingStatus()).isEqualTo(FirstAiProcessingStatus.NOT_EXECUTED);
    }

    @Test
    void missingInputIsRejected() {
        assertThatThrownBy(() -> FirstAiComponent.process((FirstAiInput) null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> FirstAiComponent.process((AiBoundaryResult) null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> FirstAiInput.of(null)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void resultRejectsModelAuthorization() {
        AiBoundaryDecision decision = new AiBoundaryDecision(
                PipelineStageStatus.SUCCESS, true, AgentDecision.READY, true, false, false);
        assertThatThrownBy(() -> new FirstAiResult(
                        FirstAiComponentStatus.PREPARED,
                        FirstAiProcessingStatus.NOT_EXECUTED,
                        decision.pipelineStatus(),
                        true,
                        AgentDecision.READY,
                        true,
                        false,
                        true,
                        AgentReasonCodes.READY_FOR_BOUNDARY,
                        List.of(),
                        "NOT_REQUESTED",
                        true,
                        true,
                        "epic-sandbox",
                        "v1",
                        "corr"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("READY does not authorize a model call");
    }

    private static FirstAiResult process(ModelBoundaryContract contract) {
        PipelineDiagnosis diagnosis = PipelineDiagnoses.fromContract(contract);
        DeterministicAgentResult agent = DeterministicAgent.evaluate(DeterministicAgentInput.of(contract, diagnosis));
        AiBoundaryResult boundary =
                AiBoundaryService.prepare(AiBoundaryInput.of(contract, diagnosis, agent), "corr-lab");
        return FirstAiComponent.process(FirstAiInput.of(boundary));
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
